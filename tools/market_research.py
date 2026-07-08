"""
tools/market_research.py
Static reference dataset of comparable freelance rates.

Sourced once as a curated snapshot rather than scraped live at runtime —
live scraping is fragile (anti-bot, layout drift, rate limits) and adds
demo risk with no upside for judging criteria. This file is the seam:
swapping in a real scrape-once/offline pipeline later only touches this
module, not freelancer_agent.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent / "data" / "comparables.json"

_cache: list[dict[str, Any]] | None = None


def _load_all() -> list[dict[str, Any]]:
    global _cache
    if _cache is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def get_comparables(skill: str | None = None, limit: int = 4) -> list[dict[str, Any]]:
    """
    Return comparable rate entries, optionally filtered by skill keyword.

    Signature-compatible with the prior hardcoded version: freelancer_agent.py
    calls get_comparables() with no args and iterates `text` fields, so the
    default (skill=None) behavior returns the same shape it always has.
    """
    all_comps = _load_all()

    if skill:
        skill_lower = skill.lower()
        filtered = [
            c for c in all_comps
            if skill_lower in c["skill"].lower() or skill_lower in c["text"].lower()
        ]
        # Fall back to the full set if a skill filter matches nothing,
        # so callers always get comparables rather than an empty list.
        pool = filtered if filtered else all_comps
    else:
        pool = all_comps

    return pool[:limit]