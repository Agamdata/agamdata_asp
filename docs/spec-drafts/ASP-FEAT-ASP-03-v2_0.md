# ASP-FEAT-ASP-03 v2.0 — Generation Service Detailed Spec (amendment)

**Status:** DRAFT — Batch 1 (§1–§5) surfaced for Architect review
**Template:** ASP-GOV-PLAYBOOK-001 v1.0, Section 5 (14-section template, verbatim)
**Migration head at authoring:** 0023
**Migration allocated by this spec:** **024** (pending acceptance)
**Base:** ASP-FEAT-ASP-03 v1.1 (GOVERNED 2026-04-12, ASP-NOTE-005) + ASP-TSCD-001 (2026-04-15)
**Driving consumer requirement:** PAP-ASP-REQ-ASP-03 v2.0 (CLOSED ACCEPTED 2026-04-18 per ASP-OUT-004)
**Drafted by:** ASP Development Team (Claude)
**Date:** 2026-04-18
**Reviewer:** Principal Architect & Engineer

> **Architect directives captured at authoring (ASP-OUT-007, 2026-04-18 20:35 IST):**
> Migration 024 is prompt-only; no DDL. `locator_source` extension is
> Pydantic-Literal only. Deactivate the L2-override row (`e92c4809`, v1)
> alongside the v3 canonical row in migration 024. ADR-035 (fail-closed
> embedding model gate) is **not** part of v2.0 — it belongs to the
> ASP-FEAT-ASP-02 RAG spec.

---

## §1 Summary

ASP-FEAT-ASP-03 v2.0 governs three additive changes to the governed
Generation service — **coverage-aware generation**, **`form_data` seed
context**, and **`locator_source="live_extracted"` support** — plus two
new task registrations (**F-01-10 as a third caller of
`generate_test_cases_with_inventory`**, and **`refactor_script_locators`**
as a new task). Migration 024 is a **prompt-only** migration: it
deactivates the current v3 canonical prompt row and the L2 override row
for `generate_test_cases_with_inventory`, and inserts a new v4 row that
carries the coverage-aware generation rules, the form_data rendering
block, and the live_extracted locator-source branch. **No DDL changes.**
The Pydantic payload extensions (`form_data`, widened `locator_source`)
are Python-only schema changes delivered in the same PR as the migration;
ADR-033 `extra="ignore"` already covers the interim silent-drop of
`form_data` in v1.1, so the transition is non-breaking. Type B additive
per ADR-023.

## §2 Background and Context

**Why this amendment exists.**

The GOVERNED `ASP-FEAT-ASP-03 v1.1` baseline (2026-04-12, ASP-NOTE-005)
locked the `generate_test_cases_with_inventory` task around the
`verified` locator source: inventory-based, no hallucinations, output
schema v3 (post-OPS-003 simplification). Three consumer-driven pressures
have since accumulated:

1. **PAP F-01-10 (live-panel interactive generation)** needs the same
   task with a fresh DOM crawl as input (locator_source="live_extracted"),
   not an inventory baked at probe time. Latency ceiling 30s
   (interactive). F-01-10 is complete on PAP's side and waits on ASP's
   schema change (ASP-OUT-004 closure note, 2026-04-18).
2. **Coverage-aware generation** — PAP needs to request specific test-case
   categories per call (`categories_to_generate`) and receive back the
   categories the LLM actually covered (`covered_categories`) so the
   consumer can detect gaps and re-request. Today the LLM picks categories
   implicitly, producing volatile output shapes.
3. **`form_data` seed context** — PAP has been smuggling realistic
   field-value seeds inside `payload{}` (opaque dict) to avoid 422
   rejection. ADR-033 `extra="ignore"` absorbs this silently. v2.0
   promotes `form_data` to a first-class `Optional[dict[str, str]]`
   field on the payload with a governed prompt-rendering contract.

**Base references.**

| Ref | Role |
|---|---|
| ASP-FEAT-ASP-03 v1.1 | GOVERNED baseline (32/32 AC PASS, 2026-04-12, commit `e8e3896`; PAP confirmed `1b32600`) |
| ASP-TSCD-001 | v1.1 amendment (2026-04-15, ASP-NOTE-006) — dual-mode F-03-08/F-03-04, max_tokens=12288, page_type/screen_key |
| OPS-003 | Resolution cycle (2026-04-15 → 16) — output-volume decisions, count enforcement moved to handler (migrations 019 → 022) |
| PAP-ASP-REQ-ASP-03 v2.0 | Driving consumer requirement (CLOSED ACCEPTED 2026-04-18, ASP-OUT-004) |
| ASP-FEAT-ASP-00 v1.0 | Gateway governance (closed 2026-04-18, ASP-NOTE-008); Gateway's RFC 7807 envelope, caller_feature pipeline, and X-Request-Id already handle v2.0's cross-cutting concerns |

**What depends on this amendment.**

- PAP F-01-10 (interactive panel) — unblocked the moment migration 024 lands.
- PAP F-03-08 batch generation — continues unchanged except the v4 prompt
  replaces v3 in the resolution chain; the covered-categories field
  appears in results (additive, callers ignoring it are unaffected).
- PAP F-03-04 single-TC path — continues unchanged; count-enforcement
  via handler post-processing remains (migration 022 legacy).

**Out-of-scope reminders (from §3).**

- v2.0 does **not** convert F-03-08 to async. Latency mitigation remains
  per DEFECT-012 MITIGATED status; async conversion is deferred.
- v2.0 does **not** touch the Gateway, auth, cost pipeline, or any non-generation
  service.
- v2.0 does **not** introduce a DB enum for `locator_source`. The extension
  is Pydantic-Literal only (Architect confirmed ASP-OUT-007, G-2).

## §3 Scope

### In scope — five items

| # | Scope item | Deliverable(s) |
|---|---|---|
| **S-1** | Coverage-aware generation | `categories_to_generate: list[str] \| None = None` (payload); `covered_categories: list[str]` (output). Prompt rules in v4 to honour requested categories when present. |
| **S-2** | `form_data` field + prompt injection | `form_data: dict[str, str] \| None = None` (payload). Prompt renders `--- Form Data Context ---` block; when absent, LLM is instructed to synthesise realistic values. AC-FORM-01 / AC-FORM-02. |
| **S-3** | `locator_source="live_extracted"` support | Widen `GenerateTestCasesWithInventoryPayload.locator_source: Literal["verified"]` → `Literal["verified", "live_extracted"]`. v4 prompt branches on the value. |
| **S-4** | F-01-10 registered as third caller | Prompt-registry maturity-chain resolution must serve F-01-10 correctly. No new task name; reuses `generate_test_cases_with_inventory`. Cross-cutting: `caller_feature="F-01-10"` already supported via ASP-FEAT-ASP-00 v1.0 (Gateway governance). |
| **S-5** | `refactor_script_locators` — new task | New entry in `VALID_TASKS` under `generation`. New Pydantic payload + output models. New prompt template seeded in v4 migration. Reuses existing `_handle_generic` dispatch pattern in `app/services/generation.py`. |

### Out of scope (deferred)

- **Async conversion of F-03-08 batch generation** (DEFECT-012 Option 4). Deferred to a future TSCD; pilot latency remains per current MITIGATED posture.
- **v2.0 output-schema restructuring** beyond `covered_categories`. The existing v3 simplified schema (OPS-003) stays.
- **Embedding-model fail-closed gate** — belongs to ASP-FEAT-ASP-02 (RAG, ADR-035). Not in v2.0.
- **PAP's Q-1 / Q-2 open questions** — the spec can be drafted on default assumptions; final answers land at review.

### Task list after v2.0 accepts

| Service | Tasks (after v2.0) |
|---|---|
| `generation` | `draft_email`, `summarise_customer`, `generate_quote_narrative`, `suggest_fields`, `draft_whatsapp`, `generate_test_cases`, `generate_test_cases_with_inventory`, `generate_playwright_script`, **`refactor_script_locators`** (NEW) |

## §4 Service Classification

| Attribute | Value |
|---|---|
| **Service ID** | ASP-03 (amendment, not a new service) |
| **Mode** | **Synchronous** for F-01-10 interactive-panel generation (30 s ceiling), F-03-04 single-TC, `refactor_script_locators`. Also synchronous for F-03-08 batch generation (async conversion deferred — §3 out-of-scope). |
| **LLM calls** | YES. `claude-haiku-4-5-20251001` (`standard` quality tier) and `claude-sonnet-4-6` (`enhanced` quality tier) per ADR-017. Handler selects model via `resolve_model(req.quality_tier)` in Gateway (unchanged from v1.1). |
| **Model tier** | Standard default; enhanced opt-in via `quality_tier` field. Caller controls. |
| **Internal ASP services called** | None new in v2.0. Existing: `app.registry.prompt_registry` (prompt resolution), `app.cost.meter` (cost emission via Gateway), `app.utils.json_parser.extract_json` (output parsing), `app.utils.llm_retry.llm_call_with_retry` (529/5xx retry). No new inter-service calls. |
| **Data stores** | PostgreSQL — `prompt_templates` (read-only at runtime; updated by migration 024); `cost_events` (Gateway-managed). No new tables. No Redis keys. No S3 objects. |
| **Latency budget** | F-01-10 interactive: **30 s ceiling** (caller SLA; below DEFECT-012 observed envelope for this branch because it operates on a small live DOM, not a full crawl inventory). F-03-08 batch: inherits v1.1 MITIGATED posture. `refactor_script_locators`: **10 s** target (single LLM call, small input). |
| **Failure domains** | Inherits v1.1: 422 (validation), 500 (parse failure), 502 (upstream Anthropic 5xx after retry), 504 (timeout). RFC 7807 envelope via Gateway (ASP-FEAT-ASP-00 v1.0). |
| **Observability** | Gateway-level: `invoke_start`, `invoke_complete`, `invoke_failed`, all carrying `caller_feature` via structlog contextvars (ASP-FEAT-ASP-00 v1.0 I-06). Service-level (unchanged): `generation_prompt_resolved`, `generation_output_parsed`, `generation_count_enforced` (where applicable). |

## §5 Data Model

### Migration required: YES — migration 024

**Migration number:** `024` (locked at this spec's acceptance; allocated per ADR-028 only once ready to write; Architect directive at ASP-OUT-007 holds the write until Batch 1 is reviewed and `alembic current = 0023 (head)` returns cleanly post-build — confirmed at this turn).

**Migration classification:** **prompt-only.** No DDL changes. No new tables. No new columns. No type changes. The Pydantic schema widening (`locator_source`, `form_data`) is Python-only and ships in the same commit as the migration but requires no Alembic operation.

**Migration 024 operations (in exact order):**

1. **Deactivate the current v3 canonical row** for `generate_test_cases_with_inventory`:
   ```sql
   UPDATE prompt_templates
   SET is_active = FALSE
   WHERE id = 'e6c88ca5-1caa-4025-b3b1-450c356cb561'   -- playwright_runner / * / v3 / inventory
     AND service_type = 'generation'
     AND task = 'generate_test_cases_with_inventory';
   ```

2. **Deactivate the stale L2-override row** (Architect directive, ASP-OUT-007):
   ```sql
   UPDATE prompt_templates
   SET is_active = FALSE
   WHERE id = 'e92c4809-3308-4b0c-aeb5-d23e4895b882'   -- playwright_runner / L2 / v1 / inventory
     AND service_type = 'generation'
     AND task = 'generate_test_cases_with_inventory';
   ```
   **Rationale.** `e92c4809` references the v1 schema semantics pre-OPS-003 and
   should not appear in the maturity-level fallback chain any more. Its
   continued presence has been silently shadowing the canonical row for L2
   callers. Deactivating it ensures the v4 row (maturity=`*`) serves all
   callers uniformly.

3. **Insert the v4 canonical row:**
   ```sql
   INSERT INTO prompt_templates
     (service_type, task, caller_module, maturity_level, version,
      is_active, ab_variant, system_prompt, user_prompt_template)
   VALUES
     ('generation', 'generate_test_cases_with_inventory',
      'playwright_runner', '*', 4, TRUE, 'inventory',
      <<<v4 system prompt>>>, <<<v4 user prompt template>>>);
   ```
   UNIQUE constraint `uq_prompt_lookup (service_type, task, caller_module, maturity_level, version, ab_variant)` makes this collision-safe.

4. **Seed the `refactor_script_locators` prompt row (§S-5):**
   ```sql
   INSERT INTO prompt_templates (...)
   VALUES
     ('generation', 'refactor_script_locators',
      'playwright_runner', '*', 1, TRUE, NULL,
      <<<refactor_script_locators system prompt>>>,
      <<<refactor_script_locators user prompt template>>>);
   ```

**Downgrade.** Reverse in exact opposite order:
- Delete the v4 row (`WHERE version=4 AND task='generate_test_cases_with_inventory'`).
- Delete the `refactor_script_locators` row (`WHERE task='refactor_script_locators' AND version=1`).
- Reactivate the L2-override row (`e92c4809`).
- Reactivate the v3 canonical row (`e6c88ca5`).

**No data loss at any point in either direction** because the migration is additive-then-switch on a lookup table; historical versions remain queryable for audit.

### Pydantic schema changes (Python-only, same commit as 024)

File: `app/schemas/generation_schemas.py`

```python
class GenerateTestCasesWithInventoryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")   # ADR-033 preserved
    # ... existing 15 fields ...
    locator_source: Literal["verified", "live_extracted"] = "verified"   # widened
    form_data: Optional[dict[str, str]] = None                            # NEW (S-2)
    categories_to_generate: Optional[list[str]] = None                    # NEW (S-1)


class GenerateTestCasesWithInventoryOutput(BaseModel):
    # ... existing output fields ...
    covered_categories: list[str] = Field(default_factory=list)           # NEW (S-1)


class RefactorScriptLocatorsPayload(BaseModel):                          # NEW (S-5)
    model_config = ConfigDict(extra="ignore")
    script_text: str
    # additional fields defined in §7 at Batch 2 authoring


class RefactorScriptLocatorsOutput(BaseModel):                           # NEW (S-5)
    # output fields defined in §7 at Batch 2 authoring
    ...
```

Adds to `app/services/generation.py`:
- `VALID_TASKS` — append `"refactor_script_locators"`.
- `TASK_OUTPUT_SCHEMAS` — `"refactor_script_locators": RefactorScriptLocatorsOutput`.
- `TASK_PAYLOAD_VALIDATORS` — `"refactor_script_locators": RefactorScriptLocatorsPayload`.
- `TASK_MAX_TOKENS` — `"refactor_script_locators": 8192` (tentative; locked at Batch 2 / §6 authoring).

### Pre-write gate confirmation (captured at this turn)

| Gate | Status | Evidence |
|---|---|---|
| G-1 Schema | ✅ | No new tables; no new columns — prompt-row changes only. |
| G-2 Types | ✅ | `locator_source` is Pydantic Literal, not PG enum (Architect ASP-OUT-007 G-2 confirmation). |
| G-3 Contract | ✅ (partial) | §1–§5 drafted; §6–§7 payload/output fleshed in Batch 2. |
| G-4 Audit | ✅ | No CHECK constraints. UNIQUE on prompt-lookup tuple; v4 collision-free. |
| G-5 Migration | ✅ | Post-build `alembic current` returned `0023 (head)` cleanly at 08:46 UTC 2026-04-18. |
| G-6 Frontend | N/A | — |
| G-7 Dependency | ✅ | Payload delta: 15 → 18 fields on `GenerateTestCasesWithInventoryPayload`; new models for `refactor_script_locators`. Import check runs in Batch 2 after full schemas land. |

---

**End of Batch 1 (§1–§5). Awaiting Architect review before Batch 2 (§6 API Contract · §7 Request/Response Detail · §8 Caller Integration · §9 LLM and Prompt Design · §10 Security Requirements).**
