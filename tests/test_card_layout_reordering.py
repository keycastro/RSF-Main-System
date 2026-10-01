import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CardLayoutReorderingTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_three_workspace_pages_have_independent_layout_roots(self):
        prospects = self.read("app/templates/prospects.html")
        inquiries = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")
        self.assertIn('data-card-layout-page="prospects"', prospects)
        self.assertIn('data-card-layout-page="inquiries"', inquiries)
        self.assertIn('data-card-layout-page="deals"', deals)
        for template in (prospects, inquiries, deals):
            self.assertIn("data-card-layout-save-url", template)
            self.assertIn("data-card-layout-state", template)

    def test_shared_deal_fields_keep_one_data_source_while_becoming_reorderable(self):
        master = self.read("app/templates/_master_deal_information.html")
        city = self.read("app/templates/_master_deal_city_country.html")
        for key in (
            "followup_date", "email", "price", "contact_number", "demo_schedule",
            "next_step", "notes_after_conversation", "google_meet", "email_conversation",
        ):
            self.assertIn(f'data-card-layout-field="{key}"', master)
        self.assertIn('data-card-layout-field="city_country"', city)
        self.assertIn('form="{{ form_id }}"', master)
        self.assertIn('data-card-layout-zone="{{ deal_layout_zone }}"', master)

    def test_page_specific_source_fields_are_reorderable(self):
        prospect = self.read("app/templates/_prospect_row.html")
        inquiry = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")
        self.assertIn('data-card-layout-zone="summary"', prospect)
        self.assertIn('data-card-layout-zone="source"', prospect)
        self.assertIn("{% set deal_layout_zone = 'other' %}", prospect)
        self.assertIn('data-card-layout-zone="source"', inquiry)
        self.assertIn("{% set deal_layout_zone = 'deal' %}", inquiry)
        self.assertIn('data-card-layout-zone="outbound"', deals)
        self.assertIn('data-card-layout-zone="inbound"', deals)

    def test_ctrl_drag_applies_to_all_cards_and_persists_server_side(self):
        js = self.read("app/static/js/app.js")
        routes = self.read("app/routes.py")
        self.assertIn("event.ctrlKey", js)
        self.assertIn("applyAll()", js)
        self.assertIn("layout_json: JSON.stringify(state)", js)
        self.assertIn("MutationObserver", js)
        self.assertIn('@bp.post("/card-layout/<page_name>")', routes)
        self.assertIn("CARD_LAYOUT_SPECS", routes)
        self.assertIn('return f"card_layout_{page_name}_v1"', routes)

    def test_visual_moves_preserve_existing_save_ownership(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("const researchSectionFor", js)
        self.assertIn("researchSectionFor(field)", js)
        self.assertIn("researchSectionFor(dealResearchLongTextSource)", js)
        self.assertIn("researchSectionFor(button)", js)
        self.assertIn("dealFormForField(notesSource)", js)


if __name__ == "__main__":
    unittest.main()
