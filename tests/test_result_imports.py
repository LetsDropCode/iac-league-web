import io
import unittest
from unittest.mock import patch

import pandas as pd

import app as app_module
from app import parse_pasted_results, preview_results_file
from finishtime import _event_result_url, _page_count, _page_url
from update_engine import read_result_file
from ultimatelive import UltimateLiveError, _distance_id, _search_table, event_id_from_url
from bs4 import BeautifulSoup


class ResultImportTests(unittest.TestCase):
    def test_finishtime_tabular_paste(self):
        raw = (
            "Pos\tRace No\tName\tClub\tCategory\tGender\tTime\tFinish\n"
            "1\t101\tAda Runner\tIRENE ATHLETICS CLUB\t40-49\tFemale\t00:48:53\t00:48:53\n"
        )
        frame = parse_pasted_results(raw, 10)
        self.assertEqual(frame.iloc[0].to_dict(), {
            "Name": "Ada Runner", "Gender": "Female", "Category": "40-49",
            "Distance": 10, "Time": "00:48:53",
        })

    def test_finishtime_mobile_card_paste(self):
        raw = """FINISH NAME GENDER TIME
1
Ada Runner #101
40-49
Female
00:48:53
00:48:53
"""
        frame = parse_pasted_results(raw, 10)
        self.assertEqual(frame.iloc[0]["Name"], "Ada Runner")
        self.assertEqual(frame.iloc[0]["Gender"], "Female")

    def test_finishtime_distance_selection_and_paging(self):
        html = """
        <a href="results.aspx?CId=35&amp;RId=1&amp;EId=1&amp;dt=0">21km</a>
        <a href="results.aspx?CId=35&amp;RId=1&amp;EId=2&amp;dt=0">10km</a>
        <a href="results.aspx?CId=35&amp;RId=1&amp;EId=6&amp;dt=0">10km Walk</a>
        <input class="page-jump" max="14">
        """
        base = "https://results.finishtime.co.za/results.aspx?CId=35&RId=1"
        run_url = _event_result_url(html, base, 10, "run")
        walk_url = _event_result_url(html, base, 10, "walk")
        self.assertIn("EId=2", run_url)
        self.assertIn("EId=6", walk_url)
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(_page_count(soup), 14)
        self.assertIn("PageNo=4", _page_url(run_url, 4))

    def test_finishtime_admin_preview(self):
        frame = pd.DataFrame([{
            "Name": "Ada Runner", "Gender": "Female", "Category": "Senior",
            "Distance": 10, "Time": "00:42:00",
        }])
        with patch.object(app_module.csrf, "_csrf_disable", True), patch.object(
            app_module.FinishTimeClient,
            "results_for_club",
            return_value=frame,
        ) as fetch:
            client = app_module.app.test_client()
            with client.session_transaction() as session:
                session["admin"] = True
            response = client.post(
                "/finishtime/import",
                base_url="https://localhost",
                data={
                    "race_url": "https://results.finishtime.co.za/results.aspx?CId=1&RId=2",
                    "club": "IRENE ATHLETICS CLUB",
                    "distance": "10",
                    "discipline": "run",
                    "action": "preview",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ada Runner", response.data)
        self.assertIn(b"Confirm import", response.data)
        fetch.assert_called_once_with(
            "https://results.finishtime.co.za/results.aspx?CId=1&RId=2",
            "IRENE ATHLETICS CLUB", 10, "run",
        )

    def test_ultimate_live_paste_derives_gender_and_league_category(self):
        raw = (
            "Rank\tRace No\tName\tNation\tClub\tCategory\tTime\tBehind\tSpeed\n"
            "1\t1042\tAda Runner\tRSA\tIRENE ATHLETICS CLUB\tW20-39\t0:42:28\t\t4:15 min/km\n"
            "2\t1043\tBob Runner\tRSA\tIRENE ATHLETICS CLUB\tM40-49\t0:48:53\t+ 6:25\t4:54 min/km\n"
        )
        frame = parse_pasted_results(raw, 10)
        self.assertEqual(frame[["Gender", "Category"]].values.tolist(), [
            ["Female", "Senior"], ["Male", "40-49"]
        ])
        self.assertEqual(frame["Distance"].tolist(), [10, 10])

    def test_comma_export_aliases_and_filename_distance_are_normalised(self):
        source = io.BytesIO(
            b"First Name,Last Name,Sex,Age Group,Chip Time\nAda,Runner,F,F40-49,00:48:53\n"
        )
        source.filename = "results/10K_provider_run.csv"
        frame = read_result_file(source)
        self.assertEqual(frame.iloc[0]["Name"], "Ada Runner")
        self.assertEqual(frame.iloc[0]["Gender"], "Female")
        self.assertEqual(frame.iloc[0]["Category"], "40-49")
        self.assertEqual(frame.iloc[0]["Distance"], 10)

    def test_invalid_upload_is_not_reported_as_ready(self):
        source = io.BytesIO(b"Runner,Clock\nAda,00:40:00\n")
        source.filename = "bad.csv"
        preview = preview_results_file(source)
        self.assertFalse(preview["ok"])
        self.assertIn("Could not read", preview["error"])

    def test_all_nonfinisher_times_are_not_reported_as_ready(self):
        source = io.BytesIO(
            b"Name;Gender;Category;Distance;Time\nAda Runner;Female;Senior;10;DNF\n"
        )
        source.filename = "10K_race_run.csv"
        preview = preview_results_file(source)
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["usable_rows"], 0)

    def test_ultimate_live_url_and_distance_are_strict(self):
        self.assertEqual(
            event_id_from_url("https://live.ultimate.dk/desktop/front/index.php?eventid=7501"),
            "7501",
        )
        with self.assertRaises(UltimateLiveError):
            event_id_from_url("https://example.com/?eventid=7501")
        soup = BeautifulSoup(
            '<select id="search_distance"><option value="3">10km</option>'
            '<option value="4">10km Walkers</option></select>',
            "html.parser",
        )
        self.assertEqual(_distance_id(soup, 10, "run"), "3")
        self.assertEqual(_distance_id(soup, 10, "walk"), "4")

    def test_ultimate_live_search_payload_is_normalised(self):
        payload = """
        search_startrecord = 1000;
        document.getElementById('search_results').innerHTML='
        <table><tr><th>Race No</th><th>Name</th><th>Club</th><th>Distance</th>
        <th>Category</th><th>Time</th></tr><tr><td>3412</td><td>Ada Runner</td>
        <td>IRENE ATHLETICS CLUB</td><td>10km</td><td>W20-39</td><td>47:37</td></tr></table>';
        """
        frame = _search_table(payload)
        self.assertEqual(frame.iloc[0]["Name"], "Ada Runner")

    def test_ultimate_live_admin_preview(self):
        frame = pd.DataFrame([{
            "Name": "Ada Runner", "Gender": "Female", "Category": "Senior",
            "Distance": 10, "Time": "00:42:00",
        }])
        with patch.object(app_module.csrf, "_csrf_disable", True), patch.object(
            app_module.UltimateLiveClient,
            "results_for_club",
            return_value=("Test Event", frame),
        ):
            client = app_module.app.test_client()
            with client.session_transaction() as session:
                session["admin"] = True
            response = client.post(
                "/ultimatelive",
                base_url="https://localhost",
                data={
                    "event_url": "https://live.ultimate.dk/desktop/front/index.php?eventid=1",
                    "club": "IRENE ATHLETICS CLUB",
                    "distance": "10",
                    "discipline": "run",
                    "action": "preview",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Event", response.data)
        self.assertIn(b"Ada Runner", response.data)


if __name__ == "__main__":
    unittest.main()
