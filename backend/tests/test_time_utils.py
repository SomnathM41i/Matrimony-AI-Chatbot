import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.time_utils import to_ist, get_ist_now, get_utc_now, format_ist

class TimeUtilsTests(unittest.TestCase):
    def test_utc_to_ist_conversion(self):
        # 12:00 UTC should be 17:30 IST (+5:30)
        dt_utc = datetime(2026, 7, 30, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.hour, 17)
        self.assertEqual(dt_ist.minute, 30)
        self.assertEqual(dt_ist.tzinfo.key, "Asia/Kolkata")

    def test_day_boundary_conversion(self):
        # 23:59 UTC on July 30 should convert to 05:29 IST on July 31 (next day)
        dt_utc = datetime(2026, 7, 30, 23, 59, 0, tzinfo=ZoneInfo("UTC"))
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.day, 31)
        self.assertEqual(dt_ist.hour, 5)
        self.assertEqual(dt_ist.minute, 29)

    def test_leap_year_boundary(self):
        dt_utc = datetime(2024, 2, 28, 23, 30, 0, tzinfo=ZoneInfo("UTC"))
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.month, 2)
        self.assertEqual(dt_ist.day, 29)
        self.assertEqual(dt_ist.hour, 5)

    def test_month_boundary_conversion(self):
        dt_utc = datetime(2026, 7, 31, 22, 0, 0, tzinfo=ZoneInfo("UTC"))
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.month, 8)
        self.assertEqual(dt_ist.day, 1)

    def test_year_boundary_conversion(self):
        dt_utc = datetime(2026, 12, 31, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.year, 2027)
        self.assertEqual(dt_ist.month, 1)
        self.assertEqual(dt_ist.day, 1)

    def test_naive_datetime_conversion(self):
        dt_naive = datetime(2026, 7, 30, 12, 0, 0)
        dt_ist = to_ist(dt_naive)
        self.assertEqual(dt_ist.hour, 17)
        self.assertEqual(dt_ist.minute, 30)

    def test_already_timezone_aware_datetime(self):
        dt_aware = datetime(2026, 7, 30, 17, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        dt_ist = to_ist(dt_aware)
        self.assertEqual(dt_ist.hour, 17)
        self.assertEqual(dt_ist.minute, 30)
        self.assertEqual(dt_ist.tzinfo.key, "Asia/Kolkata")

    def test_null_datetime_values(self):
        self.assertIsNone(to_ist(None))
        self.assertEqual(format_ist(None), "")
