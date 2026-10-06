import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SupportMaintenanceTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_deal_filter_matches_real_support_lifecycle_status(self):
        deals = self.read("app/templates/deals.html")
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn('data-deal-filter="SUPPORT_MAINTENANCE"', deals)
        self.assertIn("p.status='SUPPORT_MAINTENANCE'", routes)
        self.assertIn("i.workflow_status='SUPPORT_MAINTENANCE'", routes)
        self.assertIn("card.hidden = status !== activeDealFilter", js)
        self.assertNotIn("status === 'WON' && managementType === 'RSF_MANAGED'", js)

    def test_connected_lifecycle_remains_same_deal_record(self):
        routes = self.read("app/routes.py")
        schema = self.read("app/schema.sql")
        self.assertIn('@bp.get("/support-maintenance")', routes)
        self.assertIn("p.status='SUPPORT_MAINTENANCE'", routes)
        self.assertIn("i.workflow_status='SUPPORT_MAINTENANCE'", routes)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS support_maintenance", schema)

    def test_v42_preserves_existing_managed_won_clients_as_new_status(self):
        db = self.read("app/db.py")
        schema = self.read("app/schema.sql")
        self.assertIn("SCHEMA_VERSION = 43", db)
        self.assertIn("rsf-v1.18.202-support-maintenance-workflow-status", db)
        self.assertIn("SET status='SUPPORT_MAINTENANCE',management_type='RSF_MANAGED'", db)
        self.assertIn("SET status='SUPPORT_MAINTENANCE'", db)
        self.assertIn("SET workflow_status='SUPPORT_MAINTENANCE'", db)
        self.assertIn("'WON','SUPPORT_MAINTENANCE','LOST'", schema)

    def test_support_status_forces_rsf_managed_compatibility(self):
        routes = self.read("app/routes.py")
        self.assertIn('if status == "SUPPORT_MAINTENANCE":', routes)
        self.assertIn('management_type = "RSF_MANAGED"', routes)
        self.assertIn("UPDATE deals SET management_type='RSF_MANAGED'", routes)

    def test_only_approved_support_fields_are_rendered(self):
        template = self.read("app/templates/support_maintenance.html")
        approved_names = (
            "service_status", "system_name", "management_fee", "next_billing_date",
            "system_health", "next_maintenance", "management_start_date", "system_url",
            "hosting_provider", "repository_url", "backup_status", "open_issues",
            "client_request", "management_notes",
        )
        for name in approved_names:
            with self.subTest(name=name):
                self.assertIn(f'name="{name}"', template)

        removed_names = (
            "developer", "billing_cycle", "payment_status", "current_version",
            "last_deployment", "last_backup", "last_maintenance", "maintenance_type",
            "work_done", "issues_found", "resolution", "request_status", "priority",
            "date_requested", "date_completed", "included_support", "excluded_work",
            "major_upgrade_required", "additional_charge", "agreement_notes",
            "email", "contact_number", "whatsapp_number", "location",
            "notes_after_conversation",
        )
        for name in removed_names:
            with self.subTest(name=name):
                self.assertNotIn(f'name="{name}"', template)

    def test_main_card_and_other_fields_match_approved_labels(self):
        template = self.read("app/templates/support_maintenance.html")
        for label in (
            "System Name", "Service Status", "Management Fee", "Next Billing Date",
            "System Health", "Next Maintenance", "Management Start Date", "System URL",
            "Hosting Provider", "Repository", "Backup Status", "Open Issues",
            "Client Request", "Management Notes",
        ):
            with self.subTest(label=label):
                self.assertIn(label, template)

        for removed_label in (
            "Developer:", "Billing Cycle", "Payment Status", "Current Version",
            "Last Deployment", "Last Backup", "Last Maintenance", "Maintenance Type",
            "Work Done", "Issues Found", "Resolution", "Request Status", "Priority",
            "Date Requested", "Date Completed", "Included Support", "Excluded Work",
            "Major Upgrade Required?", "Additional Charge", "Agreement Notes",
            "Contact Number", "WhatsApp #", "Notes After Conversation",
        ):
            with self.subTest(removed_label=removed_label):
                self.assertNotIn(removed_label, template)

    def test_management_notes_reuses_existing_column_without_schema_change(self):
        template = self.read("app/templates/support_maintenance.html")
        routes = self.read("app/routes.py")
        db = self.read("app/db.py")
        self.assertIn('name="management_notes"', template)
        self.assertIn("{{ deal['agreement_notes'] }}", template)
        self.assertIn('"management_notes": fld("management_notes", 3000)', routes)
        self.assertIn("client_request=?,agreement_notes=?,updated_at=?", routes)
        self.assertIn("SCHEMA_VERSION = 43", db)

    def test_support_update_only_writes_approved_support_fields(self):
        routes = self.read("app/routes.py")
        start = routes.index("def support_maintenance_update(deal_id: int):")
        end = routes.index('@bp.get("/deals")', start)
        update = routes[start:end]
        for field in (
            "service_status", "system_name", "management_fee", "next_billing_date",
            "system_health", "next_maintenance", "management_start_date", "system_url",
            "hosting_provider", "repository_url", "backup_status", "open_issues",
            "client_request", "agreement_notes",
        ):
            self.assertIn(field, update)
        for removed in (
            "billing_cycle", "payment_status", "current_version", "last_deployment",
            "last_backup", "last_maintenance", "maintenance_type", "work_done",
            "issues_found", "resolution", "request_status", "priority",
            "date_requested", "date_completed", "included_support", "excluded_work",
            "major_upgrade_required", "additional_charge", "contact_person=?",
            "whatsapp_number=?", "notes_after_conversation=?",
        ):
            self.assertNotIn(removed, update)

    def test_other_fields_and_document_controls_initialize_on_support_page(self):
        template = self.read("app/templates/support_maintenance.html")
        js = self.read("app/static/js/app.js")
        self.assertIn("data-deal-source-toggle", template)
        self.assertIn("support-other-fields-body-", template)
        self.assertIn("const hasDealForm = Boolean(page.querySelector('[data-deal-form]'));", js)
        self.assertIn("if (!hasDealForm) return;", js)
        self.assertIn("sourceBody.hidden = !opening;", js)
        self.assertIn("fileList.hidden = !opening;", js)

    def test_deal_stages_card_structure_is_still_reused(self):
        template = self.read("app/templates/support_maintenance.html")
        self.assertIn('class="deal-card support-maintenance-card"', template)
        self.assertIn('class="deal-card-head"', template)
        self.assertIn('class="deal-form-grid"', template)
        self.assertIn("{% include '_master_deal_documents.html' %}", template)
        self.assertIn("support-maintenance-other-fields", template)
        self.assertIn('class="deal-card-footer"', template)

    def test_sidebar_uses_managed_clients_section_label(self):
        base = self.read("app/templates/base.html")
        self.assertIn('<div class="nav-section-label">MANAGED CLIENTS</div>', base)
        self.assertNotIn('<div class="nav-section-label">CLIENT SERVICES</div>', base)
        self.assertIn("url_for('main.support_maintenance')", base)
        self.assertIn("Support &amp; Maintenance", base)

    def test_support_autosaves_without_manual_save_button(self):
        template = self.read("app/templates/support_maintenance.html")
        js = self.read("app/static/js/app.js")
        routes = self.read("app/routes.py")
        self.assertIn("data-support-maintenance-form", template)
        self.assertNotIn("Save Support &amp; Maintenance", template)
        self.assertIn("saveSupportFormInBackground", js)
        self.assertIn("X-RSF-Async", js)
        self.assertIn("page.addEventListener('focusout'", js)
        self.assertIn("page.addEventListener('change'", js)
        self.assertIn('async_request = request.headers.get("X-RSF-Async") == "1"', routes)
        self.assertIn('"ok": True', routes)

    def test_support_uses_existing_page_specific_ctrl_drag_reordering(self):
        template = self.read("app/templates/support_maintenance.html")
        js = self.read("app/static/js/app.js")
        routes = self.read("app/routes.py")
        self.assertIn('data-card-layout-page="support_maintenance"', template)
        self.assertIn('data-card-layout-zones=\'["header","main","other"]\'', template)
        self.assertIn("data-support-maintenance-card", template)
        self.assertIn('data-card-layout-zone="header"', template)
        self.assertIn('data-card-layout-zone="main"', template)
        self.assertIn('data-card-layout-zone="other"', template)
        for key in (
            "service_status", "system_name", "management_fee", "next_billing_date",
            "system_health", "next_maintenance", "management_start_date", "system_url",
            "hosting_provider", "repository_url", "backup_status", "open_issues",
            "client_request", "management_notes",
        ):
            self.assertIn(f'data-card-layout-field="{key}"', template)
        self.assertIn("pageName === 'support_maintenance'", js)
        self.assertIn("[data-support-maintenance-card]", js)
        self.assertIn('"support_maintenance": {', routes)
        self.assertIn('card_layout=_card_layout_preference(db, "support_maintenance")', routes)

    def test_support_drag_reordering_does_not_replace_autosave_or_collapsibles(self):
        template = self.read("app/templates/support_maintenance.html")
        js = self.read("app/static/js/app.js")
        self.assertIn("data-support-maintenance-form", template)
        self.assertIn("data-deal-source-toggle", template)
        self.assertIn("{% include '_master_deal_documents.html' %}", template)
        self.assertIn("saveSupportFormInBackground", js)
        self.assertIn("event.ctrlKey", js)
        self.assertIn("applyAll({animate: true", js)
        self.assertIn("layout_json: payloadJson", js)


    def test_support_header_client_name_can_grow_without_clipping(self):
        template = self.read("app/templates/support_maintenance.html")
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn("<strong>{{ deal['client_name'] or '—' }}</strong>", template)
        self.assertIn("v1.18.218 — Support header text-safe row sizing.", css)
        self.assertIn("grid-template-rows:repeat(2,minmax(20px,auto));", css)
        self.assertIn("overflow:visible;", css)
        self.assertIn("label:first-child>strong", css)
        self.assertIn("overflow-wrap:anywhere;", css)

    def test_support_header_fix_is_scoped_and_preserves_right_column(self):
        css = self.read("app/static/css/workspace_v20.css")
        self.assertIn(
            ".support-maintenance-page .support-maintenance-card .deal-card-identifiers",
            css,
        )
        self.assertIn(
            ".support-maintenance-page .support-maintenance-card .deal-card-linked",
            css,
        )
        self.assertIn("grid-template-columns:minmax(0,1fr) auto;", css)
        self.assertIn("min-width:max-content;", css)
        self.assertIn("display:flex;", css)
        self.assertIn("justify-content:space-between;", css)
        self.assertIn("align-self:stretch;", css)
        self.assertIn("align-self:flex-end;", css)


if __name__ == "__main__":
    unittest.main()
