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

    def test_connection_controls_live_on_finance_dashboard(self):
        routes = self.read("app/routes.py")
        template = self.read("app/templates/integration_usage_billing.html")
        self.assertIn("Integration Connections", template)
        self.assertIn("RSF Gmail", template)
        self.assertIn("Google Calendar", template)
        self.assertIn("url_for('main.gmail_connect')", template)
        self.assertIn("url_for('main.gmail_verify')", template)
        self.assertIn("url_for('main.calendar_connect')", template)
        self.assertIn("url_for('main.calendar_verify')", template)
        self.assertIn("gmail_status=gmail_status", routes)
        self.assertIn("calendar_status=calendar_status", routes)

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

    def test_dashboard_uses_real_rsf_usage_sources(self):
        model = self.read("app/integration_billing.py")
        self.assertIn("client_messages WHERE channel='EMAIL'", model)
        self.assertIn("google_calendar_synced_at", model)
        self.assertIn("whatsapp_messages", model)
        self.assertIn("manual_client_calls", model)
        self.assertIn("pg_database_size(current_database())", model)
        self.assertIn("Provider metrics not connected", model)
        self.assertIn("not Google quota usage", model)
        self.assertIn("not Meta billing usage", model)
        self.assertIn("not Twilio invoice data", model)

    def test_manual_cost_configuration_reuses_existing_settings_table(self):
        routes = self.read("app/routes.py")
        schema = self.read("app/schema.sql")
        self.assertIn('@bp.post("/integration-usage-billing/update")', routes)
        self.assertIn('@bp.post("/admin/settings/integrations/billing")', routes)
        self.assertIn("validate_csrf()", routes)
        self.assertIn("INSERT INTO settings(key,value,updated_at,updated_by_user_id)", routes)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS integration_billing", schema)

    def test_dashboard_keeps_unknown_values_explicit(self):
        template = self.read("app/templates/integration_usage_billing.html")
        self.assertIn("Not set", template)
        self.assertIn("Not available", template)
        self.assertIn("Provider invoice and quota data is not guessed.", template)
        self.assertIn("Partial total", template)

    def test_budget_warning_levels_are_supported(self):
        model = self.read("app/integration_billing.py")
        for label in ("NORMAL", "WARNING", "NEAR LIMIT", "BUDGET REACHED", "OVERAGE", "NOT SET"):
            self.assertIn(f'"{label}"', model)

    def test_dashboard_has_connection_and_billing_styles(self):
        base = self.read("app/templates/base.html")
        css = self.read("app/static/css/integration_usage_billing.css")
        self.assertIn("integration_usage_billing.css", base)
        self.assertIn(".integration-connections{", css)
        self.assertIn(".integration-connection-grid{", css)
        self.assertIn(".integration-connection-card{", css)
        self.assertIn(".integration-billing-summary{", css)
        self.assertIn(".integration-billing-table-wrap{", css)
        self.assertIn(".integration-billing-editor{", css)
        self.assertIn("@media(max-width:760px)", css)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.224")


if __name__ == "__main__":
    unittest.main()
