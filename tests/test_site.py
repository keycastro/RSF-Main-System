import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

from app import create_app


class PortfolioSiteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/system/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["app"], "Key Castro Portfolio")
        version_file = Path(__file__).resolve().parents[1] / "VERSION.txt"
        self.assertEqual(data["version"], version_file.read_text(encoding="utf-8").strip())
        self.assertEqual(data["version"], "3.5.1")

    def test_main_pages_and_template_library_render(self):
        routes = [
            "/",
            "/about",
            "/services",
            "/contact",
            "/system-templates",
            "/system-templates/property-operations-command-center",
            "/system-templates/property-inventory-hub",
        ]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"KEY CASTRO", response.data)

        for route in ("/skills", "/experience"):
            with self.subTest(route=route):
                response = self.client.get(route, follow_redirects=False)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers["Location"], "/about")

    def test_two_systems_are_published_separately_and_nexus_is_removed(self):
        home = self.client.get("/")
        library = self.client.get("/system-templates")

        for response in (home, library):
            self.assertIn(b"Property Operations Command Center", response.data)
            self.assertIn(b"Property Inventory Hub", response.data)
            self.assertNotIn(b"Nexus Properties", response.data)

        legacy_projects = self.client.get("/projects", follow_redirects=False)
        self.assertEqual(legacy_projects.status_code, 301)
        self.assertEqual(legacy_projects.headers["Location"], "/system-templates")

        pocc = self.client.get("/system-templates/property-operations-command-center")
        pih = self.client.get("/system-templates/property-inventory-hub")
        self.assertIn(b"Task tracking with priority", pocc.data)
        self.assertNotIn(b"Reconfirmation and automatic expiry", pocc.data)
        self.assertIn(b"Reconfirmation and automatic expiry", pih.data)
        self.assertNotIn(b"Owner approvals", pih.data)

        old_nexus = self.client.get("/projects/nexus-properties")
        self.assertEqual(old_nexus.status_code, 404)

    def test_navigation_and_home_hierarchy(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b">Home</a>", response.data)
        self.assertIn(b">Systems</a>", response.data)
        self.assertIn(b">Services</a>", response.data)
        self.assertIn(b">About</a>", response.data)
        self.assertIn(b">Contact</a>", response.data)
        self.assertNotIn(b">Projects</a>", response.data)
        self.assertNotIn(b">System Templates</a>", response.data)
        self.assertIn(b">SYSTEMS<", response.data)
        self.assertIn(b"View Systems", response.data)
        self.assertIn(b"Contact Me", response.data)
        self.assertNotIn(b"$49", response.data)
        self.assertNotIn(b"$490", response.data)
        self.assertEqual(response.data.count(b"Property Operations Command Center</h3>"), 1)
        self.assertEqual(response.data.count(b"Property Inventory Hub</h3>"), 1)
        public_shell = response.data.lower()
        self.assertNotIn(b"key castro inbox", public_shell)
        self.assertNotIn(b"owner dashboard", public_shell)
        self.assertNotIn(b">admin<", public_shell)

    def test_information_architecture_uses_one_systems_mental_model(self):
        home = self.client.get("/")
        systems = self.client.get("/system-templates")
        services = self.client.get("/services")
        about = self.client.get("/about")

        # One primary place to browse systems; Projects remains a legacy redirect only.
        self.assertIn(b">Systems</a>", home.data)
        self.assertNotIn(b">Projects</a>", home.data)
        self.assertNotIn(b">System Templates</a>", home.data)
        self.assertIn(b"Choose a system.", systems.data)
        self.assertNotIn(b"Free access by request</strong>", systems.data)

        # Skills and Experience are merged into About and their old URLs redirect there.
        header = home.data.split(b"</header>", 1)[0]
        self.assertNotIn(b">Skills &amp; technology</a>", header)
        self.assertNotIn(b">Experience</a>", header)
        self.assertNotIn(b"Skills &amp; technology", about.data)
        self.assertNotIn(b">Experience</a>", about.data)

        # Services has only the two choices a visitor needs.
        self.assertIn(b"Use a ready-made system", services.data)
        self.assertIn(b"Custom work", services.data)
        self.assertNotIn(b"FREE STANDARD SYSTEM", services.data)

    def test_compact_presentation_keeps_screenshots_supporting_content(self):
        home = self.client.get("/")
        systems = self.client.get("/system-templates")
        detail = self.client.get("/system-templates/property-operations-command-center")

        self.assertIn(b"hero-simple", home.data)
        self.assertNotIn(b"orientation-panel", home.data)
        self.assertIn(b"compact-system-grid", home.data)
        self.assertIn(b"compact-library-grid", systems.data)
        self.assertIn(b"compact-template-card", systems.data)
        self.assertIn(b"template-card-copy", systems.data)
        self.assertIn(b"compact-case-cover", detail.data)
        self.assertIn(b"compact-gallery-grid", detail.data)
        self.assertIn(b"Open image", detail.data)

        css_path = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "style.css"
        css = css_path.read_text(encoding="utf-8")
        self.assertIn('3.0.0', css)
        self.assertIn('3.4.0', css)
        self.assertIn('3.5.0', css)
        self.assertIn('height:262px', css)
        self.assertIn('height:190px', css)
        self.assertIn('height:150px', css)

    def test_system_cards_have_clear_separate_visual_identities(self):
        home = self.client.get("/")
        systems = self.client.get("/system-templates")

        for response in (home, systems):
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"system-choice-card--property-operations-command-center", response.data)
            self.assertIn(b"system-choice-card--property-inventory-hub", response.data)
            self.assertIn(b"View System", response.data)

        self.assertIn(b"Each system solves a different problem. Choose one to view.", home.data)
        self.assertIn(b"Each system solves a different problem. Choose one to view.", systems.data)

        css_path = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "style.css"
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("3.5.1 — SYSTEM CARD VISUAL SEPARATION", css)
        self.assertIn("#fffaf3", css)
        self.assertIn("#f4f8fa", css)
        self.assertIn("prefers-reduced-motion:reduce", css)

    def test_system_search_is_metadata_driven_accessible_and_progressive(self):
        from app.system_templates import published_templates

        systems = self.client.get("/system-templates")
        self.assertEqual(systems.status_code, 200)
        self.assertIn(b'data-system-search', systems.data)
        self.assertIn(b'role="search"', systems.data)
        self.assertIn(b'Search systems...', systems.data)
        self.assertIn(b'aria-controls="system-results"', systems.data)
        self.assertIn(b'aria-live="polite"', systems.data)
        self.assertIn(b'>Clear</button>', systems.data)
        self.assertIn(b'No matching system.', systems.data)
        self.assertIn(b'Contact Me', systems.data)
        self.assertEqual(systems.data.count(b'data-system-card'), 2)

        templates = {item.slug: item for item in published_templates()}
        pocc_search = templates["property-operations-command-center"].search_text.lower()
        pih_search = templates["property-inventory-hub"].search_text.lower()
        for term in ("operations", "maintenance", "rental", "tenant", "approvals"):
            self.assertIn(term, pocc_search)
        for term in ("inventory", "brokerage", "listings", "marketplace"):
            self.assertIn(term, pih_search)
        self.assertNotIn("crm", pih_search)

        js_path = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "main.js"
        js = js_path.read_text(encoding="utf-8")
        self.assertIn("[data-system-search]", js)
        self.assertIn("card.dataset.search", js)
        self.assertIn("No matching systems", js)
        self.assertNotIn("property-operations-command-center", js)
        self.assertNotIn("property-inventory-hub", js)

    def test_subscription_and_paid_customization_are_clear_without_changing_contact_flow(self):
        systems = self.client.get("/system-templates")
        detail = self.client.get("/system-templates/property-operations-command-center")
        subscription_contact = self.client.get("/contact?template=property-operations-command-center&intent=subscribe")
        custom_contact = self.client.get("/contact?template=property-operations-command-center&intent=customize")

        self.assertNotIn(b'$49', systems.data)
        self.assertNotIn(b'$490', systems.data)
        self.assertIn(b'You pay for access to this system', detail.data)
        self.assertIn(b'CUSTOM CHANGES', detail.data)
        self.assertIn(b'Custom work is priced separately', detail.data)
        self.assertIn(b'You are asking for access to Property Operations Command Center', subscription_contact.data)
        self.assertNotIn(b'$49/month', subscription_contact.data)
        self.assertNotIn(b'$490/year', subscription_contact.data)
        self.assertIn(b'You are asking for changes to Property Operations Command Center', custom_contact.data)
        self.assertIn(b'name="source_intent" value="subscribe"', subscription_contact.data)
        self.assertIn(b'name="source_intent" value="customize"', custom_contact.data)

    def test_public_commercial_model_is_subscription_plus_paid_customization(self):
        public_paths = [
            "/",
            "/system-templates",
            "/system-templates/property-operations-command-center",
            "/system-templates/property-inventory-hub",
            "/services",
            "/contact",
        ]
        retired = [b"FREE STANDARD SYSTEM", b"Free Template Access", b"Request Free Access", b"free by request"]
        for path in public_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                for phrase in retired:
                    self.assertNotIn(phrase, response.data)

        systems = self.client.get("/system-templates")
        self.assertIn(b"View System", systems.data)
        self.assertNotIn(b"MANAGED SYSTEM SUBSCRIPTION", systems.data)

        detail = self.client.get("/system-templates/property-operations-command-center")
        self.assertIn(b"CUSTOM CHANGES", detail.data)
        self.assertIn(b"normal subscription still continues", detail.data)
        self.assertNotIn(b"lifetime", detail.data.lower())
        self.assertNotIn(b"own the source", detail.data.lower())

    def test_managed_subscription_pricing_has_one_trusted_source_and_correct_math(self):
        from app.system_templates import MANAGED_SUBSCRIPTION_PRICING, published_templates

        pricing = MANAGED_SUBSCRIPTION_PRICING
        self.assertEqual(pricing.currency_code, "USD")
        self.assertEqual(pricing.monthly_price, 49)
        self.assertEqual(pricing.yearly_price, 490)
        self.assertEqual(pricing.annual_monthly_total, 588)
        self.assertEqual(pricing.annual_savings, 98)
        self.assertEqual(pricing.monthly.price_label, "$49/month")
        self.assertEqual(pricing.yearly.price_label, "$490/year")
        self.assertEqual(len(published_templates()), 2)

        systems = self.client.get("/system-templates")
        self.assertEqual(systems.status_code, 200)
        self.assertNotIn(b"$49", systems.data)
        self.assertNotIn(b"$490", systems.data)

        detail = self.client.get("/system-templates/property-operations-command-center")
        self.assertIn(b"$49", detail.data)
        self.assertIn(b"$490", detail.data)
        self.assertIn(b"Save $98/year", detail.data)
        for forbidden in (b"Starter", b"Basic plan", b"Professional plan", b"Enterprise"):
            self.assertNotIn(forbidden, detail.data)

    def test_monthly_and_yearly_subscription_plan_selection_is_server_resolved(self):
        monthly = self.client.get(
            "/contact?template=property-operations-command-center&intent=subscribe&plan=monthly"
        )
        self.assertEqual(monthly.status_code, 200)
        self.assertIn("Property Operations Command Center · Monthly plan · $49/month".encode("utf-8"), monthly.data)
        self.assertIn(b'name="source_plan" value="monthly"', monthly.data)
        self.assertIn("Monthly · $49/month".encode("utf-8"), monthly.data)
        self.assertIn(b"$49/month", monthly.data)

        yearly = self.client.get(
            "/contact?template=property-inventory-hub&intent=subscribe&plan=yearly"
        )
        self.assertEqual(yearly.status_code, 200)
        self.assertIn("Property Inventory Hub · Yearly plan · $490/year".encode("utf-8"), yearly.data)
        self.assertIn(b'name="source_plan" value="yearly"', yearly.data)
        self.assertIn("Yearly · $490/year".encode("utf-8"), yearly.data)
        self.assertIn(b"$490/year", yearly.data)

        invalid = self.client.get(
            "/contact?template=property-inventory-hub&intent=subscribe&plan=free"
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertNotIn(b'name="source_plan"', invalid.data)
        self.assertNotIn("Monthly ·".encode("utf-8"), invalid.data)
        self.assertNotIn("Yearly ·".encode("utf-8"), invalid.data)

    def test_subscription_plan_and_price_cannot_be_spoofed_in_inquiry(self):
        from app.inquiries import get_inquiry

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "trusted-plan.sqlite3"
            self.app.config.update(
                CONTACT_DELIVERY_MODE="database",
                DATABASE_URL=f"sqlite:///{db_path}",
                OWNER_INBOX_TOKEN="owner-plan-token",
                SMTP_HOST="",
                SMTP_FROM_EMAIL="",
            )
            self.client.get(
                "/contact?template=property-operations-command-center&intent=subscribe&plan=monthly"
            )
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]

            response = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "source_slug": "property-operations-command-center",
                    "source_intent": "subscribe",
                    "source_plan": "monthly",
                    "source_price": "$1",
                    "source_title": "FAKE SYSTEM",
                    "name": "Pricing Prospect",
                    "email": "pricing@example.com",
                    "company": "Example Properties",
                    "message": "We want the monthly managed system subscription for our operations team.",
                    "website": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            with self.app.app_context():
                item = get_inquiry(1)

            self.assertEqual(item["source_title"], "Property Operations Command Center")
            self.assertEqual(item["source_action"], "System Subscription — Monthly · $49/month")
            self.assertNotIn("$1", item["source_action"])

            headers = {"Authorization": "Bearer owner-plan-token"}
            ticket_response = self.client.post("/__owner_api/session-ticket", headers=headers)
            access_path = urlparse(ticket_response.get_json()["url"]).path
            self.client.get(access_path, follow_redirects=False)
            detail = self.client.get("/owner/inbox/1")
            self.assertIn(b"Request type", detail.data)
            self.assertIn(b"System Subscription", detail.data)
            self.assertIn(b"Plan", detail.data)
            self.assertIn(b"Monthly", detail.data)
            self.assertIn(b"$49/month", detail.data)
            self.assertNotIn(b"$1", detail.data)

    def test_system_detail_has_truthful_status_boundary_and_dual_ctas(self):
        for slug in ("property-operations-command-center", "property-inventory-hub"):
            with self.subTest(slug=slug):
                response = self.client.get(f"/system-templates/{slug}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'aria-label="Breadcrumb"', response.data)
                self.assertIn(b"View Plans", response.data)
                self.assertIn(b"Request Monthly Access", response.data)
                self.assertIn(b"Request Yearly Access", response.data)
                self.assertIn(b"Need something changed?", response.data)
                self.assertIn(b"Request Customization", response.data)
                self.assertIn(b"$49", response.data)
                self.assertIn(b"$490", response.data)
                self.assertIn(b"Save $98/year", response.data)
                self.assertIn(b"sample/demo data", response.data)
                self.assertNotIn(b"Technical details about this build", response.data)
                self.assertNotIn(b"Request the existing system", response.data)
                self.assertNotIn(b"client hired", response.data.lower())
                self.assertNotIn(b"official client", response.data.lower())

    def test_legacy_project_urls_for_published_systems_redirect_to_canonical(self):
        response = self.client.get("/projects/property-inventory-hub", follow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "/system-templates/property-inventory-hub")

    def test_unknown_project_and_page_use_custom_404(self):
        project = self.client.get("/projects/not-real")
        self.assertEqual(project.status_code, 404)
        page = self.client.get("/does-not-exist")
        self.assertEqual(page.status_code, 404)
        self.assertIn(b"The page you requested does not exist", page.data)

    def test_contact_rejects_bad_csrf(self):
        response = self.client.post("/contact", data={"csrf_token": "bad"})
        self.assertEqual(response.status_code, 400)

    def test_contact_validation(self):
        self.client.get("/contact")
        with self.client.session_transaction() as sess:
            token = sess["contact_csrf"]
        response = self.client.post(
            "/contact",
            data={
                "csrf_token": token,
                "name": "K",
                "email": "bad",
                "company": "",
                "message": "short",
                "website": "",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_local_contact_storage_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contact_messages.jsonl"
            self.app.config.update(
                ENABLE_LOCAL_CONTACT_STORAGE=True,
                CONTACT_DELIVERY_MODE="local",
                CONTACT_STORAGE_PATH=str(path),
            )
            self.client.get("/contact")
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]
            response = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "name": "Sample Prospect",
                    "email": "prospect@example.com",
                    "company": "Example Rentals",
                    "message": "We need a property operations system to organize our rental workflow.",
                    "website": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(path.exists())
            self.assertIn("Sample Prospect", path.read_text(encoding="utf-8"))

    def test_database_contact_and_private_online_owner_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "inbox.sqlite3"
            self.app.config.update(
                CONTACT_DELIVERY_MODE="database",
                DATABASE_URL=f"sqlite:///{db_path}",
                OWNER_INBOX_TOKEN="owner-test-token",
                SMTP_HOST="",
                SMTP_FROM_EMAIL="",
            )

            self.client.get("/contact")
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]
            response = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "name": "Real Prospect",
                    "email": "real@example.com",
                    "company": "Rental Ops",
                    "message": "We need a simple system to organize property inquiries and follow-ups.",
                    "website": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(db_path.exists())

            hidden = self.client.get("/owner/inbox")
            self.assertEqual(hidden.status_code, 404)
            self.assertIn("noindex", hidden.headers.get("X-Robots-Tag", ""))

            bad_ticket = self.client.post("/__owner_api/session-ticket")
            self.assertEqual(bad_ticket.status_code, 404)

            headers = {"Authorization": "Bearer owner-test-token"}
            owner_health = self.client.get("/__owner_api/health", headers=headers)
            self.assertEqual(owner_health.status_code, 200)
            self.assertEqual(owner_health.get_json()["counts"]["new"], 1)

            ticket_response = self.client.post("/__owner_api/session-ticket", headers=headers)
            self.assertEqual(ticket_response.status_code, 200)
            access_path = urlparse(ticket_response.get_json()["url"]).path
            access = self.client.get(access_path, follow_redirects=False)
            self.assertEqual(access.status_code, 302)
            self.assertEqual(access.headers["Location"], "/owner/inbox")

            inbox = self.client.get("/owner/inbox")
            self.assertEqual(inbox.status_code, 200)
            self.assertIn(b"Real Prospect", inbox.data)
            self.assertIn(b"KEY CASTRO INBOX", inbox.data)
            self.assertIn("noindex", inbox.headers.get("X-Robots-Tag", ""))

            detail = self.client.get("/owner/inbox/1")
            self.assertEqual(detail.status_code, 200)
            self.assertIn(b"Reply by Email", detail.data)
            with self.client.session_transaction() as sess:
                owner_csrf = sess["key_castro_owner_csrf"]

            updated = self.client.post(
                "/owner/inbox/1/status",
                data={"csrf_token": owner_csrf, "status": "replied"},
                follow_redirects=True,
            )
            self.assertEqual(updated.status_code, 200)
            self.assertIn(b"replied", updated.data.lower())

    def test_sitemap_and_robots_include_two_systems_but_no_nexus_or_owner(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"/system-templates/property-operations-command-center", sitemap.data)
        self.assertIn(b"/system-templates/property-inventory-hub", sitemap.data)
        self.assertIn(b"/system-templates", sitemap.data)
        self.assertNotIn(b"/projects/nexus-properties", sitemap.data)
        self.assertNotIn(b"<loc>http://localhost/projects</loc>", sitemap.data)
        self.assertNotIn(b"/owner/", sitemap.data)
        self.assertNotIn(b"/__owner", sitemap.data)
        self.assertNotIn(b"/skills", sitemap.data)
        self.assertNotIn(b"/experience", sitemap.data)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Disallow: /", robots.data)

    def test_seo_foundation_and_structured_data(self):
        self.app.config.update(
            PUBLIC_BASE_URL="https://keycastro.onrender.com",
            GOOGLE_SITE_VERIFICATION="google-proof",
            BING_SITE_VERIFICATION="bing-proof",
        )
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"<title>Custom Real Estate Systems Developer | Key Castro</title>", home.data)
        self.assertIn(b'rel="canonical" href="https://keycastro.onrender.com/"', home.data)
        self.assertIn(b'name="twitter:card" content="summary_large_image"', home.data)
        self.assertIn(b'name="google-site-verification" content="google-proof"', home.data)
        self.assertIn(b'name="msvalidate.01" content="bing-proof"', home.data)
        self.assertIn(b'"@type": "Person"', home.data)
        self.assertIn(b'"@type": "WebSite"', home.data)

        for slug, expected_title in (
            (
                "property-operations-command-center",
                b"Property Operations Command Center | Key Castro",
            ),
            (
                "property-inventory-hub",
                b"Property Inventory Hub | Key Castro",
            ),
        ):
            case = self.client.get(f"/system-templates/{slug}")
            self.assertEqual(case.status_code, 200)
            self.assertIn(expected_title, case.data)
            self.assertIn(b'"@type": "BreadcrumbList"', case.data)
            self.assertIn(b'"@type": "SoftwareApplication"', case.data)
            self.assertIn(b"og:image:alt", case.data)
            self.assertNotIn(b'"@type": "Review"', case.data)
            self.assertNotIn(b'"aggregateRating"', case.data)

        missing = self.client.get("/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertIn(b'name="robots" content="noindex,nofollow"', missing.data)

    def test_backward_compatible_inquiry_source_action_migration(self):
        from app.inquiries import create_inquiry, get_inquiry

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE contact_inquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    company TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
                """
            )
            conn.commit()
            conn.close()

            self.app.config["DATABASE_URL"] = f"sqlite:///{db_path}"
            with self.app.app_context():
                inquiry_id = create_inquiry(
                    {
                        "name": "Template Prospect",
                        "email": "template@example.com",
                        "company": "Example Property Group",
                        "message": "We want this system adapted for our team.",
                        "source_type": "system_template",
                        "source_slug": "property-inventory-hub",
                        "source_title": "Property Inventory Hub",
                        "source_action": "Paid Customization",
                    }
                )
                item = get_inquiry(inquiry_id)

            self.assertEqual(item["source_type"], "system_template")
            self.assertEqual(item["source_slug"], "property-inventory-hub")
            self.assertEqual(item["source_title"], "Property Inventory Hub")
            self.assertEqual(item["source_action"], "Paid Customization")

    def test_subscription_and_customization_context_flow_without_breaking_generic_contact(self):
        subscription = self.client.get(
            "/contact?template=property-operations-command-center&intent=subscribe"
        )
        self.assertEqual(subscription.status_code, 200)
        self.assertIn(b"Property Operations Command Center", subscription.data)
        self.assertIn(b"System Subscription", subscription.data)
        self.assertIn(b'name="source_slug" value="property-operations-command-center"', subscription.data)
        self.assertIn(b'name="source_intent" value="subscribe"', subscription.data)
        self.assertIn(b"Request Access", subscription.data)

        customize = self.client.get(
            "/contact?template=property-inventory-hub&intent=customize"
        )
        self.assertEqual(customize.status_code, 200)
        self.assertIn(b"Property Inventory Hub", customize.data)
        self.assertIn(b"Paid Customization", customize.data)
        self.assertIn(b'name="source_intent" value="customize"', customize.data)
        self.assertIn(b"Request Customization", customize.data)

        generic = self.client.get("/contact")
        self.assertEqual(generic.status_code, 200)
        self.assertNotIn(b'name="source_slug"', generic.data)
        self.assertNotIn(b'name="source_intent"', generic.data)

    def test_template_contact_submission_records_source_and_request_type_in_private_inbox(self):
        from app.inquiries import get_inquiry

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "template-lead.sqlite3"
            self.app.config.update(
                CONTACT_DELIVERY_MODE="database",
                DATABASE_URL=f"sqlite:///{db_path}",
                OWNER_INBOX_TOKEN="owner-template-token",
                SMTP_HOST="",
                SMTP_FROM_EMAIL="",
            )

            page = self.client.get(
                "/contact?template=property-inventory-hub&intent=subscribe"
            )
            self.assertEqual(page.status_code, 200)
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]

            sent = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "source_slug": "property-inventory-hub",
                    "source_intent": "subscribe",
                    "name": "Template User",
                    "email": "template.user@example.com",
                    "company": "Example Brokerage",
                    "message": "I would like access to the standard template for our internal property inventory.",
                    "website": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(sent.status_code, 302)

            with self.app.app_context():
                item = get_inquiry(1)
            self.assertEqual(item["source_type"], "system_template")
            self.assertEqual(item["source_slug"], "property-inventory-hub")
            self.assertEqual(item["source_title"], "Property Inventory Hub")
            self.assertEqual(item["source_action"], "System Subscription")

            headers = {"Authorization": "Bearer owner-template-token"}
            ticket_response = self.client.post("/__owner_api/session-ticket", headers=headers)
            access_path = urlparse(ticket_response.get_json()["url"]).path
            self.client.get(access_path, follow_redirects=False)
            inbox = self.client.get("/owner/inbox")
            self.assertIn(b"Interested in: Property Inventory Hub", inbox.data)
            self.assertIn(b"Request: System Subscription", inbox.data)
            detail = self.client.get("/owner/inbox/1")
            self.assertIn(b"Request type", detail.data)
            self.assertIn(b"System Subscription", detail.data)

    def test_legacy_free_access_intent_normalizes_to_subscription_without_free_wording(self):
        response = self.client.get(
            "/contact?template=property-inventory-hub&intent=free-access"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"System Subscription", response.data)
        self.assertIn(b'name="source_intent" value="subscribe"', response.data)
        self.assertNotIn(b"Free Template Access", response.data)
        self.assertNotIn(b"Request Free Access", response.data)

    def test_template_source_title_cannot_be_spoofed_by_form(self):
        from app.inquiries import get_inquiry

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "trusted-source.sqlite3"
            self.app.config.update(
                CONTACT_DELIVERY_MODE="database",
                DATABASE_URL=f"sqlite:///{db_path}",
                SMTP_HOST="",
                SMTP_FROM_EMAIL="",
            )
            self.client.get("/contact?template=property-operations-command-center&intent=customize")
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]
            response = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "source_slug": "property-operations-command-center",
                    "source_intent": "customize",
                    "source_title": "FAKE TITLE FROM VISITOR",
                    "name": "Custom Prospect",
                    "email": "custom@example.com",
                    "company": "Example Ops",
                    "message": "We need the workflow adapted with our roles and operational approval process.",
                    "website": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            with self.app.app_context():
                item = get_inquiry(1)
            self.assertEqual(item["source_title"], "Property Operations Command Center")
            self.assertEqual(item["source_action"], "Paid Customization")


if __name__ == "__main__":
    unittest.main()
