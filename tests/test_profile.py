"""Integrity checks for the live activity and GitHub-safe image output."""
import copy
import importlib.util
import re
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update", ROOT/"scripts/update_activity.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)
render_spec = importlib.util.spec_from_file_location("renderer", ROOT/"scripts/render_profile.py")
renderer = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(renderer)


class ProfileTests(unittest.TestCase):
    def response(self):
        return {"data": {"user": {
            "contributionsCollection": {"contributionCalendar": {"totalContributions": 7,
                "weeks": [{"contributionDays": [{"date": "2026-10-25", "weekday": 0, "contributionCount": 7}]}]}},
            "repositories": {"nodes": [
                {"nameWithOwner": "jesusjodar/jesusjodar", "defaultBranchRef": {"target": {"history": {"nodes": [
                    {"oid": "bot", "messageHeadline": "automated update", "committedDate": "2026-10-25T10:00:00Z", "url": "https://github.com/a"}]}}}},
                {"nameWithOwner": "jesusjodar/jesusjodar.github.io", "defaultBranchRef": {"target": {"history": {"nodes": [
                    {"oid": "real", "messageHeadline": "Fix <WebGL> & capture", "committedDate": "2026-10-24T10:00:00Z", "url": "https://github.com/b"}]}}}}
            ]}}}}

    def test_activity_preserves_real_counts_and_excludes_profile_bot(self):
        data = update.normalize(self.response(), "jesusjodar")
        self.assertEqual(data["calendar"]["totalContributions"], 7)
        self.assertEqual([c["sha"] for c in data["commits"]], ["real"])

    def test_failed_api_does_not_become_zero_activity(self):
        for data in [{"errors": [{"message": "Forbidden"}]}, {"data": {"user": None}}]:
            with self.assertRaises(ValueError):
                update.normalize(data, "jesusjodar")

    def test_two_week_window_uses_dates_not_calendar_week_columns(self):
        # Sunday should include all 14 days, across three GitHub calendar columns.
        days = [{"date": (date(2026, 10, 5)+timedelta(days=i)).isoformat(), "contributionCount": 1}
                for i in range(21)]
        data = {"updated_at": "2026-10-25T12:00:00Z", "calendar": {"weeks": [{"contributionDays": days}]},
                "commits": [{"date": value} for value in ["2026-10-25T10:00:00Z", "2026-10-11T22:30:00Z", "2026-10-11T10:00:00Z"]]}
        start, end, visible, commits = renderer.activity_window(data)
        self.assertEqual((start, end), (date(2026, 10, 12), date(2026, 10, 25)))
        self.assertEqual(len(visible), 14)
        self.assertEqual(sum(d["contributionCount"] for d in visible), 14)
        self.assertEqual(len(commits), 2)

    def test_assets_are_self_contained_valid_svg(self):
        files = list((ROOT/"assets").glob("*.svg"))
        self.assertEqual(len(files), 20)
        for file in files:
            with self.subTest(file=file.name):
                doc = ET.parse(file)
                ids = {n.attrib["id"] for n in doc.iter() if "id" in n.attrib}
                for node in doc.iter():
                    self.assertNotIn(node.tag.split("}")[-1], ["script", "foreignObject", "image", "text"])
                    href = node.attrib.get("href")
                    if href:
                        self.assertTrue(href.startswith("#"))
                        self.assertIn(href[1:], ids)

    def test_readme_references_existing_assets(self):
        readme = (ROOT/"README.md").read_text()
        for path in re.findall(r'(?:src|srcset)="([^"]+)"', readme):
            self.assertTrue((ROOT/path).is_file(), path)
        self.assertIn("Desarrollo, investigación y diseño de interfaces de nueva generación", readme)
        self.assertNotIn("Ideas que se convierten en sistemas", readme)


if __name__ == "__main__":
    unittest.main()
