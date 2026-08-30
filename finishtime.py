"""Small, defensive client for public FinishTime result pages."""

from __future__ import annotations

from io import StringIO
import re
from typing import NamedTuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://results.finishtime.co.za/"
ALLOWED_HOST = "results.finishtime.co.za"
USER_AGENT = "Irene-Athletics-League/1.0 (+https://iac-league.onrender.com)"


class Race(NamedTuple):
    name: str
    date: str
    url: str


class FinishTimeError(ValueError):
    """A source page could not be read or did not contain usable results."""


def _race_url(value: str) -> str:
    """Accept only a FinishTime result URL with a concrete race identifier."""
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise FinishTimeError("Please choose a race from FinishTime search results.")

    params = parse_qs(parsed.query)
    if not params.get("CId") or not params.get("RId"):
        raise FinishTimeError("That FinishTime link does not identify a race.")
    return value


class FinishTimeClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response

    def search_races(self, query: str) -> list[Race]:
        query = query.strip()
        if len(query) < 2:
            raise FinishTimeError("Enter at least two characters of the race name.")

        # This is the endpoint used by FinishTime's own race-search modal.
        response = self.session.post(
            urljoin(BASE_URL, "data.aspx?" + urlencode({"data": 1, "srch": query})),
            timeout=30,
        )
        response.raise_for_status()
        try:
            records = response.json()
        except ValueError as exc:
            raise FinishTimeError("FinishTime returned an invalid race-search response.") from exc

        races = []
        for record in records:
            client_id = record.get("H_CLientId")
            race_id = record.get("H_RaceId")
            if client_id is None or race_id is None:
                continue
            label = BeautifulSoup(record.get("HL_RaceName", ""), "html.parser").get_text(" ", strip=True)
            if label:
                races.append(Race(
                    label,
                    record.get("Date", "Date unavailable"),
                    urljoin(BASE_URL, f"results.aspx?CId={client_id}&RId={race_id}"),
                ))

        if not races:
            raise FinishTimeError("No FinishTime races matched that search.")
        return races

    def club_names(self, race_url: str) -> list[str]:
        """Return the source's exact club labels, needed for its advanced filter."""
        page = self._get(_advanced_url(_race_url(race_url)))
        soup = BeautifulSoup(page.text, "html.parser")
        club_select = soup.select_one("select[id$='cbClub']")
        if club_select is None:
            raise FinishTimeError("FinishTime did not provide a club filter for this race.")
        return [option.get("value", "").strip() for option in club_select.select("option") if option.get("value") not in (None, "All clubs")]

    def results_for_club(self, race_url: str, club: str, distance: int) -> pd.DataFrame:
        if distance <= 0:
            raise FinishTimeError("Distance must be a positive number of kilometres.")
        club = club.strip()
        if not club:
            raise FinishTimeError("Choose the club to import.")

        url = _advanced_url(_race_url(race_url))
        initial = self._get(url)
        soup = BeautifulSoup(initial.text, "html.parser")
        form = soup.select_one("form")
        if form is None:
            raise FinishTimeError("FinishTime returned an unexpected results page.")
        category_select = soup.select_one("select[id$='cbCateg']")
        categories = [
            option.get_text(" ", strip=True)
            for option in category_select.select("option")
            if option.get("value") not in (None, "0")
        ] if category_select else []

        payload = {
            field["name"]: field.get("value", "")
            for field in form.select("input[name]")
            if field.get("type") not in {"button", "submit"}
        }
        payload.update({
            select["name"]: select.select_one("option[selected]").get("value", "")
            if select.select_one("option[selected]") else ""
            for select in form.select("select[name]")
        })
        payload.update({
            "__EVENTTARGET": "ctl00$Content_Main$btn3rdRowSearch",
            "ctl00$Content_Main$cbClub": club,
            "ctl00$Content_Main$cbGender": "0",
            "ctl00$Content_Main$cbCateg": "0",
        })
        response = self.session.post(url, data=payload, headers={"Referer": initial.url}, timeout=30)
        response.raise_for_status()

        table = _results_table(response.text)
        required = {"Name", "Time", "Category", "Gender"}
        if not required.issubset(table.columns):
            raise FinishTimeError("FinishTime's result columns have changed; no rows were imported.")

        output = table[["Name", "Gender", "Category", "Time"]].copy()
        output["Distance"] = distance
        output["Name"] = output["Name"].astype(str).str.replace(r"\s*#\S+.*$", "", regex=True).str.strip()
        output["Gender"] = output["Gender"].astype(str).str.extract(r"(Male|Female)", expand=False)
        output["Category"] = output["Category"].map(lambda value: _category_label(value, categories))
        output = output.dropna(subset=["Name", "Gender", "Category", "Time"])
        output = output.dropna(subset=["Name"]).query("Name != ''")
        if output.empty:
            raise FinishTimeError(f"No FinishTime results were found for {club}.")
        return output[["Name", "Gender", "Category", "Distance", "Time"]]


def _advanced_url(race_url: str) -> str:
    parsed = urlparse(race_url)
    params = parse_qs(parsed.query)
    params["dt"] = ["0"]
    params["adv"] = ["1"]
    return parsed._replace(query=urlencode(params, doseq=True)).geturl()


def _results_table(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table[id$='grdResults']")
    if table is None:
        # FinishTime uses this id today; this fallback makes a benign markup change recoverable.
        table = next((item for item in soup.select("table") if "Name" in item.get_text(" ")), None)
    if table is None:
        raise FinishTimeError("FinishTime did not return a result table.")

    frames = pd.read_html(StringIO(str(table)))
    if not frames:
        raise FinishTimeError("FinishTime returned an empty result table.")
    frame = frames[0]
    frame.columns = [str(column).replace("", "").strip() for column in frame.columns]
    return frame


def _category_label(value: object, categories: list[str]) -> str | None:
    text = str(value).strip()
    for category in sorted(categories, key=len, reverse=True):
        if text.startswith(category):
            return category
    return None
