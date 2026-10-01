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
        self.assertIn("{% set deal_show_documents = true %}", prospect)
        self.assertIn("{% set deal_documents_inside_body = true %}", prospect)
        self.assertNotIn("prospect-deal-documents", prospect)
        self.assertNotIn("{% include '_master_deal_documents.html' %}", prospect)
        self.assertIn("{% set deal_show_email = false %}", prospect)
        self.assertIn("{% set deal_show_contact_number = false %}", prospect)
        self.assertIn('data-prospect-field="email"', prospect)
        self.assertIn('data-prospect-field="phone"', prospect)
        self.assertNotIn('data-prospect-field="location"', prospect)

    def test_outbound_page_section_order_is_source_first(self):
        prospect = self.read("app/templates/_prospect_row.html")
        outbound_fields_at = prospect.index('<div class="prospect-detail-grid" data-card-layout-zone="source">')
        deal_at = prospect.rindex("{% include '_master_deal_information.html' %}")
        footer_at = prospect.index('<div class="prospect-deal-action">')
        self.assertLess(outbound_fields_at, deal_at)
        self.assertLess(deal_at, footer_at)
        self.assertIn("{% set deal_show_documents = true %}", prospect)
        self.assertIn("{% set deal_documents_inside_body = true %}", prospect)
        self.assertNotIn('<div class="prospect-deal-documents">', prospect)
        self.assertNotIn("{% include '_master_deal_documents.html' %}", prospect)
        self.assertNotIn('<div class="master-source-section-head"><h3>Outbound Details</h3></div>', prospect)
        self.assertNotIn("{% if is_active_deal_stage and deal %}\n        {% include '_master_deal_information.html' %}", prospect)

    def test_outbound_deal_information_is_full_width_secondary_panel(self):
        prospect = self.read("app/templates/_prospect_row.html")
        css = self.read("app/static/css/workspace_v20.css")
        details_close = prospect.index("</div>\n\n    {% if deal %}\n    <div class=\"prospect-secondary-deal-panel\">")
        deal_panel = prospect.index('<div class="prospect-secondary-deal-panel">')
        footer = prospect.index('<div class="prospect-card-footer">')
        self.assertLess(details_close, deal_panel)
        self.assertLess(deal_panel, footer)
        self.assertIn(".prospect-secondary-deal-panel", css)
        self.assertIn("border-top:1px solid #dfe8e4", css)
        self.assertIn("background:#f4fbf7", css)
        self.assertIn(".prospect-secondary-deal-panel>.master-deal-information", css)

    def test_linked_outbound_other_field_heading_and_footer_view_deal(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        deals = self.read("app/templates/deals.html")
        inquiries = self.read("app/templates/inquiries.html")
        self.assertIn("{% set deal_section_heading = 'OTHER FIELDS' %}", prospect)
        self.assertIn("{% set deal_section_heading = deal_section_heading if deal_section_heading is defined else 'Deal Information' %}", master)
        self.assertIn("<h3>{{ deal_section_heading }}</h3>", master)
        self.assertIn("{{ 'Hide' if deal_section_open else 'Show' }} {{ deal_section_heading }}", master)
        self.assertNotIn("deal_section_action_url", prospect)
        footer_at = prospect.index('<div class="prospect-card-footer">')
        view_at = prospect.index('href="{{ url_for(\'main.deals\') }}#deal-{{ linked_deal_id }}">View Deal</a>')
        copy_at = prospect.index("data-prospect-copy", footer_at)
        self.assertLess(footer_at, view_at)
        self.assertLess(view_at, copy_at)
        self.assertNotIn("deal_section_heading = 'OTHER FIELDS'", deals)
        self.assertNotIn("deal_section_heading = 'OTHER FIELDS'", inquiries)

    def test_outbound_documents_live_inside_collapsed_deal_information_only(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        deals = self.read("app/templates/deals.html")
        inquiries = self.read("app/templates/inquiries.html")
        self.assertIn("{% set deal_documents_inside_body = true %}", prospect)
        self.assertNotIn("{% include '_master_deal_documents.html' %}", prospect)
        self.assertIn("deal_show_documents and deal_documents_inside_body", master)
        self.assertIn("deal_show_documents and not deal_documents_inside_body", master)
        self.assertNotIn("deal_documents_inside_body = true", deals)
        self.assertNotIn("deal_documents_inside_body = true", inquiries)

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

    def test_deals_timezone_location_uses_separate_city_and_country_fields(self):
        deals = self.read("app/templates/deals.html")
        master = self.read("app/templates/_master_deal_information.html")
        city_country = self.read("app/templates/_master_deal_city_country.html")
        js = self.read("app/static/js/app.js")
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn("{% include '_master_deal_city_country.html' %}", master)
        self.assertIn("<small>City</small>", city_country)
        self.assertIn("<small>Country</small>", city_country)
        self.assertIn("data-timezone-city", city_country)
        self.assertIn("data-timezone-country", city_country)
        self.assertIn('name="demo_timezone_location"', city_country)
        self.assertIn("data-timezone-location-value", city_country)
        self.assertIn("timezoneSplitQuery", js)
        self.assertIn("Enter both City and Country to identify the time zone.", js)
        self.assertIn(".deal-timezone-split-grid", css)

    def test_deals_client_location_replaces_visible_shared_location(self):
        deals = self.read("app/templates/deals.html")
        master = self.read("app/templates/_master_deal_information.html")
        city_country = self.read("app/templates/_master_deal_city_country.html")
        prospect = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        self.assertIn('<input type="hidden" name="location" value="{{ deal_client_location }}">', master)
        self.assertIn('name="demo_timezone_location"', city_country)
        self.assertIn('class="deal-demo-date-time-row"', master)
        self.assertIn('data-client-time-display', master)
        self.assertIn('data-philippines-time-display', master)


    def test_latest_shared_deal_scheduling_fields_are_consistent_across_lifecycle_pages(self):
        deals = self.read("app/templates/deals.html")
        prospect = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        master = self.read("app/templates/_master_deal_information.html")
        city_country = self.read("app/templates/_master_deal_city_country.html")
        for page in (deals, prospect, inquiries):
            self.assertIn("{% include '_master_deal_information.html' %}", page)
        self.assertIn("{% include '_master_deal_city_country.html' %}", master)
        self.assertIn("<small>City</small>", city_country)
        self.assertIn("<small>Country</small>", city_country)
        self.assertIn("data-timezone-city", city_country)
        self.assertIn("data-timezone-country", city_country)

    def test_prospect_source_contact_stays_in_outbound_without_legacy_location(self):
        prospect = self.read("app/templates/_prospect_row.html")
        self.assertIn("{% set deal_show_email = false %}", prospect)
        self.assertIn("{% set deal_show_contact_number = false %}", prospect)
        self.assertIn('data-prospect-field="email"', prospect)
        self.assertIn('data-prospect-field="phone"', prospect)
        self.assertIn("<span>Contact Number</span>", prospect)
        self.assertNotIn("<span>Phone</span>", prospect)
        self.assertNotIn("{% if not is_active_deal_stage %}\n        <div class=\"prospect-detail prospect-editable-field\" data-prospect-edit-field data-prospect-field=\"email\"", prospect)
        self.assertNotIn('data-prospect-field="location"', prospect)

    def test_deals_master_field_definition_is_canonical_for_prospect(self):
        deals = self.read("app/templates/deals.html")
        prospect = self.read("app/templates/_prospect_row.html")
        inquiries = self.read("app/templates/inquiries.html")
        master = self.read("app/templates/_master_deal_information.html")
        city_country = self.read("app/templates/_master_deal_city_country.html")

        # Current Deal scheduling fields exist once in the shared renderer.
        self.assertIn("{% include '_master_deal_city_country.html' %}", master)
        self.assertIn("<small>City</small>", city_country)
        self.assertIn("<small>Country</small>", city_country)
        self.assertIn("data-timezone-city", city_country)
        self.assertIn("data-timezone-country", city_country)
        self.assertIn('name="demo_timezone_location"', city_country)
        self.assertIn('name="demo_timezone"', city_country)

        # Old Deal field definitions cannot be re-enabled by page flags.
        self.assertNotIn("deal_show_location", master)
        self.assertNotIn("deal_timezone_location_in_location_slot", master)
        self.assertNotIn("deal_timezone_split_city_country", master)
        self.assertNotIn("<span>Location</span>", master)
        self.assertNotIn("<small>Client Location / Country</small>", master)

        # All lifecycle pages use the same shared Deal renderer.
        self.assertIn("{% include '_master_deal_information.html' %}", deals)
        self.assertIn("{% include '_master_deal_information.html' %}", prospect)
        self.assertIn("{% include '_master_deal_information.html' %}", inquiries)

        # Prospect has no extra visible legacy Location and matches Contact Number naming.
        self.assertNotIn('data-prospect-field="location"', prospect)
        self.assertIn("<span>Contact Number</span>", prospect)
        self.assertNotIn("<span>Phone</span>", prospect)

    def test_prospect_moves_shared_city_country_above_platform_without_duplicate(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        shared_city_country = self.read("app/templates/_master_deal_city_country.html")
        js = self.read("app/static/js/app.js")

        self.assertIn("{% set deal_show_city_country = false %}", prospect)
        self.assertIn("{% include '_master_deal_city_country.html' %}", prospect)
        self.assertIn("{% include '_master_deal_city_country.html' %}", master)
        self.assertEqual(shared_city_country.count("<small>City</small>"), 1)
        self.assertEqual(shared_city_country.count("<small>Country</small>"), 1)
        self.assertIn('form="{{ city_country_form_id }}"', shared_city_country)
        self.assertIn('data-deal-form-id="{{ city_country_form_id }}"', shared_city_country)
        self.assertIn("explicitFormId", js)

        city_include = prospect.index("{% include '_master_deal_city_country.html' %}")
        platform = prospect.index("<span>Platform They Want</span>")
        master_include = prospect.index("{% include '_master_deal_information.html' %}")
        self.assertLess(city_include, platform)
        self.assertLess(platform, master_include)

    def test_deals_outbound_contact_fields_move_without_duplicates(self):
        deals = self.read("app/templates/deals.html")
        master = self.read("app/templates/_master_deal_information.html")
        self.assertIn("{% set deal_show_email = not deal['prospect_id'] %}", deals)
        self.assertIn("{% set deal_show_contact_number = not deal['prospect_id'] %}", deals)
        self.assertIn("{% set deal_external_email = deal['prospect_id'] %}", deals)
        self.assertIn("{% set deal_external_contact_number = deal['prospect_id'] %}", deals)
        self.assertIn('name="email" form="{{ deal_form_id }}"', deals)
        self.assertIn('name="contact_number" form="{{ deal_form_id }}"', deals)
        self.assertIn('type="hidden" name="email"', master)
        self.assertIn('type="hidden" name="contact_number"', master)
        outbound_at = deals.index("OTHER FIELDS")
        email_at = deals.index('name="email" form="{{ deal_form_id }}"')
        phone_at = deals.index('name="contact_number" form="{{ deal_form_id }}"')
        self.assertLess(outbound_at, email_at)
        self.assertLess(outbound_at, phone_at)

    def test_deals_page_remains_deal_first(self):
        deals = self.read("app/templates/deals.html")
        master_at = deals.index("{% include '_master_deal_information.html' %}")
        outbound_at = deals.index("OTHER FIELDS")
        self.assertLess(master_at, outbound_at)
        self.assertIn('<h3 id="deal-research-details-{{ deal[\'id\'] }}">OTHER FIELDS</h3>', deals)
        self.assertIn('aria-label="Show Other Fields"', deals)
        js = self.read("app/static/js/app.js")
        self.assertIn("? 'Other Fields'", js)

    def test_website_cards_reload_when_crossing_stage_boundary_either_way(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("crossedWebsiteStageBoundary", js)
        self.assertIn("websiteDealStatuses.has(previous) && websitePreDealStatuses.has(savedStatus)", js)


if __name__ == "__main__":
    unittest.main()
