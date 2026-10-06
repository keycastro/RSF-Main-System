import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommunicationProviderLabelTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_final_button_provider_mapping(self):
        templates = "\n".join([
            self.read("app/templates/prospects.html"),
            self.read("app/templates/inquiries.html"),
            self.read("app/templates/_master_deal_dialogs.html"),
        ])
        for label, provider in (
            ("AI Call", "Retell AI"),
            ("Manual Call", "Twilio"),
            ("Google Meet", "Google Meet"),
            ("Email", "Gmail"),
            ("WhatsApp", "WhatsApp Business"),
        ):
            self.assertIn(f'<span class="conversation-action-label">{label}</span>', templates)
            self.assertIn(f'<small class="conversation-action-provider">{provider}</small>', templates)

    def test_provider_text_is_visually_secondary(self):
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn(".conversation-action-provider{", css)
        self.assertIn("font-size:8px", css)
        self.assertIn("font-weight:600", css)
        self.assertIn("opacity:.52", css)
        self.assertIn(".conversation-action-copy{", css)

    def test_prospect_timeline_uses_correct_action_argument_order(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("const prospectCallAction = page.querySelector('[data-prospect-call-action]');", js)
        self.assertIn(
            "prospectConversationTimeline,\n      prospectCallAction,\n      prospectEmailAction,\n      prospectTimelineOptions",
            js,
        )
        self.assertIn("[data-prospect-call-action]", js)

    def test_retell_signed_webhook_is_csrf_exempt_but_browser_actions_are_not(self):
        init = self.read("app/__init__.py")
        routes = self.read("app/routes.py")
        self.assertIn('"main.retell_webhook"', init)
        self.assertIn('@bp.post("/integrations/retell/webhook")', routes)
        self.assertIn("X-Retell-Signature", routes)
        self.assertIn('@bp.post("/prospects/<int:prospect_id>/ai-call")', routes)
        self.assertIn("validate_csrf()", routes)

    def test_release_version(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.230")


if __name__ == "__main__":
    unittest.main()
