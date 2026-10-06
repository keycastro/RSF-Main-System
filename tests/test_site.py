import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db


class CurrentPublicSiteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "current-site-test-secret",
            "DATABASE_URL": "",
            "DATABASE": str(root / "site.db"),
            "MESSAGE_UPLOAD_DIR": str(root / "message_uploads"),
            "PROFILE_PICTURE_DIR": str(root / "profile_pictures"),
            "CLIENT_ATTACHMENT_DIR": str(root / "client_attachments"),
            "BACKUP_DIR": str(root / "backups"),
            "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
            "SESSION_COOKIE_SECURE": False,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def test_health_matches_release(self):
        response = self.client.get("/system/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "1.18.230")

    def test_public_routes_load(self):
        for path in ("/", "/system-templates", "/services", "/about", "/contact"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_three_portfolio_systems_remain_separate(self):
        index = self.client.get("/system-templates")
        self.assertEqual(index.data.count(b"data-system-card"), 3)
        for slug in (
            "property-operations-command-center",
            "property-inventory-hub",
            "student-housing-matching-and-placement-system",
        ):
            with self.subTest(slug=slug):
                detail = self.client.get(f"/system-templates/{slug}")
                self.assertEqual(detail.status_code, 200)
                self.assertIn(b"Request a Custom System", detail.data)

    def test_current_business_model_is_custom_build_only(self):
        services = self.client.get("/services")
        body = services.data
        self.assertIn(b"LIMITED FREE BUILD PROGRAM", body)
        self.assertIn(b"$0 Development Fee", body)
        self.assertIn(b"November 1, 2026", body)
        self.assertIn(b"March 31, 2027", body)
        self.assertIn(b"Paid RSF support is optional.", body)
        self.assertIn(b"Price by Agreement", body)
        self.assertIn(b"Major changes are priced separately.", body)
        self.assertNotIn(b"$199", body)
        self.assertNotIn(b"$79", body)
        self.assertNotIn(b"$149", body)
        self.assertIn(b"Does RSF sell ready-made systems?", body)
        self.assertIn(b"No. The systems shown on this website are examples", body)

    def test_portfolio_pages_do_not_sell_ready_made_systems(self):
        for path in (
            "/",
            "/system-templates",
            "/system-templates/property-operations-command-center",
            "/system-templates/property-inventory-hub",
            "/system-templates/student-housing-matching-and-placement-system",
        ):
            with self.subTest(path=path):
                body = self.client.get(path).data
                self.assertNotIn(b"$199", body)
                self.assertNotIn(b"Get This System", body)
                self.assertIn(b"Request a Custom System", body)

    def test_legacy_existing_system_intent_normalizes_to_custom_build(self):
        page = self.client.get(
            "/contact?template=property-inventory-hub&intent=existing-system"
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Property Inventory Hub", page.data)
        self.assertIn(b'name="source_intent" value="custom-build"', page.data)
        self.assertNotIn(b"Existing System Purchase", page.data)

    def test_legacy_subscription_intents_do_not_restore_old_pricing(self):
        for intent in ("managed", "subscribe", "free-access"):
            with self.subTest(intent=intent):
                page = self.client.get(
                    f"/contact?template=property-operations-command-center&intent={intent}&plan=monthly&price=$1"
                )
                self.assertEqual(page.status_code, 200)
                self.assertNotIn(b"$39", page.data)
                self.assertNotIn(b"$390", page.data)
                self.assertNotIn(b'name="source_price"', page.data)
                self.assertNotIn(b'name="source_plan"', page.data)

    def test_contact_csrf_is_required(self):
        response = self.client.post("/contact", data={"csrf_token": "bad"})
        self.assertEqual(response.status_code, 400)

    def test_contact_request_is_stored_in_workspace_database(self):
        page = self.client.get("/contact?intent=custom-build")
        self.assertEqual(page.status_code, 200)
        with self.client.session_transaction() as sess:
            token = sess["contact_csrf"]
        sent = self.client.post(
            "/contact",
            data={
                "csrf_token": token,
                "source_intent": "custom-build",
                "name": "Audit Prospect",
                "email": "audit@example.test",
                "phone": "+63 912 345 6789",
                "company": "Audit Property Group",
                "message": "We need a custom property operations system for our team.",
                "website": "",
            },
            follow_redirects=False,
        )
        self.assertIn(sent.status_code, (302, 303))
        with self.app.app_context():
            db = get_db()
            row = db.execute(
                "SELECT name,email,company,message FROM website_inquiries ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Audit Prospect")
            self.assertEqual(row["email"], "audit@example.test")

    def test_public_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers.get("Content-Security-Policy", ""))

    def test_private_workspace_requires_login(self):
        response = self.client.get("/app/", follow_redirects=False)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertIn("/app/login", response.headers.get("Location", ""))

    def test_unknown_public_path_returns_404(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
