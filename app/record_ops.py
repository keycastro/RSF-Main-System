from __future__ import annotations

from itertools import combinations

from .services import normalize_email, normalize_phone, normalize_text


RECORD_DELETE_PROTECTED_STATUSES = ("DEAL", "DEMO", "PROPOSAL", "DECISION")


def _clean(value) -> str:
    return str(value or "").strip()


def _source_effective_updated(source: dict) -> str:
    values = [
        _clean(source.get("updated_at")),
        _clean(source.get("created_at")),
    ]
    deal = source.get("deal")
    if deal:
        values.extend([
            _clean(deal.get("updated_at")),
            _clean(deal.get("created_at")),
        ])
    return max((value for value in values if value), default="")


def _identity_values(source: dict) -> dict[str, str]:
    return {
        "email": normalize_email(source.get("email")),
        "phone": normalize_phone(source.get("phone")),
        "company": normalize_text(source.get("company")),
        "contact": normalize_text(source.get("contact_name")),
    }


def identity_match_reasons(left: dict, right: dict) -> list[str]:
    """Return normalized client identity signals that agree across two source records."""
    left_values = _identity_values(left)
    right_values = _identity_values(right)
    return [
        name
        for name in ("email", "phone", "company", "contact")
        if left_values[name] and left_values[name] == right_values[name]
    ]


def identities_match(left: dict, right: dict, *, minimum_signals: int = 2) -> bool:
    return len(identity_match_reasons(left, right)) >= minimum_signals


def find_matching_website_inquiry(db, identity: dict, *, exclude_inquiry_id: int | None = None):
    sql = """SELECT id,name,email,phone,company,created_at,updated_at,status,workflow_status,client_conversation_id
             FROM website_inquiries
             WHERE status<>'SPAM'"""
    params: list = []
    if exclude_inquiry_id is not None:
        sql += " AND id<>?"
        params.append(exclude_inquiry_id)
    sql += " ORDER BY created_at DESC,id DESC"
    for row in db.execute(sql, params).fetchall():
        candidate = {
            "company": row["company"],
            "contact_name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
        }
        if identities_match(identity, candidate):
            return row
    return None


def find_matching_prospect(db, identity: dict, *, exclude_prospect_id: int | None = None):
    sql = """SELECT id,name,contact,email,phone,status,recorded_date,created_at,updated_at
             FROM prospects"""
    params: list = []
    if exclude_prospect_id is not None:
        sql += " WHERE id<>?"
        params.append(exclude_prospect_id)
    sql += " ORDER BY created_at DESC,id DESC"
    for row in db.execute(sql, params).fetchall():
        candidate = {
            "company": row["name"],
            "contact_name": row["contact"],
            "email": row["email"],
            "phone": row["phone"],
        }
        if identities_match(identity, candidate):
            return row
    return None


def _latest_nonempty(sources: list[dict], field: str) -> str:
    ordered = sorted(sources, key=_source_effective_updated, reverse=True)
    for source in ordered:
        value = _clean(source.get(field))
        if value:
            return value
    return ""


def _record_key(sources: list[dict]) -> str:
    tokens = []
    for source in sorted(sources, key=lambda item: (item["kind"], int(item["source_id"]))):
        prefix = "p" if source["kind"] == "prospect" else "i"
        tokens.append(f"{prefix}{int(source['source_id'])}")
    return "-".join(tokens)


def _query_sources(db, partner_id: int | None = None) -> list[dict]:
    prospects = db.execute(
        """SELECT p.*,
                  d.id AS deal_id,d.status AS deal_status,d.demo_date AS deal_demo_date,
                  d.followup_date AS deal_followup_date,d.next_step AS deal_next_step,
                  d.price AS deal_price,d.contact_person AS deal_contact_person,
                  d.location AS deal_location,d.contact_number AS deal_contact_number,
                  d.email AS deal_email,d.notes_after_conversation AS deal_notes_after_conversation,
                  d.created_at AS deal_created_at,d.updated_at AS deal_updated_at
           FROM prospects p
           LEFT JOIN deals d ON d.prospect_id=p.id
           ORDER BY p.created_at ASC,p.id ASC"""
    ).fetchall()

    inquiry_sql = """SELECT i.*,
                            d.id AS deal_id,d.status AS deal_status,d.demo_date AS deal_demo_date,
                            d.followup_date AS deal_followup_date,d.next_step AS deal_next_step,
                            d.price AS deal_price,d.contact_person AS deal_contact_person,
                            d.location AS deal_location,d.contact_number AS deal_contact_number,
                            d.email AS deal_email,d.notes_after_conversation AS deal_notes_after_conversation,
                            d.created_at AS deal_created_at,d.updated_at AS deal_updated_at,
                            COALESCE(u.full_name,NULLIF(p.historical_name,''),'') AS claimed_by_name
                     FROM website_inquiries i
                     LEFT JOIN deals d ON d.website_inquiry_id=i.id
                     LEFT JOIN partners p ON p.id=i.claimed_by_partner_id
                     LEFT JOIN users u ON u.id=p.user_id"""
    if partner_id is None:
        inquiries = db.execute(
            inquiry_sql + " ORDER BY i.created_at ASC,i.id ASC"
        ).fetchall()
    else:
        inquiries = db.execute(
            inquiry_sql + """
             WHERE i.status='UNCLAIMED'
                OR (i.status='CLAIMED' AND i.claimed_by_partner_id=?)
             ORDER BY i.created_at ASC,i.id ASC""",
            (partner_id,),
        ).fetchall()

    sources: list[dict] = []
    for row in prospects:
        raw = dict(row)
        deal = None
        if raw.get("deal_id"):
            deal = {
                "id": int(raw["deal_id"]),
                "status": _clean(raw.get("deal_status")),
                "demo_date": _clean(raw.get("deal_demo_date")),
                "followup_date": _clean(raw.get("deal_followup_date")),
                "next_step": _clean(raw.get("deal_next_step")),
                "price": _clean(raw.get("deal_price")),
                "contact_person": _clean(raw.get("deal_contact_person")),
                "location": _clean(raw.get("deal_location")),
                "contact_number": _clean(raw.get("deal_contact_number")),
                "email": _clean(raw.get("deal_email")),
                "notes_after_conversation": _clean(raw.get("deal_notes_after_conversation")),
                "created_at": _clean(raw.get("deal_created_at")),
                "updated_at": _clean(raw.get("deal_updated_at")),
                "source_kind": "prospect",
                "source_id": int(raw["id"]),
            }
        sources.append({
            "kind": "prospect",
            "source_id": int(raw["id"]),
            "company": _clean(raw.get("name")),
            "contact_name": _clean(raw.get("contact")),
            "email": _clean(raw.get("email")),
            "phone": _clean(raw.get("phone")),
            "workflow_status": _clean(raw.get("status")).upper() or "NOT_CONTACTED",
            "created_at": _clean(raw.get("created_at")) or _clean(raw.get("recorded_date")),
            "updated_at": _clean(raw.get("updated_at")) or _clean(raw.get("created_at")),
            "raw": raw,
            "deal": deal,
        })

    for row in inquiries:
        raw = dict(row)
        deal = None
        if raw.get("deal_id"):
            deal = {
                "id": int(raw["deal_id"]),
                "status": _clean(raw.get("deal_status")),
                "demo_date": _clean(raw.get("deal_demo_date")),
                "followup_date": _clean(raw.get("deal_followup_date")),
                "next_step": _clean(raw.get("deal_next_step")),
                "price": _clean(raw.get("deal_price")),
                "contact_person": _clean(raw.get("deal_contact_person")),
                "location": _clean(raw.get("deal_location")),
                "contact_number": _clean(raw.get("deal_contact_number")),
                "email": _clean(raw.get("deal_email")),
                "notes_after_conversation": _clean(raw.get("deal_notes_after_conversation")),
                "created_at": _clean(raw.get("deal_created_at")),
                "updated_at": _clean(raw.get("deal_updated_at")),
                "source_kind": "website",
                "source_id": int(raw["id"]),
            }
        sources.append({
            "kind": "website",
            "source_id": int(raw["id"]),
            "company": _clean(raw.get("company")),
            "contact_name": _clean(raw.get("name")),
            "email": _clean(raw.get("email")),
            "phone": _clean(raw.get("phone")),
            "workflow_status": _clean(raw.get("workflow_status")).upper() or "NOT_CONTACTED",
            "created_at": _clean(raw.get("created_at")),
            "updated_at": _clean(raw.get("updated_at")) or _clean(raw.get("created_at")),
            "raw": raw,
            "deal": deal,
        })

    return sources


def build_master_records(db, partner_id: int | None = None) -> list[dict]:
    """Build one master Records row per client journey without mutating source tables.

    Existing Prospect -> Deal and Website Inquiry -> Deal links always remain one
    lifecycle record. Separate Prospect/Website sources are automatically grouped
    only when at least two normalized identity signals agree.
    """
    sources = _query_sources(db, partner_id=partner_id)
    total = len(sources)
    if total == 0:
        return []

    parent = list(range(total))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    pair_buckets: dict[tuple, list[int]] = {}
    for index, source in enumerate(sources):
        values = _identity_values(source)
        usable = [(name, value) for name, value in values.items() if value]
        for first, second in combinations(usable, 2):
            pair_key = (first[0], first[1], second[0], second[1])
            pair_buckets.setdefault(pair_key, []).append(index)

    for indexes in pair_buckets.values():
        if len(indexes) < 2:
            continue
        base = indexes[0]
        for other in indexes[1:]:
            union(base, other)

    groups: dict[int, list[dict]] = {}
    for index, source in enumerate(sources):
        groups.setdefault(find(index), []).append(source)

    records: list[dict] = []
    for members in groups.values():
        members = sorted(members, key=_source_effective_updated)
        latest_source = max(members, key=_source_effective_updated)

        prospect_sources = [source for source in members if source["kind"] == "prospect"]
        inquiry_sources = [source for source in members if source["kind"] == "website"]

        deals_by_id: dict[int, dict] = {}
        for source in members:
            deal = source.get("deal")
            if deal:
                deals_by_id[int(deal["id"])] = deal
        deals = sorted(deals_by_id.values(), key=lambda item: (_clean(item.get("created_at")), int(item["id"])))

        first_seen_candidates = [_clean(source.get("created_at")) for source in members if _clean(source.get("created_at"))]
        first_seen_at = min(first_seen_candidates) if first_seen_candidates else ""
        last_updated_at = max((_source_effective_updated(source) for source in members), default="")

        company = _latest_nonempty(members, "company")
        contact_name = _latest_nonempty(members, "contact_name")
        email = _latest_nonempty(members, "email")
        phone = _latest_nonempty(members, "phone")
        current_status = _clean(latest_source.get("workflow_status")).upper() or "NOT_CONTACTED"

        source_steps: list[str] = []
        if prospect_sources:
            source_steps.append("Research")
        if inquiry_sources:
            source_steps.append("Website")
        if deals:
            source_steps.append("Deal")

        if prospect_sources and inquiry_sources:
            source_filter = "MULTI"
            source_label = "Research + Website"
        elif prospect_sources:
            source_filter = "RESEARCH"
            source_label = "Research"
        else:
            source_filter = "WEBSITE"
            source_label = "Website"

        can_delete = not any(
            _clean(source.get("workflow_status")).upper() in RECORD_DELETE_PROTECTED_STATUSES
            for source in members
        )

        key = _record_key(members)
        client_title = company or contact_name or email or phone or f"Record {key}"
        search_text = " ".join(
            [
                client_title,
                company,
                contact_name,
                email,
                phone,
                source_label,
                current_status,
                *[
                    _clean(source["raw"].get("system_wanted"))
                    for source in prospect_sources
                    if source.get("raw")
                ],
                *[
                    _clean(source["raw"].get("source_action") or source["raw"].get("source_title"))
                    for source in inquiry_sources
                    if source.get("raw")
                ],
            ]
        ).casefold()

        records.append({
            "record_key": key,
            "client_title": client_title,
            "company": company,
            "contact_name": contact_name,
            "email": email,
            "phone": phone,
            "current_status": current_status,
            "first_seen_at": first_seen_at,
            "last_updated_at": last_updated_at,
            "source_filter": source_filter,
            "source_label": source_label,
            "journey_steps": source_steps,
            "can_delete": can_delete,
            "search_text": search_text,
            "prospects": [source["raw"] for source in prospect_sources],
            "inquiries": [source["raw"] for source in inquiry_sources],
            "deals": deals,
            "prospect_ids": [int(source["source_id"]) for source in prospect_sources],
            "inquiry_ids": [int(source["source_id"]) for source in inquiry_sources],
            "deal_ids": [int(deal["id"]) for deal in deals],
            "source_statuses": sorted({
                _clean(source.get("workflow_status")).upper()
                for source in members
                if _clean(source.get("workflow_status"))
            }),
        })

    records.sort(
        key=lambda record: (
            _clean(record.get("last_updated_at")),
            _clean(record.get("first_seen_at")),
            record["record_key"],
        ),
        reverse=True,
    )
    return records


def find_master_record(records: list[dict], record_key: str) -> dict | None:
    target = _clean(record_key)
    for record in records:
        if record["record_key"] == target:
            return record
    return None
