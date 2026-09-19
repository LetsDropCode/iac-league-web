"""Defensive client for Ultimate Live's public event search."""

from __future__ import annotations

from io import StringIO
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
import pandas as pd
import requests

from update_engine import clean_distance, normalize_result_columns


ALLOWED_HOST = "live.ultimate.dk"
BASE_URL = "https://live.ultimate.dk/desktop/front/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class UltimateLiveError(ValueError):
    """The supplied event or its result payload could not be imported."""


def event_id_from_url(value: str) -> str:
    parsed = urlparse(value.strip())
    event_id = parse_qs(parsed.query).get("eventid", [""])[0]
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or not event_id.isdigit():
        raise UltimateLiveError("Enter a valid Ultimate Live event URL containing an eventid.")
    return event_id


class UltimateLiveClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*",
        })

    def _get(self, url: str, params=None) -> requests.Response:
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def results_for_club(
        self, event_url: str, club: str, distance: int, discipline: str
    ) -> tuple[str, pd.DataFrame]:
        event_id = event_id_from_url(event_url)
        club = club.strip()
        if not club:
            raise UltimateLiveError("Enter the running club to import.")
        if distance <= 0:
            raise UltimateLiveError("Distance must be a positive number of kilometres.")
        if discipline not in {"run", "walk"}:
            raise UltimateLiveError("Choose Run or Walk before importing.")

        event_page = self._get(
            urljoin(BASE_URL, "index.php"),
            params={"eventid": event_id, "language": "us"},
        )
        soup = BeautifulSoup(event_page.text, "html.parser")
        event_name = _event_name(soup)
        distance_id = _distance_id(soup, distance, discipline)

        params = {
            "eventid": event_id,
            "mode": "search",
            "searchmode": "advanced",
            "search_quick": "",
            "language": "us",
            "search_bib": "",
            "search_firstname": "",
            "search_lastname": "",
            "search_club": club,
            "search_city": "",
            "search_nation": "",
            "search_distance": distance_id,
            "search_category": "",
            "search_time": "Finish",
            "search_sortby": "[TIMEFIELD]",
            "search_sorttype": "ASC",
        }
        response = self._get(urljoin(BASE_URL, "data.php"), params=params)
        table = _search_table(response.text)
        table = normalize_result_columns(table)

        if "Club" in table.columns:
            table = table[
                table["Club"].astype(str).str.strip().str.casefold() == club.casefold()
            ]

        time_col = next((c for c in table.columns if c in {"Time", "Finish"}), None)
        if time_col is None:
            raise UltimateLiveError("Ultimate Live did not return finish times.")
        table = table[pd.to_timedelta(table[time_col], errors="coerce").notna()].copy()
        if table.empty:
            raise UltimateLiveError(
                f"No usable {distance} km Ultimate Live results were found for {club}."
            )

        output = table[["Name", "Gender", "Category", "Distance", time_col]].copy()
        output = output.rename(columns={time_col: "Time"})
        output["Distance"] = int(distance)
        return event_name, output


def _event_name(soup: BeautifulSoup) -> str:
    title = soup.title.get_text(" ", strip=True) if soup.title else "Ultimate Live Event"
    return re.sub(r"\s*@\s*UltimateLIVE\s*$", "", title, flags=re.IGNORECASE).strip()


def _distance_id(soup: BeautifulSoup, distance: int, discipline: str) -> str:
    select = soup.select_one("select#search_distance")
    if select is None:
        raise UltimateLiveError("Ultimate Live did not provide distance filters for this event.")

    candidates = []
    for option in select.select("option[value]"):
        label = option.get_text(" ", strip=True)
        parsed = clean_distance(re.sub(r"\bwalkers?\b", "", label, flags=re.IGNORECASE).strip())
        if parsed is None or round(parsed) != int(distance):
            continue
        is_walk = "walk" in label.casefold()
        candidates.append((option.get("value", ""), label, is_walk))

    matching = [item for item in candidates if item[2] == (discipline == "walk")]
    if not matching:
        labels = ", ".join(item[1] for item in candidates) or "none"
        raise UltimateLiveError(
            f"Ultimate Live has no {distance} km {discipline} distance option (matches: {labels})."
        )
    return matching[0][0]


def _search_table(payload: str) -> pd.DataFrame:
    soup = BeautifulSoup(payload, "html.parser")
    table = next((item for item in soup.select("table") if "Club" in item.get_text(" ")), None)
    if table is None:
        status = re.search(r"divSearch_Status[^=]*\.innerHTML='([^']+)'", payload)
        message = status.group(1) if status else "no result table"
        raise UltimateLiveError(f"Ultimate Live returned {message}.")
    frames = pd.read_html(StringIO(str(table)))
    if not frames or frames[0].empty:
        raise UltimateLiveError("Ultimate Live returned an empty result table.")
    frame = frames[0]
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame
