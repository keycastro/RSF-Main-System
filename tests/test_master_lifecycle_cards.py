import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MasterLifecycleCardTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_master_deal_section_contains_full_deal_workspace_fields(self):
        template = self.read("app/templates/_master_deal_information.html")
        documents = self.read("app/templates/_master_deal_documents.html")
        for field in (
            'name="followup_date"',
            'name="email"',
            'name="price"',
            'name="developer"',
            'name="contact_number"',
            'name="location"',
            'name="demo_date"',
            'name="demo_time"',
            'name="demo_timezone"',
            'name="demo_timezone_location"',
            'name="next_step"',
            'name="notes_after_conversation"',
            "Google Meet",
            "Email Conversation",
        ):
            with self.subTest(field=field):
                self.assertIn(field, template)
        self.assertIn("Documents / Files", documents)

    def test_outbound_card_puts_outbound_information_before_deal_information(self):
        template = self.read("app/templates/_prospect_row.html")
        source_position = template.index('<div class="prospect-detail-grid" data-card-layout-zone="source">')
        deal_position = template.index("{% include '_master_deal_information.html' %}")
        self.assertLess(source_position, deal_position)

    def test_inbound_card_preserves_stage_specific_deal_placement(self):
        template = self.read("app/templates/inquiries.html")
        active_deal_position = template.index("{% if is_active_deal_stage and deal %}")
        source_position = template.index("website-inquiry-card-body")
        predeal_deal_position = template.index("{% if (not is_active_deal_stage) and deal %}")
        self.assertLess(active_deal_position, source_position)
        self.assertLess(source_position, predeal_deal_position)

    def test_deals_page_keeps_deal_information_before_source_details(self):
        template = self.read("app/templates/deals.html")
        deal_position = template.index("{% include '_master_deal_information.html' %}")
        outbound_position = template.index("OTHER FIELDS")
        inbound_position = template.index("Inbound Details")
        self.assertLess(deal_position, outbound_position)
        self.assertLess(deal_position, inbound_position)

    def test_lifecycle_workspace_is_prepared_on_source_pages_without_premature_merge(self):
        routes = self.read("app/routes.py")
        self.assertIn("_ensure_deal_for_prospect(", routes)
        self.assertIn("_ensure_deal_for_website_inquiry(", routes)
        self.assertGreaterEqual(routes.count("allow_merge=False"), 2)
        self.assertIn("_reconcile_deal_sources_on_activation", routes)

    def test_became_deal_timestamp_is_separate_from_workspace_creation(self):
        schema = self.read("app/schema.sql")
        db = self.read("app/db.py")
        deals = self.read("app/templates/deals.html")
        self.assertIn("became_deal_at TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("SCHEMA_VERSION = 36", db)
        self.assertIn("rsf-v1.18.131-master-lifecycle-cards", db)
        self.assertIn("deal['became_deal_at']", deals)

    def test_source_pages_include_shared_deal_dialogs(self):
        self.assertIn(
            "{% include '_master_deal_dialogs.html' %}",
            self.read("app/templates/prospects.html"),
        )
        self.assertIn(
            "{% include '_master_deal_dialogs.html' %}",
            self.read("app/templates/inquiries.html"),
        )


if __name__ == "__main__":
    unittest.main()
