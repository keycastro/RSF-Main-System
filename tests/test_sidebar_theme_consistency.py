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

    def test_footer_actions_use_one_shared_icon_text_component(self):
        base = self.read("app/templates/base.html")
        w20 = self.read("app/static/css/workspace_v20.css")
        ambient = self.read("app/static/css/workspace_ambient_gold.css")
        self.assertIn('nav_icon("logout")', base)
        self.assertIn('class="signout sidebar-footer-action"', base)
        self.assertIn('class="settings-footer-link sidebar-footer-action"', base)
        self.assertIn(".sidebar-footer-action{", w20)
        self.assertIn("min-height:34px;", w20)
        self.assertIn("font:inherit;", w20)
        self.assertIn("font-size:12.5px;", w20)
        self.assertIn("font-weight:700;", w20)
        self.assertIn(".app-shell > .sidebar .sidebar-session-actions .sidebar-footer-action{", ambient)

    def test_footer_actions_remain_unboxed_and_accessible(self):
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn("border:0;", css)
        self.assertIn("border-radius:0;", css)
        self.assertIn("background:transparent;", css)
        self.assertIn(".sidebar-footer-action .nav-symbol{", css)
        self.assertIn("width:16px;", css)
        self.assertIn(".sidebar-footer-action:focus-visible{", css)
        self.assertIn("outline:2px solid #c9a95e", css)

    def test_version_advanced(self):
        self.assertEqual(self.read("VERSION.txt").strip(), "1.18.228")


if __name__ == "__main__":
    unittest.main()
