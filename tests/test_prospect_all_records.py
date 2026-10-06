import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProspectAllRecordsWorkflowTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_prospects_route_loads_all_records_without_date_queue(self):
        routes = self.read("app/routes.py")
        start = routes.index("def prospects():")
        end = routes.index('@bp.route("/prospects/new"', start)
        block = routes[start:end]
        self.assertIn('SELECT p.* FROM prospects p ORDER BY p.id DESC', block)
        self.assertNotIn("recorded_date=?", block)
        self.assertNotIn("NOT_CONTACTED','NO_ANSWER", block)
        self.assertNotIn("_selected_prospect_date", routes)
        self.assertNotIn("PROSPECT_UNFINISHED_STATUSES", routes)

    def test_prospects_page_has_no_date_navigation_or_daily_filters(self):
        template = self.read("app/templates/prospects.html")
        for removed in (
            "prospect-date-nav",
            "data-prospect-date-trigger",
            "data-prospect-date-input",
            "data-prospect-selected-date",
            "data-prospect-is-today",
        ):
            self.assertNotIn(removed, template)
        self.assertIn("data-prospect-filter", template)
        self.assertIn("data-prospect-quick-add", template)
        self.assertIn("{% for prospect in prospects %}", template)

    def test_historical_added_date_is_preserved(self):
        schema = self.read("app/schema.sql")
        row = self.read("app/templates/_prospect_row.html")
        self.assertIn("recorded_date TEXT NOT NULL", schema)
        self.assertIn("Added: {{ prospect['created_at']|dt }}", row)

    def test_prospect_backlinks_no_longer_depend_on_recorded_date(self):
        row = self.read("app/templates/_prospect_row.html")
        deals = self.read("app/templates/deals.html")
        record_detail = self.read("app/templates/record_detail.html")
        self.assertNotIn("date=selected_date", row)
        self.assertNotIn("date=deal['prospect_recorded_date']", deals)
        self.assertNotIn("date=prospect.recorded_date", record_detail)


if __name__ == "__main__":
    unittest.main()
