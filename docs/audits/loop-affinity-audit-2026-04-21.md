# Loop-Affinity Platform Audit — 2026-04-21

**Directive:** ASP-OUT-063
**MSG-ID:** DEV-IN-063
**Author:** ASP Dev Team
**Scope:** `app/services/`, `app/cost/`, `app/api/`, `app/ontology/`, `app/worker.py`
**Method:** `grep -rn "create_engine\|asyncio.run\|get_session\|emit_cost"` across the above paths + manual inspection of every hit.
**Precedents (historical instances of this class of bug):**
- **ASP-DEFECT-022** (ASP-10 cost aggregator; RESOLVED `d158221`) — sync `psycopg2` via `create_engine(sync_url)`.
- **ASP-DEFECT-024** (ASP-04 doc_intelligence, three sites; RESOLVED `e0a1244`) — same class.
- **ASP-FEAT-ASP-04 v1.0 I-DOC-11 in-cycle extension** (ASP-04 `_async_emit_cost`; fixed `1ccf85b`; NOT a separate defect — same class, caught by AC suite).

## Findings table

| # | File | Line(s) | Pattern | Risk | Disposition |
|---|---|---|---|---|---|
| **1** | `app/services/prediction.py` | 80–86 | **Sync `create_engine(sync_url)` with regex-stripped `+asyncpg`** — psycopg2 driver implicit; not in `requirements.txt`. | **CRITICAL** | **NEW DEFECT — ASP-DEFECT-025.** Identical pattern to DEFECT-024. Every ASP-05 Celery task that transitions `async_jobs` will fail on first invocation with `ModuleNotFoundError: No module named 'psycopg2'`. ASP-05 Prediction has never successfully completed an end-to-end Celery task in the pilot environment for the same reason ASP-04 hadn't before DEFECT-024 — no consumer has driven it. |
| **2** | `app/services/prediction.py` | 118, 141, 168 | `_sync_update_job_status(...)` calls from inside Celery task `run_prediction`. | **CRITICAL** | Dependent on finding #1. Fix target in DEFECT-025 remediation (asyncpg port). |
| **3** | `app/services/prediction.py` | 146–165 | `asyncio.run(_emit_and_webhook())` that calls `emit_cost_event` → `get_session()` → shared app-wide pool. | **HIGH** | Same loop-affinity pattern as the `_async_emit_cost` extension caught during I-DOC-11. `cost_events` rows for ASP-05 prediction calls are likely never written (emission catches + logs silently per ADR-006). Fix target: rewrite on same per-invocation `create_async_engine` + direct `INSERT INTO cost_events` pattern used in `doc_intelligence._async_emit_cost`. Bundle with DEFECT-025 fix. |
| **4** | `app/services/doc_intelligence.py` | 120 | `async with get_session() as session:` inside `handle()` — FastAPI request path. | **LOW** | Fine. Runs under the FastAPI event loop (consistent across the request). Not `asyncio.run`. **No action.** |
| **5** | `app/services/doc_intelligence.py` | 629–817 | Multiple `asyncio.run(_async_*(...))` calls from Celery task `process_document`. | **LOW** | Already resolved — all `_async_*` helpers use per-invocation `create_async_engine` per ENGINEERING-PLAYBOOK §12. Verified by AC-DOC-S1-01 (9/9 stress test). **No action.** |
| **6** | `app/services/doc_intelligence.py` | 505 | `_async_emit_cost` definition. | **LOW** | Already resolved in `1ccf85b` (I-DOC-11 extension) — now uses per-invocation engine + direct INSERT. Same pattern as item #3's recommended fix. **No action.** |
| **7** | `app/cost/aggregator.py` | 106 | `asyncio.run(_do_aggregation(report_month))`. | **LOW** | Already resolved — `_do_aggregation` uses per-invocation `create_async_engine` per DEFECT-022 fix. Reference implementation. **No action.** |
| **8** | `app/cost/meter.py` | 36–61 | `emit_cost_event(...)` — `async with get_session() as session:` + `session.add(event)`. | **MEDIUM** | **Helper itself is fine for FastAPI-request callers** (upload endpoint, gateway cost emission, etc.). The **caller context** determines safety: if called from inside `asyncio.run()` in a Celery task, it has the loop-affinity bug. Currently called from: doc_intelligence (already replaced by `_async_emit_cost`), prediction (BROKEN per finding #3), documents upload endpoint (FastAPI request, FINE), gateway invoke path (FastAPI request, FINE). **No code change** to the helper itself; callers must be audited. DEFECT-025 will migrate prediction away. |
| **9** | `app/cost/meter.py` | 66–71 | `check_quota(tenant_id, ...)` — `async with get_session()`. | **LOW** | Called only from the Gateway invoke path (FastAPI request). Not called from any Celery task. **No action.** |
| **10** | `app/cost/meter.py` | 85–90 | Monthly cost-report read helper — `async with get_session()`. | **LOW** | Called only from `/api/v1/cost/*` HTTP endpoints (FastAPI request path). **No action.** |
| **11** | `app/api/documents.py` | 260–261 | `await emit_cost_event(...)` in the upload endpoint. | **LOW** | FastAPI request path — consistent event loop, shared pool correct. Wrapped in try/except per ADR-006. **No action.** |
| **12** | `app/api/capabilities.py` / `app/api/dashboard.py` | (multiple) | `async with engine.begin()` with per-invocation `create_async_engine`. | **LOW** | All dashboard-router DB touches already use per-invocation engines (following the DEFECT-024 playbook). **No action.** |
| **13** | `app/ontology/manager.py` | N/A | Zero hits in the grep. ChromaDB-only (no Postgres). | **LOW** | **No action.** |
| **14** | `app/worker.py` | N/A | Celery app factory — no DB calls directly. | **LOW** | **No action.** |

## Summary counts

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 2 (findings #1 + #2 — same file, same defect) | **NEW — file as ASP-DEFECT-025** |
| HIGH | 1 (finding #3) | Bundled with DEFECT-025 fix |
| MEDIUM | 1 (finding #8 — helper-is-fine-callers-are-the-issue analysis) | Policy note added below; no immediate code change |
| LOW | 10 | No action — already safe |

## Platform policy note (for ENGINEERING-PLAYBOOK §12 extension candidate)

`app.cost.meter.emit_cost_event` and adjacent shared-pool helpers are **safe only when called from an event-loop-stable context** (FastAPI request handlers, Celery beat tasks that share one loop). They are **unsafe** from inside `asyncio.run()` blocks in Celery task bodies — the shared pool is bound to whichever loop first touched it.

**The governed rule for Celery tasks that need to emit cost events or touch the DB:**

> Create a per-invocation `create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)` scoped to the task. Use `async with engine.begin()` or `async with engine.connect()`. `await engine.dispose()` in a `finally` block before the `asyncio.run()` returns. Direct SQL where possible — avoid the ORM for bind-parameter positional-coercion robustness. Reference implementations: `app/cost/aggregator.py::_do_aggregation`, `app/services/doc_intelligence.py::_async_*`.

Worth formalising in `ENGINEERING-PLAYBOOK.md` §12 as a follow-up — currently the rule is inline in the loop-affinity section there; this audit surfaces that the rule needs an explicit "Celery task → DB write" subsection enumerating the governed helpers + prohibiting calls to the shared-pool `emit_cost_event` / `get_session` from inside `asyncio.run()`. Recommending as a docs-only follow-up commit.

## Recommended next actions (for Architect ruling)

1. **File ASP-DEFECT-025** — ASP-05 Prediction psycopg2 class-of-bug, CRITICAL, open. Scope: port `_sync_update_job_status` to async + per-invocation engine; replace the `asyncio.run(_emit_and_webhook())` body's `emit_cost_event` call with a per-invocation-engine direct INSERT (same pattern as `doc_intelligence._async_emit_cost` fix in `1ccf85b`). Verification contract: 9-successive-invocation stress test (same as DEFECT-022 / DEFECT-024).
2. **ENGINEERING-PLAYBOOK.md §12 extension** (docs-only) — add an explicit "Celery task DB-write rule" subsection codifying the pattern + prohibiting the shared-pool helpers from inside `asyncio.run()`. Refer to this audit as the origin.
3. **ASP-05 Prediction governance cycle** — schedule alongside the DEFECT-025 fix so the audit-to-governance path is tight (mirrors the ASP-04 cycle where DEFECT-024 was discovered in the pre-spec survey and fixed as S-1).

## No retroactive fix recommended without Architect ruling

Per ASP-OUT-063 — this is a **read-only audit task**. No code changes recommended in this commit beyond filing the defect + this report. Fixes follow a directive (expected: ASP-DEFECT-025 filing directive + a remediation ruling mirroring DEFECT-024).
