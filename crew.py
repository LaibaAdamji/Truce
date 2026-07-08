"""
crew.py
Orchestrates the Truce multi-agent pipeline: Client → Freelancer → Mediator.

Business logic lives in agents/*.py. This module wires them sequentially and
optionally exposes a thin CrewAI wrapper for demo purposes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from agents.client_agent import (
    ClientAgentError,
    assign_freelancer,
    create_project,
    extract_requirements,
    finalize_scope,
    get_clarifications_for_version,
    submit_clarifications,
)
from agents.freelancer_agent import FreelancerAgentError, compute_price_floor
from agents.mediator_agent import MediatorAgentError, get_negotiation_summary, run_negotiation
from db import operations as db
from models.schemas import (
    ClarificationRequest,
    NegotiationState,
    PriceFloor,
    ScopeDocument,
)


@dataclass
class PipelineResult:
    stage: Literal[
        "awaiting_clarifications",
        "negotiation_complete",
        "no_deal",
        "failed",
    ]
    project_id: str
    version_id: str
    pending_clarifications: list[ClarificationRequest] | None = None
    scope: ScopeDocument | None = None
    price_floor: PriceFloor | None = None
    negotiation: NegotiationState | None = None
    error: str | None = None
    orchestration: str = field(default="procedural")


def run_truce_pipeline(
    client_profile_id: str,
    title: str,
    brief_text: str,
    freelancer_profile_id: str,
    rate_expectation: float,
    clarification_answers: dict[str, str] | None = None,
    project_id: str | None = None,
    version_id: str | None = None,
    use_crewai: bool = False,
) -> PipelineResult:
    """
    Run (or resume) the full Truce pipeline.

    First call without project_id: creates project, extracts requirements, and
    returns awaiting_clarifications if gaps remain.

    Resume with project_id, version_id, and clarification_answers to continue.
    Pass all answers upfront for a single-shot golden-path demo.
    """
    if use_crewai and clarification_answers is not None and project_id is None:
        return run_truce_pipeline_crewai(
            client_profile_id=client_profile_id,
            title=title,
            brief_text=brief_text,
            freelancer_profile_id=freelancer_profile_id,
            rate_expectation=rate_expectation,
            clarification_answers=clarification_answers,
        )

    try:
        if project_id is None or version_id is None:
            project, version = create_project(
                client_profile_id=client_profile_id,
                title=title,
                brief_text=brief_text,
            )
            project_id = str(project.project_id)
            version_id = str(version.version_id)
            extract_requirements(project_id, version_id, brief_text)

        if clarification_answers:
            submit_clarifications(project_id, version_id, clarification_answers)

        pending = _pending_clarifications(version_id)
        if pending:
            return PipelineResult(
                stage="awaiting_clarifications",
                project_id=project_id,
                version_id=version_id,
                pending_clarifications=pending,
            )

        project = db.get_project(project_id)
        if project is None:
            raise ClientAgentError(f"Project {project_id} not found")

        scope: ScopeDocument | None = None
        price_floor: PriceFloor | None = None

        scope_row = db.get_scope_document_by_project(project_id)
        if scope_row is None:
            scope = finalize_scope(project_id, version_id)
            assign_freelancer(project_id, freelancer_profile_id)
        else:
            scope = ScopeDocument(**scope_row)
            if project.get("freelancer_profile_id") is None:
                assign_freelancer(project_id, freelancer_profile_id)

        floor_row = db.get_price_floor_by_version(version_id)
        if floor_row is None:
            price_floor = compute_price_floor(
                project_id=project_id,
                version_id=version_id,
                freelancer_profile_id=freelancer_profile_id,
                rate_expectation=rate_expectation,
            )
        else:
            price_floor = PriceFloor(**floor_row)

        negotiation = get_negotiation_summary(project_id)
        if negotiation is None or negotiation.status == "open":
            negotiation = run_negotiation(project_id, version_id)

        if negotiation.status == "capped_no_deal":
            return PipelineResult(
                stage="no_deal",
                project_id=project_id,
                version_id=version_id,
                scope=scope,
                price_floor=price_floor,
                negotiation=negotiation,
            )

        return PipelineResult(
            stage="negotiation_complete",
            project_id=project_id,
            version_id=version_id,
            scope=scope,
            price_floor=price_floor,
            negotiation=negotiation,
        )

    except (ClientAgentError, FreelancerAgentError, MediatorAgentError) as exc:
        if project_id:
            db.update_ai_processing_status(project_id, "failed", str(exc))
        return PipelineResult(
            stage="failed",
            project_id=project_id or "",
            version_id=version_id or "",
            error=str(exc),
        )
    except Exception as exc:
        if project_id:
            db.update_ai_processing_status(project_id, "failed", str(exc))
        return PipelineResult(
            stage="failed",
            project_id=project_id or "",
            version_id=version_id or "",
            error=str(exc),
        )


def run_truce_pipeline_crewai(
    client_profile_id: str,
    title: str,
    brief_text: str,
    freelancer_profile_id: str,
    rate_expectation: float,
    clarification_answers: dict[str, str],
) -> PipelineResult:
    """
    CrewAI-native single-shot runner. Requires all clarification answers upfront.
    Falls back to procedural orchestration on CrewAI failure.
    """
    try:
        from crewai import Agent, Crew, Process, Task
        from crewai.tools import tool

        pipeline_state: dict[str, str] = {}

        @tool("run_truce_pipeline_step")
        def run_truce_pipeline_step(step_payload: str) -> str:
            """Execute one Truce pipeline stage. Input is JSON with step name and args."""
            payload = json.loads(step_payload)
            step = payload["step"]

            if step == "create_and_extract":
                project, version = create_project(
                    client_profile_id=payload["client_profile_id"],
                    title=payload["title"],
                    brief_text=payload["brief_text"],
                )
                project_id = str(project.project_id)
                version_id = str(version.version_id)
                extract_requirements(project_id, version_id, payload["brief_text"])
                pipeline_state["project_id"] = project_id
                pipeline_state["version_id"] = version_id
                return json.dumps({"project_id": project_id, "version_id": version_id})

            if step == "submit_clarifications":
                submit_clarifications(
                    pipeline_state["project_id"],
                    pipeline_state["version_id"],
                    payload["answers"],
                )
                pending = _pending_clarifications(pipeline_state["version_id"])
                return json.dumps({"pending_count": len(pending)})

            if step == "finalize_and_assign":
                scope = finalize_scope(
                    pipeline_state["project_id"],
                    pipeline_state["version_id"],
                )
                assign_freelancer(
                    pipeline_state["project_id"],
                    payload["freelancer_profile_id"],
                )
                return json.dumps({"scope_id": str(scope.scope_id)})

            if step == "compute_price_floor":
                floor = compute_price_floor(
                    project_id=pipeline_state["project_id"],
                    version_id=pipeline_state["version_id"],
                    freelancer_profile_id=payload["freelancer_profile_id"],
                    rate_expectation=payload["rate_expectation"],
                )
                return json.dumps({"price_floor_id": str(floor.price_floor_id)})

            if step == "run_negotiation":
                state = run_negotiation(
                    pipeline_state["project_id"],
                    pipeline_state["version_id"],
                )
                return json.dumps({
                    "status": state.status,
                    "current_offer": state.current_offer,
                })

            raise ValueError(f"Unknown pipeline step: {step}")

        client_crew_agent = Agent(
            role="Client Agent",
            goal="Extract requirements and finalize project scope",
            backstory="Handles client briefs, clarifications, and scope documents.",
            tools=[run_truce_pipeline_step],
            verbose=False,
        )
        freelancer_crew_agent = Agent(
            role="Freelancer Agent",
            goal="Compute a fair market-based price floor",
            backstory="Analyzes comparables to set a defensible minimum rate.",
            tools=[run_truce_pipeline_step],
            verbose=False,
        )
        mediator_crew_agent = Agent(
            role="Mediator Agent",
            goal="Run bounded price negotiation to convergence",
            backstory="Facilitates agreement between client ceiling and freelancer floor.",
            tools=[run_truce_pipeline_step],
            verbose=False,
        )

        tasks = [
            Task(
                description=(
                    "Call run_truce_pipeline_step with JSON: "
                    f'{{"step":"create_and_extract","client_profile_id":"{client_profile_id}",'
                    f'"title":{json.dumps(title)},"brief_text":{json.dumps(brief_text)}}}'
                ),
                expected_output="JSON with project_id and version_id",
                agent=client_crew_agent,
            ),
            Task(
                description=(
                    "Call run_truce_pipeline_step with JSON: "
                    f'{{"step":"submit_clarifications","answers":{json.dumps(clarification_answers)}}}'
                ),
                expected_output="JSON with pending_count of 0",
                agent=client_crew_agent,
            ),
            Task(
                description=(
                    "Call run_truce_pipeline_step with JSON: "
                    f'{{"step":"finalize_and_assign","freelancer_profile_id":"{freelancer_profile_id}"}}'
                ),
                expected_output="JSON with scope_id",
                agent=client_crew_agent,
            ),
            Task(
                description=(
                    "Call run_truce_pipeline_step with JSON: "
                    f'{{"step":"compute_price_floor","freelancer_profile_id":"{freelancer_profile_id}",'
                    f'"rate_expectation":{rate_expectation}}}'
                ),
                expected_output="JSON with price_floor_id",
                agent=freelancer_crew_agent,
            ),
            Task(
                description='Call run_truce_pipeline_step with JSON: {"step":"run_negotiation"}',
                expected_output="JSON with negotiation status and current_offer",
                agent=mediator_crew_agent,
            ),
        ]

        crew = Crew(
            agents=[client_crew_agent, freelancer_crew_agent, mediator_crew_agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
        )
        crew.kickoff()

        project_id = pipeline_state.get("project_id", "")
        version_id = pipeline_state.get("version_id", "")
        if not project_id or not version_id:
            raise RuntimeError("CrewAI pipeline did not produce project identifiers")

        scope_row = db.get_scope_document_by_project(project_id)
        floor_row = db.get_price_floor_by_version(version_id)
        negotiation = get_negotiation_summary(project_id)

        stage: Literal["negotiation_complete", "no_deal", "failed"] = "negotiation_complete"
        if negotiation is None:
            stage = "failed"
        elif negotiation.status == "capped_no_deal":
            stage = "no_deal"

        return PipelineResult(
            stage=stage,
            project_id=project_id,
            version_id=version_id,
            scope=ScopeDocument(**scope_row) if scope_row else None,
            price_floor=PriceFloor(**floor_row) if floor_row else None,
            negotiation=negotiation,
            orchestration="crewai",
        )

    except Exception:
        result = run_truce_pipeline(
            client_profile_id=client_profile_id,
            title=title,
            brief_text=brief_text,
            freelancer_profile_id=freelancer_profile_id,
            rate_expectation=rate_expectation,
            clarification_answers=clarification_answers,
            use_crewai=False,
        )
        result.orchestration = "procedural_fallback"
        return result


def _pending_clarifications(version_id: str) -> list[ClarificationRequest]:
    return [
        clar
        for clar in get_clarifications_for_version(version_id)
        if clar.status == "pending"
    ]


if __name__ == "__main__":
    import os
    import sys

    client_profile_id = os.environ.get("CLIENT_PROFILE_ID")
    freelancer_profile_id = os.environ.get("FREELANCER_PROFILE_ID")

    if not client_profile_id or not freelancer_profile_id:
        print(
            "Set CLIENT_PROFILE_ID and FREELANCER_PROFILE_ID in the environment.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    demo_brief = (
        "Need a landing page redesign for my business. Budget around $45/hr max, "
        "timeline 3 weeks, looking for a Next.js developer."
    )
    demo_answers: dict[str, str] | None = None

    # Bug 3 fix: use a rate safely under the $45/hr ceiling
    result = run_truce_pipeline(
        client_profile_id=client_profile_id,
        title="Golden path demo",
        brief_text=demo_brief,
        freelancer_profile_id=freelancer_profile_id,
        rate_expectation=40.0,   # was 50.0, guaranteed to exceed $45 ceiling
        clarification_answers=demo_answers,
    )

    print(f"stage={result.stage}")
    print(f"project_id={result.project_id}")
    print(f"version_id={result.version_id}")
    if result.pending_clarifications:
        print(f"pending_clarifications={len(result.pending_clarifications)}")
    if result.negotiation:
        print(
            f"negotiation status={result.negotiation.status} "
            f"offer={result.negotiation.current_offer}"
        )
    if result.error:
        print(f"error={result.error}", file=sys.stderr)
        raise SystemExit(1)