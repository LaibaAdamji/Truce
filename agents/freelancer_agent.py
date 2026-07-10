"""
agents/freelancer_agent.py
Reasons a fair price floor from market comparables. Follows the same
call/parse/retry pattern as client_agent.py.
"""
from __future__ import annotations
import json
import re
from typing import Any
from pydantic import ValidationError
from tools.rate_ranking import rank_rate
from db import operations as db
from models.schemas import PriceFloor, Comparable
from tools.llm_client import GemmaCallError, call_gemma
from tools.market_research import get_comparables

STRICT_JSON_SUFFIX = (
    "\n\nReturn ONLY valid JSON, no other text. "
    "Do not include markdown fences or explanations."
)

PRICE_FLOOR_PROMPT = """Given these comparable freelance rates:
{comparables}

And this freelancer's stated rate expectation: ${rate_expectation}/hr

Reason a fair minimum acceptable rate (price floor) for this project.
Return JSON with exactly this structure:
{{
  "amount": <float, hourly rate floor>,
  "reasoning": "<string, 1-2 sentences>",
  "confidence": <float between 0 and 1>
}}
"""


class FreelancerAgentError(Exception):
    pass


def compute_price_floor(
    project_id: str,
    version_id: str,
    freelancer_profile_id: str,
    rate_expectation: float,
) -> PriceFloor:
    comparables = get_comparables()
    comp_text = "\n".join(f"- {c['text']}" for c in comparables)
    parsed = _call_price_floor_llm(project_id,comp_text, rate_expectation)

    floor_row = db.save_price_floor({
        "version_id": version_id,
        "amount": parsed["amount"],
        "reasoning": parsed["reasoning"],
        "confidence": parsed["confidence"],
    })
    if floor_row is None:
        raise FreelancerAgentError("Failed to save price floor")

    floor = PriceFloor(**floor_row)

    for rank, comp in enumerate(comparables, start=1):
        db.save_comparable({
            "price_floor_id": str(floor.price_floor_id),
            "text": comp["text"],
            "similarity_rank": rank,
        })
    freelancer = db.get_freelancer_profile(freelancer_profile_id)
    skill = freelancer["skills"][0] if freelancer and freelancer.get("skills") else "general"

    try:
        ranking = rank_rate(project_id,floor.amount, skill)
        print(f"[AMD] Rate ranking: {ranking}")
    except Exception as e:
        print(f"[WARN] AMD rate ranking unavailable: {e}")

    return floor



def _call_price_floor_llm(
    project_id: str, comp_text: str, rate_expectation: float
) -> dict[str, Any]:
    prompt = PRICE_FLOOR_PROMPT.format(
        comparables=comp_text, rate_expectation=rate_expectation
    )
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            current_prompt = prompt if attempt == 0 else prompt + STRICT_JSON_SUFFIX
            raw = call_gemma(
                agent_name="freelancer_agent",
                purpose="price_floor_reasoning",
                prompt=current_prompt,
                project_id=project_id,
                temperature=0.1 if attempt == 1 else 0.3,
            )
            return _parse_price_floor_response(raw)
        except (GemmaCallError, FreelancerAgentError, json.JSONDecodeError, ValidationError) as e:
            last_error = e

    raise FreelancerAgentError(f"Price floor reasoning failed after retry: {last_error}") from last_error


def _parse_price_floor_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    data = json.loads(text)
    if "amount" not in data or "reasoning" not in data or "confidence" not in data:
        raise FreelancerAgentError(f"Malformed price floor response: {data}")
    return data