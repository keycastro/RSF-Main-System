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

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.204")


if __name__ == "__main__":
    unittest.main()
