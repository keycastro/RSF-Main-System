import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GeneralRecordsTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_records_helper_is_restored_and_partner_scoped(self):
        routes = self.read("app/routes.py")
        self.assertIn("def _records_for_current_user(db):", routes)
        self.assertIn("build_master_records(db, partner_id=partner_scope_id())", routes)

    def test_general_records_uses_existing_master_record_model(self):
        routes = self.read("app/routes.py")
        self.assertIn('title="General Records"', routes)
        self.assertIn("lifecycle_counts", routes)
        self.assertIn('record["lifecycle_group"]', routes)
        self.assertIn("PROSPECT_STATUS_LABELS", routes)

    def test_general_records_interface_is_scan_first(self):
        template = self.read("app/templates/records.html")
        for marker in (
            "General Records",
            "data-records-search",
            "data-records-lifecycle-select",
            "data-records-status-select",
            "data-records-source-select",
            "data-records-visible-count",
            "data-records-manage-toggle",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("records-status-filters", template)

    def test_destructive_controls_are_intentional_manage_mode(self):
        css = self.read("app/static/css/general_records.css")
        js = self.read("app/static/js/app.js")
        self.assertIn('data-records-manage-mode="false"', self.read("app/templates/records.html"))
        self.assertIn('.general-records-page[data-records-manage-mode="true"] .records-select-col', css)
        self.assertIn("setManageMode", js)

    def test_brand_is_general_records_entry_point(self):
        base = self.read("app/templates/base.html")
        self.assertIn('href="{{ url_for(\'main.records\') }}"', base)
        self.assertIn("brand-active", base)
        self.assertIn("general_records.css", base)

    def test_record_detail_uses_general_records_language(self):
        detail = self.read("app/templates/record_detail.html")
        self.assertIn("← General Records", detail)
        self.assertIn("General Record", detail)

    def test_error_page_no_longer_references_removed_dashboard_route(self):
        error = self.read("app/templates/error.html")
        self.assertNotIn("main.dashboard", error)
        self.assertIn("main.prospects", error)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.210")


if __name__ == "__main__":
    unittest.main()
