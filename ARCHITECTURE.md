
# ARCHITECTURE.md
_Truce — AMD Developer Hackathon ACT II, Track 3 (Unicorn Track)_
_Living design document. Last updated: Day 3, July 9 2026_

---

## ⚠️ Current Inconsistencies & Known Gaps

- **`.env` loading on AMD pod:** `load_dotenv()` doesn't reliably read variables; workaround is to `export` manually before running. Tracked, not blocking.
- **`model_used` field missing** from `GemmaCallLog` — needed to track Groq→Fireworks→Gemma migrations. Tracked in Technical Debt.
- **`app.py` stale** — references DB functions that no longer exist; needs rewrite.
- **`auth/session.py` empty** — login/signup not yet implemented.
- **Mediator Agent offer curve discrepancy:** Teammate reports exponential-decay (`k=3.0`); earlier commit (`057f0a9`) showed linear interpolation. **Verify before merging PR #5.**

---

## 1. High-Level System Overview

Truce is a multi-agent AI system that takes a messy, informal freelance project brief and turns it into a signed scope-and-milestone contract. Three LLM-backed agents — **Client Agent**, **Freelancer Agent**, and **Mediator Agent** — reason over structured data persisted in Supabase, coordinated by CrewAI (`crew.py`). The system includes a **GPU-accelerated rate ranking module** running locally on AMD hardware (Gemma 2B via ROCm/PyTorch) as a concrete "AMD Platform Usage" demonstration.

---

## 2. Goals

### Functional Goals
- Extract structured requirements from an unstructured client brief, flagging ambiguous or missing information as explicit gaps.
- Support a clarification loop: ask the client targeted questions, re-extract with added context, without duplicating already-resolved or already-pending questions.
- Reason a fair, defensible price floor for a freelancer from comparable market data.
- **Run a bounded negotiation** between client ceiling and freelancer floor, producing a final offer or a clear "no deal" outcome.
- **Generate a contract artifact** (PDF) deterministically (no LLM call) and upload to Supabase Storage.
- **Score proposed rates** using a local Gemma model running on the AMD GPU — ranks against market comparables and returns a 0-100 score.
- Log every LLM call (agent, purpose, latency, success) for demo transparency.

### Non-Functional Goals
- **Provider independence:** swapping the underlying LLM (Groq → Fireworks → Gemma) requires only environment variable changes, not code changes.
- **Deterministic logic stays outside the LLM.** Anything with a correct, checkable answer (round caps, clamping offers, gap bookkeeping) is plain Python.
- **Single source of truth for data shape:** all agents and the DB layer share one Pydantic schema module (`models/schemas.py`).
- **Resilience to malformed LLM output:** every LLM-call site has a bounded retry (2 attempts) before failing loudly.
- **Hackathon-speed pragmatism:** favor working, demonstrable code over architectural purity; defer polish to technical debt.

---

## 3. Repository Structure

```
project-root/
├── agents/
│   ├── client_agent.py       ✅ implemented — requirement extraction, gaps, clarifications, scope
│   ├── freelancer_agent.py   ✅ implemented — price floor reasoning (merged via PR #6)
│   └── mediator_agent.py     ✅ implemented — bounded negotiation loop (offer curve unverified)
├── models/
│   └── schemas.py            ✅ single source of truth — 27 Pydantic models
├── db/
│   ├── client.py             ✅ Supabase client instance
│   └── operations.py         ✅ full CRUD layer, one function per table/access pattern
├── tools/
│   ├── market_research.py    ✅ implemented — static comparables from comparables.json
│   ├── rate_ranking.py       ✅ implemented — AMD GPU ranking (merged via PR #6)
│   ├── llm_client.py         ✅ implemented — Fireworks primary, Groq fallback
│   └── contract_generator.py ✅ implemented — deterministic PDF generation (not yet pushed)
├── crew.py                   🟡 implemented — orchestrates agents (PR #5)
├── app.py                    ❌ stale placeholder — needs rewrite
├── auth/
│   └── session.py            ❌ empty — login/signup not implemented
├── config/
│   └── settings.py           ✅ typed env var access via Settings class
├── seed/
│   └── demo_data.py          ❌ not yet implemented
├── tests/
│   ├── test_client_agent.py  ✅ implemented
│   ├── test_freelancer.py    ✅ implemented
│   ├── test_mediator.py      ✅ implemented
│   └── test_pipeline.py      ✅ implemented
├── run_tests.py              ✅ test runner
├── Dockerfile                ❌ empty — containerization not started
├── requirements.txt          ✅ pinned dependencies (updated with AMD libs)
├── .env.example              ✅ env var names (no real values)
└── README.md                 ✅ setup instructions (updated with AMD guide)
```

---

## 4. Component Diagram

```
                    ┌───────────────────┐
                    │   Streamlit UI    │ 
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │      crew.py       │  (PR #5 — orchestration)
                    └───┬─────────┬──────┘
                        │         │
          ┌─────────────┘         └─────────────┐
          ▼                                      ▼
 ┌─────────────────┐                   ┌───────────────────┐
 │  Client Agent    │                   │ Freelancer Agent   │
 │  ✅ merged       │                   │ ✅ merged (PR #6)  │
 └────────┬─────────┘                   └─────────┬─────────┘
          │                                        │
          │            ┌───────────────────┐        │
          └───────────►│  Mediator Agent    │◄───────┘
                       │  🟡 PR #5 open    │
                       └─────────┬─────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   tools/llm_client.py     │  ✅ Fireworks primary / Groq fallback
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
          Fireworks         Groq          AMD Local Gemma
          (primary)      (fallback)      (rate_ranking.py)
                                 │
                    ┌────────────▼────────────┐
                    │   tools/rate_ranking.py   │  ✅ AMD GPU ranking
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   db/operations.py        │
                    │   db/client.py (Supabase) │
                    └───────────────────────────┘
```

---

## 5. Data Flow

1. Client submits raw brief text → `client_agent.create_project()` creates `Project` + `ProjectVersion` (v1).
2. `client_agent.extract_requirements()` calls the LLM once, persists `Requirement` rows, deterministically detects `Gap`s, creates `ClarificationRequest`s.
3. Client answers clarifications → `client_agent.submit_clarifications()` re-extracts with enriched brief context, returns only genuinely new gaps.
4. Loop 2–3 until no new gaps.
5. `client_agent.finalize_scope()` builds a `ScopeDocument` + `ScopeItem`s, marks project `requirements_extracted`.
6. `client_agent.assign_freelancer()` links a `FreelancerProfile` to the project.
7. `freelancer_agent.compute_price_floor()` pulls comparables from `market_research.get_comparables()`, calls the LLM for reasoning, persists `PriceFloor` + `Comparable` rows.
8. **`rank_rate(project_id, proposed_rate, skill)`** runs locally on the AMD GPU, scores the rate 0-100, logs result.
9. `mediator_agent` reads client ceiling and freelancer floor, runs a bounded negotiation loop, persists `NegotiationState` + `NegotiationRound`s.
10. On convergence, `contract_generator.generate_contract()` creates a deterministic PDF and uploads to Supabase Storage.
11. Two-party `Signature` flow marks the project `signed`.

---

## 6. Backend Architecture

Plain Python, no web framework — agents are called as functions (via test scripts or `crew.py`). Supabase is accessed exclusively through `db/operations.py`'s named functions.

**Convention:** no agent or tool calls `supabase.table(...)` directly — every access goes through `db/operations.py`. This keeps the DB layer swappable and testable.

`db/operations.py` provides four generic helpers (`_insert`, `_get_by_id`, `_get_all_by_fk`, `_update`) used by every public function — avoids duplicated Supabase query boilerplate.

---

## 7. Frontend Architecture

Streamlit (`app.py`), currently a stale placeholder — predates the finalized schema. Needs a rewrite once `crew.py` is stable and merged.

---

## 8. Agent Architecture

All agents follow the same pattern:
- One `call_gemma(agent_name, purpose, prompt, project_id, temperature)` call per LLM interaction.
- **2-attempt retry:** first at `temperature=0.3`, second with strict-JSON-only instruction at `temperature=0.1`.
- Response parsed by stripping markdown code fences via regex, then `json.loads`.
- Parsed dict validated into the relevant Pydantic model before persistence.
- All deterministic logic lives in plain Python functions, never inside a prompt.

### Client Agent (`agents/client_agent.py`) — ✅ merged (PR #4)
- **Responsibilities:** requirement extraction, gap detection, clarification generation, re-extraction, scope finalization, freelancer assignment.
- **Failure handling:** raises `ClientAgentError` after 2 retries.

### Freelancer Agent (`agents/freelancer_agent.py`) — ✅ merged (PR #6)
- **Responsibilities:** reason a fair hourly rate (price floor) from market comparables and rate expectation.
- **Integration:** calls `rank_rate()` after computing the floor (optional, AMD GPU step).
- **Failure handling:** raises `FreelancerAgentError` after 2 retries; ranking failure is caught and logged but doesn't break pipeline.

### Mediator Agent (`agents/mediator_agent.py`) — 🟡 open PR (PR #5)
- **Responsibilities (planned):** run bounded negotiation loop between client ceiling and freelancer floor; produce per-round offers and messages.
- **⚠️ Offer curve discrepancy:** reported exponential-decay (`k=3.0`) but earlier commit showed linear interpolation. **Verify before merging.**

---

## 9. Tool Architecture

### `tools/llm_client.py` — ✅ merged (PR #6)
- **Purpose:** single choke point for all LLM calls; provider-agnostic.
- **Primary:** Fireworks AI (`accounts/fireworks/models/gpt-oss-20b`)
- **Fallback:** Groq via `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_ID`
- **Logging:** logs every call's latency and success/failure.

### `tools/market_research.py` — ✅ implemented (not yet pushed)
- **Purpose:** supply comparable freelance rate data from `tools/data/comparables.json` (20 curated entries).
- **Interface:** `get_comparables(skill: str | None = None, limit: int = 5) -> list[dict]`
- **No external API calls** — static data, deliberate reduction of demo risk.

### `tools/rate_ranking.py` — ✅ merged (PR #6)
- **Purpose:** score a proposed rate against market comparables using local AMD GPU inference.
- **Interface:** `rank_rate(project_id: str, proposed_rate: float, skill: str) -> dict`
- **Returns:** `{"score": int|None, "verdict": str, "reasoning": str}`
- **Implementation:** loads `google/gemma-2-2b-it` on AMD GPU via ROCm/PyTorch, `device_map="cuda"`, uses `BatchEncoding` fix (extract `input_ids` before `generate`).
- **Failure handling:** wrapped in `try/except` in `freelancer_agent.py` — ranking failures don't break pipeline.

### `tools/contract_generator.py` — ✅ implemented (not yet pushed)
- **Purpose:** generate deterministic PDF contract (no LLM call) post-convergence.
- **Fields:** `storage_path`, `file_type`, `status="draft"`, `generated_by`, party names, scope from `Requirement.value`.
- **Upload:** to Supabase Storage (`contracts` bucket, private). Requires service-role key for RLS bypass.

---

## 10. LLM Abstraction Layer

- **Provider interface:** OpenAI-compatible chat completions endpoint.
- **Current primary:** Fireworks AI (`gpt-oss-20b`).
- **Current fallback:** Groq (`llama3-70b-8192` via `LLM_MODEL_ID`).
- **Migration path:** Fireworks → Fireworks on-demand Gemma (final demo) → local AMD Gemma (bonus feature).
- **Known gap:** `model_used` field missing from `GemmaCallLog` — tracked in Technical Debt.

---

## 11. Database Design

Supabase (Postgres), 27 tables. RLS is **disabled** on all tables (accepted tradeoff). Storage RLS on `contracts` bucket requires service-role key (identified, not yet applied).

**Core tables:**
- `profiles`, `client_profiles`, `freelancer_profiles` — identity
- `projects`, `project_versions` — versioned project state
- `requirements`, `gaps`, `clarification_requests` — extraction
- `scope_documents`, `scope_items` — finalized scope
- `price_floors`, `comparables` — pricing
- `negotiation_state`, `negotiation_rounds` — negotiation
- `contracts` — generated artifacts (Supabase Storage)
- `gemma_call_logs`, `ranking_logs` — AI observability

---

## 12. Logging Architecture

Every LLM call logged via `db.operations.log_gemma_call` — captures `project_id`, `agent_name`, `purpose`, `latency_ms`, `success`. Logging failures are caught and swallowed inside `llm_client.py`.

`RankingLog` exists in schema for the AMD ranking step — `rank_rate()` currently logs to console; DB logging pending implementation.

---

## 13. Testing Strategy

- ✅ `run_tests.py` — project-wide test runner
- ✅ `tests/test_client_agent.py`
- ✅ `tests/test_freelancer.py`
- ✅ `tests/test_mediator.py`
- ✅ `tests/test_pipeline.py`
- ✅ `rank_rate()` validated on real AMD pod with `rocm-smi` proof
- ✅ Contract PDF render tested

**In progress:** Full end-to-end pipeline test (Client → Freelancer → Mediator → Contract).

---

## 14. Security Considerations

- Supabase RLS is **disabled** on all tables — accepted tradeoff for dev speed.
- Storage RLS on `contracts` bucket requires service-role key — pending application.
- No authentication (`auth/session.py` empty) — deferred.
- API keys via `.env`, gitignored.

---

## 15. Deployment Architecture

**Containerization:** `Dockerfile` is empty — not yet started. Required for submission.

**AMD Pod:** Access at `notebooks.amd.com/hackathon` — team registration required. GPU pod usage capped at 8 hours per 24 hours.

**Proof of AMD usage:** `rocm-smi` screenshots captured during `rank_rate()` execution — VRAM% spike confirmed.

---

## 16. Future Improvements

- Adopt Groq's native `response_format: json_object` for structured outputs.
- Add `model_used` field to `GemmaCallLog` for provider tracking.
- Build `app.py` UI.
- Containerize (`Dockerfile`).
- Add automated tests with mocked `call_gemma` responses.

---

## 17. Technical Debt

1. **`model_used` field missing** from `GemmaCallLog` — tracked.
2. **`app.py` stale** — references non-existent DB functions; needs rewrite.
3. **RLS disabled** on all Supabase tables — acceptable for hackathon.
4. **Debug `print()` statements** — tracked in Issue #3.
5. **`auth/session.py` empty** — no login/signup.
6. **`Dockerfile` empty** — containerization not started.
7. **`.env` loading on AMD pod** — `load_dotenv()` unreliable; use `export` workaround.
8. **Mediator Agent offer curve** — verify exponential vs linear before merging PR #5.

---

## 18. Merged PRs Status

| PR | Title | Status |
|---|---|---|
| #4 | Client Agent | ✅ Merged |
| #6 | AMD Integration (rate_ranking + Fireworks/Groq hybrid) | ✅ Merged |
| #5 | Mediator Agent |  ✅ Merged |
| #7 | Freelancer Agent + Contract Generator |  ✅ Merged |
```