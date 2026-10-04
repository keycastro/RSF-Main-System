import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SidebarThemeConsistencyTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_operational_sidebar_uses_global_dark_gold_theme(self):
        css = self.read("app/static/css/workspace_ambient_gold.css")
        self.assertIn("RSF v1.18.211 — Standard operational sidebar theme", css)
        self.assertIn(".app-shell > .sidebar{", css)
        self.assertIn("linear-gradient(180deg,#17120e 0%,#0f0c09 54%,#090706 100%)", css)
        self.assertIn(".app-shell > .sidebar .simple-primary-nav>a.active", css)
        self.assertIn(".app-shell > .sidebar .sidebar-footer", css)

    def test_general_records_does_not_define_sidebar_theme(self):
        css = self.read("app/static/css/general_records.css")
        self.assertNotIn(".general-records-page .sidebar", css)
        self.assertNotIn(".record-detail-page .sidebar", css)

    def test_settings_still_hides_operational_sidebar(self):
        css = self.read("app/static/css/settings_experience.css")
        self.assertIn("body.page-settings-dedicated .sidebar{display:none!important}", css)

    def test_support_maintenance_still_uses_deals_page_shell(self):
        template = self.read("app/templates/support_maintenance.html")
        self.assertIn('class="deals-page support-maintenance-page"', template)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.211")


if __name__ == "__main__":
    unittest.main()
