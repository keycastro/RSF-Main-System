import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MasterLifecycleCardTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_master_deal_section_contains_full_deal_workspace_fields(self):
        template = self.read("app/templates/_master_deal_information.html")
        documents = self.read("app/templates/_master_deal_documents.html")
        for field in (
            'name="followup_date"',
            'name="email"',
            'name="price"',
            'name="developer"',
            'name="contact_number"',
            'name="whatsapp_number"',
            'name="location"',
            'name="demo_date"',
            'name="demo_time"',
            'name="demo_timezone"',
            'name="demo_timezone_location"',
            'name="next_step"',
            'name="notes_after_conversation"',
            "Google Meet",
            "Email Conversation",
        ):
            with self.subTest(field=field):
                self.assertIn(field, template)
        self.assertIn("Documents / Files", documents)

    def test_outbound_card_puts_outbound_information_before_deal_information(self):
        template = self.read("app/templates/_prospect_row.html")
        source_position = template.index('<div class="prospect-detail-grid" data-card-layout-zone="source">')
        deal_position = template.index("{% include '_master_deal_information.html' %}")
        self.assertLess(source_position, deal_position)

    def test_inbound_card_preserves_stage_specific_deal_placement(self):
        template = self.read("app/templates/inquiries.html")
        active_deal_position = template.index("{% if is_active_deal_stage and deal %}")
        source_position = template.index("website-inquiry-card-body")
        predeal_deal_position = template.index("{% if (not is_active_deal_stage) and deal %}")
        self.assertLess(active_deal_position, source_position)
        self.assertLess(source_position, predeal_deal_position)

    def test_primary_sidebar_names_match_current_workspace_pages(self):
        base = self.read("app/templates/base.html")
        prospects = self.read("app/templates/prospects.html")
        inquiries = self.read("app/templates/inquiries.html")

        self.assertIn('<span class="nav-text">Prospects</span>', base)
        self.assertIn('<span class="nav-text">Website Inbox</span>', base)
        self.assertIn("<h1>Prospects</h1>", prospects)
        self.assertIn("<h1>Website Inbox</h1>", inquiries)
        self.assertIn("url_for('main.prospects')", base)
        self.assertIn("url_for('main.inquiries_list')", base)

    def test_active_pipeline_sidebar_and_deals_page_names_are_distinct(self):
        base = self.read("app/templates/base.html")
        deals = self.read("app/templates/deals.html")
        routes = self.read("app/routes.py")

        self.assertIn('<div class="nav-section-label">ACTIVE PIPELINE</div>', base)
        self.assertIn('<span class="nav-text">Deal Stages</span>', base)
        self.assertIn("<h1>Deals Pipeline</h1>", deals)
        self.assertIn('title="Deals Pipeline"', routes)
        self.assertIn('@bp.get("/deals")', routes)
        self.assertIn('data-deal-filter="DEAL"', deals)
        self.assertIn(">Deal</button>", deals)

    def test_prospect_outbound_filters_reuse_deal_stage_filter_design(self):
        prospects = self.read("app/templates/prospects.html")
        deals = self.read("app/templates/deals.html")
        row = self.read("app/templates/_prospect_row.html")
        js = self.read("app/static/js/app.js")

        self.assertIn('class="prospect-status-filters"', prospects)
        self.assertIn('class="prospect-status-filters"', deals)
        self.assertNotIn('data-prospect-filter="ALL"', prospects)
        self.assertNotIn('>All</button>', prospects)
        self.assertIn('data-prospect-filter="NOT_CONTACTED" aria-pressed="true"', prospects)
        for code, label in (
            ("NOT_CONTACTED", "Not Contacted"),
            ("NO_ANSWER", "No Answer"),
            ("REJECTED", "Rejected"),
            ("DEAL_STAGES", "In Deal Stages"),
        ):
            with self.subTest(code=code):
                self.assertIn(f'data-prospect-filter="{code}"', prospects)
                self.assertIn(f'>{label}</button>', prospects)
        self.assertIn("data-prospect-deal-stage=", row)
        self.assertIn("if is_active_deal_stage else '0'", row)
        self.assertIn("card.dataset.prospectDealStage === '1'", js)
        self.assertIn("new MutationObserver(() => applyProspectFilter())", js)

    def test_prospect_sourced_deal_card_hides_linked_in_prospect_label(self):
        deals = self.read("app/templates/deals.html")
        self.assertNotIn(">LINKED IN PROSPECT</a>", deals)
        self.assertIn("deal['prospect_id']", deals)
        self.assertIn("Became Deal:", deals)
        self.assertIn(">LINKED IN WEBSITE INBOX</a>", deals)

    def test_status_filter_pages_do_not_show_all_filter(self):
        prospects = self.read("app/templates/prospects.html")
        deals = self.read("app/templates/deals.html")
        inquiries = self.read("app/templates/inquiries.html")
        support = self.read("app/templates/support_maintenance.html")
        js = self.read("app/static/js/app.js")

        self.assertNotIn('data-prospect-filter="ALL"', prospects)
        self.assertNotIn('data-deal-filter="ALL"', deals)
        self.assertNotIn('>All</button>', prospects)
        self.assertNotIn('>All</button>', deals)
        self.assertIn('data-prospect-filter="NOT_CONTACTED" aria-pressed="true"', prospects)
        self.assertIn('data-deal-filter="DEAL" aria-pressed="true"', deals)
        self.assertIn("let activeProspectFilter = 'NOT_CONTACTED'", js)
        self.assertIn("let activeDealFilter = 'DEAL'", js)
        self.assertNotIn("data-website-inquiry-filter", inquiries)
        self.assertNotIn("data-support-maintenance-filter", support)

    def test_support_maintenance_is_real_shared_status_after_won(self):
        deals = self.read("app/templates/deals.html")
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")
        self.assertIn('"WON": "Won",\n    "SUPPORT_MAINTENANCE": "In Support & Maintenance",\n    "LOST": "Lost"', routes)
        won_at = deals.index('data-deal-filter="WON"')
        support_at = deals.index('data-deal-filter="SUPPORT_MAINTENANCE"')
        lost_at = deals.index('data-deal-filter="LOST"')
        self.assertLess(won_at, support_at)
        self.assertLess(support_at, lost_at)
        self.assertIn("card.hidden = status !== activeDealFilter", js)
        self.assertNotIn("status === 'WON' && managementType === 'RSF_MANAGED'", js)

    def test_view_deal_hash_selects_exact_stage_and_scrolls_to_exact_card(self):
        js = self.read("app/static/js/app.js")
        prospect = self.read("app/templates/_prospect_row.html")
        inquiry = self.read("app/templates/inquiries.html")
        self.assertIn('href="{{ url_for(\'main.deals\') }}#deal-{{ linked_deal_id }}">View Deal</a>', prospect)
        self.assertIn("action.dataset.dealsUrl || '/app/deals'", js)
        self.assertIn("const openTargetDeal = () =>", js)
        self.assertIn("target.matches('[data-deal-card]')", js)
        self.assertIn("activeDealFilter = targetStatus", js)
        self.assertIn("target.scrollIntoView({block:'center', behavior:'auto'})", js)
        self.assertIn("window.addEventListener('hashchange', openTargetDeal)", js)
        self.assertIn("View Deal", inquiry)

    def test_deals_page_keeps_deal_information_before_source_details(self):
        template = self.read("app/templates/deals.html")
        deal_position = template.index("{% include '_master_deal_information.html' %}")
        outbound_position = template.index("OTHER FIELDS")
        inbound_position = template.index("Inbound Details")
        self.assertLess(deal_position, outbound_position)
        self.assertLess(deal_position, inbound_position)

    def test_lifecycle_workspace_is_prepared_on_source_pages_without_premature_merge(self):
        routes = self.read("app/routes.py")
        self.assertIn("_ensure_deal_for_prospect(", routes)
        self.assertIn("_ensure_deal_for_website_inquiry(", routes)
        self.assertGreaterEqual(routes.count("allow_merge=False"), 2)
        self.assertIn("_reconcile_deal_sources_on_activation", routes)

    def test_became_deal_timestamp_is_separate_from_workspace_creation(self):
        schema = self.read("app/schema.sql")
        db = self.read("app/db.py")
        deals = self.read("app/templates/deals.html")
        self.assertIn("became_deal_at TEXT NOT NULL DEFAULT ''", schema)
        self.assertIn("SCHEMA_VERSION = 43", db)
        self.assertIn("rsf-v1.18.131-master-lifecycle-cards", db)
        self.assertIn("deal['became_deal_at']", deals)

    def test_prospect_became_deal_is_footer_only_and_future_adaptive(self):
        prospect = self.read("app/templates/_prospect_row.html")
        master = self.read("app/templates/_master_deal_information.html")
        routes = self.read("app/routes.py")
        js = self.read("app/static/js/app.js")

        self.assertIn("{% set is_active_deal_stage = prospect['status'] in deal_active_statuses %}", prospect)
        self.assertIn("{% set deal_show_became_in_heading = false %}", prospect)
        self.assertIn('class="prospect-became-deal-log"', prospect)
        self.assertIn("{% if is_active_deal_stage and deal and deal['became_deal_at'] %}", prospect)
        self.assertIn("deal_show_became_in_heading and deal['became_deal_at']", master)
        self.assertIn("PROSPECT_STATUS_CODES = tuple(PROSPECT_STATUS_LABELS)", routes)
        self.assertIn("DEAL_ACTIVE_STATUSES = PROSPECT_STATUS_CODES[DEAL_PIPELINE_START_INDEX:]", routes)
        self.assertIn("const prospectDealStartIndex = statusOptions.findIndex", js)
        self.assertIn("statusOptions.slice(prospectDealStartIndex)", js)

    def test_source_pages_include_shared_deal_dialogs(self):
        self.assertIn(
            "{% include '_master_deal_dialogs.html' %}",
            self.read("app/templates/prospects.html"),
        )
        self.assertIn(
            "{% include '_master_deal_dialogs.html' %}",
            self.read("app/templates/inquiries.html"),
        )


if __name__ == "__main__":
    unittest.main()
