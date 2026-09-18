import tempfile
import unittest
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
        self.assertEqual(data["version"], "2.3.0")

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


    def test_database_contact_and_private_owner_api(self):
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

            hidden = self.client.get("/__owner_api/inquiries")
            self.assertEqual(hidden.status_code, 404)

            headers = {"Authorization": "Bearer owner-test-token"}
            inbox = self.client.get("/__owner_api/inquiries", headers=headers)
            self.assertEqual(inbox.status_code, 200)
            data = inbox.get_json()
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["items"][0]["status"], "new")

            inquiry_id = data["items"][0]["id"]
            detail = self.client.get(f"/__owner_api/inquiries/{inquiry_id}", headers=headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.get_json()["item"]["status"], "read")

            updated = self.client.post(
                f"/__owner_api/inquiries/{inquiry_id}/status",
                headers=headers,
                json={"status": "replied"},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.get_json()["item"]["status"], "replied")

            self.assertIn("noindex", inbox.headers.get("X-Robots-Tag", ""))

    def test_sitemap_and_robots(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"/projects/nexus-properties", sitemap.data)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Disallow: /", robots.data)


if __name__ == "__main__":
    unittest.main()
