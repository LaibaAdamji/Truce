"""
agents/client_agent.py
Extracts requirements from client briefs, flags gaps, manages clarifications,
and finalizes scope documents. Called standalone — not wired into CrewAI yet.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from db import operations as db
from models.schemas import (
    ClarificationRequest,
    Gap,
    Project,
    ProjectVersion,
    Requirement,
    ScopeDocument,
)
from tools.llm_client import GemmaCallError, call_gemma

CONFIDENCE_THRESHOLD = 0.7

REQUIREMENT_TYPES = ("skill", "deliverable", "budget", "timeline")

SKILL_LOW_CONFIDENCE_DESC = "Low confidence in skill requirement"
SKILL_CORRECTION_DESC = "Skill requirement needs correction"

GAP_QUESTION_TEMPLATES: dict[str, str] = {
    "No timeline specified": "What's your timeline for this project?",
    "Budget uncertain or unspecified": "What's your confirmed budget for this project?",
    "Deliverable scope unclear": "What specific deliverables do you need for this project?",
    SKILL_CORRECTION_DESC: "What skill or expertise do you actually need for this project?",
}

STRICT_JSON_SUFFIX = (
    "\n\nReturn ONLY valid JSON, no other text. "
    "Do not include markdown fences or explanations."
)

EXTRACTION_PROMPT = """Extract freelance project requirements from the client brief below.

Return JSON with exactly this structure:
{{
  "requirements": [
    {{
      "type": "skill" | "deliverable" | "budget" | "timeline",
      "value": "<string describing the requirement>",
      "timeline": "<string or null>",
      "budget_hint": <number or null>,
      "confidence": <float between 0 and 1>
    }}
  ]
}}

Create one entry per type (skill, deliverable, budget, timeline) when the brief
mentions or implies it. Use null for unknown fields and lower confidence when
the client is uncertain.

Brief:
{brief}
"""


class ClientAgentError(Exception):
    """Raised when client agent processing fails after retries."""


def create_project(
    client_profile_id: str,
    title: str,
    brief_text: str,
) -> tuple[Project, ProjectVersion]:
    """Step 1: create a draft project and its first version (v1)."""
    result = db.save_project({
        "client_profile_id": client_profile_id,
        "title": title,
        "description": brief_text,
        "status": "draft",
        "ai_processing_status": "pending",
    })
    if result is None:
        raise ClientAgentError("create_project: save_project returned None")
    project = Project(**result["project"])
    version = ProjectVersion(**result["version"])
    return project, version


def extract_requirements(
    project_id: str,
    version_id: str,
    brief_text: str,
) -> list[Gap]:
    """
    Steps 2–4: extract requirements, detect gaps, create clarification requests.
    Persists each row as it is produced. Stops here for caller to collect answers.
    """
    parsed = _call_extraction_llm(project_id, brief_text)
    _persist_requirements(version_id, parsed)

    requirements = _load_requirements(version_id)
    gaps = _detect_gaps(requirements)
    return _create_gaps_and_clarifications(gaps)


def submit_clarifications(
    project_id: str,
    version_id: str,
    answers: dict[str, str],
    answered_by: str | None = None,
) -> list[Gap]:
    """
    Steps 5–7: record client answers, re-extract requirements with added context,
    update existing rows, and return any NEW gaps (empty list if none).
    """
    _record_answers(answers, answered_by, version_id)

    project = db.get_project(project_id)
    if project is None:
        raise ClientAgentError(f"submit_clarifications: project {project_id} not found")

    original_brief = project.get("description") or ""
    context = _build_clarification_context(version_id)
    enriched_brief = f"{original_brief}\n\nAdditional client answers:\n{context}"

    parsed = _call_extraction_llm(project_id, enriched_brief)
    _persist_requirements(version_id, parsed)

    requirements = _load_requirements(version_id)
    all_gaps = _detect_gaps(requirements)
    new_gaps = _filter_new_gaps(all_gaps, version_id)
    if not new_gaps:
        return []
    return _create_gaps_and_clarifications(new_gaps)


def finalize_scope(project_id: str, version_id: str) -> ScopeDocument:
    """
    Step 8–10: build scope document + items, persist, update project status.
    Requirements never gap-flagged are tagged as assumptions (not dropped).
    """
    requirements = _load_requirements(version_id)
    reviewed_req_ids = _client_reviewed_requirement_ids(version_id)

    scope_row = db.save_scope_document({"project_id": project_id})
    if scope_row is None:
        raise ClientAgentError("finalize_scope: failed to save scope document")

    scope = ScopeDocument(**scope_row)

    for req in requirements:
        req_id = str(req.requirement_id)
        if req_id in reviewed_req_ids:
            item_type = "included"
        else:
            item_type = "assumption"

        text = _requirement_scope_text(req)
        item_row = db.save_scope_item({
            "scope_id": str(scope.scope_id),
            "item_type": item_type,
            "text": text,
        })
        if item_row is None:
            raise ClientAgentError(
                f"finalize_scope: failed to save scope item for requirement {req_id}"
            )

    db.update_project_status(project_id, "requirements_extracted")
    db.update_ai_processing_status(project_id, "done")

    return scope


def assign_freelancer(project_id: str, freelancer_profile_id: str) -> None:
    """Step 11: plain assignment — no AI logic."""
    result = db.assign_freelancer(project_id, freelancer_profile_id)
    if result is None:
        raise ClientAgentError(
            f"assign_freelancer: failed to assign freelancer to project {project_id}"
        )


# ---------------------------------------------------------------------------
# LLM + parsing
# ---------------------------------------------------------------------------

def _call_extraction_llm(project_id: str, brief_text: str) -> list[dict[str, Any]]:
    prompt = EXTRACTION_PROMPT.format(brief=brief_text)
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            current_prompt = prompt if attempt == 0 else prompt + STRICT_JSON_SUFFIX
            raw = call_gemma(
                agent_name="client_agent",
                purpose="requirement_extraction",
                prompt=current_prompt,
                project_id=project_id,
                temperature=0.1 if attempt == 1 else 0.3,
            )
            return _parse_extraction_response(raw)
        except (GemmaCallError, ClientAgentError, json.JSONDecodeError, ValidationError) as e:
            last_error = e

    raise ClientAgentError(
        f"Requirement extraction failed after retry: {last_error}"
    ) from last_error


def _parse_extraction_response(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    data = json.loads(text)
    if not isinstance(data, dict) or "requirements" not in data:
        raise ClientAgentError("LLM response missing 'requirements' key")

    requirements_raw = data["requirements"]
    if not isinstance(requirements_raw, list):
        raise ClientAgentError("'requirements' must be a list")

    validated: list[dict[str, Any]] = []
    for item in requirements_raw:
        if not isinstance(item, dict):
            raise ClientAgentError("Each requirement must be an object")
        req_type = item.get("type")
        if req_type not in REQUIREMENT_TYPES:
            raise ClientAgentError(f"Invalid requirement type: {req_type}")

        model = Requirement(
            requirement_id=UUID(int=0),
            version_id=UUID(int=0),
            type=req_type,
            value=str(item.get("value", "")),
            timeline=item.get("timeline"),
            budget_hint=item.get("budget_hint"),
            confidence=float(item.get("confidence", 0.0)),
        )
        validated.append({
            "type": model.type,
            "value": model.value,
            "timeline": model.timeline,
            "budget_hint": model.budget_hint,
            "confidence": model.confidence,
        })

    return validated


def _persist_requirements(
    version_id: str,
    parsed: list[dict[str, Any]],
) -> None:
    existing_by_type: dict[str, dict] = {
        row["type"]: row for row in db.get_requirements_by_version(version_id)
    }

    for item in parsed:
        payload = {
            "version_id": version_id,
            "type": item["type"],
            "value": item["value"],
            "timeline": item["timeline"],
            "budget_hint": item["budget_hint"],
            "confidence": item["confidence"],
        }
        if item["type"] in existing_by_type:
            req_id = existing_by_type[item["type"]]["requirement_id"]
            result = db.update_requirement(req_id, payload)
            if result is None:
                raise ClientAgentError(
                    f"Failed to update requirement type={item['type']}"
                )
        else:
            result = db.save_requirement(payload)
            if result is None:
                raise ClientAgentError(
                    f"Failed to save requirement type={item['type']}"
                )


# ---------------------------------------------------------------------------
# Gap detection (deterministic — no LLM)
# ---------------------------------------------------------------------------

def _detect_gaps(requirements: list[Requirement]) -> list[tuple[Requirement, str]]:
    gaps: list[tuple[Requirement, str]] = []

    for req in requirements:
        description = _gap_description_for_requirement(req)
        if description:
            gaps.append((req, description))

    return gaps


def _gap_description_for_requirement(req: Requirement) -> str | None:
    if req.type == "timeline":
        if req.timeline is None or not str(req.timeline).strip():
            return "No timeline specified"
        if req.confidence < CONFIDENCE_THRESHOLD:
            return "No timeline specified"

    if req.type == "budget":
        if req.budget_hint is None or req.confidence < CONFIDENCE_THRESHOLD:
            return "Budget uncertain or unspecified"

    if req.type == "deliverable" and req.confidence < CONFIDENCE_THRESHOLD:
        return "Deliverable scope unclear"

    if req.confidence < CONFIDENCE_THRESHOLD:
        return f"Low confidence in {req.type} requirement"

    return None


def _gap_to_question(description: str, req: Requirement) -> str:
    if req.type == "skill" and description == SKILL_LOW_CONFIDENCE_DESC:
        return (
            f'We understood you need this skill: "{req.value}". '
            "Is that correct? (yes/no)"
        )
    if description in GAP_QUESTION_TEMPLATES:
        return GAP_QUESTION_TEMPLATES[description]
    if description.startswith("Low confidence in "):
        parts = description.replace("Low confidence in ", "").split(" requirement", 1)
        req_type = parts[0] if parts else "this"
        return f"Can you provide more detail about the {req_type} requirement?"
    return f"Can you clarify: {description}?"


def _create_gaps_and_clarifications(
    gap_pairs: list[tuple[Requirement, str]],
) -> list[Gap]:
    saved_gaps: list[Gap] = []

    for req, description in gap_pairs:
        gap_row = db.save_gap({
            "requirement_id": str(req.requirement_id),
            "description": description,
        })
        if gap_row is None:
            raise ClientAgentError(f"Failed to save gap: {description}")

        gap = Gap(**gap_row)
        saved_gaps.append(gap)

        clar_row = db.save_clarification_request({
            "gap_id": str(gap.gap_id),
            "question_text": _gap_to_question(description, req),
            "status": "pending",
            "asked_at": datetime.now(timezone.utc).isoformat(),
        })
        if clar_row is None:
            raise ClientAgentError(
                f"Failed to save clarification for gap {gap.gap_id}"
            )

    return saved_gaps


def _filter_new_gaps(
    gap_pairs: list[tuple[Requirement, str]],
    version_id: str,
) -> list[tuple[Requirement, str]]:
    """
    A gap is genuinely "new" only if this requirement+description combo has
    never been asked about before. If it was already answered, it's resolved
    — skip it. If it's still pending (client hasn't gotten to it yet), it's
    NOT new either — skip it too, so we don't mint a duplicate gap/clarification
    row for a question that's already sitting in front of the client.
    """
    answered_descriptions = _answered_gap_descriptions(version_id)
    pending_descriptions = _pending_gap_descriptions(version_id)
    result = []
    for req, desc in gap_pairs:
        req_id = str(req.requirement_id)
        if desc in answered_descriptions.get(req_id, set()):
            continue
        if desc in pending_descriptions.get(req_id, set()):
            continue
        result.append((req, desc))
    return result


def _answered_gap_descriptions(version_id: str) -> dict[str, set[str]]:
    answered: dict[str, set[str]] = {}
    for req in _load_requirements(version_id):
        req_id = str(req.requirement_id)
        for gap_row in db.get_gaps_by_requirement(req_id):
            for clar_row in db.get_clarifications_by_gap(gap_row["gap_id"]):
                if clar_row.get("status") == "answered":
                    answered.setdefault(req_id, set()).add(gap_row["description"])
    return answered


def _pending_gap_descriptions(version_id: str) -> dict[str, set[str]]:
    """Descriptions that already have an open (pending, unanswered) clarification."""
    pending: dict[str, set[str]] = {}
    for req in _load_requirements(version_id):
        req_id = str(req.requirement_id)
        for gap_row in db.get_gaps_by_requirement(req_id):
            for clar_row in db.get_clarifications_by_gap(gap_row["gap_id"]):
                if clar_row.get("status") == "pending":
                    pending.setdefault(req_id, set()).add(gap_row["description"])
    return pending


# ---------------------------------------------------------------------------
# Clarifications
# ---------------------------------------------------------------------------

def _is_negative_answer(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized.startswith("no") or normalized in {"n", "nope", "incorrect", "wrong"}


def _find_gap_and_requirement(
    version_id: str,
    gap_id: str,
) -> tuple[Requirement, dict] | None:
    """Locate the (Requirement, gap_row) pair for a given gap_id, reusing the
    same DB read functions used elsewhere (no new DB access patterns)."""
    for req in _load_requirements(version_id):
        for gap_row in db.get_gaps_by_requirement(str(req.requirement_id)):
            if gap_row["gap_id"] == gap_id:
                return req, gap_row
    return None


def _record_answers(
    answers: dict[str, str],
    answered_by: str | None,
    version_id: str,
) -> None:
    for gap_id, answer_text in answers.items():
        pending = _get_pending_clarification(gap_id)
        if pending is None:
            raise ClientAgentError(
                f"No pending clarification found for gap {gap_id}"
            )
        result = db.answer_clarification(
            pending["clarification_id"],
            answer_text,
            answered_by,
        )
        if result is None:
            raise ClientAgentError(
                f"Failed to record answer for gap {gap_id}"
            )

        # Skill assumptions are asked as yes/no. A "no" means the LLM's
        # guess was wrong — don't treat it as resolved. Instead, deterministically
        # (no LLM) open a fresh, explicit follow-up question asking what the
        # skill actually is, so the client gets asked directly rather than the
        # agent silently re-guessing on the next extraction pass.
        found = _find_gap_and_requirement(version_id, gap_id)
        if found:
            req, gap_row = found
            if (
                req.type == "skill"
                and gap_row["description"] == SKILL_LOW_CONFIDENCE_DESC
                and _is_negative_answer(answer_text)
            ):
                _create_gaps_and_clarifications([(req, SKILL_CORRECTION_DESC)])


def _get_pending_clarification(gap_id: str) -> dict | None:
    for clar in db.get_clarifications_by_gap(gap_id):
        if clar.get("status") == "pending":
            return clar
    return None


def _build_clarification_context(version_id: str) -> str:
    lines: list[str] = []
    for req in _load_requirements(version_id):
        req_id = str(req.requirement_id)
        for gap_row in db.get_gaps_by_requirement(req_id):
            for clar_row in db.get_clarifications_by_gap(gap_row["gap_id"]):
                if clar_row.get("status") == "answered" and clar_row.get("answer_text"):
                    q = clar_row["question_text"]
                    a = clar_row["answer_text"]
                    lines.append(f"- Q: {q}\n  A: {a}")
    return "\n".join(lines) if lines else "(none)"


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------

def _client_reviewed_requirement_ids(version_id: str) -> set[str]:
    reviewed: set[str] = set()
    for req in _load_requirements(version_id):
        req_id = str(req.requirement_id)
        for gap_row in db.get_gaps_by_requirement(req_id):
            for clar_row in db.get_clarifications_by_gap(gap_row["gap_id"]):
                if clar_row.get("status") != "answered":
                    continue
                if (
                    req.type == "skill"
                    and gap_row["description"] == SKILL_LOW_CONFIDENCE_DESC
                    and _is_negative_answer(clar_row.get("answer_text") or "")
                ):
                    # Client rejected the assumption — not resolved until the
                    # SKILL_CORRECTION_DESC follow-up is itself answered.
                    continue
                reviewed.add(req_id)
                break
    return reviewed


def _requirement_scope_text(req: Requirement) -> str:
    parts = [f"{req.type.title()}: {req.value}"]
    if req.timeline:
        parts.append(f"Timeline: {req.timeline}")
    if req.budget_hint is not None:
        parts.append(f"Budget hint: ${req.budget_hint:,.0f}")
    parts.append(f"Confidence: {req.confidence:.0%}")
    return " | ".join(parts)


def _load_requirements(version_id: str) -> list[Requirement]:
    rows = db.get_requirements_by_version(version_id)
    return [Requirement(**row) for row in rows]


def get_clarifications_for_version(version_id: str) -> list[ClarificationRequest]:
    """Helper for callers/tests to fetch pending or answered clarifications."""
    clarifications: list[ClarificationRequest] = []
    for req in _load_requirements(version_id):
        for gap_row in db.get_gaps_by_requirement(str(req.requirement_id)):
            for clar_row in db.get_clarifications_by_gap(gap_row["gap_id"]):
                clarifications.append(ClarificationRequest(**clar_row))
    return clarifications