"""
db/operations.py
All DB read/write functions. One shared Supabase client from db/client.py.
"""

from db.client import supabase
from uuid import UUID
from typing import Any, cast


# ---------------------------------------------------------------------------
# Generic helpers (internal use only — call the named functions below)
# supabase-py types `.data` as a broad JSON union; cast() narrows it to what
# we actually get back (a list of row dicts) without affecting runtime.
# ---------------------------------------------------------------------------

def _insert(table: str, data: dict) -> dict | None:
    result = supabase.table(table).insert(data).execute()
    rows = cast(list[dict[str, Any]], result.data)
    return rows[0] if rows else None


def _get_by_id(table: str, id_field: str, id_value: str | UUID) -> dict | None:
    result = supabase.table(table).select("*").eq(id_field, str(id_value)).execute()
    rows = cast(list[dict[str, Any]], result.data)
    return rows[0] if rows else None


def _get_all_by_fk(table: str, fk_field: str, fk_value: str | UUID) -> list[dict]:
    result = supabase.table(table).select("*").eq(fk_field, str(fk_value)).execute()
    return cast(list[dict[str, Any]], result.data) or []


def _update(table: str, id_field: str, id_value: str | UUID, data: dict) -> dict | None:
    result = supabase.table(table).update(data).eq(id_field, str(id_value)).execute()
    rows = cast(list[dict[str, Any]], result.data)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Profiles / Users
# ---------------------------------------------------------------------------

def save_profile(data: dict) -> dict | None:
    return _insert("profiles", data)

def get_profile(user_id: str) -> dict | None:
    return _get_by_id("profiles", "user_id", user_id)

def save_client_profile(data: dict) -> dict | None:
    return _insert("client_profiles", data)

def get_client_profile(client_profile_id: str) -> dict | None:
    return _get_by_id("client_profiles", "client_profile_id", client_profile_id)

def save_freelancer_profile(data: dict) -> dict | None:
    return _insert("freelancer_profiles", data)

def get_freelancer_profile(freelancer_profile_id: str) -> dict | None:
    return _get_by_id("freelancer_profiles", "freelancer_profile_id", freelancer_profile_id)


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

def save_subscription(data: dict) -> dict | None:
    return _insert("subscriptions", data)

def get_subscription_by_user(user_id: str) -> dict | None:
    result = supabase.table("subscriptions").select("*").eq("user_id", str(user_id)).execute()
    return (cast(list[dict[str, Any]], result.data) or [None])[0]


# ---------------------------------------------------------------------------
# Project + ProjectVersion
# ---------------------------------------------------------------------------

def save_project(project_data: dict) -> dict | None:
    """Creates the project AND its first ProjectVersion (v1) in one call.
    Every downstream table (requirements, price_floors, risks) FKs to
    version_id, not project_id — this must never be skipped."""
    project = _insert("projects", project_data)
    if project is None:
        raise RuntimeError("save_project: insert into 'projects' failed")
    version = _insert("project_versions", {
        "project_id": project["project_id"],
        "version_number": 1,
    })
    return {"project": project, "version": version}

def get_project(project_id: str) -> dict | None:
    return _get_by_id("projects", "project_id", project_id)

def update_project_status(project_id: str, status: str) -> dict | None:
    return _update("projects", "project_id", project_id, {"status": status})

def update_ai_processing_status(project_id: str, status: str, error_message: str | None = None) -> dict | None:
    return _update("projects", "project_id", project_id, {
        "ai_processing_status": status,
        "error_message": error_message,
    })

def get_latest_version(project_id: str) -> dict | None:
    result = (
        supabase.table("project_versions")
        .select("*")
        .eq("project_id", str(project_id))
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    return (cast(list[dict[str, Any]], result.data) or [None])[0]

def create_new_version(project_id: str) -> dict | None:
    latest = get_latest_version(project_id)
    next_number = (latest["version_number"] + 1) if latest else 1
    return _insert("project_versions", {
        "project_id": project_id,
        "version_number": next_number,
    })


# ---------------------------------------------------------------------------
# Requirements / Deliverables / Gaps / Clarifications / Conflicts
# ---------------------------------------------------------------------------

def save_requirement(data: dict) -> dict | None:
    return _insert("requirements", data)

def update_requirement(requirement_id: str, data: dict) -> dict | None:
    return _update("requirements", "requirement_id", requirement_id, data)

def get_requirements_by_version(version_id: str) -> list[dict]:
    return _get_all_by_fk("requirements", "version_id", version_id)

def save_deliverable(data: dict) -> dict | None:
    return _insert("deliverables", data)

def get_deliverables_by_requirement(requirement_id: str) -> list[dict]:
    return _get_all_by_fk("deliverables", "requirement_id", requirement_id)

def save_gap(data: dict) -> dict | None:
    return _insert("gaps", data)

def get_gaps_by_requirement(requirement_id: str) -> list[dict]:
    return _get_all_by_fk("gaps", "requirement_id", requirement_id)

def save_clarification_request(data: dict) -> dict | None:
    return _insert("clarification_requests", data)

def get_clarifications_by_gap(gap_id: str) -> list[dict]:
    return _get_all_by_fk("clarification_requests", "gap_id", gap_id)

def answer_clarification(clarification_id: str, answer_text: str, answered_by: str) -> dict | None:
    from datetime import datetime, timezone
    return _update("clarification_requests", "clarification_id", clarification_id, {
        "answer_text": answer_text,
        "status": "answered",
        "answered_at": datetime.now(timezone.utc).isoformat(),
        "answered_by": answered_by,
    })

def save_field_conflict(data: dict) -> dict | None:
    return _insert("field_conflicts", data)

def get_unresolved_conflicts(requirement_id: str) -> list[dict]:
    result = (
        supabase.table("field_conflicts")
        .select("*")
        .eq("requirement_id", str(requirement_id))
        .eq("resolved", False)
        .execute()
    )
    return cast(list[dict[str, Any]], result.data) or []

def resolve_field_conflict(conflict_id: str) -> dict | None:
    return _update("field_conflicts", "conflict_id", conflict_id, {"resolved": True})


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

def save_scope_document(data: dict) -> dict | None:
    return _insert("scope_documents", data)

def get_scope_document_by_project(project_id: str) -> dict | None:
    result = supabase.table("scope_documents").select("*").eq("project_id", str(project_id)).execute()
    return (cast(list[dict[str, Any]], result.data) or [None])[0]

def save_scope_item(data: dict) -> dict | None:
    return _insert("scope_items", data)

def get_scope_items(scope_id: str) -> list[dict]:
    return _get_all_by_fk("scope_items", "scope_id", scope_id)


# ---------------------------------------------------------------------------
# Milestones / Change Orders
# ---------------------------------------------------------------------------

def save_milestone(data: dict) -> dict | None:
    return _insert("milestones", data)

def get_milestones_by_project(project_id: str) -> list[dict]:
    result = (
        supabase.table("milestones")
        .select("*")
        .eq("project_id", str(project_id))
        .order("sequence")
        .execute()
    )
    return cast(list[dict[str, Any]], result.data) or []

def update_milestone_status(milestone_id: str, status: str) -> dict | None:
    return _update("milestones", "milestone_id", milestone_id, {"status": status})

def save_change_order(data: dict) -> dict | None:
    return _insert("change_orders", data)

def get_change_orders_by_milestone(milestone_id: str) -> list[dict]:
    return _get_all_by_fk("change_orders", "milestone_id", milestone_id)

def update_change_order_status(change_order_id: str, status: str) -> dict | None:
    return _update("change_orders", "change_order_id", change_order_id, {"status": status})


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def save_price_floor(data: dict) -> dict | None:
    return _insert("price_floors", data)

def get_price_floor_by_version(version_id: str) -> dict | None:
    result = supabase.table("price_floors").select("*").eq("version_id", str(version_id)).execute()
    return (cast(list[dict[str, Any]], result.data) or [None])[0]

def save_comparable(data: dict) -> dict | None:
    return _insert("comparables", data)

def get_comparables(price_floor_id: str) -> list[dict]:
    result = (
        supabase.table("comparables")
        .select("*")
        .eq("price_floor_id", str(price_floor_id))
        .order("similarity_rank")
        .execute()
    )
    return cast(list[dict[str, Any]], result.data) or []

def save_human_price_adjustment(data: dict) -> dict | None:
    """Audit trail only — never overwrite price_floors.amount directly."""
    return _insert("human_price_adjustments", data)

def get_price_adjustments(price_floor_id: str) -> list[dict]:
    return _get_all_by_fk("human_price_adjustments", "price_floor_id", price_floor_id)


# ---------------------------------------------------------------------------
# Negotiation
# ---------------------------------------------------------------------------

def save_negotiation_state(data: dict) -> dict | None:
    return _insert("negotiation_state", data)

def get_negotiation_state(project_id: str) -> dict | None:
    result = supabase.table("negotiation_state").select("*").eq("project_id", str(project_id)).execute()
    return (cast(list[dict[str, Any]], result.data) or [None])[0]

def update_negotiation_state(negotiation_id: str, data: dict) -> dict | None:
    return _update("negotiation_state", "negotiation_id", negotiation_id, data)

def save_negotiation_round(data: dict) -> dict | None:
    return _insert("negotiation_rounds", data)

def get_negotiation_rounds(negotiation_id: str) -> list[dict]:
    result = (
        supabase.table("negotiation_rounds")
        .select("*")
        .eq("negotiation_id", str(negotiation_id))
        .order("round_number")
        .execute()
    )
    return cast(list[dict[str, Any]], result.data) or []


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

def save_risk(data: dict) -> dict | None:
    return _insert("risks", data)

def get_risks_by_version(version_id: str) -> list[dict]:
    return _get_all_by_fk("risks", "version_id", version_id)


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------

def save_signature(data: dict) -> dict | None:
    return _insert("signatures", data)

def get_signatures_by_project(project_id: str) -> list[dict]:
    return _get_all_by_fk("signatures", "project_id", project_id)

def is_fully_signed(project_id: str) -> bool:
    sigs = get_signatures_by_project(project_id)
    roles = {s["signer_role"] for s in sigs}
    return {"client", "freelancer"}.issubset(roles)


# ---------------------------------------------------------------------------
# Processing Lock (chat UI concurrency guard)
# ---------------------------------------------------------------------------

def get_processing_lock(project_id: str) -> dict | None:
    return _get_by_id("processing_locks", "project_id", project_id)

def acquire_lock(project_id: str, locked_by: str) -> dict | None:
    from datetime import datetime, timezone
    existing = get_processing_lock(project_id)
    payload = {
        "locked": True,
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "locked_by": locked_by,
    }
    if existing:
        return _update("processing_locks", "project_id", project_id, payload)
    return _insert("processing_locks", {"project_id": project_id, **payload})

def release_lock(project_id: str) -> dict | None:
    return _update("processing_locks", "project_id", project_id, {
        "locked": False, "locked_at": None, "locked_by": None,
    })


# ---------------------------------------------------------------------------
# AI Logs
# ---------------------------------------------------------------------------

def log_gemma_call(data: dict) -> dict | None:
    return _insert("gemma_call_logs", data)

def get_gemma_calls(project_id: str) -> list[dict]:
    return _get_all_by_fk("gemma_call_logs", "project_id", project_id)

def log_ranking(data: dict) -> dict | None:
    return _insert("ranking_logs", data)

def get_ranking_logs(project_id: str) -> list[dict]:
    return _get_all_by_fk("ranking_logs", "project_id", project_id)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

def save_contract(data: dict) -> dict | None:
    return _insert("contracts", data)

def get_contract_by_project(project_id: str) -> dict | None:
    result = (
        supabase.table("contracts")
        .select("*")
        .eq("project_id", str(project_id))
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    return (cast(list[dict[str, Any]], result.data) or [None])[0]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def save_notification(data: dict) -> dict | None:
    return _insert("notifications", data)

def get_notifications_by_user(user_id: str, unread_only: bool = False) -> list[dict]:
    query = supabase.table("notifications").select("*").eq("user_id", str(user_id))
    if unread_only:
        query = query.eq("read", False)
    result = query.order("created_at", desc=True).execute()
    return cast(list[dict[str, Any]], result.data) or []

def mark_notification_read(notification_id: str) -> dict | None:
    return _update("notifications", "notification_id", notification_id, {"read": True})

def assign_freelancer(project_id: str, freelancer_profile_id: str) -> dict | None:
    return _update("projects", "project_id", project_id, {"freelancer_profile_id": freelancer_profile_id})

