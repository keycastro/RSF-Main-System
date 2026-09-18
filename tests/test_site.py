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

    def test_main_pages_and_template_library_render(self):
        routes = [
            "/",
            "/about",
            "/services",
            "/skills",
            "/experience",
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
        self.assertIn(b"Work items with priority", pocc.data)
        self.assertNotIn(b"Freshness engine with reconfirmation", pocc.data)
        self.assertIn(b"Freshness engine with reconfirmation", pih.data)
        self.assertNotIn(b"Owner approval requests", pih.data)

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
        self.assertIn(b"SYSTEMS BUILT BY KEY CASTRO", response.data)
        self.assertIn(b"View Systems", response.data)
        self.assertIn(b"Discuss a Custom System", response.data)
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
        self.assertIn(b"Completed systems for", systems.data)
        self.assertNotIn(b"Free access by request</strong>", systems.data)

        # Skills and Experience remain useful secondary pages, but not primary navigation items.
        header = home.data.split(b"</header>", 1)[0]
        self.assertNotIn(b">Skills & technology</a>", header)
        self.assertNotIn(b">Experience</a>", header)
        self.assertIn(b"Skills & technology", about.data)
        self.assertIn(b"Experience", about.data)

        # Services is about paid work, not another copy of the systems catalog.
        self.assertIn(b"Paid development", services.data)
        self.assertIn(b"Custom System Development", services.data)
        self.assertIn(b"Customize an Existing KEY CASTRO System", services.data)

    def test_system_detail_has_truthful_status_boundary_and_dual_ctas(self):
        for slug in ("property-operations-command-center", "property-inventory-hub"):
            with self.subTest(slug=slug):
                response = self.client.get(f"/system-templates/{slug}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'aria-label="Breadcrumb"', response.data)
                self.assertIn(b"FREE STANDARD SYSTEM", response.data)
                self.assertIn(b"Request Free Template Access", response.data)
                self.assertIn(b"Customize This System", response.data)
                self.assertEqual(response.data.count(b"Request Free Template Access"), 2)
                self.assertEqual(response.data.count(b"Customize This System"), 2)
                self.assertIn(b"sample/demo data", response.data)
                self.assertIn(b"Technical details about this build", response.data)
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
                b"Property Operations Command Center Template | Key Castro",
            ),
            (
                "property-inventory-hub",
                b"Property Inventory Hub Free Real Estate Template | Key Castro",
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
                        "source_action": "Custom System / Customization",
                    }
                )
                item = get_inquiry(inquiry_id)

            self.assertEqual(item["source_type"], "system_template")
            self.assertEqual(item["source_slug"], "property-inventory-hub")
            self.assertEqual(item["source_title"], "Property Inventory Hub")
            self.assertEqual(item["source_action"], "Custom System / Customization")

    def test_free_access_and_customization_context_flow_without_breaking_generic_contact(self):
        free_access = self.client.get(
            "/contact?template=property-operations-command-center&intent=free-access"
        )
        self.assertEqual(free_access.status_code, 200)
        self.assertIn(b"Property Operations Command Center", free_access.data)
        self.assertIn(b"Free Template Access", free_access.data)
        self.assertIn(b'name="source_slug" value="property-operations-command-center"', free_access.data)
        self.assertIn(b'name="source_intent" value="free-access"', free_access.data)
        self.assertIn(b"Request Free Template Access", free_access.data)

        customize = self.client.get(
            "/contact?template=property-inventory-hub&intent=customize"
        )
        self.assertEqual(customize.status_code, 200)
        self.assertIn(b"Property Inventory Hub", customize.data)
        self.assertIn(b"Custom System / Customization", customize.data)
        self.assertIn(b'name="source_intent" value="customize"', customize.data)
        self.assertIn(b"Send Customization Request", customize.data)

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
                "/contact?template=property-inventory-hub&intent=free-access"
            )
            self.assertEqual(page.status_code, 200)
            with self.client.session_transaction() as sess:
                token = sess["contact_csrf"]

            sent = self.client.post(
                "/contact",
                data={
                    "csrf_token": token,
                    "source_slug": "property-inventory-hub",
                    "source_intent": "free-access",
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
            self.assertEqual(item["source_action"], "Free Template Access")

            headers = {"Authorization": "Bearer owner-template-token"}
            ticket_response = self.client.post("/__owner_api/session-ticket", headers=headers)
            access_path = urlparse(ticket_response.get_json()["url"]).path
            self.client.get(access_path, follow_redirects=False)
            inbox = self.client.get("/owner/inbox")
            self.assertIn(b"Interested in: Property Inventory Hub", inbox.data)
            self.assertIn(b"Request: Free Template Access", inbox.data)
            detail = self.client.get("/owner/inbox/1")
            self.assertIn(b"Request type", detail.data)
            self.assertIn(b"Free Template Access", detail.data)

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
            self.assertEqual(item["source_action"], "Custom System / Customization")


if __name__ == "__main__":
    unittest.main()
