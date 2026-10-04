import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowDiagramTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_route_uses_canonical_status_sets_and_founder_access(self):
        routes = self.read("app/routes.py")
        self.assertIn('@bp.get("/workflow-diagram")', routes)
        self.assertIn("def workflow_diagram():", routes)
        self.assertIn("@admin_required", routes)
        self.assertIn("build_workflow_diagram(", routes)
        self.assertIn("PROSPECT_STATUS_LABELS", routes)
        self.assertIn("DEAL_PRE_STATUS_STATUSES", routes)
        self.assertIn("DEAL_ACTIVE_STATUSES", routes)

    def test_sidebar_exposes_workflow_diagram_as_rsf_feature(self):
        base = self.read("app/templates/base.html")
        self.assertIn("workflow_active", base)
        self.assertIn("Workflow Diagram", base)
        self.assertIn("url_for('main.workflow_diagram')", base)
        self.assertIn("name == 'workflow'", base)
        self.assertIn("g.user.role == 'admin'", base)

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

    def test_lifecycle_and_sync_rules_are_represented(self):
        workflow = self.read("app/workflow_diagram.py")
        for text in (
            "Backward Movement Gate",
            "Source Reconciliation",
            "Linked Deal Record",
            "Notes After Conversation",
            "Manual Call",
            "WhatsApp",
            "Google Meet / Calendar",
            "Documents / Files",
            "deals.prospect_id",
            "deals.website_inquiry_id",
        ):
            self.assertIn(text, workflow)
        self.assertIn("status_labels.get", workflow)
        self.assertIn("pre_statuses", workflow)
        self.assertIn("active_statuses", workflow)

    def test_diagram_is_read_only_and_interactive(self):
        template = self.read("app/templates/workflow_diagram.html")
        js = self.read("app/static/js/workflow_diagram.js")
        css = self.read("app/static/css/workflow_diagram.css")
        self.assertIn("data-workflow-viewport", template)
        self.assertIn("data-workflow-inspector", template)
        self.assertIn("data-workflow-fit", template)
        self.assertIn("data-workflow-model", template)
        self.assertIn("fitView", js)
        self.assertIn("selectNode", js)
        self.assertIn("pointerdown", js)
        self.assertIn("workflow-diagram-node", css)
        self.assertNotIn("<form", template)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.203")


if __name__ == "__main__":
    unittest.main()
