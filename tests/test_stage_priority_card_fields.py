import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StagePriorityCardFieldTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_master_deal_shared_fields_can_render_once_without_losing_form_values(self):
        master = self.read("app/templates/_master_deal_information.html")
        for flag in (
            "deal_show_email",
            "deal_show_contact_number",
            "deal_show_location",
            "deal_show_notes",
            "deal_show_email_conversation",
        ):
            self.assertIn(flag, master)
        self.assertIn('type="hidden" name="email"', master)
        self.assertIn('type="hidden" name="contact_number"', master)
        self.assertIn('type="hidden" name="location"', master)
        self.assertIn('name="notes_after_conversation" data-deal-notes-compact hidden', master)

    def test_prospect_card_keeps_original_shell_and_shared_field_rules(self):
        prospect = self.read("app/templates/_prospect_row.html")
        self.assertIn("is_active_deal_stage", prospect)
        self.assertIn("<span>Business Type:</span>", prospect)
        self.assertIn('<span>Budget</span>', prospect)
        self.assertIn('<span>Post Date</span>', prospect)
        self.assertIn('<span>Platform They Want</span>', prospect)
        self.assertNotIn('{% if is_active_deal_stage %}\n        <div class="prospect-detail prospect-editable-field" data-prospect-edit-field data-prospect-field="business_type"', prospect)
        self.assertEqual(prospect.count("{% include '_master_deal_information.html' %}"), 1)
        self.assertIn("{% set deal_show_documents = false %}", prospect)
        self.assertIn("prospect-deal-documents", prospect)
        self.assertIn("{% include '_master_deal_documents.html' %}", prospect)
        self.assertIn("{% set deal_show_email = is_active_deal_stage %}", prospect)
        self.assertIn("{% set deal_show_location = is_active_deal_stage %}", prospect)

    def test_outbound_page_section_order_is_source_first(self):
        prospect = self.read("app/templates/_prospect_row.html")
        outbound_at = prospect.index('<div class="master-source-section-head"><h3>Outbound Details</h3></div>')
        documents_at = prospect.index('<div class="prospect-deal-documents">')
        deal_at = prospect.rindex("{% include '_master_deal_information.html' %}")
        footer_at = prospect.index('<div class="prospect-deal-action">')
        self.assertLess(outbound_at, documents_at)
        self.assertLess(documents_at, deal_at)
        self.assertLess(deal_at, footer_at)
        self.assertIn("{% set deal_show_documents = false %}", prospect)
        self.assertNotIn("{% if is_active_deal_stage and deal %}\n        {% include '_master_deal_information.html' %}", prospect)

    def test_outbound_page_collapses_deal_information_but_keeps_deals_page_open(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        deals = self.read("app/templates/deals.html")
        self.assertIn("{% set deal_section_collapsible = true %}", prospect)
        self.assertIn("{% set deal_section_open = false %}", prospect)
        self.assertIn("data-master-deal-toggle", master)
        self.assertIn("master-deal-body-{{ dom_key }}", master)
        self.assertIn("deal_section_collapsible and not deal_section_open", master)
        self.assertNotIn("deal_section_collapsible = true", deals)

    def test_inquiry_card_uses_one_editable_email_phone_instance_predeal(self):
        inquiry = self.read("app/templates/inquiries.html")
        self.assertIn('name="email"', inquiry)
        self.assertIn('name="contact_number"', inquiry)
        self.assertIn('form="{{ deal_form_id }}" data-inquiry-email', inquiry)
        self.assertIn('form="{{ deal_form_id }}" data-inquiry-phone', inquiry)
        self.assertIn("{% set deal_external_email = not is_active_deal_stage %}", inquiry)
        self.assertIn("{% if is_active_deal_stage and deal %}", inquiry)
        self.assertIn("{% if (not is_active_deal_stage) and deal %}", inquiry)

    def test_deals_page_remains_deal_first(self):
        deals = self.read("app/templates/deals.html")
        master_at = deals.index("{% include '_master_deal_information.html' %}")
        outbound_at = deals.index("Outbound Details")
        self.assertLess(master_at, outbound_at)

    def test_website_cards_reload_when_crossing_stage_boundary_either_way(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("crossedWebsiteStageBoundary", js)
        self.assertIn("websiteDealStatuses.has(previous) && websitePreDealStatuses.has(savedStatus)", js)


if __name__ == "__main__":
    unittest.main()
