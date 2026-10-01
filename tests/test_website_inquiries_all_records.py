import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebsiteInquiryAllRecordsWorkflowTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_inquiries_route_loads_all_visible_records_without_date_queue(self):
        routes = self.read("app/routes.py")
        start = routes.index("def inquiries_list():")
        end = routes.index("\n\n@bp.", start)
        block = routes[start:end]
        self.assertIn("WHERE status NOT IN ('ARCHIVED','SPAM')", block)
        self.assertIn("ORDER BY created_at DESC,id DESC", block)
        self.assertNotIn("substr(created_at,1,10)", block)
        self.assertNotIn("NOT_CONTACTED','NO_ANSWER", block)
        self.assertNotIn("_selected_inquiry_date", routes)

    def test_inquiries_page_has_no_date_navigation_or_today_filters(self):
        template = self.read("app/templates/inquiries.html")
        for removed in (
            "prospect-date-nav",
            "data-website-date-trigger",
            "data-website-date-input",
            "data-website-selected-date",
            "data-website-is-today",
            "data-website-filter",
            "date=selected_date",
        ):
            self.assertNotIn(removed, template)
        self.assertIn("data-website-inquiry-list", template)

    def test_received_date_is_preserved_as_historical_information(self):
        schema = self.read("app/schema.sql")
        template = self.read("app/templates/inquiries.html")
        self.assertIn("created_at TEXT NOT NULL", schema)
        self.assertIn("Received: {{ inquiry.created_at|dt }}", template)

    def test_inquiry_backlinks_no_longer_depend_on_received_date(self):
        deals = self.read("app/templates/deals.html")
        record_detail = self.read("app/templates/record_detail.html")
        self.assertNotIn("date=(deal['inquiry_created_at'] or '')[:10]", deals)
        self.assertNotIn("date=inquiry.created_at[:10]", record_detail)


if __name__ == "__main__":
    unittest.main()
