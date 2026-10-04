from __future__ import annotations

from typing import Iterable, Mapping


def build_workflow_diagram(
    status_labels: Mapping[str, str],
    pre_statuses: Iterable[str],
    active_statuses: Iterable[str],
) -> dict:
    """Build the read-only RSF architecture map from the canonical lifecycle statuses."""

    pre_statuses = tuple(pre_statuses)
    active_statuses = tuple(active_statuses)

    sections = [
        {"id": "lead-sources", "label": "Lead Sources", "subtitle": "Where a client journey begins", "x": 40, "y": 55, "width": 330, "height": 590, "tone": "source"},
        {"id": "client-intake", "label": "Client Intake", "subtitle": "The two operational entry pages", "x": 400, "y": 55, "width": 390, "height": 590, "tone": "page"},
        {"id": "pre-deal", "label": "Pre-Deal", "subtitle": "Before the record enters Deal Stages", "x": 820, "y": 55, "width": 330, "height": 590, "tone": "predeal"},
        {"id": "active-pipeline", "label": "Active Deal Pipeline", "subtitle": "Deal-side lifecycle statuses", "x": 1180, "y": 55, "width": 400, "height": 690, "tone": "pipeline"},
        {"id": "outcomes", "label": "Won / Lost", "subtitle": "Commercial lifecycle outcomes", "x": 1610, "y": 55, "width": 300, "height": 690, "tone": "outcome"},
        {"id": "managed", "label": "Support & Maintenance", "subtitle": "Managed-client lifecycle", "x": 1940, "y": 55, "width": 360, "height": 690, "tone": "managed"},
        {"id": "actions", "label": "Communication / Actions", "subtitle": "Connected tools around the same client record", "x": 1180, "y": 775, "width": 1320, "height": 390, "tone": "action"},
        {"id": "data", "label": "Database Relationships", "subtitle": "Canonical tables and linked history", "x": 40, "y": 1195, "width": 2460, "height": 390, "tone": "data"},
    ]

    nodes: list[dict] = []
    edges: list[dict] = []

    def add_node(
        node_id: str,
        label: str,
        *,
        x: int,
        y: int,
        section: str,
        kind: str,
        eyebrow: str,
        summary: str,
        details: list[str],
        badge: str = "",
        endpoint: str = "",
        width: int = 230,
    ) -> None:
        nodes.append({
            "id": node_id,
            "label": label,
            "x": x,
            "y": y,
            "width": width,
            "section": section,
            "kind": kind,
            "eyebrow": eyebrow,
            "summary": summary,
            "details": details,
            "badge": badge,
            "endpoint": endpoint,
        })

    def add_edge(
        source: str,
        target: str,
        *,
        label: str = "",
        style: str = "primary",
        source_anchor: str = "right",
        target_anchor: str = "left",
    ) -> None:
        edges.append({
            "source": source,
            "target": target,
            "label": label,
            "style": style,
            "source_anchor": source_anchor,
            "target_anchor": target_anchor,
        })

    add_node(
        "research-source",
        "Researched Prospect",
        x=85,
        y=155,
        section="lead-sources",
        kind="source",
        eyebrow="OUTBOUND SOURCE",
        summary="A client opportunity is manually added from research or outreach.",
        details=[
            "Creates a Prospect in the prospects table.",
            "Duplicate checks prevent a second Prospect with the same normalized company name.",
            "A matching Website Inquiry is detected before a duplicate outbound record is created.",
        ],
        endpoint="main.prospects",
    )
    add_node(
        "website-form",
        "Public Website Request",
        x=85,
        y=315,
        section="lead-sources",
        kind="source",
        eyebrow="INBOUND SOURCE",
        summary="The public RSF contact form stores a Website Inquiry.",
        details=[
            "The request is validated, CSRF-protected, and stored by the public website.",
            "Source intent and selected system context are retained when present.",
            "The new record appears in Website Inbox.",
        ],
    )
    add_node(
        "identity-check",
        "Identity / Duplicate Check",
        x=85,
        y=475,
        section="lead-sources",
        kind="condition",
        eyebrow="CONDITION",
        summary="RSF checks whether the same client already exists in another intake source.",
        details=[
            "Prospect creation checks matching Website Inquiry identity.",
            "Deal activation can reconcile Prospect and Website Inquiry sources into one Deal.",
            "The goal is one connected client journey instead of duplicate Deal records.",
        ],
        badge="Conditional",
    )

    add_node(
        "prospects-page",
        "Prospects",
        x=455,
        y=140,
        section="client-intake",
        kind="page",
        eyebrow="PRIVATE PAGE",
        summary="Outbound working page for researched prospects.",
        details=[
            "Displays every Prospect in one continuous list.",
            "Status, source details, shared client fields, Notes, and communication actions live here.",
            "Prospect-side edits synchronize linked Deal/source fields where applicable.",
        ],
        endpoint="main.prospects",
    )
    add_node(
        "website-inbox",
        "Website Inbox",
        x=455,
        y=285,
        section="client-intake",
        kind="page",
        eyebrow="PRIVATE PAGE",
        summary="Inbound working page for requests submitted through the public website.",
        details=[
            "Website Inquiry workflow_status uses the same lifecycle labels as Prospects.",
            "When Deal-side, the card exposes the connected Deal information and actions.",
            "Status and shared values synchronize through the same linked Deal.",
        ],
        endpoint="main.inquiries_list",
    )
    add_node(
        "linked-deal-record",
        "Linked Deal Record",
        x=455,
        y=430,
        section="client-intake",
        kind="data",
        eyebrow="INTERNAL LINK",
        summary="RSF prepares one Deal row as the canonical bridge for Deal-side shared data.",
        details=[
            "A Deal row can exist before the client is visible in Deal Stages.",
            "deals.prospect_id and deals.website_inquiry_id connect the intake sources.",
            "Developer, WhatsApp #, Deal scheduling, Support fields, and other shared Deal data live here.",
        ],
        badge="Hidden until Deal-side",
    )
    add_node(
        "source-reconcile",
        "Source Reconciliation",
        x=455,
        y=565,
        section="client-intake",
        kind="condition",
        eyebrow="MERGE RULE",
        summary="When sources represent the same client, activation reconciles them into one Deal journey.",
        details=[
            "A Deal can reference both a Prospect and a Website Inquiry.",
            "Existing linked communication and history are preserved during reconciliation.",
            "No separate Support client table is created later in the lifecycle.",
        ],
        badge="One client",
    )

    pre_y = 140
    pre_gap = 128
    pre_ids: dict[str, str] = {}
    for index, code in enumerate(pre_statuses):
        node_id = f"status-{code.lower().replace('_', '-')}"
        pre_ids[code] = node_id
        label = status_labels.get(code, code.replace("_", " ").title())
        summary_map = {
            "NOT_CONTACTED": "The client has not yet been contacted.",
            "NO_ANSWER": "Contact was attempted but the client did not answer.",
            "REJECTED": "The opportunity is currently rejected and remains outside Deal Stages.",
        }
        detail_map = {
            "NOT_CONTACTED": [
                "Default lifecycle status for new Prospects and Website Inquiries.",
                "The record stays on its source page and is not visible in Deal Stages.",
            ],
            "NO_ANSWER": [
                "Still a pre-Deal status.",
                "The linked Deal data is preserved internally even though Deal Stages stays hidden.",
            ],
            "REJECTED": [
                "Still a pre-Deal status.",
                "The client can later be moved to a Deal-side status if the opportunity reopens.",
            ],
        }
        add_node(
            node_id,
            label,
            x=870,
            y=pre_y + index * pre_gap,
            section="pre-deal",
            kind="status-pre",
            eyebrow="STATUS",
            summary=summary_map.get(code, "A canonical pre-Deal lifecycle status."),
            details=detail_map.get(code, [
                "This status is part of the canonical pre-Deal status set.",
                "It stays outside Deal Stages until a Deal-side status is selected.",
            ]),
            badge="Pre-Deal",
        )

    add_node(
        "backward-confirmation",
        "Backward Movement Gate",
        x=870,
        y=520,
        section="pre-deal",
        kind="condition",
        eyebrow="SAFETY RULE",
        summary="Moving from any Deal-side status back to a pre-Deal status requires confirmation.",
        details=[
            "The confirmation protects against accidentally removing the client from Deal Stages.",
            "After confirmation, the same linked Deal record and Deal details are preserved.",
            "The selected pre-Deal Status is synchronized back to linked sources.",
        ],
        badge="Yes / No",
    )

    special = {"WON", "LOST", "SUPPORT_MAINTENANCE"}
    pipeline_codes = [code for code in active_statuses if code not in special]
    pipeline_ids: dict[str, str] = {}
    pipeline_y = 130
    pipeline_gap = 118
    for index, code in enumerate(pipeline_codes):
        node_id = f"status-{code.lower().replace('_', '-')}"
        pipeline_ids[code] = node_id
        label = status_labels.get(code, code.replace("_", " ").title())
        details = [
            "Part of DEAL_ACTIVE_STATUSES and visible in Deal Stages.",
            "Status changes synchronize to linked Prospect and Website Inquiry records.",
            "Deal-side fields remain on the same connected Deal row.",
        ]
        if code == "DEAL":
            details.insert(0, "Entering Deal-side marks the first became_deal_at timestamp and activates the Deal pipeline.")
        add_node(
            node_id,
            label,
            x=1265,
            y=pipeline_y + index * pipeline_gap,
            section="active-pipeline",
            kind="status-active",
            eyebrow="DEAL STATUS",
            summary=f"{label} is an active Deal-side lifecycle status.",
            details=details,
            badge="Deal-side",
            endpoint="main.deals",
        )

    if "WON" in active_statuses:
        add_node(
            "status-won",
            status_labels.get("WON", "Won"),
            x=1650,
            y=170,
            section="outcomes",
            kind="status-won",
            eyebrow="OUTCOME",
            summary="The client has reached Won while remaining on the same connected Deal.",
            details=[
                "Won is a real lifecycle Status.",
                "A Won client can later enter In Support & Maintenance.",
                "Existing shared fields, communication history, files, and Deal data remain attached.",
            ],
            badge="Won",
            endpoint="main.deals",
        )
    if "LOST" in active_statuses:
        add_node(
            "status-lost",
            status_labels.get("LOST", "Lost"),
            x=1650,
            y=410,
            section="outcomes",
            kind="status-lost",
            eyebrow="OUTCOME",
            summary="Lost is a Deal-side lifecycle Status for an opportunity that does not continue.",
            details=[
                "Lost remains represented in Deal Stages under the Lost filter.",
                "The Status can be selected from Deal-side work; it is not limited to one exact preceding stage.",
                "History and linked records remain preserved.",
            ],
            badge="Deal-side",
            endpoint="main.deals",
        )
    if "SUPPORT_MAINTENANCE" in active_statuses:
        add_node(
            "status-support-maintenance",
            status_labels.get("SUPPORT_MAINTENANCE", "In Support & Maintenance"),
            x=1985,
            y=155,
            section="managed",
            kind="status-support",
            eyebrow="LIFECYCLE STATUS",
            summary="A Won client can move into the managed-client lifecycle without creating a duplicate client record.",
            details=[
                "SUPPORT_MAINTENANCE is a real shared lifecycle Status.",
                "Entering it forces the legacy Deal management_type compatibility value to RSF_MANAGED.",
                "The status synchronizes to every linked Prospect and Website Inquiry source.",
            ],
            badge="Managed",
            endpoint="main.support_maintenance",
            width=270,
        )
        add_node(
            "support-page",
            "Support & Maintenance Page",
            x=1985,
            y=330,
            section="managed",
            kind="page",
            eyebrow="PRIVATE PAGE",
            summary="Shows only connected clients whose canonical lifecycle Status is In Support & Maintenance.",
            details=[
                "Uses the existing Deal row; there is no duplicate Support client table.",
                "Support fields autosave on the connected Deal.",
                "Documents / Files, OTHER FIELDS, and field reordering remain connected.",
            ],
            endpoint="main.support_maintenance",
            width=270,
        )
        add_node(
            "service-status",
            "Service Status",
            x=1985,
            y=515,
            section="managed",
            kind="status-service",
            eyebrow="SUPPORT FIELD",
            summary="Operational Support state is separate from the shared client lifecycle Status.",
            details=[
                "Values: Onboarding, Active, Paused, Ended.",
                "Changing Service Status does not replace the lifecycle Status.",
                "System Health and management details are maintained on the same Deal record.",
            ],
            badge="Onboarding / Active / Paused / Ended",
            width=270,
        )

    add_node(
        "client-actions",
        "Client Actions Hub",
        x=1225,
        y=865,
        section="actions",
        kind="hub",
        eyebrow="CONNECTED ACTIONS",
        summary="Communication and operational actions resolve the same connected Prospect / Inquiry / Deal identity.",
        details=[
            "Actions use the current linked record context instead of creating separate client identities.",
            "Availability can depend on Status, contact data, or external integration configuration.",
        ],
        badge="Same client",
        width=225,
    )
    action_nodes = [
        ("shared-fields", "Shared Fields", 1485, 835, "sync", "Client Name, Location, Email, Contact Number, WhatsApp #, Developer and other connected values are synchronized through source/Deal update logic.", [
            "Deal-side edits write shared identity values back to linked Prospect and Website Inquiry records.",
            "Developer and WhatsApp # are canonical Deal-backed fields.",
            "Notes After Conversation has explicit cross-source synchronization.",
        ], "Bidirectional"),
        ("notes", "Notes After Conversation", 1745, 835, "action", "Conversation notes stay connected across the linked client journey.", [
            "Prospect, Website Inquiry, and Deal note values synchronize where linked.",
            "Manual notes and communication timeline entries preserve client context.",
        ], "Shared"),
        ("email", "Email", 2005, 835, "integration", "Email uses the canonical client_conversations / client_messages thread.", [
            "Merged Prospect + Website journeys collapse to one canonical conversation where possible.",
            "Sending depends on configured email credentials / provider readiness.",
        ], "Conditional"),
        ("manual-call", "Manual Call", 1485, 1000, "integration", "Manual Call uses the linked client context and Twilio-backed call state.", [
            "Controls include End Call, Mute / Unmute, Hold / Resume and duration.",
            "Recording and transcript history attach to the same client journey.",
            "Calling requires a usable Contact Number and provider configuration.",
        ], "Twilio"),
        ("whatsapp", "WhatsApp", 1745, 1000, "integration", "WhatsApp uses the Deal-backed WhatsApp # and stores message history against linked ids.", [
            "Messaging supports text/media routes when Meta API configuration is available.",
            "No WhatsApp # means the action is disabled.",
            "WhatsApp Calling remains a separate not-connected capability.",
        ], "Meta API"),
        ("google-meet", "Google Meet / Calendar", 2005, 1000, "integration", "Deal demo scheduling can synchronize a Google Calendar event and Google Meet link.", [
            "Requires a Deal-side Status plus valid date, time and timezone.",
            "Calendar must be connected for live event creation/update.",
            "Client Time and Philippines Time are calculated from the selected timezone.",
        ], "Conditional"),
        ("documents", "Documents / Files", 2265, 835, "action", "Files are stored against the Deal so they follow the connected lifecycle.", [
            "Uploads use deal_documents with Deal ownership.",
            "Files remain available through Deal and Support views when connected.",
            "Preview/view/delete controls do not create a separate client record.",
        ], "Deal-owned"),
        ("activity-log", "Activity / History", 2265, 1000, "data", "Lifecycle and operational events are logged for historical traceability.", [
            "Status changes, Deal creation, meeting sync and Support updates write activity records.",
            "Records & History Control reconstructs the connected client story.",
        ], "History"),
    ]
    for node_id, label, x, y, kind, summary, details, badge in action_nodes:
        add_node(
            node_id, label, x=x, y=y, section="actions", kind=kind,
            eyebrow="ACTION" if kind == "action" else ("INTEGRATION" if kind == "integration" else "SYNC / DATA"),
            summary=summary, details=details, badge=badge, width=225,
        )

    db_nodes = [
        ("db-prospects", "prospects", 90, "SOURCE TABLE", "Outbound source record and pre-/Deal lifecycle status."),
        ("db-inquiries", "website_inquiries", 335, "SOURCE TABLE", "Inbound source record and shared workflow_status."),
        ("db-deals", "deals", 580, "CANONICAL DEAL", "One connected Deal row bridges source identity and Deal/Support data."),
        ("db-conversations", "client_conversations", 825, "COMMUNICATION", "Canonical email/client conversation identity."),
        ("db-messages", "client_messages", 1070, "COMMUNICATION", "Website/Email message history."),
        ("db-calls", "manual_client_calls", 1315, "CALL HISTORY", "Twilio manual-call state, recording and transcript."),
        ("db-whatsapp", "whatsapp_messages", 1560, "MESSAGE HISTORY", "WhatsApp inbound/outbound message and media history."),
        ("db-documents", "deal_documents", 1805, "FILE HISTORY", "Deal-owned uploaded files."),
        ("db-activity", "activity_log", 2050, "AUDIT HISTORY", "Lifecycle and operational event history."),
    ]
    for node_id, label, x, eyebrow, summary in db_nodes:
        add_node(
            node_id,
            label,
            x=x,
            y=1325,
            section="data",
            kind="db-table",
            eyebrow=eyebrow,
            summary=summary,
            details=[
                "This node represents an actual RSF database table.",
                "Relationships shown by the connectors mirror current backend ownership/linkage.",
            ],
            width=215,
        )

    add_edge("research-source", "prospects-page", label="add prospect")
    add_edge("website-form", "website-inbox", label="store inquiry")
    add_edge("research-source", "identity-check", label="before save", style="conditional", source_anchor="bottom", target_anchor="top")
    add_edge("website-form", "identity-check", label="matching identity", style="conditional", source_anchor="bottom", target_anchor="top")
    add_edge("prospects-page", "linked-deal-record", label="ensure linked Deal", style="sync", source_anchor="bottom", target_anchor="top")
    add_edge("website-inbox", "linked-deal-record", label="ensure linked Deal", style="sync", source_anchor="bottom", target_anchor="top")
    add_edge("linked-deal-record", "source-reconcile", label="on activation / match", style="conditional", source_anchor="bottom", target_anchor="top")

    first_pre = pre_ids.get("NOT_CONTACTED") or (next(iter(pre_ids.values())) if pre_ids else "")
    if first_pre:
        add_edge("prospects-page", first_pre, label="Prospect Status")
        add_edge("website-inbox", first_pre, label="workflow_status")
    if "NOT_CONTACTED" in pre_ids and "NO_ANSWER" in pre_ids:
        add_edge(pre_ids["NOT_CONTACTED"], pre_ids["NO_ANSWER"], label="contact attempted", style="secondary", source_anchor="bottom", target_anchor="top")
    if "NOT_CONTACTED" in pre_ids and "REJECTED" in pre_ids:
        add_edge(pre_ids["NOT_CONTACTED"], pre_ids["REJECTED"], label="not proceeding", style="secondary", source_anchor="bottom", target_anchor="top")

    first_pipeline = pipeline_ids.get("DEAL") or (next(iter(pipeline_ids.values())) if pipeline_ids else "")
    if first_pipeline:
        if first_pre:
            add_edge(first_pre, first_pipeline, label="set Deal")
        if "NO_ANSWER" in pre_ids:
            add_edge(pre_ids["NO_ANSWER"], first_pipeline, label="can progress", style="secondary")
        if "REJECTED" in pre_ids:
            add_edge(pre_ids["REJECTED"], first_pipeline, label="can reopen", style="secondary")
        add_edge("source-reconcile", first_pipeline, label="single Deal identity", style="sync")

    for left, right in zip(pipeline_codes, pipeline_codes[1:]):
        add_edge(pipeline_ids[left], pipeline_ids[right], label="canonical path", source_anchor="bottom", target_anchor="top")

    last_pipeline = pipeline_ids[pipeline_codes[-1]] if pipeline_codes else ""
    if last_pipeline and "WON" in active_statuses:
        add_edge(last_pipeline, "status-won", label="set Won")
    if last_pipeline and "LOST" in active_statuses:
        add_edge(last_pipeline, "status-lost", label="set Lost", style="secondary")
    if first_pipeline and "LOST" in active_statuses:
        add_edge(first_pipeline, "status-lost", label="Lost may be selected from Deal-side", style="conditional")

    if "WON" in active_statuses and "SUPPORT_MAINTENANCE" in active_statuses:
        add_edge("status-won", "status-support-maintenance", label="enter managed support")
        add_edge("status-support-maintenance", "support-page", label="visible when this Status", source_anchor="bottom", target_anchor="top")
        add_edge("support-page", "service-status", label="operational state", style="secondary", source_anchor="bottom", target_anchor="top")

    if first_pipeline:
        add_edge(first_pipeline, "backward-confirmation", label="any Deal-side → pre-Deal", style="conditional", source_anchor="left", target_anchor="right")
        if first_pre:
            add_edge("backward-confirmation", first_pre, label="confirm Yes", style="conditional", source_anchor="top", target_anchor="bottom")

    add_edge("linked-deal-record", "shared-fields", label="canonical shared Deal data", style="sync", source_anchor="bottom", target_anchor="left")
    add_edge("shared-fields", "prospects-page", label="sync", style="sync", source_anchor="left", target_anchor="bottom")
    add_edge("shared-fields", "website-inbox", label="sync", style="sync", source_anchor="left", target_anchor="bottom")

    if first_pipeline:
        add_edge(first_pipeline, "client-actions", label="same client context", style="secondary", source_anchor="bottom", target_anchor="top")
    add_edge("prospects-page", "client-actions", label="pre-Deal actions", style="action", source_anchor="bottom", target_anchor="left")
    add_edge("website-inbox", "client-actions", label="inbound actions", style="action", source_anchor="bottom", target_anchor="left")
    for target in ("notes", "email", "manual-call", "whatsapp", "google-meet", "documents", "activity-log"):
        add_edge("client-actions", target, style="action")
    add_edge("client-actions", "shared-fields", style="sync")

    add_edge("db-prospects", "db-deals", label="deals.prospect_id", style="data")
    add_edge("db-inquiries", "db-deals", label="deals.website_inquiry_id", style="data")
    add_edge("db-prospects", "db-conversations", label="prospect_id", style="data")
    add_edge("db-inquiries", "db-conversations", label="inquiry_id", style="data")
    add_edge("db-conversations", "db-messages", label="conversation_id", style="data")
    add_edge("db-deals", "db-calls", label="deal_id / linked source ids", style="data")
    add_edge("db-deals", "db-whatsapp", label="deal_id / linked source ids", style="data")
    add_edge("db-deals", "db-documents", label="deal_id", style="data")
    add_edge("db-deals", "db-activity", label="entity history", style="data")

    # v1.18.205 display-only compact layout.
    # Semantic nodes, edges, lifecycle rules, and database relationships above remain unchanged.
    compact_sections = {
        "lead-sources": (30, 30, 210, 390),
        "client-intake": (255, 30, 225, 390),
        "pre-deal": (495, 30, 215, 390),
        "active-pipeline": (725, 30, 230, 390),
        "outcomes": (970, 30, 190, 390),
        "managed": (1175, 30, 575, 390),
        "actions": (255, 435, 1495, 200),
        "data": (30, 650, 1720, 170),
    }
    for section in sections:
        layout = compact_sections.get(section["id"])
        if layout:
            section["x"], section["y"], section["width"], section["height"] = layout

    compact_nodes = {
        "research-source": (50, 90, 170),
        "website-form": (50, 205, 170),
        "identity-check": (50, 320, 170),
        "prospects-page": (280, 85, 175),
        "website-inbox": (280, 175, 175),
        "linked-deal-record": (280, 265, 175),
        "source-reconcile": (280, 335, 175),
        "backward-confirmation": (520, 340, 165),
        "status-won": (995, 120, 140),
        "status-lost": (995, 260, 140),
        "status-support-maintenance": (1205, 90, 250),
        "support-page": (1470, 90, 250),
        "service-status": (1338, 250, 250),
        "client-actions": (285, 490, 170),
        "shared-fields": (480, 470, 170),
        "notes": (665, 470, 170),
        "email": (850, 470, 170),
        "documents": (1035, 470, 170),
        "manual-call": (480, 555, 170),
        "whatsapp": (665, 555, 170),
        "google-meet": (850, 555, 170),
        "activity-log": (1035, 555, 170),
    }

    for index, code in enumerate(pre_statuses):
        compact_nodes[f"status-{code.lower().replace('_', '-')}"] = (520, 85 + index * 90, 165)
    for index, code in enumerate(pipeline_codes):
        compact_nodes[f"status-{code.lower().replace('_', '-')}"] = (750, 75 + index * 85, 180)

    db_ids = (
        "db-prospects",
        "db-inquiries",
        "db-deals",
        "db-conversations",
        "db-messages",
        "db-calls",
        "db-whatsapp",
        "db-documents",
        "db-activity",
    )
    for index, node_id in enumerate(db_ids):
        compact_nodes[node_id] = (70 + index * 185, 700, 165)

    for node in nodes:
        layout = compact_nodes.get(node["id"])
        if layout:
            node["x"], node["y"], node["width"] = layout

    return {
        "board_width": 1780,
        "board_height": 840,
        "sections": sections,
        "nodes": nodes,
        "edges": edges,
        "status_count": len(status_labels),
        "pre_status_count": len(pre_statuses),
        "active_status_count": len(active_statuses),
        "notes": [
            "The main arrows show the canonical way to read the lifecycle, not a restriction that forces every status change to happen one step at a time.",
            "RSF currently allows selecting another valid Status directly. Moving from any Deal-side Status back to a pre-Deal Status requires confirmation.",
            "Solid gold/green paths are lifecycle flow; dashed paths represent conditions, synchronization, or optional integrations.",
        ],
    }
