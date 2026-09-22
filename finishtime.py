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
# FinishTime serves its search data to the browser-based results interface.
# Match that ordinary request shape rather than presenting an unknown client name.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class Race(NamedTuple):
    name: str
    date: str
    url: str


class FinishTimeError(ValueError):
    """A source page could not be read or did not contain usable results."""


def _raise_for_status(response: requests.Response) -> None:
    """Turn provider-side automation blocks into an actionable admin error."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if response.status_code in {403, 429}:
            raise FinishTimeError(
                "FinishTime blocked the direct request from this server. "
                "Open FinishTime in your browser, filter the required results, "
                "then use Paste results from a webpage."
            ) from exc
        raise


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
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
        })

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=30)
        _raise_for_status(response)
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
        _raise_for_status(response)
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

    def results_for_club(
        self, race_url: str, club: str, distance: int, discipline: str = "run"
    ) -> pd.DataFrame:
        if distance <= 0:
            raise FinishTimeError("Distance must be a positive number of kilometres.")
        club = club.strip()
        if not club:
            raise FinishTimeError("Choose the club to import.")
        if discipline not in {"run", "walk"}:
            raise FinishTimeError("Choose Run or Walk before importing.")

        race_page = self._get(_race_url(race_url))
        url = _event_result_url(race_page.text, race_page.url, distance, discipline)
        initial = self._get(url)
        soup = BeautifulSoup(initial.text, "html.parser")
        category_select = soup.select_one("select[id$='cbCateg']")
        categories = [
            option.get_text(" ", strip=True)
            for option in category_select.select("option")
            if option.get("value") not in (None, "0")
        ] if category_select else []

        pages = _page_count(soup)
        tables = [_results_table(initial.text)]
        for page_number in range(2, pages + 1):
            response = self._get(_page_url(initial.url, page_number))
            tables.append(_results_table(response.text))
        table = pd.concat(tables, ignore_index=True)
        required = {"Name", "Time", "Category", "Gender"}
        if not required.issubset(table.columns):
            raise FinishTimeError("FinishTime's result columns have changed; no rows were imported.")
        if "Club" not in table.columns:
            raise FinishTimeError("FinishTime did not return club names; no rows were imported.")

        table = table[
            table["Club"].astype(str).str.strip().str.casefold() == club.casefold()
        ].copy()

        output = table[["Name", "Gender", "Category", "Time"]].copy()
        output["Distance"] = distance
        output["Name"] = output["Name"].astype(str).str.replace(r"\s*#\S+.*$", "", regex=True).str.strip()
        output["Gender"] = output["Gender"].astype(str).str.extract(r"(Male|Female)", expand=False)
        output["Category"] = output["Category"].map(lambda value: _category_label(value, categories))
        output = output.dropna(subset=["Name", "Gender", "Category", "Time"])
        output = output[pd.to_timedelta(output["Time"], errors="coerce").notna()]
        output = output.dropna(subset=["Name"]).query("Name != ''")
        if output.empty:
            raise FinishTimeError(
                f"No {distance} km {discipline} FinishTime results were found for {club}."
            )
        return output[["Name", "Gender", "Category", "Distance", "Time"]]


def _advanced_url(race_url: str) -> str:
    parsed = urlparse(race_url)
    params = parse_qs(parsed.query)
    params["dt"] = ["0"]
    params["adv"] = ["1"]
    return parsed._replace(query=urlencode(params, doseq=True)).geturl()


def _event_result_url(html: str, page_url: str, distance: int, discipline: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for link in soup.select("a[href*='EId=']"):
        label = link.get_text(" ", strip=True)
        distance_match = re.search(r"(\d+(?:\.\d+)?)\s*km\b", label, re.IGNORECASE)
        if not distance_match or round(float(distance_match.group(1))) != int(distance):
            continue
        is_walk = "walk" in label.casefold()
        if is_walk == (discipline == "walk"):
            matches.append(urljoin(page_url, link.get("href")))
    if not matches:
        raise FinishTimeError(
            f"FinishTime has no {distance} km {discipline} result set for this race."
        )
    return _advanced_url(matches[0])


def _page_count(soup: BeautifulSoup) -> int:
    jump = soup.select_one("input.page-jump[max]")
    if jump is None:
        return 1
    try:
        pages = int(jump.get("max", "1"))
    except ValueError:
        return 1
    if pages < 1 or pages > 100:
        raise FinishTimeError("FinishTime returned an unsafe result-page count.")
    return pages


def _page_url(result_url: str, page_number: int) -> str:
    parsed = urlparse(result_url)
    params = parse_qs(parsed.query)
    params["PageNo"] = [str(page_number)]
    return parsed._replace(query=urlencode(params, doseq=True)).geturl()


def _results_table(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table[id$='tblResults']")
    if table is None:
        # Keep compatibility with the former grid id and benign markup changes.
        table = soup.select_one("table[id$='grdResults']")
    if table is None:
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
