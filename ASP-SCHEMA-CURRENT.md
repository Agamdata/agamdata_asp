# ASP-SCHEMA-CURRENT — Database Schema Reference

## Migration Head
**Current:** `0022` (neutral_rule3_count_not_prompt_enforced — OPS-003 resolution)

## Tables

### tenants
Stores API client configuration and keys.
- Created in: 0001

### prompt_templates
Prompt templates for all AI services with variant support.
- Created in: 0001
- Seeded in: 0002 (base services), 0003 (test cases inferred+snapshot), 0004 (Playwright TS POM), 0005 (Playwright Python pytest)
- Modified in: 0012 (TC ID naming rule), 0013 (flat script variants), 0014 (analyse_failure), 0015 (OUTPUT CONTRACT)
- Reconstituted in: 0016 (with_inventory from serene-shtern archive, ASP-NOTE-004)
- Seeded in: 0017 (classify_probe_result for ASP-01 NLP)

### cost_events
Per-call cost tracking records.
- Created in: 0001

### async_jobs
Tracks Celery async job status for Doc Intelligence and Prediction services.
- Created in: 0001

### webhook_registrations
Per-tenant webhook configuration for event delivery.
- Created in: 0001

### cost_monthly_reports
Aggregated monthly cost rollups (idempotent).
- Created in: 0001

## Migration Chain
| ID | Description | Notes |
|----|-------------|-------|
| 0001 | Initial schema — all core tables | Baseline |
| 0002 | Seed prompt templates for base services | |
| 0003 | Generate test cases prompt templates (inferred + snapshot) | |
| 0004 | Generate Playwright TypeScript POM script prompt | |
| 0005 | Playwright Python/pytest prompt variant | |
| 0012 | TC ID naming rule for inventory prompt | down_revision healed 0011→0005 (ASP-NOTE-004) |
| 0013 | Flat script generation prompts (TS + Python) | Cherry-picked from serene-shtern |
| 0014 | analyse_failure prompt for playwright_runner | Cherry-picked from serene-shtern |
| 0015 | OUTPUT CONTRACT append to test-case prompts | Cherry-picked from serene-shtern |
| 0016 | Reconstitute with_inventory prompt from archive | ASP-NOTE-004 Phase 2 |
| 0017 | Seed classify_probe_result prompt (NLP, PAP canonical) | Renumbered from 0006 |
| 0018 | Ban lambda in Python Playwright script prompts | ASP-FEAT-ASP-03 v1.1 / DEFECT-006 |
| 0019 | Update generate_test_cases_with_inventory prompt to v2 (dual-mode: F-03-08 + F-03-04) | ASP-TSCD-001 CHG-03 |
| 0020 | Redesign with_inventory prompt v3 — simplified schema, F-03-04/F-03-08 modes | OPS-003 resolution |
| 0021 | Elevate count enforcement to system prompt (Rule 3 hard-constraint) | Superseded by 0022 |
| 0022 | Neutral Rule 3 — count enforcement moved to handler post-processing | Principal Architect ruling |

## Last Updated
2026-04-16
