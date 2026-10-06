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
            "data-records-filter-toggle",
            "data-records-filter-panel",
            "data-records-visible-count",
            "Where Now",
            "Last Activity",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("general-records-summary", template)
        self.assertNotIn("<th>Source</th>", template)
        self.assertNotIn("<th>Linked Records</th>", template)

    def test_filters_remain_secondary_and_row_action_is_direct(self):
        template = self.read("app/templates/records.html")
        css = self.read("app/static/css/general_records.css")
        js = self.read("app/static/js/app.js")
        self.assertIn("data-records-filter-panel hidden", template)
        self.assertNotIn("data-records-manage-toggle", template)
        self.assertNotIn("data-record-row-check", template)
        self.assertIn("data-records-remove-trigger", template)
        self.assertIn(".general-records-row-actions", css)
        self.assertIn("data-records-remove-trigger", js)

    def test_empty_states_respect_hidden_attribute(self):
        css = self.read("app/static/css/general_records.css")
        self.assertIn(".general-records-empty[hidden]{display:none!important}", css)

    def test_permanent_control_is_centralized_in_general_records(self):
        prospects = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        records = self.read("app/templates/records.html")
        routes = self.read("app/routes.py")
        self.assertNotIn("data-prospect-delete-form", prospects)
        self.assertNotIn("website-inquiry-delete-form", inquiries)
        self.assertIn("general-records-row-remove", records)
        self.assertIn("def _delete_master_record_tree(db, record: dict)", routes)
        self.assertIn('"general_records_only"', routes)
        self.assertIn('request.form.get("confirm_delete"', routes)

    def test_general_records_action_order_is_remove_then_open(self):
        template = self.read("app/templates/records.html")
        remove_at = template.index("general-records-row-remove")
        open_at = template.index('class="general-records-open"')
        self.assertLess(remove_at, open_at)

    def test_confirmation_has_yes_and_no(self):
        template = self.read("app/templates/records.html")
        js = self.read("app/static/js/app.js")
        self.assertIn("data-records-delete-no", template)
        self.assertIn("data-records-delete-yes", template)
        self.assertIn("submitRemoval", js)
        self.assertIn("confirm_delete: 'yes'", js)

    def test_master_delete_tree_cleans_linked_internal_history(self):
        routes = self.read("app/routes.py")
        for marker in (
            '"communication_notes"',
            '"whatsapp_messages"',
            '"manual_client_calls"',
            '"ai_sales_calls"',
            "DELETE FROM activity_log",
            "DELETE FROM client_notifications",
            'DELETE FROM client_conversations',
            '_delete_rows_for_ids(db, "deals", "id", deal_ids)',
            '_delete_rows_for_ids(db, "website_inquiries", "id", inquiry_ids)',
            '_delete_rows_for_ids(db, "prospects", "id", prospect_ids)',
        ):
            self.assertIn(marker, routes)

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

    def test_general_record_detail_hides_shared_topbar(self):
        base = self.read("app/templates/base.html")
        condition_line = next(
            line for line in base.splitlines()
            if "request.endpoint not in" in line and "main.records" in line
        )
        self.assertIn("'main.record_detail'", condition_line)

    def test_record_detail_dark_surface_has_explicit_readable_text(self):
        css = self.read("app/static/css/general_records.css")
        required = (
            ".record-detail-page .record-origin-item small",
            ".record-detail-page .record-origin-item strong",
            ".record-detail-page .record-origin-item>div>span",
            ".record-detail-page .record-origin-merged span",
            ".record-detail-page .record-origin-merged strong",
            ".record-detail-page .record-client-meta strong",
            ".record-detail-page .record-no-deal span",
            ".record-detail-page .record-document-links>span",
        )
        for selector in required:
            self.assertIn(selector, css)

    def test_record_detail_source_groups_use_dark_theme_consistently(self):
        css = self.read("app/static/css/general_records.css")
        self.assertIn(".record-detail-page .record-source-group{", css)
        self.assertIn("background:rgba(255,255,255,.018)!important", css)
        self.assertIn(".record-detail-page .record-source-card-outbound .record-source-type", css)
        self.assertIn(".record-detail-page .record-source-card-inbound .record-source-type", css)
        self.assertIn(".record-detail-page .record-deal-card-v2 .record-source-type", css)

    def test_record_detail_readability_colors_are_high_contrast_light_tokens(self):
        css = self.read("app/static/css/general_records.css")
        for color in ("#f4eadc", "#b8ad9e", "#a99f92", "#9ed9c8", "#9fc5ee", "#e0c27b"):
            self.assertIn(color, css)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.225")


if __name__ == "__main__":
    unittest.main()
