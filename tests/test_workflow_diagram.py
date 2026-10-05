import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowDiagramTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_legacy_route_redirects_to_settings_workflow(self):
        routes = self.read("app/routes.py")
        self.assertIn('@bp.get("/workflow-diagram")', routes)
        self.assertIn("def workflow_diagram():", routes)
        self.assertIn('url_for("main.settings", section="workflow")', routes)

    def test_settings_route_builds_workflow_from_canonical_status_sets(self):
        routes = self.read("app/routes.py")
        self.assertIn('section == "workflow"', routes)
        self.assertIn("build_workflow_diagram(", routes)
        self.assertIn("PROSPECT_STATUS_LABELS", routes)
        self.assertIn("DEAL_PRE_STATUS_STATUSES", routes)
        self.assertIn("DEAL_ACTIVE_STATUSES", routes)

    def test_normal_sidebar_no_longer_exposes_system_map(self):
        base = self.read("app/templates/base.html")
        self.assertNotIn("SYSTEM MAP", base)
        self.assertNotIn("workflow_active", base)
        self.assertIn("data-settings-entry", base)
        self.assertIn("settings-footer-link", base)

    def test_dedicated_settings_navigation_contains_real_sections(self):
        template = self.read("app/templates/_settings_navigation.html")
        for label in ("General", "Appearance", "Account", "Workflow Diagram", "Integrations"):
            self.assertIn(label, template)

    def test_dedicated_settings_hides_operational_sidebar(self):
        css = self.read("app/static/css/settings_experience.css")
        self.assertIn("body.page-settings-dedicated .sidebar{display:none!important}", css)
        self.assertIn("body.page-settings-dedicated .workspace-visual-panel", css)

    def test_back_and_escape_restore_previous_operational_page_safely(self):
        js = self.read("app/static/js/settings_experience.js")
        app_js = self.read("app/static/js/app.js")
        self.assertIn("rsf.settings.returnTo", js)
        self.assertIn("event.key !== 'Escape'", js)
        self.assertIn("input, textarea, select", js)
        self.assertIn("dialog[open]", js)
        self.assertIn("data-settings-entry", app_js)

    def test_account_password_success_returns_to_dedicated_settings_route(self):
        routes = self.read("app/routes.py")
        self.assertIn('return redirect(url_for("main.account_security"))', routes)

    def test_diagram_contains_required_architecture_areas(self):
        workflow = self.read("app/workflow_diagram.py")
        for label in (
            "Lead Sources",
            "Client Intake",
            "Pre-Deal",
            "Active Deal Pipeline",
            "Won / Lost",
            "Support & Maintenance",
            "Communication / Actions",
            "Database Relationships",
        ):
            self.assertIn(label, workflow)

    def test_diagram_is_read_only_and_interactive(self):
        template = self.read("app/templates/workflow_diagram.html")
        js = self.read("app/static/js/workflow_diagram.js")
        self.assertIn("data-workflow-viewport", template)
        self.assertIn("data-workflow-inspector", template)
        self.assertIn("data-workflow-fit", template)
        self.assertIn("data-workflow-model", template)
        self.assertIn("fitView", js)
        self.assertIn("selectNode", js)
        self.assertIn("pointerdown", js)
        self.assertNotIn("<form", template)

    def test_diagram_uses_compact_panel_friendly_layout(self):
        workflow = self.read("app/workflow_diagram.py")
        self.assertIn('"board_width": 1780', workflow)
        self.assertIn('"board_height": 840', workflow)
        self.assertIn("compact_sections", workflow)
        self.assertIn("compact_nodes", workflow)

    def test_csp_safe_layout_does_not_depend_on_server_inline_styles(self):
        template = self.read("app/templates/workflow_diagram.html")
        js = self.read("app/static/js/workflow_diagram.js")
        base = self.read("app/templates/base.html")
        self.assertNotIn('style="left:', template)
        self.assertNotIn('--workflow-board-width:', template)
        self.assertIn("data-workflow-section", template)
        self.assertIn("data-workflow-section", template)
        self.assertIn("build_workflow_layout_css", self.read("app/workflow_diagram.py"))
        self.assertIn("workflow_diagram_layout_css", self.read("app/routes.py"))
        self.assertIn("workflow_diagram_layout_css", base)
        self.assertIn("layoutMatchesModel", js)
        self.assertIn("applyEmergencyLayoutFallback", js)
        self.assertIn("?v={{ app_version }}", base)

    def test_fit_uses_rendered_content_bounds_and_inspector_is_overlay(self):
        js = self.read("app/static/js/workflow_diagram.js")
        css = self.read("app/static/css/workflow_diagram.css")
        template = self.read("app/templates/workflow_diagram.html")
        self.assertIn("getContentBounds", js)
        self.assertIn("fitBounds", js)
        self.assertIn("has-workflow-selection", js)
        self.assertIn("position:absolute", css)
        self.assertIn("data-workflow-detail-close", template)
        settings = self.read("app/templates/settings.html")
        self.assertIn("settings-experience--{{ active_section }}", settings)

    def test_workflow_normal_mode_allocates_more_space_to_canvas(self):
        settings_css = self.read("app/static/css/settings_experience.css")
        workflow_css = self.read("app/static/css/workflow_diagram.css")
        self.assertIn("grid-template-columns:225px minmax(0,1fr)", settings_css)
        self.assertIn("height:54px", settings_css)
        self.assertIn("workflow-diagram-head", workflow_css)
        self.assertIn("workflow-diagram-toolbar", workflow_css)

    def test_workflow_expand_focus_mode_and_escape_priority(self):
        template = self.read("app/templates/workflow_diagram.html")
        js = self.read("app/static/js/workflow_diagram.js")
        css = self.read("app/static/css/workflow_diagram.css")
        self.assertIn("data-workflow-expand", template)
        self.assertIn("setExpanded", js)
        self.assertIn("workflow-diagram-focus-active", js)
        self.assertIn("event.stopImmediatePropagation()", js)
        self.assertIn("isEditingControl", js)
        self.assertIn("hasOpenDialog", js)
        self.assertIn(".workflow-diagram-page.is-expanded", css)
        self.assertIn("position:fixed", css)

    def test_workflow_f_shortcut_toggles_focus_mode_safely(self):
        template = self.read("app/templates/workflow_diagram.html")
        js = self.read("app/static/js/workflow_diagram.js")
        self.assertIn('aria-keyshortcuts="F"', template)
        self.assertIn("String(event.key).toLowerCase() !== 'f'", js)
        self.assertIn("event.repeat", js)
        self.assertIn("event.ctrlKey", js)
        self.assertIn("event.altKey", js)
        self.assertIn("event.metaKey", js)
        self.assertIn("isEditingControl()", js)
        self.assertIn("hasOpenDialog()", js)
        self.assertIn("setExpanded(!expanded)", js)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.220")


if __name__ == "__main__":
    unittest.main()
