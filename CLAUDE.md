# CLAUDE.md — ASP (AI Service Platform) Project Instructions

## Project
AI Service Platform (ASP) — A FastAPI/Python backend providing a unified gateway for AI capabilities (NLP, RAG, generation, doc intelligence, prediction, dashboard analytics) to internal CRM modules.

## Stack
- Backend: Python 3.11, FastAPI 0.115.0, SQLAlchemy 2.0.35 (async/asyncpg), Alembic 1.13.2
- AI: Anthropic SDK 0.34.2, LangChain 0.3.0, ChromaDB 0.5.7, sentence-transformers 3.0.1
- Task Queue: Celery 5.4.0 + Redis 7 + Flower 2.0.1
- Storage: MinIO (S3-compatible), boto3 1.35.0
- Infrastructure: Docker Compose (ai-service, celery-worker, flower, postgres, redis, minio)
- DB: PostgreSQL 16 — `postgresql+asyncpg://asp:asp_secret@postgres:5432/asp_db` (port 5434 external)

## Current State
- Migration head: `0020` (redesign_with_inventory_schema_v3 — OPS-003 resolution)
- Applied chain: 0001 → 0002 → 0003 → 0004 → 0005 → 0012 → 0013 → 0014 → 0015 → 0016 → 0017 → 0018 → 0019
- ADRs: ADR-001 through ADR-033 (see ASP-ADR.md)
- Branch: `claude/asp-v2` (governance + new features)
- Phase: Governance Onboarding
- ASP-01 NLP: **GOVERNED** (25/25 ACs PASS — first service through governance)
- ASP-03 Generation: **GOVERNED** (32/32 ACs PASS — ASP-NOTE-005 closure)

## Implemented Features
| ID | Service | Status |
|----|---------|--------|
| ASP-00 | Gateway (POST /api/v1/ai/invoke, auth, cost emitter) | COMPLETE |
| ASP-01 | NLP (nl_to_sql, intent, entity, sentiment, language, classify_probe_result) | GOVERNED |
| ASP-02 | RAG (ChromaDB schema retrieval, exclude_tables filter) | COMPLETE |
| ASP-03 | Generation (draft_email, summarise, quote, suggest, whatsapp) | COMPLETE |
| ASP-04 | Doc Intelligence (async: extract, classify) | COMPLETE |
| ASP-05 | Prediction (async: churn, revenue, anomaly, lead_scoring) | COMPLETE |
| ASP-06 | Prompt Registry (DB + Redis 10-min cache, 4-level fallback) | COMPLETE |
| ASP-07 | Context Store (Redis, TTL from config) | COMPLETE |
| ASP-08 | Cost Meter (per-call tracking, quota enforcement) | COMPLETE |
| ASP-09 | Webhook Service (exponential backoff, HMAC-SHA256) | COMPLETE |
| ASP-10 | Cost Aggregator (Celery beat, idempotent monthly rollup) | COMPLETE |
| ASP-11 | Model Router (quality_tier → Claude model mapping) | COMPLETE |
| ASP-12 | Ontology Manager (ChromaDB schema sync) | COMPLETE |
| ASP-13 | Dashboard Intelligence (interpret, narrate, anomaly, drilldown) | COMPLETE |

## Auth Flow
- API key authentication via `X-Api-Key` header
- bcrypt-hashed keys stored in `tenants` table
- Gateway validates key → extracts tenant_id → passes to services
- Cost quota checked per-call before invocation

## Known Gotchas
- **Datetime:** NEVER mix naive/aware. DB uses `TIMESTAMP WITH TIME ZONE` → always `datetime.now(timezone.utc)`
- **FK mismatches:** Always verify target column exists with `\d <table>` before writing migrations
- **Docker rebuild:** After code changes, always `--build` flag. Restart alone uses cached image
- **UUID sort order:** UUIDs are random. NEVER sort by UUID for chronological order. Use `created_at`
- **Cross-tenant responses:** Always 404, never 403 — do not leak entity existence
- **Windows asyncio:** Event loop teardown requires special handling on Windows (see app/main.py lifespan)
- **UUID vs VARCHAR tenant_id:** If tenant_id column is VARCHAR but ORM maps as UUID, queries will fail. Use `cast(Model.tenant_id, String)` in queries
- **Partial migration failures:** Check `alembic_version` table for last successful revision, drop partial artefacts, re-apply
- **API key header:** Canonical header is `X-ASP-API-Key` (not `X-Api-Key`). Rename requires Type C breaking change process per ASP-GOV-CONSUMPTION-002
- **ASP-INDEX ownership:** Dev Team (you) owns and maintains ASP-INDEX.md in the repo. Chief Architect reviews at deployment. See ADR-026

## Pre-Implementation Checklist

**Gate 1 (SCHEMA):** `\d table_name` before ORM — map every column 1:1
**Gate 2 (TYPES):** `udt_name` query — match exact PG types in SQLAlchemy
**Gate 3 (CONTRACT):** Share JSON response examples before frontend codes
**Gate 4 (AUDIT):** If using audit trail: verify CHECK constraints before INSERT
**Gate 5 (MIGRATION):** `alembic current` → copy exact string as down_revision. Single head after apply.
**Gate 6 (FRONTEND):** Incognito + disable cache + zero console errors
**Gate 7 (DEPENDENCY):** `python -c 'from app.{module} import router'` (backend) before commit

## Post-Implementation Checklist (MANDATORY)
After writing/applying any migration or completing a feature:
1. Update `ASP-SCHEMA-CURRENT.md` — affected tables + migration head
2. Update `ASP-INDEX.md` — migration head, feature status
3. Update `ASP-ADR.md` — if architectural decision was locked
4. Update this `CLAUDE.md` — migration head + applied chain
5. **Do NOT wait to be asked. This is part of the implementation.**

## Document Management
- `ASP-INDEX.md` — Single canonical file. Updated in-place. No version suffix.
- `ASP-SCHEMA-CURRENT.md` — Single canonical file. Updated in-place.
- `ASP-ADR.md` — Single canonical file. Updated in-place.
- Governance trail lives in: migration files, TSCDs

## Team Structure
| Team | Role |
|------|------|
| Product Management | Product vision, objectives |
| Chief Architect & Engineer | Specs, review, acceptance, governance |
| You (Claude Code) | End-to-end development, deployment, infrastructure, documentation |
| Users | Actual users of the product |

**All implementation tasks are your responsibility.** Domain labels (Fullstack, Backend, DevOps, etc.) describe code areas, not separate teams. You implement everything.

## Spec Review Standards
When reviewing a feature spec:
- Categorize findings: **Critical** / **Design Concern** / **Minor**
- Always check: CHECK constraints, FK targets, auth flow e2e, audit trail, timezone awareness
- Share feedback before implementation
- If issues found → recommend TSCD before proceeding

## AC Verification Rules
- **100% AC passage required** before marking COMPLETE
- Test security ACs (cross-tenant, auth, role enforcement) — these are non-skippable
- Run full E2E verification, not just happy path
- Submit verification report with all ACs listed

## Key File Locations
- `app/main.py` — FastAPI app factory + lifespan
- `app/config.py` — pydantic-settings, all env vars
- `app/gateway/router.py` — POST /api/v1/ai/invoke, GET /api/v1/ai/jobs/{job_id}
- `app/gateway/auth.py` — bcrypt API key verification
- `app/models/db_models.py` — SQLAlchemy ORM (all tables)
- `app/models/request.py` — InvokeRequest + related schemas
- `app/models/response.py` — InvokeResponse + related schemas
- `app/services/_shared.py` — shared Anthropic client + helper
- `app/registry/prompt_registry.py` — get_prompt() with Redis cache + DB fallback
- `app/registry/context_store.py` — conversation context in Redis
- `app/cost/meter.py` — emit_cost_event(), check_quota()
- `app/cost/aggregator.py` — monthly rollup Celery task
- `app/worker.py` — Celery app + beat schedule
- `alembic/versions/` — all migrations (0001–0005)
- `tests/conftest.py` — fixtures

## Reference
See `ENGINEERING-PLAYBOOK.md` for detailed patterns, conventions, and common mistakes.
