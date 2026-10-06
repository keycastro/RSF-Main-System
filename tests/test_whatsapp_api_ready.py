import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WhatsAppApiReadyTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_whatsapp_storage_is_separate_from_email_channel_constraint(self):
        schema = self.read("app/schema.sql")
        db = self.read("app/db.py")
        self.assertIn("CREATE TABLE IF NOT EXISTS whatsapp_messages (", schema)
        self.assertIn("channel TEXT NOT NULL CHECK (channel IN ('WEBSITE','EMAIL'))", schema)
        self.assertIn("SCHEMA_VERSION = 43", db)
        self.assertIn('rsf-v1.18.178-whatsapp-api-ready', db)
        self.assertIn('"whatsapp_messages"', db)

    def test_api_credentials_are_environment_only_and_dormant_by_default(self):
        config = self.read("config.py")
        ops = self.read("app/whatsapp_ops.py")
        for name in (
            "WHATSAPP_GRAPH_API_VERSION",
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_WABA_ID",
            "WHATSAPP_VERIFY_TOKEN",
            "WHATSAPP_APP_SECRET",
        ):
            with self.subTest(name=name):
                self.assertIn(name, config)
        self.assertIn("def whatsapp_messaging_configured()", ops)
        self.assertIn("WhatsApp API is not connected yet.", ops)

    def test_number_controls_whatsapp_action_url(self):
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn('whatsapp_number = (whatsapp_deal["whatsapp_number"] or "").strip()', routes)
        self.assertIn("if whatsapp_number:", routes)
        self.assertIn('"whatsapp_url": whatsapp_url', routes)
        self.assertIn("setAction(whatsappAction, data.whatsapp_url || '')", js)

    def test_whatsapp_thread_send_media_and_webhook_routes_exist(self):
        routes = self.read("app/routes.py")
        for route in (
            '@bp.get("/communications/whatsapp-thread")',
            '@bp.post("/communications/whatsapp-send")',
            '@bp.get("/communications/whatsapp-media/<int:message_id>")',
            '@bp.get("/webhooks/whatsapp")',
            '@bp.post("/webhooks/whatsapp")',
        ):
            with self.subTest(route=route):
                self.assertIn(route, routes)
        self.assertIn("upload_media(", routes)
        self.assertIn("send_media(", routes)
        self.assertIn("verify_webhook_signature(", routes)

    def test_all_notes_dialogs_have_whatsapp_action_and_panel(self):
        for path, action in (
            ("app/templates/prospects.html", "data-prospect-whatsapp-action"),
            ("app/templates/inquiries.html", "data-website-whatsapp-action"),
            ("app/templates/_master_deal_dialogs.html", "data-deal-whatsapp-action"),
        ):
            with self.subTest(path=path):
                template = self.read(path)
                self.assertIn(action, template)
                self.assertIn("{% include '_whatsapp_conversation_panel.html' %}", template)
        panel = self.read("app/templates/_whatsapp_conversation_panel.html")
        self.assertIn("WhatsApp Conversation", panel)
        self.assertIn("data-whatsapp-call", panel)
        self.assertIn("data-whatsapp-media", panel)
        self.assertIn("data-whatsapp-send", panel)

    def test_whatsapp_history_survives_provisional_deal_merge_and_timeline(self):
        routes = self.read("app/routes.py")
        merge_start = routes.index("def _merge_provisional_deal_into")
        merge_end = routes.index("def _reconcile_deal_sources_on_activation", merge_start)
        merge = routes[merge_start:merge_end]
        self.assertIn("UPDATE whatsapp_messages SET deal_id=?", merge)
        self.assertIn('"channel": "WHATSAPP"', routes)
        js = self.read("app/static/js/app.js")
        self.assertIn("WHATSAPP RECEIVED", js)
        self.assertIn("WHATSAPP SENT", js)

    def test_call_control_is_present_but_not_falsely_enabled(self):
        routes = self.read("app/routes.py")
        panel = self.read("app/templates/_whatsapp_conversation_panel.html")
        self.assertIn('"call_ready": False', routes)
        self.assertIn("WhatsApp Calling is not connected yet.", routes)
        self.assertIn("data-whatsapp-call disabled", panel)


if __name__ == "__main__":
    unittest.main()
