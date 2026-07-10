
# PROJECT_STATE.md
_Last updated: Day 3 (July 9, 2026), end of session — AMD Developer Hackathon ACT II, Track 3_

## Repository Topology
- **Upstream (source of truth):** https://github.com/duaasiraj/Truce
- **Fork (Laiba's dev):** https://github.com/LaibaAdamji/Truce
- **Workflow:** Laiba works on fork → PRs into upstream. Duaa works directly on upstream feature branches.

---



## Branches
| Branch | Location | Status |
|---|---|---|
| `main` | upstream | **UPDATED** — contains all merged features (PR #4, PR #6) |
| `amd-integration` | upstream (Duaa) | **MERGED** (PR #6) — AMD local Gemma ranking + Fireworks primary LLM |
| `feat/client-agent` | upstream | Merged via PR #4, safe to delete |
| `feat/mediator-agent` | upstream | PR #5 open, described as "all tests passing" — **offer-curve implementation unverified against source, see discrepancy note above** |
| `main` | fork (LaibaAdamji) | Behind upstream `main` — Freelancer Agent + market_research + contract_generator ready to push, not yet committed |

## Pull Requests
| # | Title | Status |
|---|---|---|
| 4 | feat(client_agent): requirement extraction w/ confidence-based gap detection | **Merged** → upstream `main` |
| 5 | fix(mediator): offer curve + termination fix | **Open** — reported ready for review; offer-curve description unverified this session |
| 6 | feat(amd-integration): AMD local Gemma rate ranking + Fireworks primary LLM | **MERGED** → upstream `main` (Duaa) |
| 7 | feat(freelancer-contract): Freelancer Agent market research + contract generator | **Not yet opened** — code complete and tested, awaiting push from Laiba |

---

## Issues
| # | Title | Status |
|---|---|---|
| 1 | help101 | Closed |
| 2 | [Auth] Gemma key / Fireworks API missing | Open — de-prioritized (Groq fallback working) |
| 3 | Clean up debug statements before submission | Open — defer to cleanup pass |
| 4 | Project status enum mismatch (`no_deal_possible`) | Closed — fixed via valid enum values (`pricing_ready`/`cancelled`) |

---

## Current Milestone
**Get all four pieces — Freelancer Agent, Mediator Agent, contract generator, UI — merged and reconciled into one working end-to-end demo pipeline.**

## Progress

### ✅ Merged upstream (`duaasiraj/Truce main`)
- 27-table Supabase schema + CRUD layer, provider-agnostic `llm_client.py`
- **Client Agent** (`agents/client_agent.py`) — merged via PR #4
- **AMD Integration (Duaa, PR #6)** — successfully pushed, merged, and authentication issues resolved on the AMD pod.

### ✅ AMD Integration — Completed & Merged (Duaa, PR #6)
- **Local Gemma rate ranking** (`tools/rate_ranking.py`):
  - Runs `google/gemma-2-2b-it` on AMD GPU via ROCm/PyTorch
  - Scores freelancer rates against market comparables (0-100)
  - Returns `{"score": int, "verdict": str, "reasoning": str}`
  - Uses `device_map="cuda"` with `BatchEncoding` fix (extract `input_ids` before `model.generate()`)
  - Integrated into `agents/freelancer_agent.py` with `try/except` fallback
- **LLM Client** (`tools/llm_client.py`):
  - **Primary:** Fireworks AI (`accounts/fireworks/models/gpt-oss-20b`)
  - **Fallback:** Groq via `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_ID`
  - Unified `_try_provider()` helper for clean error handling
- **Infrastructure:** `requirements.txt` updated with `transformers`, `accelerate`, `huggingface_hub`, `safetensors`, `bitsandbytes`
- **Testing:** Validated on real AMD pod with `rocm-smi` confirming GPU utilisation; Git/SSL authentication resolved and pushed successfully.

### 🟡 Teammate branch — open PR, unverified details (upstream `feat/mediator-agent`, PR #5)
- Mediator Agent + `crew.py` orchestration, per commit `057f0a9` (confirmed by direct source read): bounded negotiation loop, linear offer interpolation, convergence/duplicate-insert bug fixes, demo tuning (`rate_expectation=40.0`)
- This session's incoming report additionally claims an exponential-decay rewrite and a new `test_negotiation_scenarios.py` suite (3 scenarios passing) and an enum fix (`no_deal_possible` → `cancelled`/`pricing_ready`) — **not yet independently verified against source this session**

### 🟢 Local/fork work — Laiba, this session, tested and verified (not yet pushed)
- `tools/market_research.py` rewritten to read from `tools/data/comparables.json` (20 curated entries)
- Verified via standalone test and real Groq smoke test
- `tools/contract_generator.py` — deterministic PDF contract generation, fields verified against real `models/schemas.py`
- PDF render test **passed**; bucket upload test **failed** with `403 RLS policy violation` — root cause identified (service role key needed), fix pending confirmation

### ⬜ Not started
- `app.py` — still stale placeholder, single biggest demo blocker
- `Dockerfile`, `seed/demo_data.py` — empty

---

## Testing
- **AMD rate ranking:** `rank_rate()` tested on real AMD pod with `rocm-smi` confirming GPU utilisation — **passing**
- **LLM Client (Fireworks primary, Groq fallback):** tested with real calls — Fireworks returns responses; Groq fallback is ready if needed
- **Git/SSL authentication:** Resolved on AMD pod; push to upstream successful
- **Freelancer Agent + market_research.json swap:** verified twice — passing
- **Contract generator:** PDF render verified — passing. Bucket upload: RLS fix pending
- **Mediator Agent test suite** — reported passing by teammate; not independently re-run
- **Full-pipeline rehearsal** — reported passing; not independently re-run

## Demo Readiness
- Client Agent, Freelancer Agent (local), Mediator Agent (branch, PR #5), Contract Generator (local, near-complete), and AMD rate ranking now cover the full agent chain conceptually
- No UI — `app.py` remains the biggest gap for an interactive demo
- Contract generation is one config fix away from a full green run

## Blockers
- **Bucket RLS on private `contracts` bucket** — blocks contract upload until service role key is swapped in `.env`. Low effort, high priority.
- **Interface/description conflict on Mediator Agent** (see Discrepancy note) — needs a direct diff of `feat/mediator-agent` before merging PR #5.
- **Possible duplicate contract-generator work** — confirm with teammate.
- **`.env` loading issue on AMD pod** — `load_dotenv()` still not picking up variables reliably; workaround: `export` manually before running (acceptable for final demo).

## Technical Debt
1. `model_used` field still missing from `GemmaCallLog`.
2. `app.py` stale — full rewrite needed.
3. RLS disabled on Supabase tables (accepted tradeoff); Storage RLS on `contracts` bucket needs service role key.
4. Debug `print()` statements (Issue #3) — deferred.
5. No `seed/demo_data.py`, no Dockerfile.

## Decisions Log
- (Prior) Groq as active provider; provider-agnostic architecture preserved.
- (This session) AMD local Gemma ranking is an **optional bonus feature** — wrapped in `try/except` so pipeline works even if AMD pod is unavailable.
- (This session) Fireworks is primary LLM; Groq is fallback.
- (This session) Contract generator is fully deterministic (no LLM call) by design.
- (Incoming, unverified) Reported adoption of exponential-decay offer curve on Mediator Agent — flagged for verification.

## Development Log
**Day 1–2:** Client Agent merged. Freelancer Agent + market_research built and smoke-tested locally.
**Day 2:** Teammate pushed `feat/mediator-agent` (`057f0a9`) — Mediator Agent + `crew.py`, linear offer curve.
**Day 3 (this session):**
- **Laiba:** Rebuilt `market_research.py`, built `tools/contract_generator.py`. PDF render passed; RLS upload pending.
- **Duaa:** Built AMD integration, updated `llm_client.py`, tested on real AMD pod, resolved Git/SSL authentication issues, successfully pushed and merged `amd-integration` branch (PR #6) into `main`.

---

## Immediate Next Task (single highest priority)

**Apply the service-role-key fix and rerun `test_upload_contract.py` to get a fully green contract generator, then push it alongside the already-tested Freelancer Agent in one PR.**

1. Set `SUPABASE_KEY` to the service role key in `.env`
2. Rerun `python test_upload_contract.py` — confirm signed URL opens a real PDF
3. Delete throwaway test files (`test_render_contract.py`, `test_upload_contract.py`)
4. `git add agents/freelancer_agent.py tools/market_research.py tools/data/comparables.json tools/contract_generator.py`
5. Commit, push to fork, open PR into upstream `main`
6. Pull `feat/mediator-agent` fresh and diff `_next_offer()` to resolve the offer-curve discrepancy
7. Ping teammate to confirm they're not building a duplicate contract generator

## Remaining Before Submission
- [x] AMD Integration + Firewalls/Groq hybrid (Duaa) — **DONE & MERGED**
- [ ] Merge `feat/freelancer-contract` PR (Laiba)
- [ ] Resolve Mediator Agent offer-curve discrepancy and merge PR #5
- [ ] Build `app.py` UI (single biggest demo blocker)
- [ ] Create `Dockerfile` for containerised submission
- [ ] Run full end-to-end demo rehearsal
- [ ] Capture final `rocm-smi` proof screenshots
- [ ] Clean up debug statements
- [ ] Submit to hackathon
```