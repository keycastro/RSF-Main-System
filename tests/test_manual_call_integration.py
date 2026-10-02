import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManualCallIntegrationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_schema_and_migration_store_manual_calls_separately(self):
        schema = self.read("app/schema.sql")
        db = self.read("app/db.py")
        self.assertIn("CREATE TABLE IF NOT EXISTS manual_client_calls (", schema)
        self.assertIn("recording_bytes BLOB", schema)
        self.assertIn("caption TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("transcript TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("SCHEMA_VERSION = 39", db)
        self.assertIn('rsf-v1.18.179-manual-call-recording', db)
        self.assertIn('"manual_client_calls"', db)

    def test_manual_call_button_exists_on_all_notes_dialogs(self):
        cases = (
            ("app/templates/prospects.html", "data-prospect-manual-call-action"),
            ("app/templates/inquiries.html", "data-website-manual-call-action"),
            ("app/templates/_master_deal_dialogs.html", "data-deal-manual-call-action"),
        )
        for path, attr in cases:
            with self.subTest(path=path):
                template = self.read(path)
                self.assertIn(attr, template)
                self.assertIn("conversation-action--manual-call", template)
                self.assertIn(">Manual Call</span>", template)
                self.assertIn("{% include '_manual_call_panel.html' %}", template)

    def test_manual_call_action_is_controlled_only_by_page_contact_number(self):
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn("Exact button rule: use the Contact Number belonging to the page", routes)
        self.assertIn('manual_phone = (deal["contact_number"] or "").strip()', routes)
        self.assertIn('manual_phone = (inquiry["phone"] or "").strip()', routes)
        self.assertIn('manual_phone = (prospect["phone"] or "").strip()', routes)
        self.assertIn('if manual_phone:', routes)
        self.assertIn('"manual_call_url": manual_call_url', routes)
        self.assertIn("setAction(manualCallAction, data.manual_call_url || '')", js)

    def test_manual_call_panel_can_open_without_provider_but_start_stays_dormant(self):
        routes = self.read("app/routes.py")
        config = self.read("config.py")
        panel = self.read("app/templates/_manual_call_panel.html")
        self.assertIn('"start_ready": start_ready', routes)
        self.assertIn("RSF Manual Call service is not connected yet.", routes)
        for name in (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_FROM_NUMBER",
            "TWILIO_AGENT_NUMBER",
        ):
            self.assertIn(name, config)
        self.assertIn("data-manual-call-start", panel)
        self.assertIn("data-manual-call-consent", panel)

    def test_manual_call_uses_recording_callback_and_protected_audio(self):
        routes = self.read("app/routes.py")
        ops = self.read("app/twilio_manual_call_ops.py")
        self.assertIn('record="record-from-answer-dual"', routes)
        self.assertIn("recordingStatusCallback=", routes)
        self.assertIn('@bp.get("/communications/manual-call/<int:call_id>/recording")', routes)
        self.assertIn("download_recording", routes)
        self.assertIn("Authorization", ops)
        self.assertIn("audio/mpeg", ops)

    def test_manual_call_timeline_order_is_caption_recording_then_collapsed_transcript(self):
        js = self.read("app/static/js/app.js")
        start = js.index("if (channel === 'MANUAL CALL')")
        end = js.index("else if (channel === 'AI SALES CALL')", start)
        block = js[start:end]
        caption = block.index("manual-call-caption")
        recording = block.index("manual-call-recording")
        transcript = block.index("manual-call-transcript")
        self.assertLess(caption, recording)
        self.assertLess(recording, transcript)
        self.assertIn("transcriptToggle.textContent = 'Expand'", block)
        self.assertIn("transcript.open ? 'Collapse' : 'Expand'", block)
        self.assertNotIn("transcript.open = true", block)

    def test_manual_call_timeline_heading_contains_duration(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("meta.textContent = 'MANUAL CALL'", js)
        self.assertIn("· Duration:", js)

    def test_optional_batch_transcription_is_api_ready(self):
        config = self.read("config.py")
        routes = self.read("app/routes.py")
        ops = self.read("app/twilio_manual_call_ops.py")
        self.assertIn("TWILIO_BATCH_TRANSCRIPTION_CONFIGURATION_ID", config)
        self.assertIn("TWILIO_TRANSCRIPTION_WEBHOOK_SECRET", config)
        self.assertIn("https://voice.twilio.com/v3/Transcriptions", ops)
        self.assertIn("sourceId", ops)
        self.assertIn('@bp.post("/webhooks/twilio/manual-call/transcription/<secret>")', routes)
        self.assertIn('transcript_status=\'COMPLETED\'', routes)

    def test_manual_call_history_survives_provisional_deal_merge(self):
        routes = self.read("app/routes.py")
        merge_start = routes.index("def _merge_provisional_deal_into")
        merge_end = routes.index("def _reconcile_deal_sources_on_activation", merge_start)
        merge = routes[merge_start:merge_end]
        self.assertIn("UPDATE manual_client_calls SET deal_id=?", merge)


if __name__ == "__main__":
    unittest.main()
