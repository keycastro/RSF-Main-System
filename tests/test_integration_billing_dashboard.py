import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IntegrationBillingDashboardTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_dashboard_is_a_founder_only_finance_page(self):
        routes = self.read("app/routes.py")
        base = self.read("app/templates/base.html")
        template = self.read("app/templates/integration_usage_billing.html")
        self.assertIn('@bp.get("/integration-usage-billing")', routes)
        self.assertIn("def integration_usage_billing():", routes)
        self.assertIn('@bp.get("/integration-usage-billing")\n@admin_required', routes)
        self.assertIn('"integration_usage_billing.html"', routes)
        self.assertIn("url_for('main.integration_usage_billing')", base)
        self.assertIn("Integration Usage &amp; Billing", base)
        self.assertIn("{% if g.user.role == 'admin' %}", base)
        self.assertIn("<h1>Integration Usage &amp; Billing</h1>", template)

    def test_integrations_are_removed_from_settings_navigation_and_page(self):
        routes = self.read("app/routes.py")
        settings = self.read("app/templates/settings.html")
        navigation = self.read("app/templates/_settings_navigation.html")
        self.assertNotIn("active_section == 'integrations'", settings)
        self.assertNotIn(">Integrations<", navigation)
        self.assertNotIn("Connected tools and services", navigation)
        self.assertNotIn("integrations, account access", navigation)
        self.assertIn('if section == "integrations":', routes)
        self.assertIn('return redirect(url_for("main.integration_usage_billing"))', routes)
        self.assertIn('allowed_sections = {"general", "appearance", "workflow"}', routes)

    def test_connection_controls_are_merged_into_the_single_usage_table(self):
        template = self.read("app/templates/integration_usage_billing.html")
        self.assertNotIn("Integration Connections", template)
        self.assertNotIn("integration-connection-card", template)
        self.assertNotIn("integration-connection-grid", template)
        self.assertEqual(template.count("<table"), 1)
        self.assertIn("<th>Action</th>", template)

        table_start = template.index('<table class="integration-billing-table integration-billing-table--simple">')
        table_end = template.index("</table>", table_start)
        table_markup = template[table_start:table_end]
        self.assertIn("item.slug == 'gmail'", table_markup)
        self.assertIn("item.slug == 'calendar'", table_markup)
        self.assertIn("url_for('main.gmail_connect')", table_markup)
        self.assertIn("url_for('main.gmail_verify')", table_markup)
        self.assertIn("url_for('main.calendar_connect')", table_markup)
        self.assertIn("url_for('main.calendar_verify')", table_markup)
        self.assertIn("integration-row-details", table_markup)

    def test_manual_cost_and_budget_editing_is_completely_removed(self):
        template = self.read("app/templates/integration_usage_billing.html")
        routes = self.read("app/routes.py")
        model = self.read("app/integration_billing.py")
        css = self.read("app/static/css/integration_usage_billing.css")

        self.assertNotIn("Edit Costs", template)
        self.assertNotIn("Monthly Budget", template)
        self.assertNotIn("Billing Date", template)
        self.assertNotIn("type=\"number\"", template)
        self.assertNotIn("integration_billing_update", routes)
        self.assertNotIn('/integration-usage-billing/update', routes)
        self.assertNotIn('/admin/settings/integrations/billing', routes)
        self.assertNotIn("validate_manual_money", routes)
        self.assertNotIn("integration_billing.", model)
        self.assertNotIn("_budget_status", model)
        self.assertNotIn("_setting_value", model)
        self.assertNotIn("integration-billing-editor", css)
        self.assertNotIn("integration-billing-form", css)

    def test_summary_is_automatic_only(self):
        template = self.read("app/templates/integration_usage_billing.html")
        model = self.read("app/integration_billing.py")
        for label in ("Known Cost", "Costs Found", "Active", "Needs Setup"):
            self.assertIn(f"<span>{label}</span>", template)
        self.assertIn('"known_cost_text"', model)
        self.assertIn('"cost_available_count"', model)
        self.assertIn('"active_count"', model)
        self.assertIn('"needs_setup_count"', model)
        self.assertNotIn("<span>Budget</span>", template)
        self.assertNotIn("<span>Left</span>", template)
        self.assertNotIn("<span>Over Budget</span>", template)

    def test_twilio_cost_comes_from_twilio_usage_api(self):
        twilio = self.read("app/twilio_manual_call_ops.py")
        model = self.read("app/integration_billing.py")
        self.assertIn("def current_month_usage()", twilio)
        self.assertIn("Usage/Records/ThisMonth.json?PageSize=1000", twilio)
        self.assertIn('"totalprice"', twilio)
        self.assertIn('"calls"', twilio)
        self.assertIn("twilio_current_month_usage", model)
        self.assertIn('"Cost comes from Twilio."', model)
        self.assertIn('"Usage comes from Twilio."', model)

    def test_unavailable_provider_costs_are_not_guessed(self):
        template = self.read("app/templates/integration_usage_billing.html")
        model = self.read("app/integration_billing.py")
        self.assertIn("Not available", model)
        self.assertIn("Render billing is not connected to this dashboard.", model)
        self.assertIn("Database billing is not connected to this dashboard.", model)
        self.assertIn("Google billing is not connected to this dashboard.", model)
        self.assertIn("WhatsApp billing is not connected to this dashboard.", model)
        self.assertIn("If a provider does not give RSF billing data, the cost shows as Not available instead of using a guess.", template)

    def test_dashboard_keeps_real_usage_sources(self):
        model = self.read("app/integration_billing.py")
        self.assertIn("client_messages WHERE channel='EMAIL'", model)
        self.assertIn("google_calendar_synced_at", model)
        self.assertIn("whatsapp_messages", model)
        self.assertIn("manual_client_calls", model)
        self.assertIn("pg_database_size(current_database())", model)
        self.assertIn('"usage_source": "Measured by RSF."', model)
        self.assertIn('"usage_source": "Based on emails recorded in RSF."', model)
        self.assertIn('"usage_source": "Based on calendar syncs recorded in RSF."', model)
        self.assertIn('"usage_source": "Based on WhatsApp messages recorded in RSF."', model)

    def test_oauth_endpoint_urls_are_preserved_but_return_to_finance(self):
        routes = self.read("app/routes.py")
        self.assertIn('@bp.get("/admin/settings/gmail/connect")', routes)
        self.assertIn('@bp.get("/admin/settings/gmail/callback")', routes)
        self.assertIn('@bp.post("/admin/settings/gmail/verify")', routes)
        self.assertIn('@bp.get("/admin/settings/calendar/connect")', routes)
        self.assertIn('@bp.get("/admin/settings/calendar/callback")', routes)
        self.assertIn('@bp.post("/admin/settings/calendar/verify")', routes)
        self.assertNotIn('url_for("main.settings", section="integrations")', routes)
        self.assertGreaterEqual(routes.count('url_for("main.integration_usage_billing")'), 10)

    def test_main_usage_table_has_simple_scan_columns(self):
        template = self.read("app/templates/integration_usage_billing.html")
        for heading in ("Service", "Status", "Usage", "Cost", "Action"):
            self.assertIn(f"<th>{heading}</th>", template)
        self.assertNotIn("<th>Monthly Budget</th>", template)
        self.assertNotIn("<th>Remaining / Overage</th>", template)
        self.assertNotIn("<th>Usage Level</th>", template)
        self.assertNotIn("<th>Billing / Reset</th>", template)
        self.assertIn("Needs setup", template)

    def test_technical_details_are_secondary(self):
        template = self.read("app/templates/integration_usage_billing.html")
        self.assertIn('<details class="integration-data-note">', template)
        self.assertIn('<details class="integration-row-details">', template)
        self.assertIn("View Details", template)
        self.assertIn("About These Numbers", template)
        self.assertIn("Usage and cost are filled automatically when RSF can read them safely.", template)

    def test_dashboard_has_unified_responsive_styles(self):
        base = self.read("app/templates/base.html")
        css = self.read("app/static/css/integration_usage_billing.css")
        self.assertIn("integration_usage_billing.css", base)
        self.assertIn(".integration-dashboard-section{", css)
        self.assertIn(".integration-billing-summary{", css)
        self.assertIn(".integration-billing-table--simple", css)
        self.assertIn(".integration-row-actions{", css)
        self.assertIn(".integration-row-details{", css)
        self.assertIn(".integration-attention--setup", css)
        self.assertIn(".integration-data-note", css)
        self.assertIn("@media(max-width:760px)", css)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.228")


if __name__ == "__main__":
    unittest.main()
