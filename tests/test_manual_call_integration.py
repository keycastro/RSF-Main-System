import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ManualCallIntegrationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_schema_and_migration_store_manual_calls_and_live_control_state(self):
        schema=self.read("app/schema.sql"); db=self.read("app/db.py")
        self.assertIn("provider_client_call_sid TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("conference_sid TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("agent_muted INTEGER NOT NULL DEFAULT 0", schema)
        self.assertIn("client_held INTEGER NOT NULL DEFAULT 0", schema)
        self.assertIn("SCHEMA_VERSION = 41", db)
        self.assertIn("rsf-v1.18.180-manual-call-live-controls", db)

    def test_manual_call_button_exists_on_all_notes_dialogs(self):
        for path,attr in (
            ("app/templates/prospects.html","data-prospect-manual-call-action"),
            ("app/templates/inquiries.html","data-website-manual-call-action"),
            ("app/templates/_master_deal_dialogs.html","data-deal-manual-call-action"),
        ):
            with self.subTest(path=path):
                template=self.read(path)
                self.assertIn(attr,template)
                self.assertIn("conversation-action--manual-call",template)
                self.assertIn("{% include '_manual_call_panel.html' %}",template)

    def test_click_starts_immediately_without_setup_form(self):
        panel=self.read("app/templates/_manual_call_panel.html")
        js=self.read("app/static/js/app.js")
        routes=self.read("app/routes.py")
        self.assertNotIn("data-manual-call-form",panel)
        self.assertNotIn("data-manual-call-start",panel)
        self.assertNotIn("data-manual-call-consent",panel)
        self.assertNotIn("Ready to call",panel)
        self.assertIn("await start(panel)",js)
        self.assertNotIn("recording_consent",routes)

    def test_live_ui_shows_only_real_supported_controls(self):
        panel=self.read("app/templates/_manual_call_panel.html")
        routes=self.read("app/routes.py")
        self.assertIn("data-manual-call-mute",panel)
        self.assertIn("data-manual-call-hold",panel)
        self.assertIn("data-manual-call-end",panel)
        self.assertNotIn("Keypad",panel)
        self.assertNotIn("Speaker",panel)
        self.assertNotIn("Add Call",panel)
        self.assertIn('"mute": bool(in_progress and conference_sid and agent_sid)',routes)
        self.assertIn('"hold": bool(in_progress and conference_sid and client_sid)',routes)
        self.assertIn('"end": bool(not terminal',routes)

    def test_provider_uses_real_twilio_conference_controls(self):
        routes=self.read("app/routes.py")
        ops=self.read("app/twilio_manual_call_ops.py")
        self.assertIn("<Conference",routes)
        self.assertIn('statusCallbackEvent="start end join leave mute hold"',routes)
        self.assertIn("update_conference_participant",routes)
        self.assertIn('("Muted", "true" if muted else "false")',ops)
        self.assertIn('("Hold", "true" if hold else "false")',ops)
        self.assertIn('("Status", "completed")',ops)

    def test_recording_and_collapsed_transcript_are_preserved(self):
        routes=self.read("app/routes.py")
        ops=self.read("app/twilio_manual_call_ops.py")
        js=self.read("app/static/js/app.js")
        self.assertIn('("Record", "true")',ops)
        self.assertIn("RecordingStatusCallback",ops)
        self.assertIn('@bp.get("/communications/manual-call/<int:call_id>/recording")',routes)
        self.assertIn("manual-call-transcript",js)
        self.assertIn("transcriptToggle.textContent = 'Expand'",js)
        self.assertIn("transcript.open ? 'Collapse' : 'Expand'",js)

    def test_premium_rsf_live_call_visuals_exist(self):
        css=self.read("app/static/css/workspace_v20.css")
        self.assertIn("radial-gradient(",css)
        self.assertIn("backdrop-filter:blur(",css)
        self.assertIn("@keyframes manual-call-breathe",css)
        self.assertIn("conversation-manual-call-end",css)

    def test_history_survives_provisional_deal_merge(self):
        routes=self.read("app/routes.py")
        a=routes.index("def _merge_provisional_deal_into")
        b=routes.index("def _reconcile_deal_sources_on_activation",a)
        self.assertIn("UPDATE manual_client_calls SET deal_id=?",routes[a:b])

if __name__=="__main__":
    unittest.main()
