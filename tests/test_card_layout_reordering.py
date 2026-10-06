import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CardLayoutReorderingTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_four_workspace_pages_have_independent_layout_roots(self):
        prospects = self.read("app/templates/prospects.html")
        inquiries = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")
        support = self.read("app/templates/support_maintenance.html")
        self.assertIn('data-card-layout-page="prospects"', prospects)
        self.assertIn('data-card-layout-page="inquiries"', inquiries)
        self.assertIn('data-card-layout-page="deals"', deals)
        self.assertIn('data-card-layout-page="support_maintenance"', support)
        for template in (prospects, inquiries, deals, support):
            self.assertIn("data-card-layout-save-url", template)
            self.assertIn("data-card-layout-state", template)

    def test_shared_deal_fields_keep_one_data_source_while_becoming_reorderable(self):
        master = self.read("app/templates/_master_deal_information.html")
        city = self.read("app/templates/_master_deal_city_country.html")
        for key in (
            "followup_date", "email", "price", "developer", "contact_number", "whatsapp_number", "demo_schedule",
            "next_step", "notes_after_conversation", "google_meet", "email_conversation",
        ):
            self.assertIn(f'data-card-layout-field="{key}"', master)
        self.assertIn('data-card-layout-field="city_country"', city)
        self.assertIn('form="{{ form_id }}"', master)
        self.assertIn('data-card-layout-zone="{{ deal_layout_zone }}"', master)

    def test_page_specific_source_fields_are_reorderable(self):
        prospect = self.read("app/templates/_prospect_row.html")
        inquiry = self.read("app/templates/inquiries.html")
        deals = self.read("app/templates/deals.html")
        self.assertIn('data-card-layout-zone="summary"', prospect)
        self.assertIn('data-card-layout-zone="source"', prospect)
        self.assertIn("{% set deal_layout_zone = 'other' %}", prospect)
        self.assertIn('data-card-layout-zone="source"', inquiry)
        self.assertIn("{% set deal_layout_zone = 'deal' %}", inquiry)
        self.assertIn('data-card-layout-zone="outbound"', deals)
        self.assertIn('data-card-layout-zone="inbound"', deals)

    def test_ctrl_drag_applies_to_all_cards_and_persists_server_side(self):
        js = self.read("app/static/js/app.js")
        routes = self.read("app/routes.py")
        self.assertIn("event.ctrlKey", js)
        self.assertIn("applyAll({animate: true", js)
        self.assertIn("layout_json: payloadJson", js)
        self.assertIn("MutationObserver", js)
        self.assertIn('@bp.post("/card-layout/<page_name>")', routes)
        self.assertIn("CARD_LAYOUT_SPECS", routes)
        self.assertIn('"support_maintenance": {', routes)
        self.assertIn('return f"card_layout_{page_name}_v1"', routes)

    def test_smooth_engine_is_pointer_driven_not_native_html_drag(self):
        js = self.read("app/static/js/app.js")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("window.addEventListener('pointermove'", smooth)
        self.assertIn("window.addEventListener('pointerup'", smooth)
        self.assertIn("requestAnimationFrame", smooth)
        self.assertIn("createGhost", smooth)
        self.assertIn("createPlaceholder", smooth)
        self.assertIn("animateReflow", smooth)
        self.assertIn("zoneAtPoint", smooth)
        self.assertIn("autoScrollSpeed", smooth)
        self.assertIn("distance < 6", smooth)
        self.assertNotIn("field.draggable = true", smooth)
        self.assertNotIn("root.addEventListener('dragover'", smooth)
        self.assertNotIn("root.addEventListener('drop'", smooth)

    def test_smooth_engine_prevents_accidental_activation_and_supports_cancel(self):
        js = self.read("app/static/js/app.js")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("event.pointerType !== 'mouse'", smooth)
        self.assertIn("event.preventDefault()", smooth)
        self.assertIn("event.stopPropagation()", smooth)
        self.assertIn("window.getSelection?.()?.removeAllRanges?.()", smooth)
        self.assertIn("event.key === 'Escape'", smooth)
        self.assertIn("window.addEventListener('blur'", smooth)
        self.assertIn("card-layout-dragging-global", smooth)

    def test_smooth_engine_has_stable_insertion_feedback_and_reflow_animation(self):
        js = self.read("app/static/js/app.js")
        css = self.read("app/static/css/workspace_v20.css")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("placementSignature", smooth)
        self.assertIn("rectDistance", smooth)
        self.assertIn("visibleZonesForCard", smooth)
        self.assertIn("is-card-layout-drop-zone", smooth)
        self.assertIn("card-layout-placeholder", css)
        self.assertIn("card-layout-drag-ghost", css)
        self.assertIn("will-change:transform", css)

    def test_reordered_fields_track_origin_and_destination_zones(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("const syncAdaptiveFieldZones", js)
        self.assertIn("field.dataset.cardLayoutOriginZone", js)
        self.assertIn("field.dataset.cardLayoutCurrentZone", js)
        self.assertIn("card-layout-field-relocated", js)
        self.assertIn("syncAdaptiveFieldZones(completed.card)", js)

    def test_header_destination_has_adaptive_formatting_on_all_three_pages(self):
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn('[data-card-layout-current-zone="header"]>input', css)
        self.assertIn('.deals-page [data-card-layout-zone="header"]', css)
        self.assertIn('.prospects-page [data-card-layout-zone="header"]', css)
        self.assertIn('.website-inbox-page [data-card-layout-zone="header"]', css)
        self.assertIn('font-size:12.5px!important', css)
        self.assertIn('background:transparent!important', css)

    def test_reverse_adaptation_restores_body_field_format(self):
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn('label[data-card-layout-current-zone]:not([data-card-layout-current-zone="header"])>input', css)
        self.assertIn('border:1px solid #d7e1dd!important', css)
        self.assertIn('border-radius:8px!important', css)
        self.assertIn('background:#fff!important', css)

    def test_prospect_whatsapp_reuses_native_contact_number_display_and_editor_pattern(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        js = self.read("app/static/js/app.js")
        css = self.read("app/static/css/workspace_v20.css")

        self.assertIn("{% set deal_use_prospect_native_whatsapp = true %}", prospect)
        self.assertIn('data-prospect-shared-deal-field="whatsapp_number"', master)
        self.assertIn('data-prospect-editor="tel"', master)
        self.assertIn('class="prospect-edit-value"', master)
        self.assertIn('data-prospect-edit-trigger', master)
        self.assertIn('data-prospect-shared-deal-input', master)

        self.assertIn("field.classList.toggle('prospect-detail', useProspectNative)", js)
        self.assertIn("field.classList.toggle('prospect-editable-field', useProspectNative)", js)
        self.assertIn("const sharedDealFieldName = field.dataset.prospectSharedDealField", js)
        self.assertIn("editor.className = 'prospect-inline-editor'", js)
        self.assertIn("window.RSFSaveDealFormInBackground", js)

        self.assertNotIn('label.card-layout-field-relocated[data-card-layout-current-zone="source"][data-card-layout-field]', css)
        self.assertIn('.prospects-page .prospect-detail{', css)
        self.assertIn('.prospects-page .prospect-detail>.prospect-edit-value', css)

    def test_visual_moves_preserve_existing_save_ownership(self):
        js = self.read("app/static/js/app.js")
        self.assertIn("const researchSectionFor", js)
        self.assertIn("researchSectionFor(field)", js)
        self.assertIn("researchSectionFor(dealResearchLongTextSource)", js)
        self.assertIn("researchSectionFor(button)", js)
        self.assertIn("dealFormForField(notesSource)", js)

    def test_reorder_engine_serializes_fast_layout_saves(self):
        js = self.read("app/static/js/app.js")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("let persistQueue = Promise.resolve()", smooth)
        self.assertIn("persistRequestedVersion", smooth)
        self.assertIn("lastPersistedState", smooth)
        self.assertIn("persistQueue = persistQueue.then", smooth)
        self.assertIn("requestVersion === persistRequestedVersion", smooth)

    def test_drop_uses_final_pointer_position_and_zone_hysteresis(self):
        js = self.read("app/static/js/app.js")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("const rectContainsWithPadding", smooth)
        self.assertIn("drag?.highlightedZone", smooth)
        self.assertIn("updateDragPlacement()", smooth)
        self.assertIn("drag.x = event.clientX", smooth)
        self.assertIn("drag.y = event.clientY", smooth)

    def test_collapsed_sections_auto_expand_during_drag(self):
        js = self.read("app/static/js/app.js")
        css = self.read("app/static/css/workspace_v20.css")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("const collapsedZoneAtPoint", smooth)
        self.assertIn("const armAutoExpand", smooth)
        self.assertIn("aria-expanded", smooth)
        self.assertIn("360", smooth)
        self.assertIn("is-card-layout-expand-target", css)

    def test_placeholder_adapts_to_destination_field_size(self):
        js = self.read("app/static/js/app.js")
        css = self.read("app/static/css/workspace_v20.css")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("syncPlaceholderToZone", smooth)
        self.assertIn("cardLayoutCurrentZone", smooth)
        self.assertIn("--card-layout-placeholder-height", smooth)
        self.assertIn("--card-layout-placeholder-height", css)

    def test_insertion_feedback_has_micro_jitter_guard(self):
        js = self.read("app/static/js/app.js")
        smooth = js[js.index("/* v1.18.151 — smooth pointer-driven"):]
        self.assertIn("pointerTravel", smooth)
        self.assertIn("pointerTravel < 4", smooth)
        self.assertIn("lastPlacementX", smooth)
        self.assertIn("lastPlacementY", smooth)


if __name__ == "__main__":
    unittest.main()
