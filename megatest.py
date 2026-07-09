"""
test_full_pipeline_vague_brief.py
Full base-pipeline rehearsal — NOT a pinned/deterministic scenario test.

Unlike test_negotiation_scenarios.py (which pins floor/ceiling to force a
specific outcome), this test runs the entire pipeline for real, start to
finish, from a deliberately vague/incomplete brief:

    vague brief -> gap detection -> clarification loop (multi-round) ->
    real price floor reasoning -> real negotiation -> terminal outcome

Nothing is pinned. Floor and ceiling both come from real LLM output, so the
final negotiation outcome (converged vs capped_no_deal) is genuinely
determined by the pipeline, not scripted. rate_expectation is set safely
below the stated budget ceiling to bias toward convergence (same pattern
used in your original golden-path script) — but it is a bias, not a
guarantee, and that's the point: this is your closest proxy for what a real
judge/demo run looks like.

This is your "manual golden-path rehearsal" per the roadmap — read the
printed trace, don't just check the final PASS/FAIL line.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from agents.client_agent import (
    assign_freelancer,
    create_project,
    extract_requirements,
    finalize_scope,
    get_clarifications_for_version,
    submit_clarifications,
)
from agents.freelancer_agent import compute_price_floor
from agents.mediator_agent import run_negotiation
from config.settings import settings
from db import operations as db

load_dotenv()

# Deliberately vague: no named skill/tech stack, soft deliverable, fuzzy
# budget language, no timeline. Should trigger multiple distinct gaps
# (skill correction, deliverable scope, budget uncertain, no timeline).
VAGUE_BRIEF = (
    "I need some help getting my small business online. Not totally sure "
    "what I need built yet, but budget is tight. Whatever's fastest to get "
    "started works for me."
)

# Answers keyed by topic. Realistic, specific enough for the LLM to extract
# clean structured values on the re-extraction pass.
FIXTURE_ANSWERS = {
    "skill": "A frontend developer comfortable with React or Next.js.",
    "deliverable": "A single-page marketing website with a contact form — no backend, no e-commerce.",
    "budget": "Up to $40 per hour, ideally less.",
    "timeline": "Would like it done within 2 weeks.",
}

ROUND_CAP = 5
MAX_CLARIFICATION_ROUNDS = 5

# Kept safely under the stated $40/hr ceiling to bias toward convergence —
# a bias, not a forced outcome. The freelancer LLM still reasons its own floor.
RATE_EXPECTATION = 28.0


def _topic_for_clarification(question_text: str) -> str | None:
    q = question_text.lower()
    if "skill" in q or "expertise" in q:
        return "skill"
    if "deliverable" in q or "scope" in q:
        return "deliverable"
    if "budget" in q:
        return "budget"
    if "timeline" in q:
        return "timeline"
    return None


def _ensure_freelancer_profile(client_profile_id: str, rate_expectation: float) -> str:
    env_id = os.environ.get("FREELANCER_PROFILE_ID")
    if env_id and db.get_freelancer_profile(env_id):
        return env_id

    client = db.get_client_profile(client_profile_id)
    if client is None:
        raise RuntimeError(f"Client profile not found: {client_profile_id}")

    row = db.save_freelancer_profile({
        "user_id": client["user_id"],
        "skills": ["React", "Next.js"],
        "years_experience": 3,
        "rate_expectation": rate_expectation,
    })
    if row is None:
        raise RuntimeError("Failed to create demo freelancer profile")
    return str(row["freelancer_profile_id"])


def run_full_pipeline(client_profile_id: str) -> bool:
    print("\n=== FULL PIPELINE — vague brief golden path ===")
    print(f"Brief: {VAGUE_BRIEF!r}\n")

    original_cap = settings.NEGOTIATION_ROUND_CAP
    settings.NEGOTIATION_ROUND_CAP = ROUND_CAP
    try:
        freelancer_profile_id = _ensure_freelancer_profile(client_profile_id, RATE_EXPECTATION)

        # --- Client Agent: intake + gap detection ---
        project, version = create_project(
            client_profile_id=client_profile_id,
            title="Full pipeline test — vague brief",
            brief_text=VAGUE_BRIEF,
        )
        project_id, version_id = str(project.project_id), str(version.version_id)
        print(f"project_id={project_id} version_id={version_id}")

        extract_requirements(project_id, version_id, VAGUE_BRIEF)

        # --- Clarification loop: keep answering until no gaps remain ---
        rounds = 0
        while rounds < MAX_CLARIFICATION_ROUNDS:
            pending = [
                c for c in get_clarifications_for_version(version_id) if c.status == "pending"
            ]
            if not pending:
                break
            rounds += 1
            print(f"\n--- Clarification round {rounds}: {len(pending)} gap(s) ---")
            answers: dict[str, str] = {}
            for clar in pending:
                topic = _topic_for_clarification(clar.question_text)
                print(f"  Q: {clar.question_text}  (topic={topic})")
                if topic and topic in FIXTURE_ANSWERS:
                    answers[str(clar.gap_id)] = FIXTURE_ANSWERS[topic]
                    print(f"  A: {FIXTURE_ANSWERS[topic]}")
                else:
                    print("  A: (no fixture answer for this topic — stopping)")
            if not answers:
                print("FAIL: unmatched clarification topic(s), see above")
                return False
            submit_clarifications(project_id, version_id, answers)
        else:
            print("FAIL: clarification loop did not settle within MAX_CLARIFICATION_ROUNDS")
            return False

        print(f"\nClarifications resolved after {rounds} round(s).")

        # --- Finalize scope, assign freelancer ---
        scope = finalize_scope(project_id, version_id)
        assign_freelancer(project_id, freelancer_profile_id)
        print(f"Scope finalized: scope_id={scope.scope_id}")

        # --- Freelancer Agent: real price floor reasoning ---
        price_floor = compute_price_floor(
            project_id=project_id,
            version_id=version_id,
            freelancer_profile_id=freelancer_profile_id,
            rate_expectation=RATE_EXPECTATION,
        )
        print(f"\nPrice floor: ${price_floor.amount}/hr (confidence={price_floor.confidence})")
        print(f"  reasoning: {price_floor.reasoning}")

        budget_req = next(
            (r for r in db.get_requirements_by_version(version_id) if r["type"] == "budget"),
            None,
        )
        ceiling = budget_req.get("budget_hint") if budget_req else None
        print(f"Client ceiling (extracted): ${ceiling}/hr")

        # --- Mediator Agent: real negotiation, no pinning ---
        state = run_negotiation(project_id, version_id)
        print(f"\nNegotiation result: status={state.status} round_count={state.round_count} "
              f"offer=${state.current_offer}/hr")

        # --- Read back persisted project status (surfaces enum/constraint bugs) ---
        project_row = db.get_project(project_id)
        print(f"Persisted project.status={project_row.get('status') if project_row else '???'}")

        gemma_logs = db.get_gemma_calls(project_id)
        by_agent: dict[str, int] = {}
        for log in gemma_logs:
            by_agent[log.get("agent_name", "?")] = by_agent.get(log.get("agent_name", "?"), 0) + 1
        print(f"Gemma call counts: {by_agent}")

        ok = state.status in ("converged", "capped_no_deal")
        print("\nPASS" if ok else "FAIL: unexpected terminal status")
        return ok

    except Exception as exc:
        print(f"\nFAIL (exception): {exc}")
        return False
    finally:
        settings.NEGOTIATION_ROUND_CAP = original_cap


def main() -> int:
    client_profile_id = os.environ.get("CLIENT_PROFILE_ID")
    if not client_profile_id:
        print("Set CLIENT_PROFILE_ID", file=sys.stderr)
        return 1

    ok = run_full_pipeline(client_profile_id)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())