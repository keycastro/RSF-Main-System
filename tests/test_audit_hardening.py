import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.auth import valid_password
from app.db import get_db

ROOT = Path(__file__).resolve().parents[1]


class AuditHardeningTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "hardening-test-secret",
            "DATABASE_URL": "",
            "DATABASE": str(root / "hardening.db"),
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

    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_external_provider_webhooks_are_not_blocked_by_browser_csrf(self):
        whatsapp = self.client.post("/app/webhooks/whatsapp", data=b"{}")
        self.assertEqual(whatsapp.status_code, 503)

        twilio = self.client.post("/app/webhooks/twilio/manual-call/not-a-real-token/twiml")
        self.assertEqual(twilio.status_code, 404)

        transcription = self.client.post(
            "/app/webhooks/twilio/manual-call/transcription/not-a-real-secret",
            json={},
        )
        self.assertEqual(transcription.status_code, 403)

    def test_retell_active_call_surface_is_removed(self):
        routes = self.read("app/routes.py")
        config = self.read("config.py")
        requirements = self.read("requirements.txt")
        prospects = self.read("app/templates/prospects.html")
        inquiries = self.read("app/templates/inquiries.html")
        js = self.read("app/static/js/app.js")
        for text in (routes, config, requirements, prospects, inquiries, js):
            self.assertNotIn("RETELL_", text)
            self.assertNotIn("retell-sdk", text)
            self.assertNotIn("prospect_ai_call", text)
            self.assertNotIn("AI Call", text)
        self.assertEqual(self.client.post("/app/integrations/retell/webhook").status_code, 404)

    def test_historical_ai_call_storage_is_preserved_read_only(self):
        schema = self.read("app/schema.sql")
        routes = self.read("app/routes.py")
        self.assertIn("CREATE TABLE IF NOT EXISTS ai_sales_calls", schema)
        self.assertIn("FROM ai_sales_calls", routes)
        self.assertNotIn("INSERT INTO ai_sales_calls", routes)
        self.assertNotIn("UPDATE ai_sales_calls", routes)

    def test_passwords_are_hash_only_and_new_passwords_need_12_characters(self):
        self.assertFalse(valid_password("short"))
        self.assertTrue(valid_password("twelve-chars!"))
        schema = self.read("app/schema.sql")
        routes = self.read("app/routes.py")
        template = self.read("app/templates/account_security.html")
        self.assertNotIn("account_password_vault", schema)
        self.assertNotIn("reveal-password", routes)
        self.assertNotIn("Current Password", template)
        self.assertIn('minlength="12"', template)
        with self.app.app_context():
            db = get_db()
            table = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='account_password_vault'"
            ).fetchone()
            self.assertIsNone(table)

    def test_retired_existing_system_price_source_is_removed(self):
        source = self.read("app/system_templates.py")
        public_routes = self.read("app/public_routes.py")
        for text in (source, public_routes):
            self.assertNotIn("EXISTING_SYSTEM_PRICING", text)
            self.assertNotIn("one_time_price", text)

    def test_release_version(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.229")


if __name__ == "__main__":
    unittest.main()
