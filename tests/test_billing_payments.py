import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BillingPaymentsTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_private_billing_page_route_exists(self):
        routes = self.read("app/routes.py")
        self.assertIn('@bp.get("/billing-payments")', routes)
        self.assertIn("def billing_payments():", routes)
        self.assertIn("@login_required", routes)
        self.assertIn('"billing_payments.html"', routes)

    def test_billing_page_reuses_existing_managed_client_fields(self):
        routes = self.read("app/routes.py")
        template = self.read("app/templates/billing_payments.html")
        self.assertIn("d.management_fee", routes)
        self.assertIn("d.next_billing_date", routes)
        self.assertIn("SUPPORT_MAINTENANCE", routes)
        self.assertIn("MANAGEMENT FEE", template)
        self.assertIn("NEXT BILLING DATE", template)
        self.assertIn("<h1>Client Billing &amp; Payments</h1>", template)
        self.assertIn("client['management_fee']", template)
        self.assertIn("client['next_billing_date']", template)

    def test_sidebar_has_finance_section_and_billing_page(self):
        base = self.read("app/templates/base.html")
        self.assertIn('<div class="nav-section-label">FINANCE</div>', base)
        self.assertIn("url_for('main.billing_payments')", base)
        self.assertIn("Client Billing &amp; Payments", base)
        self.assertIn('nav_icon("billing")', base)
        self.assertIn("billing_active", base)

    def test_billing_page_uses_dedicated_styles_and_responsive_table(self):
        base = self.read("app/templates/base.html")
        css = self.read("app/static/css/billing_payments.css")
        self.assertIn("billing_payments.css", base)
        self.assertIn(".billing-payments-table-shell", css)
        self.assertIn("color:#f5eadc!important;", css)
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn("content:attr(data-label)", css)

    def test_billing_page_is_overview_only(self):
        template = self.read("app/templates/billing_payments.html")
        self.assertNotIn("<form", template)
        self.assertNotIn("payment_status", template)
        self.assertNotIn("billing_cycle", template)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.229")


if __name__ == "__main__":
    unittest.main()
