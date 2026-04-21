# ASP-FEAT-ASP-05 v1.0 — Prediction Service

| Field | Value |
|---|---|
| Feature ID | ASP-FEAT-ASP-05 |
| Version | v1.0-draft |
| Service governed | ASP-05 Prediction Service |
| Status | **IN SPEC — BATCH 1 SURFACED FOR REVIEW** |
| Authored | 2026-04-21 |
| Commit head | `4793ac2` (post-ASP-OUT-073 survey refresh) |
| Migration head | **0030** → 0031 (prompt-only seed for the four tasks, per §5 below) |
| Spec driver | Four-task contract lock + ADR-compliance closure (ADR-006 / ADR-010 / ADR-030) |
| Governance trail | ASP-OUT-066 Task 1 (pre-spec survey `3d1bbec`) · ASP-OUT-073 survey refresh (`4793ac2`, §12) · ASP-OUT-074 Batch 1 green light + confirmed §1–§5 scope |
| Predecessor | None — ASP-05 was ACTIVE (pre-governance). This is the first full governance spec for the service. |

---

## §1 Summary

ASP-05 Prediction Service governs four existing tasks: `churn_prediction`,
`revenue_forecast`, `anomaly_detection`, `lead_scoring`. All four are
**asynchronous** — Gateway returns `JobAcceptedResponse(202)` immediately
and Celery processes via the `asp.prediction` task.

**LLM tier: `enhanced` (Claude Sonnet) for all four tasks** per
ASP-OUT-074 directive — prediction outputs demand reasoning quality
above short-form generation (Haiku). Change is request-layer only;
ASP-11 Model Router already maps `quality_tier="enhanced"` to Sonnet.

**LogiCRM is the primary consumer.** PAP does not currently drive
ASP-05 end-to-end; the four tasks exist for LogiCRM churn + revenue
+ anomaly + lead-scoring workflows. Consumer contract lock is the
primary v1.0 deliverable.

**DEFECT-025 resolved in pre-spec cycle** (commit `0695c38`,
ASP-OUT-064). The psycopg2 class-of-bug was the Stream A / S-1 blocker;
it is already gone. This spec's S-1 is the confirmation lock, not a
fresh remediation.

**No new tables.** v1.0 is contract-lock + ADR-compliance + formalised
Pydantic output schemas + DB-backed prompts per ADR-027.

**Classification summary:** Category-B governance closure (existing
functionality, new contract-lock + tests + prompt migration). Expected
scope: 20-25 ACs, one prompt-only migration (0031), no DDL.

---

## §2 Background

### §2.1 Pre-governance state

ASP-05 was **ACTIVE (pre-governance)** from pilot launch through
2026-04-21. It is present in `app/services/prediction.py` (337 LOC
post-DEFECT-025 fix) and wired into the Gateway router as an async
service; its four tasks were implicit in the handler but absent from
`prompt_templates`, `SERVICE_CAPABILITIES`, and `TASK_SCHEMA_MODELS`.

**No consumer has invoked the ASP-05 Celery worker end-to-end in the
pilot environment** before the DEFECT-025 fix. The enqueue path (FastAPI
→ `async_jobs` INSERT) succeeded; the worker path was broken because
`_sync_update_job_status` used `sqlalchemy.create_engine` with
regex-stripped `+asyncpg`, selecting the unshipped psycopg2 driver.
Identical to DEFECT-022 (cost aggregator) and DEFECT-024 (doc
intelligence).

**Post-DEFECT-025 state (0695c38):** `prediction.py` ported to asyncpg
with per-invocation `create_async_engine` + `engine.dispose()` at all
three DB-touching sites, matching the ENGINEERING-PLAYBOOK §12 Celery
DB-write rule (added in ASP-OUT-064). 9-successive-invocation stress
test PASS. ADR-006 cost-emission `try/except` + ADR-010 five-event
structlog transitions bundled into the same commit.

### §2.2 Gap matrix (from pre-spec survey §8, accepted per ASP-OUT-074)

Seven gaps identified in the pre-spec survey (`3d1bbec` §8, refreshed
in `4793ac2` §12). All are contract-lock / observability / ADR-compliance
work — no infrastructure defects, no loop-affinity bugs, no CRITICALs
remaining (DEFECT-025 RESOLVED in-cycle).

| ID | Severity | v1.0 disposition |
|---|---|---|
| **G-05-01** LOW — Gateway handler emits only `prediction_queued` | S-4 structlog parity fix (add `_invoke_start` / `_invoke_accepted`) |
| **G-05-02** HIGH — ASP-05 absent from `SERVICE_CAPABILITIES` + `TASK_SCHEMA_MODELS` (ADR-030 non-compliance) | **S-2** register all four tasks |
| **G-05-03** HIGH — `PredictionOutput.scores: dict[str, Any]` untyped | **S-5** four per-task Pydantic result models |
| **G-05-04** LOW — `PredictionOutput` missing explicit `ConfigDict(extra="...")` | S-5 bundle (add `extra="ignore"` per ADR-033) |
| **G-05-05** MEDIUM — prompts hardcoded in `prediction.py` (ADR-027 violation) | **S-7** migration 031 seeds four prompt rows |
| **G-05-06** MEDIUM — no `tests/test_prediction.py` | Implementation-side AC suite (post Batch 3 acceptance) |
| **G-05-07** LOW — no OpenAPI snapshot ever captured at a prediction-specific head | Closure-commit `docs/openapi/asp-openapi-0031.json` |

### §2.3 Cross-references

- `docs/spec-drafts/ASP-FEAT-ASP-05-v1_0-PRE-SPEC-SURVEY.md` — §1–§11
  authoritative survey (`3d1bbec`); §12 post-F-03-03 refresh (`4793ac2`).
- `ASP-DEFECT-REGISTER.md` — DEFECT-025 closure narrative (RESOLVED
  `0695c38`; AC verification via 9/9 stress; stress script retained at
  `tests/_stress_defect025.py`).
- `ENGINEERING-PLAYBOOK.md` §12 — Celery task DB-write rule + pre-spec
  survey mandatory check (added under ASP-OUT-064; governs ASP-05's
  pre-build re-check in §7.3 of the survey — result **CLEAN**).
- **Four prior instances of the loop-affinity class of bug** already
  resolved: DEFECT-022 (ASP-10), DEFECT-024 (ASP-04), I-DOC-11
  extension (ASP-04 cost emission), DEFECT-025 (ASP-05).

---

## §3 Scope

### §3.1 In scope — seven governance items

| ID | Item | Sequencing note |
|---|---|---|
| **S-1** | **DEFECT-025 confirmation lock.** No remediation work — already resolved in `0695c38`. Spec records the fix + verification contract (9/9 stress) as the governed floor. AC block enforces: static grep for `psycopg2`/`create_engine(sync_url)` returns zero code hits; 9-successive-invocation stress still PASS. | Already complete pre-cycle; this spec locks regression via AC. |
| **S-2** | **ADR-030 compliance** — register `prediction` in `SERVICE_CAPABILITIES` and all four tasks in `TASK_SCHEMA_MODELS` at `app/api/capabilities.py`. `GET /api/v1/ai/schemas/prediction/{task}` currently 422s; must 200 post-fix. | Depends on S-5 (payload model needed for schema-export). |
| **S-3** | **ADR-006 compliance re-verification** — `_async_emit_cost` in `prediction.py` is already wrapped via try/except at the Celery task boundary (post-DEFECT-025 fix, `0695c38`). Spec records this as the governed floor; AC block enforces. | Already implemented; AC coverage added. |
| **S-4** | **ADR-010 structlog parity** — Gateway handler `handle()` emits only `prediction_queued` today. Add `asp_prediction_invoke_start` + `asp_prediction_invoke_accepted` for parity with ASP-04's Gateway-boundary logging contract. Celery task already emits five transition events per DEFECT-025 fix. | Small handler-side addition; one commit. |
| **S-5** | **Per-task Pydantic output schemas** (OQ-05-1 rationale). Four new models: `ChurnPredictionResult`, `RevenueForecastScores` (or `RevenueForecastResult`), `AnomalyDetectionResult`, `LeadScoringResult`. Each replaces the untyped `scores: dict[str, Any]` with a governed shape. New module `app/schemas/prediction_schemas.py`. Handler dispatches via `req.task` → per-task schema parse. `ConfigDict(extra="ignore")` per ADR-033. | Biggest surface change in this cycle. |
| **S-6** | **G-PROMPT-REACH verification** (per ENGINEERING-PLAYBOOK §G-PROMPT-REACH expanded rule, ASP-OUT-051). Once S-7 migration lands, run the governed 24-probe matrix (4 tasks × 4 caller values × 2 maturities, limited to the seeded caller + playwright_runner + test_generator + `*`) = 32 probes minimum per the playbook. All 32 must PASS before the spec closes. | Verification gate at migration closure. |
| **S-7** | **Prompts to DB** (ADR-027 compliance) — migration 0031 seeds four prompt rows (`service_type='prediction'`, one row per task, `caller_module='*'`, `maturity_level='*'`, `version=1`, `ab_variant=NULL`). Handler migrates from the hardcoded f-string to a `prompt_registry.get_prompt` call. | Blocks on S-5 (prompts reference the governed output-schema contract in their STRICT RULES). |

### §3.2 Out of scope (v1.0)

Explicitly excluded per ASP-OUT-074 directive:

- New prediction algorithms.
- Real-time / streaming prediction.
- Model training / fine-tuning.
- Prediction feedback loop.
- LogiCRM direct DB integration.

These are not deferred — they are simply not this spec. A future v1.1
or tenant-specific feature proposal can take them up.

### §3.3 Pre-write gate (summary)

| Gate | Status |
|---|---|
| G-1 Schema | N/A — no Postgres tables added |
| G-2 Types | N/A |
| G-3 Contract | Pending §6 (Batch 2) |
| G-4 Audit (CHECK) | N/A |
| G-5 Migration | **0031** (free; F-03-03 took 0030 per ASP-NOTE-014; ASP-05 takes 0031 per §12 OQ-05-4 resolution) |
| G-6 Frontend | N/A — no UI |
| G-7 Dependency | New module `app/schemas/prediction_schemas.py` (S-5); `app/services/prediction.py` handler edits (S-2, S-4, S-7); `app/api/capabilities.py` registration (S-2) |
| **G-8 Prompt Reach** | Pending S-6 post-S-7 — 32-probe matrix minimum |
| **Loop-affinity pre-spec check (ENGINEERING-PLAYBOOK §12, post-ASP-OUT-064)** | ✅ **CLEAN** — DEFECT-025 RESOLVED; `grep` on `prediction.py` confirms all three helpers use per-invocation engine + dispose |

---

## §4 Classification

### §4.1 Service type

ASP-05 Prediction is **asynchronous** (Celery). Zone 2 Shared Contract
surface via the Gateway (ADR-001). No new zone classification is
introduced — the existing ASP-05 surface is already Zone 2.

### §4.2 LLM tier matrix

| Task | Tier | Model (via ASP-11 Model Router) | Rationale |
|---|---|---|---|
| `churn_prediction` | `enhanced` | Claude Sonnet | Multi-factor reasoning on customer history + behavioural signals. |
| `revenue_forecast` | `enhanced` | Claude Sonnet | Time-series reasoning + outlier interpretation. |
| `anomaly_detection` | `enhanced` | Claude Sonnet | Pattern-recognition + cause-hypothesis generation. |
| `lead_scoring` | `enhanced` | Claude Sonnet | Multi-signal aggregation with justification. |

Per ASP-OUT-074 directive: *"LLM calls: enhanced (Sonnet) for all four
tasks."* Prior pre-governance state routed through `standard` (Haiku)
by default — the tier upgrade is a request-layer default change in the
handler, not a prompt change. `quality_tier` on the `InvokeRequest`
remains the authoritative override for callers that want to force a
different model.

### §4.3 Async contract

Pre-governance state preserved with one addition:

- **Request.** `POST /api/v1/ai/invoke` with `service_type="prediction"`
  and one of the four tasks. Gateway returns
  `JobAcceptedResponse(request_id, job_id, status='queued')` immediately.
- **Worker.** `asp.prediction` Celery task. Transitions through
  `queued → running → completed | failed` on `async_jobs.status`.
- **Polling.** `GET /api/v1/ai/jobs/{job_id}` — tenant-scoped, 404 on
  cross-tenant (ADR-022 leak-safe).
- **Webhook.** Optional `payload.webhook_url` fires on completion via
  `app.webhook.service.fire_webhook`.

**ADR-010 structlog transitions** (post-DEFECT-025, committed `0695c38`):
- `asp_prediction_job_running` (Celery task entry)
- `asp_prediction_job_completed` (success exit, with `duration_ms`,
  token counts)
- `asp_prediction_job_failed` (exception, with `error`, `reason`)
- `asp_prediction_cost_emission_failed` (cost-meter exception — ADR-006
  path)
- `asp_prediction_status_update_failed` (double-failure path)

**S-4 additions** at the Gateway boundary:
- `asp_prediction_invoke_start` (handler entry, pre-enqueue)
- `asp_prediction_invoke_accepted` (post-enqueue, 202 returned)

### §4.4 No binary input

ASP-05 does not handle binary input. All four tasks take JSON payloads
only. No MinIO dependency, no OCR pipeline, no file-upload surface.

### §4.5 Reference implementations

- **DEFECT-025 fix** (`app/services/prediction.py` @ `0695c38`) — the
  governed baseline for this spec. Already in compliance with
  ENGINEERING-PLAYBOOK §12 Celery DB-write rule.
- **DEFECT-022 fix** (`app/cost/aggregator.py`) — first instance of the
  pattern; still the canonical reference.
- **ASP-FEAT-ASP-04 v1.0** — pattern precedent for service-level v1.0
  closure with ADR-006/010/030 compliance + Pydantic schema module.
- **F-03-03 `assess_test_quality`** (ASP-NOTE-014) — pattern for
  per-task Pydantic models + wildcard prompt seed (relevant to S-5 +
  S-7).

---

## §5 Data Model

### §5.1 No new Postgres tables

ASP-05 v1.0 introduces **no new tables**. Existing infrastructure
(`async_jobs`, `cost_events`, `prompt_templates`) already carries the
contract. Migration 0031 is **prompt-only** — four rows, no DDL.

### §5.2 Current `prompt_templates` state — verified live

Live DB probe (2026-04-21 at Batch 1 authoring time):

```
SELECT service_type, task, caller_module, maturity_level, version, is_active
FROM prompt_templates
WHERE service_type='prediction'
   OR task IN ('churn_prediction','revenue_forecast',
               'anomaly_detection','lead_scoring');
-- (0 rows)
```

**Zero prompt rows** for any of the four tasks. Confirmed: prompts are
hardcoded in `app/services/prediction.py::run_prediction` as an
f-string constant. Migration 0031 seeds all four (no deactivations,
no updates — clean additions).

### §5.3 Migration 0031 — prompt seed (governed structure)

Four `INSERT` statements, one per task. All rows seeded at the
post-ASP-OUT-051 wildcard pattern:

| Column | Value |
|---|---|
| `service_type` | `'prediction'` |
| `task` | one of `churn_prediction` / `revenue_forecast` / `anomaly_detection` / `lead_scoring` |
| `caller_module` | `'*'` |
| `maturity_level` | `'*'` |
| `version` | `1` |
| `is_active` | `TRUE` |
| `ab_variant` | `NULL` |
| `system_prompt` | Governed in §9 (Batch 2) |
| `user_prompt_template` | Governed in §9 (Batch 2) |

Downgrade deletes the four rows by exact tuple.

**Migration structural preview:**

```python
# alembic/versions/0031_seed_prediction_prompts.py
# revision = "0031"; down_revision = "0030"

_INSERT = """
    INSERT INTO prompt_templates
      (service_type, task, caller_module, maturity_level, version,
       is_active, ab_variant, system_prompt, user_prompt_template)
    VALUES
      ('prediction', :task, '*', '*', 1, TRUE, NULL,
       :sys, :usr)
"""
# 4 tasks × 1 INSERT = 4 ops. Full prompt bodies land in §9 Batch 2.
```

**Reach gate (S-6) — 32 probes at minimum** per the expanded
G-PROMPT-REACH rule:

| Caller | Maturity |
|---|---|
| `playwright_runner` | `L2` |
| `playwright_runner` | `*` |
| `test_generator` | `L2` |
| `test_generator` | `*` |
| `logicrm` | `L2` |
| `logicrm` | `*` |
| `*` | `L2` |
| `*` | `*` |

8 caller × maturity combinations × 4 tasks = **32 probes**. All 32
must pass pre-commit per ENGINEERING-PLAYBOOK §G-PROMPT-REACH
(expanded rule). **LogiCRM** added to the standard matrix because it
is the primary consumer per §1.

Reference probe runner: `tests/_reach_probe_f0302.py` — copy-adapted
per the tests/README.md governed pattern.

### §5.4 Pydantic models — new module `app/schemas/prediction_schemas.py`

S-5 creates a new dedicated schemas module. Existing inline
`PredictionOutput` in `app/services/prediction.py:53-57` is **removed**
and replaced by four per-task result models. The handler dispatches on
`req.task` to pick the appropriate model for `model_validate_json`.

**Governed shapes** (to be confirmed during Batch 2 §7 Request/Response
Detail authoring; first-cut scaffolding only here):

```python
# app/schemas/prediction_schemas.py  (NEW)

from typing import Optional
from pydantic import BaseModel, ConfigDict


# ─── Shared fragments ──────────────────────────────────────────────

class _PredictionMeta(BaseModel):
    """Optional metadata shared across prediction tasks."""
    model_config = ConfigDict(extra="ignore")
    confidence:        float
    explanation:       str
    metadata:          dict = {}


# ─── Per-task result models ────────────────────────────────────────

class ChurnPredictionResult(BaseModel):
    """Customer churn probability + per-factor attribution."""
    model_config = ConfigDict(extra="ignore")
    churn_probability:   float                # [0.0, 1.0]
    risk_tier:           str                  # "low" | "medium" | "high"
    contributing_factors: list[str]           # top 3-5 signals
    confidence:          float
    explanation:         str


class RevenueForecastResult(BaseModel):
    """Forward revenue projection with scenario bands."""
    model_config = ConfigDict(extra="ignore")
    forecast_period:     str                  # e.g. "Q3 2026", "next_30_days"
    projected_revenue:   float                # USD (denomination governed by caller)
    lower_band:          Optional[float] = None
    upper_band:          Optional[float] = None
    confidence:          float
    explanation:         str


class AnomalyDetectionResult(BaseModel):
    """Detected anomaly with severity + suggested action."""
    model_config = ConfigDict(extra="ignore")
    anomalies:           list[dict]           # first-cut; per-field tightening in Batch 2
    severity:            str                  # "info" | "warning" | "critical"
    confidence:          float
    explanation:         str


class LeadScoringResult(BaseModel):
    """Lead conversion score + priority recommendation."""
    model_config = ConfigDict(extra="ignore")
    lead_score:          float                # [0.0, 100.0] (scaled differently from churn_probability)
    priority:            str                  # "low" | "medium" | "high"
    recommended_action:  str
    confidence:          float
    explanation:         str
```

**Rationale for four distinct models** (OQ-05-1 disposition): each task
has a semantically distinct output shape. A single `scores: dict[str,
Any]` Union type loses contract precision. Four models give consumers
a precise per-task JSON Schema via the ADR-030 `/schemas/prediction/{task}`
endpoint.

**Pending confirmation in Batch 2 §7:**

- `AnomalyDetectionResult.anomalies: list[dict]` — should the inner
  shape be a `BaseModel` too? (Likely yes; placeholder until Batch 2.)
- `LeadScoringResult.lead_score` range — `[0.0, 100.0]` vs `[0.0, 1.0]`.
  Current LogiCRM convention is 0-100; Batch 2 will confirm and freeze.
- `ChurnPredictionResult.risk_tier` Literal vs `str` — depends on
  whether LogiCRM surface enforces the three-state set.

### §5.5 Payload shapes

Current `app/services/prediction.py::handle()` accepts `payload: dict`
without governed shape. S-5 does **not** govern payload shapes in v1.0
— consumer payloads vary widely per task (churn input ≠ anomaly
input). The `payload` dict stays Pydantic-loose (`dict[str, Any]`)
with `ConfigDict(extra="ignore")` on the containing request model.

Governed payload shapes per task become a **v1.1 candidate** — once
LogiCRM contract details are locked, the payload Pydantic models ship
as a Type B additive.

### §5.6 SQLAlchemy ORM

No new ORM classes. Existing `AsyncJob` + `CostEvent` + `PromptTemplate`
cover the data surface.

### §5.7 Pre-write gate — G-1..G-8 at Batch 1 close

| Gate | Status | Notes |
|---|---|---|
| G-1 Schema | ✓ §5.1 N/A (no new tables) | |
| G-2 Types | ✓ §5.1 N/A | |
| G-3 Contract | Pending §6 (Batch 2) | |
| G-4 Audit (CHECK) | ✓ N/A | |
| G-5 Migration | ✓ 0031 structural preview in §5.3; full SQL in §9 Batch 2 | |
| G-6 Frontend | ✓ N/A | |
| G-7 Dependency | Noted: new module `app/schemas/prediction_schemas.py`; handler edits in `app/services/prediction.py`; capabilities registration in `app/api/capabilities.py` | |
| G-8 Prompt Reach | Pending post-S-7 — 32-probe matrix (§5.3) | |

---

**End of Batch 1 (§1–§5).** Batch 2 (§6 API Contract · §7 Request/Response
Detail · §8 Caller Integration Guide · §9 LLM/Prompt Design · §10 Security
Requirements) follows on review.

**Awaiting Architect review before Batch 2 authoring.** Points of
particular interest for the review pass:

1. §4.2 — `enhanced` tier for all four tasks (directive-confirmed). Any
   cost-budget concern at full Sonnet? (Prediction payloads are small;
   likely OK.)
2. §5.3 — 32-probe reach matrix includes `logicrm` caller in addition
   to the standard `playwright_runner` / `test_generator` / `*`. Confirm
   LogiCRM callers use `caller_module="logicrm"` at the Gateway.
3. §5.4 — Four per-task result models (OQ-05-1 disposition locked as
   "four distinct"). Three open detail questions flagged for Batch 2
   confirmation (anomalies inner shape, lead_score range, risk_tier
   Literal).
4. §5.5 — Governed payload shapes deferred to v1.1 (pending LogiCRM
   contract details). Confirm this boundary is acceptable for v1.0 or
   whether a loose `dict` payload is itself a HIGH gap needing
   immediate coverage.
