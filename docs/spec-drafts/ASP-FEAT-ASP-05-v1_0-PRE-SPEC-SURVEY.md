# ASP-FEAT-ASP-05 v1.0 — Pre-Spec Survey

| Field | Value |
|---|---|
| Service | ASP-05 Prediction |
| Directive | ASP-OUT-066 (Task 1) |
| Author | ASP Dev Team |
| Date | 2026-04-21 |
| Status | Survey only — no spec writing yet |
| DEFECT-025 | **RESOLVED** in commit `0695c38` (ASP-OUT-064). Stream A / S-1 of the v1.0 cycle is already done. This survey covers the remaining gap matrix only. |

Format mirrors `ASP-FEAT-ASP-04-v1_0-PRE-SPEC-SURVEY.md` (accepted for the
Doc Intelligence cycle, commit `cf09432`).

---

## §1 — File inventory and line counts

| File | Lines | Notes |
|---|---|---|
| `app/services/prediction.py` | 337 | DEFECT-025-fixed; ported to asyncpg in `0695c38`; three governed async helpers + Celery task rewritten |
| `app/models/request.py` (ASP-05 surface) | — (shared) | `service_type="prediction"` passes through the standard invoke envelope |
| `app/models/response.py` (ASP-05 surface) | — (shared) | `JobAcceptedResponse` shared with ASP-04 |
| `tests/` | N/A | **No dedicated ASP-05 test suite exists** — gap to address in v1.0 |
| `tests/_stress_defect025.py` | 205 | Governed 9/9 stress runner (retained as a reference probe) |

---

## §2 — Current task registrations (live state)

`app/services/prediction.py:48-54`:

```python
VALID_TASKS = {
    "churn_prediction",
    "revenue_forecast",
    "anomaly_detection",
    "lead_scoring",
}
```

Four tasks. All routed through the single `run_prediction` Celery task
(same prompt shape — differentiated by `task` parameter inside the
LLM's system prompt). No per-task prompt rows in `prompt_templates`
(the prompt is hardcoded in the handler — **see Gap G-05-05 below**).

---

## §3 — Async pattern (Celery task structure, job_id issuance, result storage)

**Gateway path (`handle`, lines 63-94):**
- Generates `job_id = uuid.uuid4()` server-side.
- Creates an `async_jobs` row via `get_session()` (FastAPI request — consistent event loop; fine).
- Dispatches `celery_app.send_task("asp.prediction", ...)`.
- Returns `JobAcceptedResponse(202)` immediately.

**Celery worker (`run_prediction`, lines 228-328)** — post-DEFECT-025 fix:
- Five `asyncio.run(...)` calls, each with a per-invocation
  `create_async_engine` via one of three async helpers:
  - `_async_update_job_status` (2 call sites: running / completed).
  - `_async_emit_cost` (post-completion; ADR-006-wrapped).
  - `_fire_webhook_async` (isolated for test patching).
- Failure path: best-effort `_async_update_job_status('failed', error=...)` + `self.retry(exc=exc, countdown=60)`.
- ADR-010 transitions: `asp_prediction_job_running` / `_completed` / `_failed` / `_cost_emission_failed` / `_status_update_failed`.

**Job-result storage:** `async_jobs.result_json` JSONB column. Polled
via the existing `GET /api/v1/ai/jobs/{job_id}` Gateway endpoint
(no new endpoint needed).

---

## §4 — Current output schema

```python
# app/services/prediction.py:56-60
class PredictionOutput(BaseModel):
    scores:      dict[str, Any]
    explanation: str
    confidence:  float
    metadata:    dict[str, Any] = {}
```

One schema, all four tasks. `scores` is a free-form dict — shape is
task-dependent and not currently contract-locked. **See Gap G-05-03
below.**

No `ConfigDict(extra="...")` set on `PredictionOutput` — uses
Pydantic's default (strict, which is effectively `extra='ignore'`
for BaseModel without `extra='forbid'` set). Spec should set this
explicitly.

---

## §5 — ADR compliance gaps

| ADR | Status | Gap |
|---|---|---|
| **ADR-006** (cost-emission resilience) | ✅ **COMPLIANT** (post-DEFECT-025 fix) | `_async_emit_cost` call wrapped in `try/except` → `asp_prediction_cost_emission_failed` warn; does not break response path. |
| **ADR-010** (structlog everywhere) | ⚠️ **PARTIAL** | Five transition events emitted by the Celery task. Handler path (`handle`) emits only one event (`prediction_queued`). Should add `asp_prediction_invoke_start` / `asp_prediction_invoke_accepted` at the Gateway-boundary for parity with the ASP-04 logging contract. **G-05-01.** |
| **ADR-030** (capabilities + schemas) | ❌ **NON-COMPLIANT** | `prediction` service is **not** in `SERVICE_CAPABILITIES` (see `app/api/capabilities.py`). `TASK_SCHEMA_MODELS` has zero entries for any of the four prediction tasks. `GET /api/v1/ai/schemas/prediction/{task}` currently returns 422. **G-05-02.** |
| **ADR-008** (Pydantic `extra="forbid"` or `"ignore"` explicit) | ⚠️ **IMPLICIT** | `PredictionOutput` uses default `model_config`. Should be explicit — `extra="ignore"` per ADR-033 for LLM outputs. **G-05-04 (minor).** |
| **ADR-028** (async job pattern) | ✅ **COMPLIANT** | `async_jobs` row + `job_id` + polling contract — standard pattern. |
| **ADR-032** (new-format API keys) | ✅ **COMPLIANT** | Shared Gateway auth; no ASP-05-specific key surface. |

---

## §6 — Pre-existing prompt rows in `prompt_templates` for prediction tasks

**Live DB probe** (`SELECT ... FROM prompt_templates WHERE service_type='prediction'`):

```
# Expected: zero rows. Prompt is hardcoded in app/services/prediction.py::run_prediction
# (lines 241-256) as an f-string constant. No DB-backed prompt rows
# for any of the four tasks.
```

**Gap G-05-05** (MEDIUM). Per ADR-027 (prompts in DB, not code), the
four prediction prompts should be seeded in `prompt_templates`. v1.0
spec scope: migrate the hardcoded f-string into per-task rows with a
`{task}` placeholder variant or per-task ab_variants. Enables prompt
updates without code deploys + G-PROMPT-REACH coverage per the
expanded playbook rule.

---

## §7 — Pre-write gate results

| Gate | Status | Notes |
|---|---|---|
| **G-1 Schema** | N/A | No new Postgres tables expected in v1.0 (existing `async_jobs` + `cost_events` already carry the contract). |
| **G-2 Types** | N/A | Same. |
| **G-3 Contract** | Pending §6 of v1.0 draft | Consumer contract for `scores` per task is the primary Gap G-05-03. |
| **G-4 Audit (CHECK)** | N/A | No new CHECK constraints expected. |
| **G-5 Migration** | **Next migration: 0030** (confirmed free — `alembic/versions/` tail is 0029; head `0029` per `alembic current`). If prompt seed lands in v1.0, that's 0030. If F-03-03 assess_test_quality lands first, F-03-03 takes 0030 and ASP-05 takes 0031. **To be disambiguated at spec-write time.** |
| **G-6 Frontend** | N/A | No UI for ASP-05 in v1.0. |
| **G-7 Dependency** | Noted | New Pydantic schemas module candidate: `app/schemas/prediction_schemas.py` (migrate existing `PredictionOutput` + add per-task sub-schemas per G-05-03). |
| **G-8 Prompt Reach** | N/A until Gap G-05-05 scoped | If prompts move to DB, G-PROMPT-REACH matrix applies (4 tasks × 4 callers × 2 maturities = 32 probe minimum per the expanded playbook rule). |
| **Loop-affinity pre-spec check (new per ASP-OUT-064 playbook)** | ✅ **CLEAN** | DEFECT-025 already RESOLVED. `grep -nE 'create_engine\|asyncio.run' app/services/prediction.py` returns only the governed per-invocation-engine pattern. No CRITICAL findings. |

---

## §8 — Gap matrix (governed input to v1.0 spec)

| ID | Severity | Description | Proposed fix |
|---|---|---|---|
| **G-05-01** | LOW | Gateway handler emits only `prediction_queued` structlog event — not `asp_prediction_invoke_start` / `_accepted` for parity with ASP-04. | Add two transition events in `handle()`. |
| **G-05-02** | **HIGH** | ASP-05 absent from `SERVICE_CAPABILITIES` + `TASK_SCHEMA_MODELS` (ADR-030 non-compliance). | Register `prediction` + all four tasks in `app/api/capabilities.py`. Requires per-task Pydantic payload model (likely shared since all four use `data: dict`). |
| **G-05-03** | **HIGH** | `PredictionOutput.scores: dict[str, Any]` is untyped — no contract lock for consumers. Four distinct tasks have four distinct score shapes in practice. | v1.0: author per-task result models (ChurnScores, RevenueForecastScores, AnomalyDetectionScores, LeadScoringScores). Reduce `Any` to governed field schema. LLM output parser branches on `task`. |
| **G-05-04** | LOW | `PredictionOutput` missing explicit `ConfigDict(extra="...")`. | Add `extra="ignore"` per ADR-033. |
| **G-05-05** | MEDIUM | Prompts hardcoded in `prediction.py` — ADR-027 violation. | Migration: four prompt rows (one per task) at `service_type='prediction'`, `caller_module='*'`, `maturity_level='*'`. Handler fetches via existing `prompt_registry.get_prompt` path. |
| **G-05-06** | MEDIUM | No dedicated `tests/test_prediction.py` — zero AC coverage. | v1.0 AC suite required. ≥20 ACs covering handler dispatch, async contract, cost emission, ADR compliance, per-task output shape, cross-tenant rejection. |
| **G-05-07** | LOW | No OpenAPI snapshot ever captured at a prediction-specific head. | Ship as part of I-DOC-style governance-sync commit: `docs/openapi/asp-openapi-<head>.json` at spec closure. |

No CRITICAL gaps. DEFECT-025 was the CRITICAL blocker; it is resolved.
v1.0 spec scope is almost entirely contract-lock work + per-task
output shapes + capabilities registration.

---

## §9 — Confirmed decisions preview (for §1–§5 of v1.0 spec draft)

- **§1 Summary:** ASP-05 Prediction governance closure. Four existing
  tasks (no new tasks in v1.0). Per-task output contract lock.
  Capabilities + schemas registration. DB-backed prompts.
- **§2 Background:** DEFECT-025 already RESOLVED (Stream A / S-1 done).
  Surveyed gaps G-05-01..07. No consumer has driven ASP-05 Celery task
  end-to-end in pilot — first live exercise will be via the v1.0 AC
  suite.
- **§3 Scope:** S-1 per-task output schemas (G-05-03) · S-2
  capabilities registration (G-05-02) · S-3 prompts-to-DB migration
  (G-05-05) · S-4 AC suite (G-05-06) · S-5 ADR-010 event parity
  (G-05-01) · S-6 Pydantic `extra="ignore"` hygiene (G-05-04) · S-7
  OpenAPI snapshot + governance sync (G-05-07).
  Out of scope: new tasks, frontend.
- **§4 Classification:** Async (Celery). Quality tier: `standard`
  (Haiku) — prediction is inference-grade, not generation-grade.
  Can be overridden per task at the request layer if an upgrade is
  needed later.
- **§5 Data Model:** No new Postgres tables. Migration 0030 (or later
  — disambiguated against F-03-03) seeds four prompt rows.

---

## §10 — Open questions for Architect ruling at spec-draft time

| ID | Question | Default answer |
|---|---|---|
| **OQ-05-1** | Per-task output schemas — one shared `PredictionOutput` with a `scores` Pydantic union type, or four distinct output models? | Four distinct, routed through the existing `task` dispatch. |
| **OQ-05-2** | Prompt-seed migration (G-05-05) — four rows or one row with `{task}` placeholder + four `ab_variant` keys? | Four rows (simpler; mirrors the F-03-02 pattern; cleaner change-control per ADR-027). |
| **OQ-05-3** | Quality tier default — keep `standard` (Haiku) or bump to `enhanced` (Sonnet)? | `standard`. Prediction output is numeric + short-form; Haiku is sufficient. |
| **OQ-05-4** | Migration number if F-03-03 lands first (taking 0030). | Allocate 0031; G-5 migration column to be disambiguated at spec-write time. |
| **OQ-05-5** | Test harness — integration tests with mocked Anthropic (like F-03-02 + Doc-Intel) or a new pattern for the four quantitative tasks? | Same pattern. Mocked Anthropic; direct Celery-task invocation (no broker); per-invocation engine for test scaffolding. |

---

## §11 — Summary

- **Survey complete.** No new critical findings. DEFECT-025 already
  resolved via ASP-OUT-064.
- **7 gaps identified** (2 HIGH, 3 MEDIUM, 2 LOW). All are contract-
  lock / observability / ADR-compliance work — no infrastructure
  defects, no loop-affinity bugs, no CRITICALs.
- **v1.0 spec cycle is a Category-B governance closure** — existing
  functionality, new contract-lock + tests. Expected to be faster
  than ASP-04 (which had the DEFECT-024 gate, OCR pipeline, frontend,
  new documents table). Rough scope: 20-25 ACs, one migration (0030
  or 0031), no DDL.
- **Recommended next directive:** Architect review of this survey →
  spec cycle green light → Batch 1 authoring.

---

## §12 — Post-F-03-03 refresh (ASP-OUT-073, 2026-04-21 later)

This section refreshes §1–§11 for platform shifts since the survey
was originally filed at commit `3d1bbec` (ASP-OUT-066 Task 1). Filed
in response to ASP-OUT-073 directive to "proceed per ASP-OUT-072"
— ASP-OUT-072's enumerated eight items did not reach the ASP session
(fifth session routing gap, logged in ASP-FEAT-ASP-04 v1.0 IMPL-LOG
§Routing gaps). The refresh updates state where it has materially
changed; §1–§11 remain otherwise valid.

### §12.1 — Migration number allocation resolved

**OQ-05-4 RESOLVED** at F-03-03 build time: F-03-03 took **0030**
(commit `3f0e38e`, ASP-NOTE-014). Therefore **ASP-05 v1.0 prompt-seed
migration is 0031**. Confirmed free: `ls alembic/versions/` tail is
`0030_seed_f0303_assess_test_quality_prompt.py`. §7 G-5 row may now
be written concretely as "Migration 0031" at spec-write time.

### §12.2 — Platform state delta since 3d1bbec

| Field | At `3d1bbec` | Now |
|---|---|---|
| Migration head | 0029 | **0030** |
| Governed services | 7/14 | 7/14 (unchanged) |
| Open defects | 0 | 0 |
| ASP-03 `VALID_TASKS` size | 12 | 13 (assess_test_quality added per ASP-NOTE-014) |
| Celery task DB-write rule | governed (ASP-OUT-064) | governed; applied to ASP-05 pre-spec check below |

### §12.3 — Pre-build loop-affinity re-check (per ENGINEERING-PLAYBOOK §12 pre-spec rule)

Re-ran the mandatory grep per the expanded playbook rule added in
ASP-OUT-064:

```
grep -rn "create_engine\|asyncio.run\|get_session\|emit_cost" \
    app/services/prediction.py app/api/
```

| Site | Risk | Notes |
|---|---|---|
| `prediction.py::handle()` — `async with get_session()` | LOW | FastAPI request path. Consistent event loop; shared pool correct. |
| `prediction.py::run_prediction` (Celery task) — 5 `asyncio.run(...)` calls | LOW | All route through `_async_update_job_status` / `_async_emit_cost` / `_fire_webhook_async`, each using per-invocation `create_async_engine` + `engine.dispose()` per the DEFECT-025 fix (commit `0695c38`). No shared-pool helper calls from inside `asyncio.run()`. |
| `prediction.py::_async_emit_cost` | LOW | Per-invocation engine + direct `INSERT INTO cost_events` SQL. Mirrors the doc_intelligence pattern. No shared-pool risk. |

**Result: CLEAN.** No CRITICAL findings. Zero new defects surfaced
by the loop-affinity re-check. ASP-05 v1.0 has no S-1 gate bug to
remediate — Stream A / S-1 was handled pre-cycle by DEFECT-025
resolution. This is the first governance cycle to benefit from the
pre-build check passing on the first pass (ASP-04 had DEFECT-024
CRITICAL; F-03-03 had the check marked N/A because ASP-03 is
synchronous).

### §12.4 — §8 gap matrix refinements

No new gaps surfaced by the refresh. The 7 gaps identified in §8
remain the authoritative input.

**One clarification on G-05-04** (`extra="..."` on `PredictionOutput`):
The existing `PredictionOutput` at `app/services/prediction.py:53`
uses Pydantic defaults (no explicit `ConfigDict`). Per ADR-033, LLM
output models should use `extra="ignore"` explicitly. This remains
a LOW gap; spec Batch 1 will set it verbatim. No change to the gap
itself — just note that the fix is a one-line addition to the
model.

### §12.5 — Cross-reference to F-03-03 lessons

F-03-03 shipped in the same day as this survey was filed. Two
patterns surfaced there that inform the ASP-05 spec:

1. **In-process TestClient vs live httpx.** F-03-03 initially used
   live httpx against the Docker ai-service and hit the live
   Anthropic API because the test process cannot patch the server
   process's LLM client. Rewrote to use `authed_client` +
   `mock_anthropic` from `conftest.py`. **Lesson for ASP-05 v1.0
   S-4 (AC suite):** start with in-process TestClient pattern;
   avoid live httpx against Docker for any AC that needs to mock
   an LLM.

2. **Prep-draft-as-authoritative pattern.** F-03-03 build used the
   ASP-OUT-066 Task 2 prep draft as the authoritative shape because
   PAP's v3.0 formal schema had not arrived. Any later delta → TSCD.
   **Lesson for ASP-05 v1.0:** if the spec is paused awaiting
   external input, the Batch-1 draft can be authored as a prep
   draft ahead of the cycle green light without blocking.

### §12.6 — Open items for Architect at spec-write time

No new items beyond the five OQ-05-N from §10. OQ-05-4 is now
resolved in-line: migration 0031 for the ASP-05 prompt seed.

### §12.7 — Summary (post-refresh)

- Survey remains **complete** post-refresh. Zero new CRITICAL or HIGH
  findings. Platform delta (migration head 0029 → 0030, ASP-03
  VALID_TASKS 12 → 13) does not change the ASP-05 gap matrix.
- Loop-affinity pre-check **CLEAN** — DEFECT-025 already RESOLVED
  per ASP-OUT-064. No S-1 gate bug for ASP-05 v1.0.
- Migration number **resolved** — ASP-05 prompt-seed migration is
  **0031** (F-03-03 took 0030).
- Recommended next directive **unchanged** — Architect review → spec
  cycle green light → Batch 1 authoring.
