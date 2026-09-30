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
from app.timezone_location import resolve_location_query


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

    def _assert_auto_timezone(self, query: str, expected_timezone: str):
        result = resolve_location_query(query)
        self.assertTrue(result["auto_select"], msg=f"{query}: {result}")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["timezone"], expected_timezone)
        self.assertTrue(result["results"][0]["location"])
        self.assertTrue(result["results"][0]["offset"].startswith("UTC"))

    def test_location_country_philippines_auto_resolves(self):
        self._assert_auto_timezone("Philippines", "Asia/Manila")

    def test_location_davao_city_auto_resolves(self):
        self._assert_auto_timezone("Davao City", "Asia/Manila")

    def test_location_tokyo_japan_auto_resolves(self):
        self._assert_auto_timezone("Tokyo, Japan", "Asia/Tokyo")

    def test_location_london_uk_auto_resolves(self):
        self._assert_auto_timezone("London, United Kingdom", "Europe/London")

    def test_location_new_york_usa_auto_resolves(self):
        self._assert_auto_timezone("New York, USA", "America/New_York")

    def test_location_los_angeles_usa_auto_resolves(self):
        self._assert_auto_timezone("Los Angeles, USA", "America/Los_Angeles")

    def test_multizone_country_united_states_is_never_auto_selected(self):
        result = resolve_location_query("United States")
        self.assertFalse(result["auto_select"])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIn("city or state/province", result["message"])
        self.assertGreater(len({item["timezone"] for item in result["results"]}), 1)

    def test_multizone_country_canada_is_never_auto_selected(self):
        result = resolve_location_query("Canada")
        self.assertFalse(result["auto_select"])
        self.assertEqual(result["status"], "ambiguous")
        self.assertGreater(len({item["timezone"] for item in result["results"]}), 1)


    def test_state_california_auto_resolves(self):
        self._assert_auto_timezone("California, USA", "America/Los_Angeles")

    def test_province_or_region_search_uses_worldwide_admin1_data(self):
        self._assert_auto_timezone("New South Wales, Australia", "Australia/Sydney")

    def test_multizone_country_australia_is_never_auto_selected(self):
        result = resolve_location_query("Australia")
        self.assertFalse(result["auto_select"])
        self.assertEqual(result["status"], "ambiguous")
        self.assertGreater(len({item["timezone"] for item in result["results"]}), 1)

    def test_exact_iana_zone_remains_supported(self):
        self._assert_auto_timezone("Pacific/Auckland", "Pacific/Auckland")


if __name__ == "__main__":
    unittest.main()
