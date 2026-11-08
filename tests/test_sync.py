import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_calendars.py"
spec = importlib.util.spec_from_file_location("calendar_sync", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class CalendarParserTests(unittest.TestCase):
    def test_parses_relevant_future_releases_and_et_timezone(self):
        fixture = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:bls-cpi-1
DTSTART;TZID=America/New_York:20261113T083000
SUMMARY:Consumer Price Index\\, October 2026
URL:https://www.bls.gov/news.release/cpi.htm
END:VEVENT
BEGIN:VEVENT
UID:irrelevant
DTSTART:20261113T140000Z
SUMMARY:Local area report
END:VEVENT
END:VCALENDAR
"""
        rows = sync.parse_ics(fixture, "BLS", datetime(2026, 11, 8, tzinfo=timezone.utc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "inflation")
        self.assertEqual(rows[0]["start_utc"], "2026-11-13T13:30:00+00:00")
        self.assertEqual(rows[0]["source_url"], "https://www.bls.gov/news.release/cpi.htm")

    def test_unfolds_lines_and_skips_date_only(self):
        fixture = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:gdp-1
DTSTART;VALUE=DATE-TIME:20261125T133000Z
SUMMARY:Gross Domestic Product\\, Q3 2026 (Second 
 Estimate)
END:VEVENT
BEGIN:VEVENT
UID:all-day
DTSTART;VALUE=DATE:20261126
SUMMARY:Producer Price Index
END:VEVENT
END:VCALENDAR
"""
        rows = sync.parse_ics(fixture, "BEA", datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual(len(rows), 1)
        self.assertIn("Second Estimate", rows[0]["title"])
        self.assertEqual(rows[0]["category"], "growth")

    def test_old_events_are_ignored(self):
        fixture = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:old
DTSTART:20260101T133000Z
SUMMARY:Gross Domestic Product
END:VEVENT
END:VCALENDAR
"""
        rows = sync.parse_ics(fixture, "BEA", datetime(2026, 11, 8, tzinfo=timezone.utc))
        self.assertEqual(rows, [])

    def test_cancelled_events_are_ignored(self):
        fixture = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:cancelled-cpi
DTSTART;TZID=America/New_York:20261113T083000
SUMMARY:Consumer Price Index
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR
"""
        rows = sync.parse_ics(fixture, "BLS", datetime(2026, 11, 8, tzinfo=timezone.utc))
        self.assertEqual(rows, [])

    def test_failed_source_retains_its_previous_calendar(self):
        old_file = sync.DATA_FILE
        bls_feed = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:keep-cpi
DTSTART;TZID=America/New_York:20261113T083000
SUMMARY:Consumer Price Index
END:VEVENT
END:VCALENDAR
"""
        bea_feed = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:new-gdp
DTSTART:20261125T133000Z
SUMMARY:Gross Domestic Product Q3
END:VEVENT
END:VCALENDAR
"""
        try:
            with tempfile.TemporaryDirectory() as temp:
                sync.DATA_FILE = Path(temp) / "events.json"
                def first_fetch(url):
                    if "bls.gov" in url:
                        return bls_feed
                    raise OSError("feed temporarily unavailable")
                with patch.object(sync, "fetch_ics", side_effect=first_fetch):
                    first = sync.update_calendar(datetime(2026, 11, 8, tzinfo=timezone.utc))
                self.assertEqual({x["id"] for x in first["events"]}, {"BLS:keep-cpi"})
                self.assertEqual(next(s for s in first["sources"] if s["name"]=="BEA")["status"], "error")

                def second_fetch(url):
                    if "bls.gov" in url:
                        raise OSError("still unavailable")
                    return bea_feed
                with patch.object(sync, "fetch_ics", side_effect=second_fetch):
                    second = sync.update_calendar(datetime(2026, 11, 8, tzinfo=timezone.utc))
                self.assertEqual({x["id"] for x in second["events"]}, {"BLS:keep-cpi", "BEA:new-gdp"})
                saved = json.loads(sync.DATA_FILE.read_text(encoding="utf-8"))
                self.assertEqual(len(saved["events"]), 2)
        finally:
            sync.DATA_FILE = old_file

if __name__ == "__main__":
    unittest.main()
