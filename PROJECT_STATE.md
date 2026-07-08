# PROJECT_STATE.md
_Last updated: Day 1 (July 7, 2026), end of day — AMD Developer Hackathon ACT II, Track 3_

## Repository Topology
- **Upstream (source of truth):** https://github.com/duaasiraj/Truce
- **Fork (Laiba's dev):** https://github.com/LaibaAdamji/Truce
- **Workflow:** Laiba works on fork → PRs into upstream. Teammate (duaasiraj) works directly on upstream feature branches.

---

## Branches
| Branch | Location | Status |
|---|---|---|
| `main` | upstream | current source of truth, HEAD `ba8ab45` |
| `feat/client-agent` | upstream | **merged** via PR #4, safe to delete |
| `main` | fork (LaibaAdamji) | behind upstream `main` — needs sync before next PR |

No teammate feature branch for Mediator Agent detected yet on upstream — either not pushed, or still local-only on their machine. **Confirm with teammate before assuming progress.**

## Pull Requests
| # | Title | Status |
|---|---|---|
| 4 | feat(client_agent): requirement extraction w/ confidence-based gap detection | **Merged** → upstream `main` |

No open PRs right now.

## Issues
| # | Title | Status |
|---|---|---|
| 1 | help101 | Closed |
| 2 | [Auth] Gemma key / Fireworks API missing | **Open** — de-prioritized (Groq fallback working, Gemma migration is env-var-only whenever access resolves) |
| 3 | Clean up files from debug statements before submission | **Open** — defer to Day 4/5, don't touch now |

---

## Current Milestone
**Client Agent + Freelancer Agent + Market Research → done. Mediator Agent + crew wiring → in progress / next.**

## Progress

### ✅ Merged upstream (`duaasiraj/Truce main`)
- Full 27-table Supabase schema + CRUD layer (`db/operations.py`, `db/client.py`)
- Provider-agnostic `llm_client.py` (`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_ID` — Groq → Fireworks → Gemma swap is env-var only, <5 min)
- `log_gemma_call` signature bug (fixed — passes dict correctly)
- **Client Agent** (`agents/client_agent.py`, 544 lines) — requirement extraction, gap detection, clarification loop, scope finalization. Fully implemented, retry-with-strict-JSON pattern established as the reusable template for all future agents.

### 🟡 Local work only — NOT YET pushed anywhere (not on fork, not on upstream)
- `tools/market_research.py` — hardcoded golden-path comparables, done
- `agents/freelancer_agent.py` — price floor reasoning, **tested successfully against real Groq (`openai/gpt-oss-120b`)**, verified rows in Supabase (`price_floors` + 4 `comparables` rows confirmed via table editor)
- ⚠️ **Risk:** this is real, working code sitting only on Laiba's local machine. Not on fork, not on a PR, not visible to teammate.

### 🟡 Teammate — status unclear
- Mediator Agent: assigned, presumably in progress, but no branch/commit visible on upstream yet. **Needs a status check** — are they blocked, working locally, or on an unpushed branch?

### ⬜ Not started
- `crew.py` (orchestration)
- `tools/rate_ranking.py` (GPU ranking — deferred, non-blocking)
- `seed/demo_data.py`
- Contract generator (no file/module currently owns this — gap in current file structure)
- UI (`app.py` still stale scaffolding referencing non-existent `get_projects`)

---

## Testing
- Freelancer Agent: manually smoke-tested via throwaway `test_freelancer.py` against real project/version/freelancer UUIDs — **passed**, confirmed both `price_floors` and `comparables` rows in Supabase.
- Client Agent: implemented with retry logic; no smoke test run/confirmed in this conversation — recommend one before building Mediator against it.
- No automated test suite (`tests/`) exists yet anywhere in the repo.

## Demo Readiness
- Core reasoning agents (Client, Freelancer) prove the "Gemma via Fireworks/Groq" LLM story end-to-end.
- Nothing wired together yet — `crew.py` is empty, so there is no runnable pipeline demo yet, only isolated agent calls.
- `app.py` will crash if run as-is (stale, mismatched to current schema).

## Blockers
- None hard-blocking. Gemma/Fireworks access (Issue #2) is soft-blocked but irrelevant right now since Groq fallback works.

## Technical Debt
1. **`model_used` field still missing** from `GemmaCallLog` schema + log call — agreed to add last session, not yet done. Add before more agents start logging (currently only Client + Freelancer log calls; Mediator will be a third).
2. `app.py` stale scaffolding — will need a rewrite once UI step starts, not urgent now.
3. RLS disabled on Supabase — acceptable for hackathon speed, noted for submission awareness, not urgent.
4. Debug `print()` statements in `llm_client.py` (Issue #3) — cosmetic, defer to pre-submission cleanup pass.
5. No contract-generation module exists yet despite being the literal end deliverable ("signed scope-and-milestone contract") — needs a home (`tools/contract_generator.py` or similar) before Day 3-4.

## Decisions Log
- Switched primary LLM provider to **Groq (free)** for active development; architecture kept provider-agnostic so Fireworks/Gemma swap is env-var only.
- Adopted `openai/gpt-oss-120b` as working Groq model (confirmed via `/models` endpoint, supports `json_mode`/`structured_outputs` — worth adopting `response_format` later for stricter JSON enforcement than prompt-suffix retry).
- Canonical repo confirmed as `duaasiraj/Truce` (not `LaibaAdamji/Truce-main`, an earlier misconfigured remote).
- `PriceFloor` keyed to `version_id`, not `project_id` — `project_id` still passed separately to LLM call logging only.
- Retry-with-strict-JSON-suffix + fence-strip parse pattern (established in Client Agent) is now the standard template all agents should follow.

## Development Log (this session)
- Confirmed PR #4 (Client Agent) merged to upstream.
- Built and tested `market_research.py` + `freelancer_agent.py` locally against real Groq calls — verified in Supabase.
- Diagnosed and fixed: missing `requests`/`dotenv` deps, `Settings` object mismatch, wrong `.env` var names (Fireworks → generic `LLM_*`), literal placeholder text left in `.env`/test file, `PriceFloor` schema field mismatch (`project_id` → `version_id`).

---

## Immediate Next Task (single highest priority)

**Push local Freelancer Agent + Market Research work to fork, open PR into upstream — before starting anything else.**

This is currently uncommitted, unpushed, working code that only exists on one machine. Every hour it stays local is an hour of risk (laptop dies, merge conflicts pile up, teammate can't build Mediator Agent against real data). This blocks the stated EOD goal (all 4 pieces integrated) more than any unstarted work does.

```bash
git add tools/market_research.py agents/freelancer_agent.py
git commit -m "feat(freelancer_agent): price floor reasoning + market comparables"
git push origin main   # or a feature branch, per your convention
# then open PR: LaibaAdamji/Truce → duaasiraj/Truce
```

**Time estimate:** 10 min
**Can teammate work in parallel?** Yes — but ping them immediately once pushed so they swap their (assumed) mocked Freelancer output for the real thing before going further on Mediator Agent.