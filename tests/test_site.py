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
        self.assertEqual(data["version"], "2.0.0")

    def test_main_pages_render(self):
        routes = ["/", "/about", "/services", "/projects", "/skills", "/experience", "/contact"]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"KEY CASTRO", response.data)

    def test_nexus_case_study_has_clear_status_boundary(self):
        response = self.client.get("/projects/nexus-properties")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Nexus Properties", response.data)
        self.assertIn(b"not presented as an official deployed Nexus system", response.data)

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

    def test_sitemap_and_robots(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b"/projects/nexus-properties", sitemap.data)
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Disallow: /", robots.data)


if __name__ == "__main__":
    unittest.main()
