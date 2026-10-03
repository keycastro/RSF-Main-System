import pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class SupportMaintenanceTests(unittest.TestCase):
    def read(self,p): return (ROOT/p).read_text(encoding="utf-8")
    def test_connected_lifecycle(self):
        r=self.read("app/routes.py"); s=self.read("app/schema.sql")
        self.assertIn('@bp.get("/support-maintenance")',r)
        self.assertIn("d.management_type='RSF_MANAGED'",r)
        self.assertIn("p.status='WON'",r); self.assertIn("i.workflow_status='WON'",r)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS support_maintenance",s)
    def test_sidebar_and_fields(self):
        b=self.read("app/templates/base.html"); t=self.read("app/templates/support_maintenance.html")
        self.assertIn("CLIENT SERVICES",b); self.assertIn("Support &amp; Maintenance",b)
        for x in ("System Name","Service Status","Management Fee","Next Billing Date","System Health","Last Maintenance","Next Maintenance","OTHER FIELDS","Management Start Date","Billing Cycle","Payment Status","System URL","Hosting Provider","Repository","Current Version","Last Deployment","Backup Status","Last Backup","Maintenance Type","Work Done","Issues Found","Resolution","Open Issues","Client Request","Request Status","Priority","Date Requested","Date Completed","Included Support","Excluded Work","Major Upgrade Required?","Additional Charge","Agreement Notes","Developer","Contact Number","WhatsApp #","Email","Notes After Conversation","Documents / Files"):
            self.assertIn(x,t)
    def test_schema_and_won_management_selector(self):
        d=self.read("app/db.py"); m=self.read("app/templates/_master_deal_information.html"); j=self.read("app/static/js/app.js")
        self.assertIn("SCHEMA_VERSION = 41",d); self.assertIn("rsf-v1.18.192-support-maintenance-lifecycle",d)
        self.assertIn('name="management_type"',m); self.assertIn("deal_workflow_status != 'WON'",m)
        self.assertIn("managementField.hidden = data.status !== 'WON'",j)
if __name__=="__main__": unittest.main()
