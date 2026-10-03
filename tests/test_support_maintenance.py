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
        for x in ("System Name","Service Status","Management Fee","Next Billing Date","System Health",
                  "Management Start Date","Last Maintenance","Next Maintenance","OTHER FIELDS",
                  "Billing Cycle","Payment Status","System URL","Hosting Provider","Repository",
                  "Current Version","Last Deployment","Backup Status","Last Backup","Maintenance Type",
                  "Work Done","Issues Found","Resolution","Open Issues","Client Request","Request Status",
                  "Priority","Date Requested","Date Completed","Included Support","Excluded Work",
                  "Major Upgrade Required?","Additional Charge","Agreement Notes","Company","Developer",
                  "Contact Number","WhatsApp #","Email","Location","Notes After Conversation","Documents / Files"):
            self.assertIn(x,t)

    def test_schema_and_won_management_selector(self):
        d=self.read("app/db.py"); m=self.read("app/templates/_master_deal_information.html"); j=self.read("app/static/js/app.js")
        self.assertIn("SCHEMA_VERSION = 41",d); self.assertIn("rsf-v1.18.192-support-maintenance-lifecycle",d)
        self.assertIn('name="management_type"',m); self.assertIn("deal_workflow_status != 'WON'",m)
        self.assertIn("managementField.hidden = data.status !== 'WON'",j)

    def test_support_card_reuses_deal_stages_master_structure(self):
        t=self.read("app/templates/support_maintenance.html")
        self.assertIn('class="deal-card support-maintenance-card"',t)
        self.assertIn('class="deal-card-head"',t)
        self.assertIn('class="deal-card-identifiers"',t)
        self.assertIn('class="deal-identifier-input"',t)
        self.assertIn('class="deal-header-status-select"',t)
        self.assertIn('class="deal-form support-maintenance-core-fields"',t)
        self.assertIn('class="deal-form-grid"',t)
        self.assertIn('class="deal-source-details deal-source-research support-maintenance-other-fields"',t)
        self.assertIn('data-deal-source-toggle',t)
        self.assertIn('class="deal-source-grid"',t)
        self.assertIn('class="deal-card-footer"',t)
        self.assertIn('class="deal-footer-action"',t)

    def test_support_card_section_order_matches_deal_card_hierarchy(self):
        t=self.read("app/templates/support_maintenance.html")
        core=t.index("support-maintenance-core-fields")
        docs=t.index("_master_deal_documents.html")
        other=t.index("support-maintenance-other-fields")
        footer=t.index('class="deal-card-footer"')
        self.assertLess(core,docs)
        self.assertLess(docs,other)
        self.assertLess(other,footer)

    def test_support_save_form_still_owns_all_management_fields(self):
        t=self.read("app/templates/support_maintenance.html")
        self.assertIn("support_form_id = 'support-form-' ~ deal['id']",t)
        self.assertIn('action="{{ url_for(\'main.support_maintenance_update\', deal_id=deal[\'id\']) }}"',t)
        for name in ("client_name","service_status","developer","system_name","management_fee","next_billing_date",
                     "system_health","management_start_date","last_maintenance","next_maintenance","billing_cycle",
                     "payment_status","system_url","hosting_provider","repository_url","current_version","last_deployment",
                     "backup_status","last_backup","maintenance_type","work_done","issues_found","resolution","open_issues",
                     "client_request","request_status","priority","date_requested","date_completed","included_support",
                     "excluded_work","major_upgrade_required","additional_charge","agreement_notes","email","contact_number",
                     "whatsapp_number","location","notes_after_conversation"):
            self.assertIn(f'name="{name}"',t)

    def test_support_uses_same_deal_document_component(self):
        t=self.read("app/templates/support_maintenance.html")
        d=self.read("app/templates/_master_deal_documents.html")
        self.assertIn("{% include '_master_deal_documents.html' %}",t)
        self.assertIn("deal_documents_description",d)

if __name__=="__main__": unittest.main()
