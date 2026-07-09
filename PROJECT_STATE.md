# PROJECT_STATE.md
_Last updated: Day 3 (July 9, 2026), end of session — AMD Developer Hackathon ACT II, Track 3_

## Repository Topology
- **Upstream (source of truth):** https://github.com/duaasiraj/Truce
- **Fork (Laiba's dev):** https://github.com/LaibaAdamji/Truce
- **Workflow:** Laiba works on fork → PRs into upstream. Teammate (duaasiraj) works directly on upstream feature branches.

---

## Branches
| Branch | Location | Status |
|---|---|---|
| `main` | upstream | updated with all merged features, current HEAD `...` |
| `feat/client-agent` | upstream | **merged** via PR #4, safe to delete |
| `feat/mediator-agent` | upstream | contains mediator logic + fixes, PR open / ready to merge |
| `main` | fork (LaibaAdamji) | behind upstream `main` — needs sync after PRs merged |

**Mediator Agent branch is now on upstream** (`duaasiraj/Truce`), so the risk of local-only code is resolved.

## Pull Requests
| # | Title | Status |
|---|---|---|
| 4 | feat(client_agent): requirement extraction w/ confidence-based gap detection | **Merged** → upstream `main` |
| 5 | fix(mediator): exponential‑decay offer curve + termination fix | **Open** — ready for review, all tests passing |

## Issues
| # | Title | Status |
|---|---|---|
| 1 | help101 | Closed |
| 2 | [Auth] Gemma key / Fireworks API missing | **Open** — de‑prioritised (Groq fallback working) |
| 3 | Clean up files from debug statements before submission | **Open** — defer to clean‑up pass |
| 4 | Project status enum mismatch (`no_deal_possible`) | **Closed** — fixed by using valid enum values (`pricing_ready` / `cancelled`) |

---

## Current Milestone
**Client + Freelancer + Mediator agents are now functionally complete and tested end‑to‑end.**  
The next critical path is **UI (`app.py`)** and **contract generator** (teammate) to deliver a demoable product.

## Progress

### ✅ Completed and merged/pushed this session
- **Mediator Agent overhaul** – replaced linear `ceiling → floor` with an exponential‑decay curve converging to the midpoint.  
- **Fixed termination regression** – reaching the round cap now correctly returns `"converged"` with the midpoint offer (not `"capped_no_deal"`).  
- **Added test suite** (`test_negotiation_scenarios.py`):
  - Scenario 1 (immediate convergence, floor==ceiling) – **PASS**
  - Scenario 2 (full cap, 5 rounds) – **PASS** with midpoint offer (`37.5`)
  - Scenario 3 (no‑deal, floor>ceiling) – **PASS** after enum fix
- **Fixed project status enum bug** – `"no_deal_possible"` replaced with `"cancelled"` for failed negotiations, and `"pricing_ready"` for successful ones, respecting the Supabase check constraint.
- **Pushed all code to upstream** – mediator logic, tests, and fixes are now on `duaasiraj/Truce feat/mediator-agent` branch, PR #5 open.

### 🟡 Teammate work (status needs confirmation)
- Contract generator – assigned, but no visible branch/PR yet. **Check in tomorrow morning** – this is now the only unbuilt piece besides UI.

### ⬜ Not started (now urgent)
- `app.py` – still the 16‑line placeholder. **This is the single biggest blocker for a live demo** – start today.
- `tools/rate_ranking.py` – AMD GPU ranking step (needed for judging criteria).
- `Dockerfile` – empty.
- `seed/demo_data.py` – empty.

---

## Testing
- All three negotiation outcome scenarios pass deterministically:
  - **Immediate convergence**: `status=converged`, `round_count=1`, `offer=40.0`, `mediator_calls=0` (correct short‑circuit).
  - **Multi‑round convergence**: `status=converged`, `round_count=5`, `offer=37.5`, `mediator_calls=5` (one per round).
  - **No‑deal**: `status=capped_no_deal`, `round_count=0`, `mediator_calls=0` (rejected before any round).
- The full‑pipeline rehearsal (`test_full_pipeline_vague_brief.py`) was run successfully, showing the end‑to‑end flow with real LLM calls; no further regressions surfaced.

---

## Demo Readiness
- **Headless pipeline is ready** – you can invoke `crew.py` (once wired) and get a negotiation result with all three agents.
- **No UI** – currently no way to show this interactively. `app.py` must be built before the July 11 deadline.
- Contract generation is still a gap – the final output of the pipeline is a signed contract; without it, the demo ends mid‑flow.

---

## Blockers
- None hard‑blocking for the core agent logic.
- The Fireworks/Gemma deployment is still pending but can be done in one shot tomorrow (July 10) as planned.

---

## Technical Debt
1. `model_used` field still missing from `GemmaCallLog` – add before final submission.
2. `app.py` stale – rewrite required for UI step.
3. RLS disabled – acceptable for hackathon.
4. Debug `print()` statements – defer to cleanup pass.
5. No contract‑generation module exists – needs to be created.

---

## Decisions Log (this session)
- Adopted exponential‑decay offer curve (`k=3.0`) for more realistic negotiation.
- Termination at cap is now considered success, not failure.
- Project status enum values aligned with Supabase constraints (`pricing_ready`, `cancelled`).

---

## Immediate Next Tasks (priority order)

1. **Merge PR #5 (mediator agent) into upstream `main`** – once approved, sync forks.
2. **Start building `app.py`** – even a minimal Streamlit dashboard to show negotiation rounds and final agreement will make the demo tangible.
3. **Check in with teammate on contract generator** – confirm status and integration point.
4. **Prepare the Gemma‑on‑Fireworks deployment** – plan for tomorrow (July 10), one deliberate run for proof.
5. **Build Dockerfile** – cheap and can be done in parallel.
6. **Run `rate_ranking.py` on AMD hardware** – get the GPU ranking evidence needed for judging.

---

## Development Log (this session)
- Implemented and tested the new `_next_offer` formula with exponential decay.
- Fixed the post‑loop termination check.
- Wrote `test_negotiation_scenarios.py` and verified all three scenarios.
- Diagnosed and fixed the project status enum bug (`no_deal_possible` → `cancelled`).
- Pushed all changes to `duaasiraj/Truce feat/mediator-agent` and opened PR #5.
- Ran the full‑pipeline rehearsal successfully.

---

## Summary
All three core agents are now operational and tested. The project is on track for the July 11 deadline, but **UI and contract generation must start immediately** to have a demo‑ready product. The Gemma/Fireworks deployment can be done tomorrow as a short proof step.