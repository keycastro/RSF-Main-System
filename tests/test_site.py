import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

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

    def test_main_pages_render(self):
        routes = ["/", "/about", "/services", "/projects", "/skills", "/experience", "/contact"]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"KEY CASTRO", response.data)

    def test_nexus_completed_project_has_clear_status_boundary(self):
        response = self.client.get("/projects/nexus-properties")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Nexus Properties", response.data)
        self.assertIn(b"Completed working portfolio implementation", response.data)
        self.assertIn(b"not presented as an official Nexus production deployment", response.data)


    def test_navigation_and_home_hierarchy(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b">Projects</a>", response.data)
        self.assertIn(b">Services</a>", response.data)
        self.assertIn(b">About</a>", response.data)
        self.assertIn(b">Contact</a>", response.data)
        self.assertIn(b"COMPLETED PROJECT", response.data)
        self.assertEqual(response.data.count(b"<h3>Nexus Properties</h3>"), 1)
        public_shell = response.data.lower()
        self.assertNotIn(b"key castro inbox", public_shell)
        self.assertNotIn(b"owner dashboard", public_shell)
        self.assertNotIn(b">admin<", public_shell)

    def test_nexus_case_study_has_breadcrumb_and_simplified_section_nav(self):
        response = self.client.get("/projects/nexus-properties")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'aria-label="Breadcrumb"', response.data)
        self.assertIn(b' href="#overview">Overview</a>', response.data)
        self.assertIn(b' href="#features">Features</a>', response.data)
        self.assertNotIn(b' href="#problem">Problem</a>', response.data)
        self.assertNotIn(b' href="#solution">Solution</a>', response.data)

    def test_unknown_project_uses_custom_404(self):
        response = self.client.get("/projects/not-real")
        self.assertEqual(response.status_code, 404)

    def test_unknown_page_uses_custom_404(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"The page you requested does not exist", response.data)

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
        from urllib.parse import urlparse

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "inbox.sqlite3"
            self.app.config.update(
                CONTACT_DELIVERY_MODE="database",
                DATABASE_URL=f"sqlite:///{db_path}",
                OWNER_INBOX_TOKEN="owner-test-token",
                SMTP_HOST="",
                SMTP_FROM_EMAIL="",
            )

            # Public contact form remains open and stores the inquiry.
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

            # The online owner inbox is not publicly accessible.
            hidden = self.client.get("/owner/inbox")
            self.assertEqual(hidden.status_code, 404)
            self.assertIn("noindex", hidden.headers.get("X-Robots-Tag", ""))

            # The desktop launcher exchanges its private bearer token for a short-lived access ticket.
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

    def test_sitemap_and_robots(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"/projects/nexus-properties", sitemap.data)
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

        case = self.client.get("/projects/nexus-properties")
        self.assertIn(b"Nexus Properties Real Estate System Case Study | Key Castro", case.data)
        self.assertIn(b'"@type": "BreadcrumbList"', case.data)
        self.assertIn(b'og:image:alt', case.data)

        missing = self.client.get("/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertIn(b'name="robots" content="noindex,nofollow"', missing.data)

    def test_template_library_stays_unpublished_until_real_content_exists(self):
        index = self.client.get("/system-templates")
        self.assertEqual(index.status_code, 404)
        detail = self.client.get("/system-templates/property-maintenance-system")
        self.assertEqual(detail.status_code, 404)

        home = self.client.get("/")
        self.assertNotIn(b">System Templates</a>", home.data)
        sitemap = self.client.get("/sitemap.xml")
        self.assertNotIn(b"/system-templates", sitemap.data)

    def test_backward_compatible_inquiry_source_migration(self):
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
                        "message": "We want this property maintenance workflow adapted for our team.",
                        "source_type": "system_template",
                        "source_slug": "property-maintenance-system",
                        "source_title": "Property Maintenance Management System",
                    }
                )
                item = get_inquiry(inquiry_id)

            self.assertEqual(item["source_type"], "system_template")
            self.assertEqual(item["source_slug"], "property-maintenance-system")
            self.assertEqual(item["source_title"], "Property Maintenance Management System")

    def test_template_context_can_flow_to_contact_without_breaking_generic_contact(self):
        from app.system_templates import SystemTemplate

        sample = SystemTemplate(
            slug="property-maintenance-system",
            name="Property Maintenance Management System",
            category="Property Operations",
            short_description="Track maintenance requests from report to completion.",
            full_description="A standard property maintenance workflow for requests, assignments, status, and completion.",
            business_problem="Maintenance work is difficult to coordinate when requests and updates are scattered.",
            target_users=("Property managers",),
            workflow=("Report request", "Assign work", "Track status", "Complete request"),
            features=("Request records", "Assignment", "Status history"),
            technologies=("Flask", "SQL"),
            standard_scope=("Standard request workflow",),
            customization_opportunities=("Custom roles", "Notifications"),
            status="published",
            seo_title="Property Maintenance Management System | Key Castro",
            meta_description="A property maintenance management system template for requests, assignments, status, and completion.",
        )

        with patch("app.routes.get_system_template", return_value=sample):
            response = self.client.get("/contact?template=property-maintenance-system")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Property Maintenance Management System", response.data)
            self.assertIn(b'name="source_slug" value="property-maintenance-system"', response.data)

        generic = self.client.get("/contact")
        self.assertEqual(generic.status_code, 200)
        self.assertNotIn(b'name="source_slug"', generic.data)


if __name__ == "__main__":
    unittest.main()
