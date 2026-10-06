import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SharedDeveloperFieldTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_developer_is_canonical_on_deals_only(self):
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

        self.assertIn("developer TEXT NOT NULL DEFAULT ''", deals_schema)
        self.assertNotIn("developer TEXT", prospects_schema)
        self.assertNotIn("developer TEXT", inquiries_schema)

    def test_schema_migration_adds_developer_once(self):
        db = self.read("app/db.py")
        self.assertIn("SCHEMA_VERSION = 43", db)
        self.assertIn('if "developer" not in deal_columns:', db)
        self.assertIn('ALTER TABLE deals ADD COLUMN developer TEXT NOT NULL DEFAULT', db)
        self.assertIn('(36, "rsf-v1.18.155-shared-developer-field")', db)

    def test_master_field_is_shared_and_editable_on_all_three_pages(self):
        master = self.read("app/templates/_master_deal_information.html")
        prospects = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")

        self.assertIn('data-card-layout-field="developer"', master)
        self.assertIn('<span>Developer</span>', master)
        self.assertIn('name="developer" form="{{ form_id }}"', master)
        self.assertIn("value=\"{{ deal['developer'] }}\"", master)
        self.assertNotIn('placeholder="e.g. John Cruz"', master)

        for template in (prospects, inquiries, deals):
            self.assertIn("{% include '_master_deal_information.html' %}", template)

    def test_developer_header_colon_and_blank_placeholder(self):
        master = self.read("app/templates/_master_deal_information.html")
        css = self.read("app/static/css/workspace_v20.css")
        self.assertNotIn('placeholder="e.g. John Cruz"', master)
        self.assertIn('[data-card-layout-current-zone="header"][data-card-layout-field="developer"]>span::after', css)
        self.assertIn('content:":"', css)

    def test_developer_participates_in_each_page_layout(self):
        routes = self.read("app/routes.py")
        specs = routes[routes.index("CARD_LAYOUT_SPECS = {"):routes.index("def _card_layout_setting_key")]
        self.assertGreaterEqual(specs.count('"developer"'), 3)

    def test_developer_autosaves_through_deal_update_only(self):
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn('developer = (request.form.get("developer", deal["developer"] or "") or "").strip()[:200]', routes)
        self.assertIn("price=?,developer=?", routes)
        self.assertIn('"developer": developer', routes)
        self.assertIn("'developer'", js)

    def test_developer_survives_provisional_deal_merge(self):
        routes = self.read("app/routes.py")
        merge_start = routes.index("def _merge_provisional_deal_into")
        merge_end = routes.index("def _reconcile_deal_sources_on_activation", merge_start)
        merge = routes[merge_start:merge_end]
        self.assertIn('"developer"', merge)


if __name__ == "__main__":
    unittest.main()
