import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SharedWhatsAppFieldTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_whatsapp_is_canonical_on_deals_only(self):
        schema = self.read("app/schema.sql")
        deals_start = schema.index("CREATE TABLE IF NOT EXISTS deals (")
        deals_end = schema.index(");", deals_start)
        deals_schema = schema[deals_start:deals_end]
        prospects_start = schema.index("CREATE TABLE IF NOT EXISTS prospects (")
        prospects_end = schema.index(");", prospects_start)
        prospects_schema = schema[prospects_start:prospects_end]
        inquiries_start = schema.index("CREATE TABLE IF NOT EXISTS website_inquiries (")
        inquiries_end = schema.index(");", inquiries_start)
        inquiries_schema = schema[inquiries_start:inquiries_end]

        self.assertIn("whatsapp_number TEXT NOT NULL DEFAULT ''", deals_schema)
        self.assertNotIn("whatsapp_number TEXT", prospects_schema)
        self.assertNotIn("whatsapp_number TEXT", inquiries_schema)

    def test_schema_migration_adds_whatsapp_once(self):
        db = self.read("app/db.py")
        self.assertIn("SCHEMA_VERSION = 38", db)
        self.assertIn('if "whatsapp_number" not in deal_columns:', db)
        self.assertIn('ALTER TABLE deals ADD COLUMN whatsapp_number TEXT NOT NULL DEFAULT', db)
        self.assertIn('(37, "rsf-v1.18.175-shared-whatsapp-number")', db)

    def test_master_field_is_shared_across_all_three_pages(self):
        master = self.read("app/templates/_master_deal_information.html")
        prospects = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")

        self.assertIn('data-card-layout-field="whatsapp_number"', master)
        self.assertIn('<span>WhatsApp #</span>', master)
        self.assertIn('name="whatsapp_number" form="{{ form_id }}"', master)
        self.assertIn("value=\"{{ deal['whatsapp_number'] }}\"", master)

        for template in (prospects, inquiries, deals):
            self.assertIn("{% include '_master_deal_information.html' %}", template)

    def test_whatsapp_participates_in_each_page_layout(self):
        routes = self.read("app/routes.py")
        specs = routes[routes.index("CARD_LAYOUT_SPECS = {"):routes.index("def _card_layout_setting_key")]
        self.assertGreaterEqual(specs.count('"whatsapp_number"'), 3)

    def test_whatsapp_autosaves_and_returns_from_deal_update(self):
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn(
            'whatsapp_number = (request.form.get("whatsapp_number", deal["whatsapp_number"] or "") or "").strip()[:120]',
            routes,
        )
        self.assertIn("contact_number=?,whatsapp_number=?,email=?", routes)
        self.assertIn('"whatsapp_number": whatsapp_number', routes)
        self.assertIn("'whatsapp_number'", js)

    def test_whatsapp_survives_provisional_deal_merge(self):
        routes = self.read("app/routes.py")
        merge_start = routes.index("def _merge_provisional_deal_into")
        merge_end = routes.index("def _reconcile_deal_sources_on_activation", merge_start)
        merge = routes[merge_start:merge_end]
        self.assertIn('"whatsapp_number"', merge)


if __name__ == "__main__":
    unittest.main()
