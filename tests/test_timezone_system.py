import unittest
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from app.calendar_ops import (
    PHILIPPINES_TIMEZONE,
    demo_time_display,
    resolve_demo_datetime,
    server_time_snapshot,
    timezone_options,
)
from app.services import server_utc_now


class RSFTimezoneSystemTests(unittest.TestCase):
    def test_complete_worldwide_timezone_catalog_has_core_iana_zones(self):
        zones = set(timezone_options())
        expected = {
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Asia/Tokyo",
            "Australia/Sydney",
            "Asia/Manila",
            "UTC",
            "Etc/GMT",
        }
        self.assertTrue(expected.issubset(zones))
        self.assertGreaterEqual(len(zones), 500)
        self.assertNotIn("localtime", zones)
        self.assertNotIn("posixrules", zones)

    def test_server_clock_is_aware_utc_and_not_browser_time(self):
        before = server_utc_now()
        snapshot = server_time_snapshot()
        after = server_utc_now()
        self.assertEqual(before.utcoffset(), timedelta(0))
        self.assertEqual(after.utcoffset(), timedelta(0))
        self.assertTrue(snapshot["utc"].endswith("+00:00"))
        self.assertIn("+08:00", snapshot["philippines"])

    def test_winter_and_summer_dst_conversion_to_philippines(self):
        winter = resolve_demo_datetime("2026-01-15", "14:00", "America/New_York")
        summer = resolve_demo_datetime("2026-07-15", "14:00", "America/New_York")
        manila = ZoneInfo(PHILIPPINES_TIMEZONE)

        self.assertEqual(winter.astimezone(manila).strftime("%Y-%m-%d %H:%M"), "2026-01-16 03:00")
        self.assertEqual(summer.astimezone(manila).strftime("%Y-%m-%d %H:%M"), "2026-07-16 02:00")

    def test_nonexistent_dst_local_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            resolve_demo_datetime("2026-03-08", "02:30", "America/New_York")

    def test_ambiguous_dst_local_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            resolve_demo_datetime("2026-11-01", "01:30", "America/New_York")

    def test_display_uses_selected_timezone_and_manila(self):
        result = demo_time_display("2026-07-15", "14:00", "America/New_York")
        self.assertIn("America/New_York", result["client"])
        self.assertIn("Asia/Manila", result["philippines"])


if __name__ == "__main__":
    unittest.main()
