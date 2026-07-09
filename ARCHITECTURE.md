# ARCHITECTURE.md
_Truce — AMD Developer Hackathon ACT II, Track 3 (Unicorn Track)_
_Living design document. Last updated: Day 1 EOD._

> **Note on current inconsistencies (flagged, not yet fixed in code):**
> - The `Profiles` model (users table) is named `Profiles` in `models/schemas.py`, matching the `profiles` table name — this was a deliberate team decision (keep `Profiles`, don't rename to `User`), documented here as resolved, not a bug.
> - `GemmaCallLog` does not yet include a `model_used` field, despite the LLM abstraction layer needing to report which provider/model served each call (especially during the Groq → Fireworks → Gemma migration). Tracked in Technical Debt (§18); should be added before more agents start logging calls.
> - `app.py` (Streamlit UI) currently calls `save_project(name)` and `get_projects()`, neither of which match the current `db/operations.py` interface (`save_project(dict)`, no `get_projects` at all — only singular `get_project`). Stale scaffolding from before the schema was finalized; not yet rewritten.
> - `auth/session.py` exists in the folder structure but is currently empty — login/signup not yet implemented.

---

## 1. High-Level System Overview

Truce is a multi-agent AI system that takes a messy, informal freelance project brief and turns it into a signed scope-and-milestone contract. Three LLM-backed agents — **Client Agent**, **Freelancer Agent**, and **Mediator Agent** — reason over structured data persisted in Supabase, coordinated (eventually) by a CrewAI pipeline (`crew.py`). The system demonstrates LLM inference (Gemma, via a provider-agnostic abstraction) and containerized deployment on AMD infrastructure.

## 2. Goals

### Functional Goals
- Extract structured requirements from an unstructured client brief, flagging ambiguous or missing information as explicit gaps.
- Support a clarification loop: ask the client targeted questions, re-extract with added context, without duplicating already-resolved or already-pending questions.
- Reason a fair, defensible price floor for a freelancer from comparable market data.
- Run a bounded negotiation between client ceiling and freelancer floor, producing a final offer or a clear "no deal" outcome.
- Finalize an explicit scope document (included / excluded / assumed) and milestone breakdown.
- Generate a contract artifact and support a lightweight two-party signature flow.
- Log every LLM call (agent, purpose, latency, success) for demo transparency.

### Non-Functional Goals
- **Provider independence:** swapping the underlying LLM (Groq → Fireworks → Gemma) must require only environment variable changes, not code changes.
- **Deterministic logic stays outside the LLM.** Anything with a correct, checkable answer (round caps, clamping offers to floor/ceiling, gap-answered-vs-pending bookkeeping) is plain Python, never delegated to a model.
- **Single source of truth for data shape:** all agents and the DB layer share one Pydantic schema module (`models/schemas.py`) — no ad hoc dicts crossing module boundaries.
- **Resilience to malformed LLM output:** every LLM-call site has a bounded retry (currently: 2 attempts, second with a stricter JSON-only instruction and lower temperature) before failing loudly.
- **Hackathon-speed pragmatism:** favor working, demonstrable code over architectural purity; defer polish (RLS, auth hardening, UI, cleanup) to explicitly tracked technical debt rather than blocking core pipeline work.

## 3. Repository Structure
project-root/
├── agents/
│   ├── client_agent.py       ← implemented — requirement extraction, gaps, clarifications, scope
│   ├── freelancer_agent.py   ← implemented locally — price floor reasoning (not yet merged upstream)
│   └── mediator_agent.py     ← not yet implemented
├── models/
│   └── schemas.py            ← shared Pydantic data models (single source of truth), 20 models
├── db/
│   ├── client.py             ← Supabase client instance
│   └── operations.py         ← full CRUD layer, one function per table/access pattern
├── tools/
│   ├── market_research.py    ← implemented locally — hardcoded golden-path comparables
│   ├── rate_ranking.py       ← not yet implemented (GPU ranking step, deferred)
│   └── llm_client.py         ← provider-agnostic LLM wrapper (implemented)
├── crew.py                   ← not yet implemented — will wire the 3 agents into one pipeline
├── app.py                    ← Streamlit frontend — currently stale, predates schema finalization
├── auth/
│   └── session.py            ← not yet implemented — signup/login
├── config/
│   └── settings.py           ← implemented — typed env var access via Settings class
├── seed/
│   └── demo_data.py          ← not yet implemented — golden-path fixtures
├── Dockerfile                ← present, empty — containerization not yet started
├── requirements.txt          ← pinned dependencies
├── .env.example               ← env var names, no real values
└── README.md                  ← setup instructions

## 4. Component Diagram

```
                    ┌───────────────────┐
                    │   Streamlit UI     │  (app.py — stale, to be rebuilt)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │      crew.py       │  (not yet implemented)
                    │  orchestration     │
                    └───┬─────────┬──────┘
                        │         │
          ┌─────────────┘         └─────────────┐
          ▼                                      ▼
 ┌─────────────────┐                   ┌───────────────────┐
 │  Client Agent    │                   │ Freelancer Agent   │
 │  (implemented)   │                   │ (implemented,      │
 │                  │                   │  not yet merged)   │
 └────────┬─────────┘                   └─────────┬─────────┘
          │                                        │
          │            ┌───────────────────┐        │
          └───────────►│  Mediator Agent    │◄───────┘
                       │  (not yet built)   │
                       └─────────┬─────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   tools/llm_client.py     │  (provider-agnostic)
                    └────────────┬────────────┘
                                 │
                 Groq → Fireworks (cheap) → Gemma
                                 │
                    ┌────────────▼────────────┐
                    │   db/operations.py        │
                    │   db/client.py (Supabase) │
                    └───────────────────────────┘
```

## 5. Data Flow

1. Client submits raw brief text → `client_agent.create_project()` creates `Project` + `ProjectVersion` (v1).
2. `client_agent.extract_requirements()` calls the LLM once, persists `Requirement` rows, deterministically detects `Gap`s (low confidence, missing timeline/budget/deliverable), creates `ClarificationRequest`s.
3. Client answers clarifications → `client_agent.submit_clarifications()` re-extracts with enriched brief context, returns only genuinely new gaps (filters out already-answered and already-pending descriptions).
4. Loop 2–3 until no new gaps.
5. `client_agent.finalize_scope()` builds a `ScopeDocument` + `ScopeItem`s (client-reviewed requirements → "included", everything else → "assumption"), marks project `requirements_extracted`.
6. `client_agent.assign_freelancer()` links a `FreelancerProfile` to the project (no AI).
7. `freelancer_agent.compute_price_floor()` pulls hardcoded comparables from `market_research.get_comparables()`, calls the LLM once for reasoning, persists `PriceFloor` + `Comparable` rows.
8. **(Not yet built)** `mediator_agent` reads client ceiling (from scope/requirements) and freelancer floor (`PriceFloor.amount`), runs a bounded negotiation loop, persists `NegotiationState` + `NegotiationRound`s, terminates in `converged` or `capped_no_deal`.
9. **(Not yet built)** Contract generation step reads final scope + milestones + negotiated price → produces a `Contract` artifact.
10. **(Not yet built)** Two-party `Signature` flow marks the project `signed`.

## 6. Backend Architecture

Plain Python, no web framework — agents are called as functions (currently invoked via throwaway test scripts; `crew.py` will be the real entry point). Supabase is accessed exclusively through `db/operations.py`'s named functions; no agent or tool calls `supabase.table(...)` directly. This is a firm convention, not a suggestion — it's what keeps the DB layer swappable and testable.

`db/operations.py` provides four generic private helpers (`_insert`, `_get_by_id`, `_get_all_by_fk`, `_update`) that every public function is built from — avoids duplicated Supabase query boilerplate across ~35 public functions.

## 7. Frontend Architecture

Streamlit (`app.py`), currently a stale placeholder from initial scaffolding — predates the finalized schema and will need a rewrite once the core pipeline (`crew.py`) exists to call into. Not a priority until agents + orchestration are done.

## 8. Agent Architecture

All agents follow the same established pattern (set by Client Agent, reused by Freelancer Agent):
- One `call_gemma(agent_name, purpose, prompt, project_id, temperature)` call per LLM interaction.
- 2-attempt retry: first attempt at `temperature=0.3`, second appends a strict-JSON-only instruction suffix at `temperature=0.1`.
- Response parsed by stripping markdown code fences via regex, then `json.loads`.
- Parsed dict validated into the relevant Pydantic model before persistence.
- All deterministic logic (gap detection, answered/pending bookkeeping, negotiation math) lives in plain Python functions, never inside a prompt.

### Client Agent (`agents/client_agent.py`) — implemented
- **Responsibilities:** requirement extraction from raw brief text, gap detection, clarification question generation, re-extraction with enriched context, scope document finalization, freelancer assignment.
- **Inputs:** raw brief text (`str`), client answers (`dict[gap_id, answer_text]`).
- **Outputs:** `Requirement`, `Gap`, `ClarificationRequest`, `ScopeDocument`, `ScopeItem` rows.
- **Dependencies:** `tools.llm_client`, `db.operations`, `models.schemas`.
- **Failure handling:** raises `ClientAgentError` after exhausting the 2-attempt retry; skill-type gaps rejected by the client ("no") deterministically spawn a follow-up correction question rather than re-guessing via LLM.

### Freelancer Agent (`agents/freelancer_agent.py`) — implemented, not yet merged upstream
- **Responsibilities:** reason a fair minimum hourly rate (price floor) from market comparables and the freelancer's own rate expectation.
- **Inputs:** `project_id`, `version_id`, `freelancer_profile_id`, `rate_expectation` (float).
- **Outputs:** `PriceFloor` row, `Comparable` rows (ranked, unfiltered — ranking currently by list order, not similarity).
- **Dependencies:** `tools.llm_client`, `tools.market_research`, `db.operations`.
- **Failure handling:** same 2-attempt retry pattern as Client Agent; raises `FreelancerAgentError`.

### Mediator Agent (`agents/mediator_agent.py`) — not yet implemented
- **Responsibilities (planned):** run a bounded negotiation loop between client ceiling and freelancer floor; produce per-round offers and natural-language messages; terminate deterministically.
- **Inputs (planned):** `project_id`, client ceiling, `PriceFloor.amount` (freelancer floor).
- **Outputs (planned):** `NegotiationState` (with terminal `status`), `NegotiationRound` rows.
- **Dependencies (planned):** `tools.llm_client`, `db.operations`, `config.settings.NEGOTIATION_ROUND_CAP`.
- **Failure handling (planned):** LLM proposes the natural-language framing of each offer; the offer's numeric value itself must be clamped to `[floor, ceiling]` deterministically, never trusted raw from the model. Round count hitting `NEGOTIATION_ROUND_CAP` forces `capped_no_deal`, never an infinite loop.

## 9. Tool Architecture

### `tools/llm_client.py` — implemented
- **Purpose:** single choke point for every LLM call in the system; provider-agnostic.
- **Interface:** `call_gemma(agent_name: str, purpose: str, prompt: str, project_id: str | None, temperature: float = 0.3, max_tokens: int = 1024) -> str`
- **Inputs:** prompt text, calling agent's name, call purpose (for logging), optional project id.
- **Outputs:** raw text content from the model's response.
- **Dependencies:** `config.settings`, `db.operations.log_gemma_call`.
- Logs every call's latency and success/failure regardless of outcome (logging failure itself is swallowed — never crashes the actual LLM call).

### `tools/market_research.py` — implemented
- **Purpose:** supply comparable freelance rate data for price floor reasoning.
- **Interface:** `get_comparables(skill: str | None = None) -> list[dict]`
- **Inputs:** optional skill filter (currently unused — reserved for future filtering).
- **Outputs:** list of `{"text": str, "description": str}` — hardcoded golden-path demo data, explicitly labeled as such via a `WARNING` prefix baked into `description`.
- **Dependencies:** none (no external API call).

### `tools/rate_ranking.py` — not yet implemented
- **Purpose (planned):** embed and rank comparables by similarity (the GPU-accelerated step — the concrete, demonstrable "AMD Platform Usage" hook beyond just running Gemma).
- **Interface (planned):** takes a project's requirement text + a list of comparables, returns ranked comparables with similarity scores.
- **Outputs (planned):** persisted via `db.operations.log_ranking` into `RankingLog` (`ran_on_gpu: bool` field already exists in schema, ready to receive this).
- **Dependencies (planned):** an embedding model, GPU runtime.

## 10. LLM Abstraction Layer

- **Provider interface:** OpenAI-compatible chat completions (`{LLM_BASE_URL}/chat/completions`), single function `call_gemma()` in `tools/llm_client.py`. All provider-specific values (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID`) come from `config.settings`, never hardcoded in agent code.
- **Current provider:** Groq (free tier), model `openai/gpt-oss-120b` — confirmed supports `json_mode`/`structured_outputs`, not yet adopted in place of the prompt-suffix-retry pattern (candidate future improvement, §17).
- **Migration path:** Groq → Fireworks (inexpensive model) → Gemma (on-demand, AMD MI300X/A100-hosted, once budget/access allows). Migration between any of these three is purely `.env` changes to `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_ID` — no code touches a provider name directly. Verified in practice: swapping providers means re-running the golden path once to catch model-behavior differences (e.g. stricter/looser JSON adherence), not a code change.
- **Known gap:** no field currently records *which* model actually served a given call (see Technical Debt §18) — needed to make the Groq→Fireworks→Gemma story visible in the demo's log data, not just asserted in the README.

## 11. Database Design

Supabase (Postgres), 27 tables. No table is written to directly by agents — always through `db/operations.py`.

**Core entity groups and relationships:**
- **Identity:** `profiles` (1) → `client_profiles` / `freelancer_profiles` (1:1 each), → `subscriptions` (1:many)
- **Project:** `projects` → `project_versions` (1:many, versioned re-extraction) → `requirements` (1:many) → `deliverables`, `gaps` → `clarification_requests`; `requirements` → `field_conflicts`
- **Scope:** `projects` → `scope_documents` (1:1) → `scope_items` (1:many)
- **Milestones:** `projects` → `milestones` (1:many) → `change_orders` (1:many)
- **Pricing:** `project_versions` → `price_floors` (1:1 per version) → `comparables` (1:many), → `human_price_adjustments` (1:many, audit trail)
- **Negotiation:** `projects` → `negotiation_state` (1:1) → `negotiation_rounds` (1:many)
- **Risk:** `project_versions` → `risks` (1:many)
- **Signing:** `projects` → `signatures` (1:many, one per role)
- **Concurrency:** `projects` → `processing_locks` (1:1, "one message in flight" guard)
- **AI observability:** `projects` → `gemma_call_logs` (1:many), `ranking_logs` (1:many)
- **Contract:** `projects` → `contracts` (1:many, versioned)
- **Notifications:** `profiles` → `notifications` (1:many)

**Entity responsibilities:** `ProjectVersion` exists specifically so re-extraction after clarifications doesn't destructively overwrite prior requirement rows — every version's `requirements`/`price_floors`/`risks` are scoped to `version_id`, not `project_id`, directly. `Project.status` is the single state machine driving which stage of the pipeline a project is in; `ai_processing_status` is a separate, orthogonal field for UI-level "is an agent currently working on this" feedback (supports graceful loading/failure states rather than a raw crash).

## 12. API Design

No HTTP API currently exists — agents are called as direct Python functions (from test scripts today, from `crew.py` once built). This section will be filled in if/when `crew.py` or the UI needs a formal internal contract; not needed for the current architecture. Documented here as a deliberate scope decision, not an oversight.

## 13. Logging Architecture

Every LLM call is logged via `db.operations.log_gemma_call` regardless of success/failure — captures `project_id`, `agent_name`, `purpose`, `latency_ms`, `success`. Logging failures are caught and swallowed inside `llm_client.py`'s `finally` block so a logging problem can never crash an actual agent call. `RankingLog` exists in schema for the planned GPU ranking step, unused until `rate_ranking.py` is built.

## 14. Testing Strategy

No automated test suite yet. Current practice: throwaway root-level scripts (`test_llm.py`, `test_freelancer.py` — both gitignored) that call an agent function directly against real or seeded Supabase rows and print results for manual verification. Adequate for hackathon speed, but should graduate to a minimal `tests/` directory with mocked `call_gemma` responses (success case + malformed-JSON case, to verify the retry path) before final submission — see Technical Debt §18.

## 15. Security Considerations

- Supabase Row-Level Security (RLS) is currently **disabled** on all tables — accepted tradeoff for hackathon dev speed, not a blocker, but noted for submission awareness.
- No authentication currently implemented (`auth/session.py` is empty) — deferred until core pipeline is proven.
- API keys (`LLM_API_KEY`, `SUPABASE_KEY`) via `.env`, gitignored; `.env.example` documents variable names only.

## 16. Deployment Architecture

`Dockerfile` present but currently empty — containerization for AMD Developer Cloud submission not yet started. Required for the "AMD Platform Usage" judging criterion; should not be left to the last day.

## 17. Future Improvements

- Adopt Groq's native `response_format: json_object` / structured outputs instead of (or alongside) the current prompt-suffix-retry pattern, now that it's confirmed supported by the working model.
- Implement `tools/rate_ranking.py` as the concrete GPU-usage story, separate from wherever Gemma itself ends up hosted.
- Add a `tools/contract_generator.py` (or similar) — currently no module owns turning final negotiated state into the actual "signed scope-and-milestone contract" artifact, which is the literal product output.

## 18. Technical Debt

1. **`model_used` field missing** from `GemmaCallLog` — agreed, not yet implemented. Needed before the Groq→Fireworks→Gemma story is demonstrable from logged data rather than asserted.
2. **`app.py` is stale** — references DB functions that no longer exist/match; needs a rewrite once orchestration exists to call into.
3. **RLS disabled** on all Supabase tables — acceptable for now, revisit only if time permits post-core-pipeline.
4. **Debug `print()` statements** in `tools/llm_client.py` (`Status:`, raw response body) — cosmetic, tracked in GitHub Issue #3, defer to pre-submission cleanup.
5. **No contract-generation module** exists despite being the stated end deliverable.
6. **No automated tests** — only manual throwaway scripts.
7. **`auth/session.py` empty** — no login/signup implemented yet.
8. **`Dockerfile` empty** — containerization not started; required for AMD deployment criterion.

### Folder Structure:
Note: This is very tentative for now and can/will be changed as required throughout the week 

```
project-root/
├── agents/
│   ├── client_agent.py       ← extracts requirements + flags gaps from client brief
│   ├── freelancer_agent.py   ← reasons about fair price floor from market data
│   └── mediator_agent.py     ← runs negotiation loop between client & freelancer
├── models/
│   └── schemas.py            ← shared Pydantic data models (single source of truth)
├── db/
│   ├── client.py              ← Supabase connection instance
│   └── operations.py         ← all DB read/write functions
├── tools/
│   ├── market_research.py    ← fetches comparable freelance rate data
│   ├── rate_ranking.py       ← GPU-ranking step (embeds + ranks comparables)
│   └── llm_client.py         ← wrapper around Fireworks/Gemma calls
├── crew.py                   ← wires the 3 agents into one CrewAI pipeline
├── app.py                    ← Streamlit frontend / UI
├── auth/
│   └── session.py            ←signup/login        
├── config/
│   └── settings.py           ← reads env vars, exposes typed settings
├── seed/
│   └── demo_data.py          ← seeds golden-path demo data for testing/judges
├── Dockerfile                ← containerizes the app for submission
├── requirements.txt          ← pinned Python dependencies
├── .env.example               ← env var names (no real values, safe to commit)
└── README.md                  ← setup + run instructions for judges
```
