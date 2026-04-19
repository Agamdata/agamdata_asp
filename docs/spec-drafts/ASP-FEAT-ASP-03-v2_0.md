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

- **Async conversion of F-03-08 batch generation AND F-03-04 single-TC generation** (DEFECT-012 Option 4). Explicitly deferred to a future TSCD. Pilot latency remains per current MITIGATED posture. **Note 1 / ASP-OUT-009 directive: this exclusion is locked in non-goals to prevent a future TSCD from treating the async gap as an oversight of v2.0.**
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
| **Mode** | **v2.0 is entirely synchronous.** F-01-10 interactive-panel generation (30 s ceiling), F-03-04 single-TC, F-03-08 batch, `refactor_script_locators` — all sync. **Async conversion for F-03-08 AND F-03-04 is explicitly OUT OF SCOPE for v2.0** (Note 1, ASP-OUT-009); see §3 non-goals. |
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

**Migration 024 operations (in exact order; five ops per Note 2 split-by-caller ruling):**

**Note 2 ruling (Dev Team, accepting Architect's proposed split):** the v4 prompt is **split by caller_module**, not a single row. Two INSERTs replace the one in the original plan. Rationale: OPS-003 demonstrated that mode-selection logic embedded in a single LLM prompt is unreliable — the LLM regularly picked the wrong mode under dual-mode framing, requiring handler-side enforcement (migration 022). Folding a third operational mode (F-01-10 interactive live-DOM, 30 s ceiling) into the same prompt would multiply that failure class. Prompt Registry's `(service_type, task, caller_module, maturity_level)` resolution key is designed for exactly this split. Drift on shared rules across the two rows is mitigated by AC-SHARED-01 (to be authored in §12 Batch 3) comparing the common-fragment sections.

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
   **Rationale.** `e92c4809` references the v1 schema semantics pre-OPS-003. Its continued presence has been silently shadowing the canonical row for L2 callers. Deactivating ensures v4 serves all callers uniformly through the maturity fallback chain.

3. **Insert the v4 batch/single-TC row** — serves F-03-08 (batch) and F-03-04 (single-TC) via `caller_module=playwright_runner`:
   ```sql
   INSERT INTO prompt_templates
     (service_type, task, caller_module, maturity_level, version,
      is_active, ab_variant, system_prompt, user_prompt_template)
   VALUES
     ('generation', 'generate_test_cases_with_inventory',
      'playwright_runner', '*', 4, TRUE, 'inventory',
      <<<v4 playwright_runner system prompt>>>, <<<v4 playwright_runner user prompt template>>>);
   ```

4. **Insert the v4 interactive row** — serves F-01-10 via `caller_module=test_generator`:
   ```sql
   INSERT INTO prompt_templates
     (service_type, task, caller_module, maturity_level, version,
      is_active, ab_variant, system_prompt, user_prompt_template)
   VALUES
     ('generation', 'generate_test_cases_with_inventory',
      'test_generator', '*', 4, TRUE, 'inventory',
      <<<v4 test_generator system prompt>>>, <<<v4 test_generator user prompt template>>>);
   ```

   UNIQUE constraint `uq_prompt_lookup (service_type, task, caller_module, maturity_level, version, ab_variant)` makes ops 3 and 4 collision-free against each other (different `caller_module`) and against any historical rows.

5. **Seed the `refactor_script_locators` prompt row (§S-5):**
   ```sql
   INSERT INTO prompt_templates (...)
   VALUES
     ('generation', 'refactor_script_locators',
      'playwright_runner', '*', 1, TRUE, NULL,
      <<<refactor_script_locators system prompt>>>,
      <<<refactor_script_locators user prompt template>>>);
   ```

**Downgrade.** Reverse in exact opposite order:
- Delete the `refactor_script_locators` row (`WHERE task='refactor_script_locators' AND version=1`).
- Delete both v4 rows (`WHERE version=4 AND task='generate_test_cases_with_inventory' AND caller_module IN ('playwright_runner', 'test_generator')`).
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
| **G-8 Prompt Reach (NEW per ASP-OUT-015)** | ✅ (retroactively, via ASP-OUT-014 Option A fix) | Probe against live DB post-migration 024: `get_prompt_variant(caller=playwright_runner, maturity=L2, ab_variant=inventory)` resolves to v4-batch row (verified in T-A1); `get_prompt_variant(caller=test_generator, maturity=L2, ab_variant=inventory)` resolves to v4-interactive row (verified in T-A2). Both paths functional after the fallback chain was added to `get_prompt_variant`. **Without the Option A fix, this gate would have FAILED** — migration 024 originally rendered both rows unreachable for default-maturity callers. ENGINEERING-PLAYBOOK.md now carries this gate as mandatory for every future `prompt_templates` migration. |

---

**End of Batch 1 (§1–§5).** Batch 2 follows.

---

## §6 API Contract

ASP-03 is reached through the Gateway (ADR-001). The external HTTP surface
is owned by ASP-FEAT-ASP-00 v1.0 (`POST /api/v1/ai/invoke`, RFC 7807 error
envelope, X-Request-Id header, caller_feature in structlog + cost_events).
§6 here governs the **internal handler contract** plus the **three calling
modes** for `generate_test_cases_with_inventory` and the separate task
`refactor_script_locators`.

### §6.1 Common envelope (inherited from Gateway)

All invocations use the governed `InvokeRequest` shape:

```python
class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_type:   Literal["nlp","generation","doc_intelligence","prediction","dashboard_intelligence"]  # "generation" here
    task:           str            # "generate_test_cases_with_inventory" | "refactor_script_locators"
    caller_module:  str            # "playwright_runner" | "test_generator"
    caller_feature: Optional[str] = Field(default=None, max_length=128)
    tenant_id:      str
    quality_tier:   Literal["standard","enhanced","premium"] = "standard"
    # ... user_context / ui_context / session_id / conversation_history / schema_hints ...
    payload:        dict[str, Any]   # service-specific — validated by TASK_PAYLOAD_VALIDATORS[task]
```

Handler validates `req.task ∈ VALID_TASKS["generation"]`; returns 422 with the supported-task list if unknown (ASP-FEAT-ASP-00 v1.0 pattern).

### §6.2 Calling mode — F-03-08 batch generation

| Field | Value |
|---|---|
| `service_type` | `generation` |
| `task` | `generate_test_cases_with_inventory` |
| `caller_module` | `playwright_runner` |
| `caller_feature` | `F-03-08` |
| `quality_tier` | `standard` (Haiku) default; PAP may escalate |
| Payload | `GenerateTestCasesWithInventoryPayload` (see §7) with `locator_source="verified"`, `categories_to_generate` typically large (≥5 categories) or `None` for full-coverage, `form_data` optional |
| Prompt row resolved | `(generation, generate_test_cases_with_inventory, playwright_runner, *, v4, inventory)` |
| Response | `InvokeResponse` wrapping `GenerateTestCasesWithInventoryOutput` (multi-TC list + `covered_categories`) |
| Latency posture | MITIGATED per DEFECT-012; async conversion explicitly deferred (§3 non-goals) |

### §6.3 Calling mode — F-03-04 single-TC generation

| Field | Value |
|---|---|
| `caller_feature` | `F-03-04` |
| `caller_module` | `playwright_runner` (same as F-03-08; handler distinguishes via count enforcement + prompt cues) |
| Payload | Same shape as F-03-08; handler's `_enforce_test_case_count()` (migration 022) truncates output to exactly one TC when `categories_to_generate` has a single entry. Unchanged from v1.1 baseline. |
| Prompt row | Same v4 playwright_runner row as F-03-08 |
| Response | `InvokeResponse` wrapping `GenerateTestCasesWithInventoryOutput` with `test_cases: list[...]` of length 1 |

### §6.4 Calling mode — F-01-10 interactive live-panel (NEW in v2.0)

| Field | Value |
|---|---|
| `caller_feature` | `F-01-10` |
| `caller_module` | `test_generator` (**new** in v2.0 — caller-module split per Note 2 ruling) |
| Payload | Same shape as F-03-08 with `locator_source="live_extracted"`, `categories_to_generate` typically small or `None`, `form_data` typically populated (PAP has live field context) |
| Prompt row resolved | `(generation, generate_test_cases_with_inventory, test_generator, *, v4, inventory)` — different row from batch |
| Response | `InvokeResponse` wrapping `GenerateTestCasesWithInventoryOutput`; `test_cases` typically 1–3 short-form TCs suitable for interactive review |
| Latency ceiling | **30 s** (interactive-panel SLA). Caller assumed to hold a live UI panel; synchronous only. |

### §6.5 Task — `refactor_script_locators` (NEW in v2.0)

Separate task registration under the same service.

| Field | Value |
|---|---|
| `service_type` | `generation` |
| `task` | `refactor_script_locators` |
| `caller_module` | `playwright_runner` (pilot caller; other consumers add rows as they onboard) |
| `caller_feature` | PAP-side label (e.g. F-03-05); opaque to ASP per ADR — logged only |
| Payload | `RefactorScriptLocatorsPayload` (§7) |
| Prompt row resolved | `(generation, refactor_script_locators, playwright_runner, *, v1, NULL)` (v1 row seeded by migration 024 op 5) |
| Response | `InvokeResponse` wrapping `RefactorScriptLocatorsOutput` (updated script + changes summary) |
| Latency target | ~10 s (single LLM call over a bounded-size script + locator inventory) |

### §6.6 Error matrix (inherited from Gateway, service-specific additions)

| HTTP | Cause (ASP-03 specific) |
|---|---|
| 422 `/errors/unsupported-task` | `task` not in `VALID_TASKS["generation"]` after v2.0 expansion |
| 422 `/errors/validation-failed` | Pydantic payload validation failed (extra field dropped per ADR-033 → INFO log; required field missing → 422) |
| 500 `/errors/internal` | Generation output JSON parse failure, handler exception |
| 502 `/errors/upstream-bad-gateway` | Anthropic 5xx after exhausted retries (`llm_call_with_retry`) |
| 504 `/errors/upstream-timeout` | Anthropic timeout / connection error |

No new error types in v2.0. All envelope rendering inherited from Gateway global exception handler.

## §7 Request / Response Detail

### §7.1 `GenerateTestCasesWithInventoryPayload` v2 — 18 fields (authoritative)

File: `app/schemas/generation_schemas.py`. `ConfigDict(extra="ignore")` preserved per ADR-033. **Pydantic model is authoritative.** Field count evolved during review: Batch 2 "16" → Batch 3 "17" (`form_data` + `categories_to_generate`) → **Batch 3 revised "18" (ASP-OUT-013 added `covered_categories` to Payload as consumer-echo symmetry)**.

**Implementation note on `Payload.covered_categories`:** the v4 prompt templates do NOT render this field (it is not in the user-prompt `--- Form Data Context ---` / `--- Generation Instructions ---` blocks). It is available for future multi-call de-duplication scenarios where a caller may pass previously-generated categories to inform subsequent calls. The LLM populates `Output.covered_categories` independently based on `categories_to_generate` (or its own selection when absent).

| # | Field | Type | New in v2.0? | Notes |
|---|---|---|---|---|
| 1 | `url` | `str` | — | Page URL under test |
| 2 | `page_title` | `str` | — | |
| 3 | `page_type` | `Literal["FORM", "LIST", "DETAIL", "DASHBOARD"]` | — | TSCD-001 |
| 4 | `screen_key` | `str` | — | TSCD-001 |
| 5 | `tc_id` | `str` | — | Caller-supplied stable ID |
| 6 | `language` | `Literal["typescript","python_playwright_pytest_flat"]` | — | |
| 7 | `expected_result` | `str` | — | Business outcome description |
| 8 | `preconditions` | `str` | — | |
| 9 | `submitted_fields` | `dict[str, Any]` | — | Fields the scenario submits |
| 10 | `probe_outcome` | `Literal["success","validation_error","auth_redirect","server_error","unknown"]` | — | Mirrors ASP-01 classify_probe_result |
| 11 | `probe_success_indicators` | `list[str]` | — | |
| 12 | `probe_error_messages` | `list[str]` | — | |
| 13 | `test_steps` | `list[dict]` | — | Step-level hints |
| 14 | `locator_inventory` | `list[LocatorInventoryItem]` | — | |
| 15 | `locator_source` | `Literal["verified", "live_extracted"] = "verified"` | **Widened** (S-3) | **Python-only change; no PG enum (Architect G-2)**. Default unchanged (backward compatible). |
| 16 | `form_data` | `Optional[dict[str, str]] = None` | **NEW** (S-2) | Seed values for form inputs. When `None`, LLM synthesises realistic values from field names (prompt v4 rendering block). |
| 17 | `categories_to_generate` | `Optional[list[str]] = None` | **NEW** (S-1) | Caller-requested category list. When `None`, LLM covers full canonical set. |

**Reconciliation closed (ASP-OUT-010):** Architect confirmed 17 fields is authoritative; the earlier "16" was a count error in the directive. See impl-log entry "2026-04-18 · Architect field count corrected to 17 per Pydantic model authority."

### §7.2 `GenerateTestCasesWithInventoryOutput` v2

```python
class GenerateTestCasesWithInventoryOutput(BaseModel):
    test_cases: list[TestCaseOutput]                              # unchanged (v3 schema)
    missing_locators: list[str] = Field(default_factory=list)     # unchanged (TSCD-001)
    covered_categories: list[str] = Field(default_factory=list)   # NEW (S-1)
    model_config = ConfigDict(extra="forbid")
```

`covered_categories` is additive. v1.1 callers ignoring it are unaffected. When `categories_to_generate` is present in the request, the prompt instructs the LLM to populate `covered_categories` as the subset of requested categories actually addressed. When `categories_to_generate` is absent, `covered_categories` reflects the LLM's self-selected coverage (observability dimension).

### §7.3 `RefactorScriptLocatorsPayload` (NEW — §S-5)

**Aligned with authoritative prompt-template placeholders per ASP-OUT-012 v4 prompt content ruling.**

```python
class LocatorDiffItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element_name: str                                                # PAP's stable element identifier
    old_locator:  str                                                # prior locator string (as it appears in script_body)
    new_locator:  str                                                # replacement locator string


class RefactorScriptLocatorsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    script_body:  str                                                # existing test script (TS or Python)
    locator_diff: list[LocatorDiffItem]                              # PAP-supplied list of changes (old → new per element)
    screen_key:   str                                                # context identifier (same semantic as inventory task)
    language:     Literal["typescript", "python_playwright_pytest_flat"]
```

### §7.4 `RefactorScriptLocatorsResult` (NEW — §S-5)

**Aligned with authoritative prompt-template output schema per ASP-OUT-012.**

```python
class RefactorScriptLocatorsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refactored_script:  str                                          # updated test code (verbatim copy if no change needed)
    changes_made:       list[str]                                    # each: "element_name: brief description"
    unchanged_locators: list[str]                                    # each: "element_name: reason (e.g. 'not found in script')"
    warnings:           list[str]                                    # each: ambiguous-replacement / multi-occurrence warnings
```

**Note.** Field-name alignment from Batch 2 draft → Batch 3 authoritative:

| Batch 2 draft | Batch 3 authoritative (ASP-OUT-012) |
|---|---|
| `script_text` | `script_body` |
| `script_format` | `language` |
| `locator_inventory` | `locator_diff` (different semantic — diff list, not full inventory) |
| `page_url` | `screen_key` |
| `change_hints` | (removed — `locator_diff` carries the changes) |
| `changes_summary` | `changes_made` |
| `locators_replaced` (list of dicts) | (folded into `changes_made` free-form strings) |
| `unchanged_reason` (single Optional str) | `unchanged_locators` (list of strings) |
| (implicit) | `warnings` (new list) |

The AC-S5 suite in §12 references the aligned names.

### §7.5 Structlog delta

No new events. Existing `invoke_start` / `invoke_complete` / `invoke_failed` (Gateway) and `generation_prompt_resolved` / `generation_output_parsed` / `generation_count_enforced` (service) remain. `caller_feature` binding via `structlog.contextvars` already carries `F-01-10` / `F-03-05` (refactor) / etc.

## §8 Caller Integration Guide

### §8.1 Three-caller matrix

| Field to send | F-03-08 | F-03-04 | F-01-10 |
|---|---|---|---|
| `caller_module` | `playwright_runner` | `playwright_runner` | `test_generator` |
| `caller_feature` | `F-03-08` | `F-03-04` | `F-01-10` |
| `quality_tier` | `standard` (default) | `standard` | `standard` (interactive; latency-sensitive) |
| `locator_source` | `verified` | `verified` | `live_extracted` |
| `categories_to_generate` | typically a 5+ list, or `None` for full coverage | exactly 1 entry (handler enforces count=1 per migration 022) | small list (1–3) or `None` |
| `form_data` | optional | optional | recommended (PAP has live values) |
| Prompt row served | v4 playwright_runner row | v4 playwright_runner row | v4 test_generator row |
| Expected latency | MITIGATED (pilot) | MITIGATED | ≤ 30 s |

### §8.2 `refactor_script_locators` integration

| Field | Guidance |
|---|---|
| `task` | `refactor_script_locators` |
| `caller_module` | `playwright_runner` initially (other consumers add caller rows as they onboard) |
| `caller_feature` | PAP's feature ID, e.g. `F-03-05`. Opaque to ASP. |
| `script_text` | **Must be scrubbed of PII** (see §10). Test credentials, real customer emails, real names must be tokenised by caller before send. |
| `script_format` | Must match the actual language of `script_text`. |
| `locator_inventory` | Fresh crawl after the UI change — same shape as `generate_test_cases_with_inventory` |
| `change_hints` | Optional. If PAP's diff engine has identified likely-changed selectors, pass them to narrow LLM focus. |

### §8.3 F-01-10 `missing_locators` / low-confidence handling

For F-01-10 with `locator_source="live_extracted"`, the live DOM crawl may produce a locator inventory with lower confidence than PAP's verified-locator path. Consumer guidance:

- **If `missing_locators` is non-empty in the response:** one or more LLM-requested selectors were not found in the inventory. PAP should re-crawl (possibly with a longer wait or different viewport) and re-invoke rather than trusting the generated test as-is.
- **If a locator has `is_fragile=True` (from LocatorInventoryItem):** the generated test case may still use it, but PAP should surface this in the interactive panel as an amber marker — the LLM is working against a weak locator and regressions on minor UI changes are likely.
- **Zero-confidence mode:** if the crawl yields empty or near-empty inventory (e.g. SPA not fully hydrated), the handler will return a 422 `validation-failed` at payload-level `locator_inventory min_length=1` (caller-enforced). PAP should surface this as "retry in 500 ms" to the user rather than silently invoking.
- **30-second ceiling:** if the caller times out before ASP responds, the generation is wasted — PAP should abort rather than retry to keep budget intact.

## §9 LLM and Prompt Design

### §9.1 Prompt split (Note 2 ruling)

v2.0 splits `generate_test_cases_with_inventory` into **two prompt rows** by `caller_module`, seeded in migration 024 ops 3 and 4. Rationale captured in §5 / ruling paragraph.

| Prompt | Row key | Serves | Focus |
|---|---|---|---|
| v4-batch | `playwright_runner` | F-03-08 + F-03-04 | Comprehensive category coverage, robust JSON output, handler-enforced count for F-03-04 |
| v4-interactive | `test_generator` | F-01-10 | Live-DOM context, short-form output (1–3 TCs), `live_extracted` locator branch primary |

### §9.2 Shared prompt fragments (maintained across both rows)

**Governed invariant (ASP-OUT-010):** **Shared fragments must be identical across both rows. Any divergence is a prompt drift defect.** The four named fragments below appear verbatim in both v4 `INSERT` statements in migration 024 operations 3 and 4. AC-SHARED-01 (§12) verifies via substring match that every row contains each fragment with its marker comment `<!-- SHARED_FRAGMENT: <NAME> -->`.

**Note on rule numbering (ASP-OUT-013 clarification).** Rules 6 and 7 are **system-prompt additions**. `FORM_DATA_BLOCK` is a **user-prompt-template addition** — not a numbered rule. Rule 9 applies to the **v4-interactive row only** (test_generator caller). The numbering 6, 7, (skip 8), 9 is intentional — there is no Rule 8. An earlier directive outline listed "6, 7, 8" during planning but the detailed content only materialised RULE 6 (CATEGORIES_SCHEMA) and RULE 7 (LOCATOR_SOURCE_BRANCH); FORM_DATA_BLOCK lives in the user-prompt block, not as a system rule.

| Fragment ID | Purpose |
|---|---|
| `OUTPUT_CONTRACT_V3` | JSON-only output shape per OPS-003 simplified v3 schema |
| `CATEGORIES_SCHEMA` (S-1) | Canonical category list + rendering of `categories_to_generate` block when present, with rules for populating `covered_categories` on the way out |
| `FORM_DATA_BLOCK` (S-2) | Rendering of `--- Form Data Context ---` + fallback instruction when absent |
| `LOCATOR_SOURCE_BRANCH` (S-3) | Branching on `locator_source` value — `verified` path (trust inventory) vs `live_extracted` path (treat inventory as best-effort; prefer stable role/label selectors) |

### §9.3 v4-batch prompt structure (playwright_runner row)

```
[System prompt]
  1. Role: Playwright test case generator for automated testing pipelines.
  2. Output contract: JSON only. <!-- SHARED_FRAGMENT: OUTPUT_CONTRACT_V3 -->
  3. Count rule (NEUTRAL per migration 022 — handler enforces count):
     "Generate test cases for each requested category. Do not exceed the
      requested count."
  4. Category coverage rules <!-- SHARED_FRAGMENT: CATEGORIES_SCHEMA -->
  5. Form-data handling <!-- SHARED_FRAGMENT: FORM_DATA_BLOCK -->
  6. Locator source handling <!-- SHARED_FRAGMENT: LOCATOR_SOURCE_BRANCH -->
  7. Locator selection rules (verified-inventory path primary)

[User prompt template]
  --- Page Context ---
  URL: {url}
  Page title: {page_title}
  Page type: {page_type}
  Screen key: {screen_key}
  ...
  --- Locator Inventory ---
  {locator_inventory_json}
  --- Form Data Context ---
  {form_data_block}                    # see FORM_DATA_BLOCK fragment
  --- Categories Requested ---
  {categories_block}                   # "all canonical" if None; explicit list otherwise
  --- Generation Instructions ---
  {count_line}
```

### §9.4 v4-interactive prompt structure (test_generator row)

```
[System prompt]
  1. Role: Interactive test-case generator for a live-DOM panel.
     Operator expects short-form, precise output within 30 seconds.
  2. Output contract <!-- SHARED_FRAGMENT: OUTPUT_CONTRACT_V3 -->
  3. Count rule: "Generate 1–3 test cases covering the requested scenario.
     Brevity is more important than breadth."
  4. Category coverage rules <!-- SHARED_FRAGMENT: CATEGORIES_SCHEMA -->
  5. Form-data handling <!-- SHARED_FRAGMENT: FORM_DATA_BLOCK -->
  6. Locator source handling <!-- SHARED_FRAGMENT: LOCATOR_SOURCE_BRANCH -->
     — live_extracted branch primary: treat inventory as best-effort;
       prefer role/label/testid selectors; flag fragile locators in
       `missing_locators` if a confident selector cannot be derived.
  7. No-hallucination rule (unchanged from v1.1 TSCD-001).

[User prompt template]
  --- Page Context ---                # same shape as batch
  ...
  --- Locator Inventory (live-extracted) ---
  {locator_inventory_json}
  --- Form Data Context ---
  {form_data_block}
  --- Interactive Request ---
  {categories_block_brief}            # single-category typical
```

### §9.5 `refactor_script_locators` prompt structure

```
[System prompt]
  1. Role: Playwright script refactoring expert. Given an existing test
     script and a fresh locator inventory, update selectors that have
     changed while preserving test intent.
  2. Output contract: JSON with refactored_script, changes_summary,
     locators_replaced, unchanged_reason. <!-- shares OUTPUT_CONTRACT_V3 shape -->
  3. Preservation rule: do NOT change assertions, test names, or scenario
     flow. Only update selectors.
  4. Format preservation: output must be syntactically valid in
     {script_format}.
  5. If no change needed (locators all still resolvable): set
     refactored_script = script_text verbatim, unchanged_reason = short text.

[User prompt template]
  --- Original Script ({script_format}) ---
  {script_text}
  --- Current Locator Inventory ---
  {locator_inventory_json}
  --- Page Context ---
  URL: {page_url}
  Change hints: {change_hints_or_none}
```

### §9.6 `max_tokens` settings

| Task | caller_module | max_tokens | Notes |
|---|---|---|---|
| `generate_test_cases_with_inventory` | `playwright_runner` | 12288 | unchanged from DEFECT-017 fix |
| `generate_test_cases_with_inventory` | `test_generator` | 4096 | lower bound reflects short-form output expectation (1–3 TCs) and tighter 30s latency ceiling |
| `refactor_script_locators` | `playwright_runner` | 8192 | pilot default; input size (script + inventory) can approach 4k — leaving headroom. Tunable via TASK_MAX_TOKENS per-caller in future. |

### §9.7 JSON parsing / retry

No changes from v1.1. `app.utils.json_parser.extract_json` handles truncation + markdown fences; `app.utils.llm_retry.llm_call_with_retry` handles Anthropic 5xx / overload per DEFECT-016.

## §10 Security Requirements

### §10.1 Tenant isolation (ADR-012, ADR-013)

Unchanged from v1.1. All generation handlers receive `tenant_id` from `InvokeRequest` (Gateway-validated). No cross-tenant data access possible — prompt templates are global (per ADR-005) but payloads, responses, and cost events are tenant-scoped.

### §10.2 ADR-033 extra-field behaviour

Unchanged. Generation payloads use `ConfigDict(extra="ignore")`. When PAP sends a field that the v2.0 schema doesn't know about, it is silently dropped and an INFO log is emitted (existing behaviour, per ADR-033 decision at ASP-FEAT-ASP-03 v1.1).

### §10.3 `refactor_script_locators` — script_text PII handling (NEW, ADR-012 applicability)

`RefactorScriptLocatorsPayload.script_text` is a **free-form string carrying test code**. It may contain:

- Test credentials (usernames/passwords for dedicated test accounts)
- Placeholder email addresses (`test_user@example.com`)
- Placeholder customer names / company names
- Mock API tokens / keys

**Governed policy:**

1. **Caller responsibility.** PAP (and any future caller) is responsible for scrubbing real PII from `script_text` before invocation. Real customer data, production credentials, or live API keys MUST NOT appear in the payload. This is a **Zone 3 consumer obligation** per ASP-GOV-CONSUMPTION-002.
2. **ASP storage.** `script_text` is **NOT persisted** at ASP. It appears in the LLM prompt (sent to Anthropic) and in the response (`refactored_script` echoes the body). ASP's `cost_events` table does NOT store payloads or responses (ADR-015).
3. **ASP logging.** `script_text` is NOT bound to structlog at any level by default. When DEBUG logging is enabled, `generation_prompt_resolved` may include a truncated prefix of the prompt — caller must treat DEBUG logs as privileged.
4. **Third-party disclosure.** `script_text` is sent to Anthropic's API per §4 LLM calls. Callers implicitly accept Anthropic's data handling for the content they send. This matches the existing posture for `generate_test_cases_with_inventory` payloads; no new disclosure surface in v2.0.

### §10.4 No new security surface

- No new auth flow (Gateway handles all auth per ASP-FEAT-ASP-00 v1.0).
- No new rate-limit surface (Gateway's SlowAPI per-tenant applies).
- No new storage surface (no new tables, no new files, no new cache keys).
- No new external egress (Anthropic is the only outbound call, unchanged from v1.1).

### §10.5 Universal ADR references

Per playbook §7, ADRs 012–016 apply universally:

- **ADR-012** — Cross-tenant → 404.
- **ADR-013** — Tenant-scoped queries on every DB access.
- **ADR-014** — API key in header, bcrypted at rest (Gateway owns).
- **ADR-015** — No raw payload persistence beyond cost metadata.
- **ADR-016** — Structlog never binds secrets.

No new ADRs introduced by v2.0.

---

**End of Batch 2 (§6–§10).** Batch 3 follows.

---

## §11 Implementation Checklist

All tasks owned by the ASP Development Team. Order below is the recommended
execution order; numbered labels are stable identifiers referenced in §12
ACs.

### I-024-01 — Write and apply migration 024 (prompt-only, 5 ops)

- Write `alembic/versions/0024_<slug>.py` with `down_revision = "0023"`.
- Five ordered operations per §5:
  1. UPDATE deactivate v3 canonical row (`e6c88ca5-…`).
  2. UPDATE deactivate L2-override row (`e92c4809-…`).
  3. INSERT v4 `playwright_runner` row (F-03-08 + F-03-04).
  4. INSERT v4 `test_generator` row (F-01-10).
  5. INSERT `refactor_script_locators` v1 row (playwright_runner, *).
- Both INSERTs (ops 3 + 4) must contain all four shared fragments
  verbatim (AC-SHARED-01).
- Downgrade reverses in exact opposite order.
- Fresh-DB round-trip per ADR-029 before applying to live:
  - `alembic upgrade head` on empty DB must run 0001 → 0024.
  - `alembic heads` returns single head 0024.
  - `alembic downgrade -1` then `alembic upgrade head` round-trips clean.
- Update `CLAUDE.md` applied chain; update `ASP-SCHEMA-CURRENT.md`;
  update `ASP-INDEX.md` migration head.

### I-024-02 — Pydantic schema updates (`app/schemas/generation_schemas.py`)

- `GenerateTestCasesWithInventoryPayload`:
  - Add `form_data: Optional[dict[str, str]] = None` (S-2).
  - Add `categories_to_generate: Optional[list[str]] = None` (S-1).
  - Widen `locator_source: Literal["verified"]` → `Literal["verified", "live_extracted"]` (S-3). Default remains `"verified"`.
- `GenerateTestCasesWithInventoryOutput`:
  - Add `covered_categories: list[str] = Field(default_factory=list)` (S-1).
- New `RefactorScriptLocatorsPayload` and `RefactorScriptLocatorsOutput` per §7.3/§7.4 (S-5).
- `ConfigDict(extra="ignore")` on payloads per ADR-033.
- `ConfigDict(extra="forbid")` on outputs.

### I-024-03 — Handler update: `_build_generation_instructions()` + interactive-mode timeout

- Extend the user-prompt rendering helper to:
  - Render a "Categories Requested" block from `payload.categories_to_generate` when present; render "Categories: all canonical" when None.
  - Render a "Form Data Context" block from `payload.form_data` when present; render the synthesize-realistic-values instruction when None (matches `FORM_DATA_BLOCK` shared fragment rendering contract).
  - Pass through the count instruction unchanged (post-OPS-003 neutral wording).
- Post-parse: extract `covered_categories` from the LLM output and return it on `GenerateTestCasesWithInventoryOutput`.

**OQ-2 ruling applied (ASP-OUT-011) — F-01-10 30s ceiling has TWO enforcement mechanisms:**

1. **Primary — `max_tokens=4096`** on the v4-interactive row's LLM call. Already locked in §9.6. Forces the LLM to self-bound output size.
2. **Secondary — handler-level timeout** wrapping the LLM call when `caller_module="test_generator"`:
   ```python
   try:
       response = await asyncio.wait_for(
           llm_call_with_retry(anthropic_client, ...),
           timeout=28.0,   # 28s, leaving 2s of budget for parsing + response assembly
       )
   except asyncio.TimeoutError:
       log.warning("generation_interactive_timeout",
                   caller_feature=req.caller_feature,
                   request_id=request_id)
       raise HTTPException(status_code=504, detail="Interactive generation timeout")
   ```
   The 28-second inner timeout holds the total request under the 30-second caller ceiling even when the LLM returns slowly within its `max_tokens` budget. 504 is correct per RFC 7807 — upstream timeout, retry after backoff.
- **Applies only to `caller_module="test_generator"`.** The `playwright_runner` batch/single-TC path retains its current MITIGATED-latency posture.

### I-024-04 — Handler update: `locator_source` branch

- In `app/services/generation.py`, the branch consuming `payload.locator_source`:
  - `"verified"`: unchanged from v1.1 (trust inventory).
  - `"live_extracted"`: new branch. Treat inventory as best-effort; prefer role/label/testid selectors; populate `missing_locators` more liberally when confidence is low (matches `LOCATOR_SOURCE_BRANCH` shared fragment).

### I-024-05 — Handler mode detection: F-01-10 caller

- In `generation.handle()`, when `req.task == "generate_test_cases_with_inventory"`, resolve the prompt row on `(req.caller_module, maturity_level, ab_variant=inventory)`. No change to dispatch code required — Prompt Registry (ADR-005/007) already keys on `caller_module`, so the new `test_generator` row is selected automatically when PAP sends `caller_module="test_generator"` for F-01-10 calls.
- Add a structlog sanity event `generation_caller_routed` bound with `caller_module`, `caller_feature`, `resolved_prompt_id` for per-request observability of the split.

### I-024-06 — `refactor_script_locators` handler

- Add `_handle_refactor_script_locators(req, model, request_id)` in `app/services/generation.py`.
- Slots into the existing `_handle_generic` pattern (prompt lookup → LLM → JSON parse → Pydantic validate). No RAG, no additional services.
- `TASK_MAX_TOKENS["refactor_script_locators"] = 8192`.

### I-024-07 — Register `refactor_script_locators` in `VALID_TASKS`

- `VALID_TASKS.add("refactor_script_locators")` in `app/services/generation.py`.
- `TASK_PAYLOAD_VALIDATORS["refactor_script_locators"] = RefactorScriptLocatorsPayload`.
- `TASK_OUTPUT_SCHEMAS["refactor_script_locators"] = RefactorScriptLocatorsOutput`.
- `TASK_MAX_TOKENS["refactor_script_locators"] = 8192`.

### I-RAG-04 — `docker-compose.yml` celery `-B` flag

**Not a new Stream B item; checklist entry to close the pre-existing gap surfaced during I-RAG-03 verification.**

- Update celery-worker command in `docker-compose.yml`:
  ```yaml
  command: celery -A app.worker worker -B --loglevel=info
  ```
  Note: `--concurrency=4` is dropped alongside adding `-B` because embedding beat inside a multi-concurrency worker is not the recommended Celery pattern. Pilot single-instance single-beat is fine; if scale demands concurrency, split into a separate `celery beat` service later.
- Recreate celery-worker (`docker compose up -d celery-worker`).
- Verify the scheduler boots by tailing worker logs for `Scheduler: Sending due task ontology-sync-daily` at the next trigger (02:00 UTC) and `Sending due task monthly-cost-aggregation` at the next 1st-of-month 01:00 UTC. For AC verification use a temporary `crontab(minute="*")` override to force a near-term trigger, then revert.

### I-024-08 — AC verification (36+ ACs)

- Write `tests/test_generation_v2.py` covering all five scope items + cross-cutting + AC-SHARED-01 + I-RAG-04.
- Mirror Gateway/ASP-01 test pattern: `httpx.AsyncClient + ASGITransport`, stubbed LLM call where appropriate to avoid Anthropic dependency during AC runs.
- Full 36+ AC matrix per §12. 100% PASS required before GOVERNED.

### I-024-09 — Governance sync + 4-way sync

- Update `CLAUDE.md`, `ASP-SCHEMA-CURRENT.md`, `ASP-INDEX.md`, `ASP-ADR.md`, `ASP-DEFECT-REGISTER.md` (if any new defect surfaced during AC), `ASP-COMMS-LOG.md`.
- 4-way sync per ADR-026.2 across repo + three asp-projects mirrors.
- sha256 checksum verification.

### I-024-10 — OpenAPI snapshot export (ADR-034)

- After migration 024 applies, export the OpenAPI 3.x JSON snapshot:
  `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > docs/openapi/asp-openapi-0024.json`
- Verify the snapshot includes:
  - `GenerateTestCasesWithInventoryPayload` with 17 fields, `form_data` and `categories_to_generate` nullable.
  - `locator_source` as `anyOf: ["verified", "live_extracted"]` enum.
  - `RefactorScriptLocatorsPayload` / `Output` schemas.
- Commit alongside the migration per `CLAUDE.md` Post-Implementation Checklist step 5.

## §12 Acceptance Criteria

**Target: 36+ ACs.** Actual: **37** — S-1 (8) + S-2 (4) + S-3 (4) + S-4 (4) + S-5 (8) + AC-SHARED-01 (1) + I-RAG-04 (2) + AC-CC (5) + AC-BC (1) = 37. 100% PASS required before GOVERNED.

### S-1 — Coverage-aware generation (8 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-S1-01** | Request with `categories_to_generate=["boundary_values","unauthorised_access"]` returns exactly 2 test cases, one per category | integration test; assert `len(test_cases) == 2` + category tagging |
| **AC-S1-02** | Request with `categories_to_generate=None` returns at least 5 test cases covering the canonical set | integration test; assert `len(test_cases) >= 5` |
| **AC-S1-03** | `covered_categories` field is populated on every response whether `categories_to_generate` was present or not | output schema assertion |
| **AC-S1-04** | Request with `categories_to_generate=[]` (empty list) returns 422 at Pydantic validation | assert 422 + RFC 7807 envelope |
| **AC-S1-05** | Request with an unknown category name (e.g. `"made_up_category"`) results in the LLM skipping it; `covered_categories` does not contain the unknown name; `missing_locators` (or equivalent warning channel) surfaces the skip | integration test |
| **AC-S1-06** | `covered_categories` is always a **subset** of `categories_to_generate` when the latter is present (never a superset) | assertion on every response where `categories_to_generate` is provided |
| **AC-S1-07** | Order of `categories_to_generate` is preserved in `covered_categories` when both are present | order-sensitive list compare |
| **AC-S1-08** | Coverage-gap detection: when `categories_to_generate=[A,B,C]` and the LLM covers only [A,B], the response has `covered_categories=[A,B]` (not `[A,B,C]`) so callers can detect the gap | integration test; induce partial coverage via constrained prompt or short max_tokens |

### S-2 — `form_data` seed context (4 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-FORM-01** (v2.0 acceptance) | Request with `form_data={"first_name":"Alice","email":"alice@example.com"}` produces at least one step whose value contains `"Alice"` or `"alice@example.com"` | integration test; scan `test_cases[*].steps[*].value` |
| **AC-FORM-02** (v2.0 acceptance) | Request without `form_data` returns 200 with behaviour unchanged from v1.1; LLM synthesises plausible values | behaviour-parity test against a v1.1 golden payload |
| **AC-S2-03** | `form_data` with invalid value types (e.g. `form_data={"x": 123}`) returns 422 (Pydantic rejects non-string values) | assert 422 on `dict[str, int]` payload |
| **AC-S2-04** | `script_text` (for `refactor_script_locators`) and `form_data` payload contents are NOT written to any ASP persistent store: `cost_events`, `prompt_templates`, `async_jobs`, `tenants`, `tenant_api_keys`, or `webhook_registrations` | post-test SQL scan on all seven tables; assert zero rows contain the probe string from any payload |

### S-3 — `locator_source="live_extracted"` support (4 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-S3-01** | Request with `locator_source="live_extracted"` returns 200 with `missing_locators` typically more populated than the `"verified"` equivalent (live-DOM inventory is best-effort) | paired-request comparison; not a strict inequality but a trend assertion |
| **AC-S3-02** | Request with `locator_source="verified"` returns output structurally identical to v1.1 baseline | behaviour-parity test against v1.1 golden payload |
| **AC-S3-03** | Request with `locator_source="live"` or any value outside `{"verified","live_extracted"}` returns 422 | Pydantic Literal validation |
| **AC-S3-04** | OPS-009 trigger: after migration 024 is applied, PAP's `PAP_F0110_LOCATOR_SOURCE="live_extracted"` switch is valid. Confirmed by an integration call carrying the new value and receiving a 200; recorded in ASP-COMMS-LOG as PAP-side switch completed | out-of-band test + COMMS-LOG entry |

### S-4 — F-01-10 caller registration (4 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-S4-01** | Request with `caller_module="test_generator"` and `task="generate_test_cases_with_inventory"` resolves to the v4-interactive prompt row (different `prompt_template_id` than the playwright_runner row) | test captures `generation_caller_routed` structlog event + asserts `resolved_prompt_id` differs between calls |
| **AC-S4-02** | Request with `caller_module="playwright_runner"` resolves to the v4-batch prompt row | same pattern, assert the paired IDs differ |
| **AC-S4-03** | Request with `caller_feature="F-01-10"` produces a `cost_events` row with `caller_feature="F-01-10"`; structlog events `invoke_start` / `invoke_complete` carry `caller_feature="F-01-10"` via contextvars | DB scan + log capture |
| **AC-S4-04** | F-01-10 request with typical live-extracted payload completes within the 30 s ceiling at p95 under Haiku (`standard` tier) | latency harness; 20 iterations over a small fixture |

### S-5 — `refactor_script_locators` (8 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-S5-01** | Happy path: payload with `script_body` + `locator_diff` (one+ entries) returns 200 with `refactored_script` non-empty, `changes_made` non-empty with at least one `element_name: ...` entry | integration test with a known before/after fixture |
| **AC-S5-02** | When `locator_diff` is empty, the handler returns `refactored_script == script_body` verbatim and `changes_made == []`; `unchanged_locators == []`; `warnings == []` (no ambiguity to flag) | behaviour-parity assertion |
| **AC-S5-03** | Ambiguous change — when an `old_locator` appears more than once in `script_body` — produces at least one entry in `warnings` noting the multi-occurrence risk; the LLM still performs the replacement but surfaces the ambiguity | inspection of `warnings` content |
| **AC-S5-04** | Payload missing `script_body`, `language`, `screen_key`, or `locator_diff` returns 422 at Pydantic validation | assert 422 on each absent required field |
| **AC-S5-05** | Payload with `locator_diff` containing an entry whose `old_locator` does NOT appear in `script_body` returns 200 with that `element_name` in `unchanged_locators` and the note "not found in script" | integration test with a deliberately-missing `old_locator` |
| **AC-S5-06** | `script_body` payload content is NOT written to any ASP persistent store (covered by AC-S2-04 seven-table scan; re-listed here for S-5 traceability) | cross-reference to AC-S2-04 |
| **AC-S5-07** | Request with `quality_tier="enhanced"` correctly invokes `claude-sonnet-4-6` for the refactor task (higher-quality model warranted for non-trivial refactors) | model routing assertion |
| **AC-S5-08** | Output `stop_reason == "end_turn"` on a standard-size payload (no truncation); `refactored_script` is syntactically valid in its declared `language` | linter hook in test (py compile for Python, basic syntax check for TS) |

### AC-SHARED-01 — Cross-row shared-fragment consistency (1 AC)

| AC | Statement | Verification |
|---|---|---|
| **AC-SHARED-01** | The four named shared fragments — `OUTPUT_CONTRACT_V3`, `CATEGORIES_SCHEMA`, `FORM_DATA_BLOCK`, `LOCATOR_SOURCE_BRANCH` — appear verbatim identical (byte-for-byte) in both v4 prompt rows (`caller_module="playwright_runner"` and `caller_module="test_generator"`). Any divergence is a prompt drift defect. | Post-migration SQL scan: `SELECT caller_module, system_prompt, user_prompt_template FROM prompt_templates WHERE task='generate_test_cases_with_inventory' AND version=4;` → extract each fragment (delimited by `<!-- SHARED_FRAGMENT: <NAME> -->` markers) → diff → assert `difflib.ndiff` is empty. Enforcement policy per OQ-3 (default: manual review at migration authoring time; CI-enforceable later). |

### I-RAG-04 — Celery beat `-B` flag (2 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-RAG04-01** | After `-B` flag lands and celery-worker is recreated, the `ontology-sync-daily` scheduled task fires at its next trigger; a `ontology_sync_scheduled_trigger` structlog event appears in the worker logs | worker-log tail around the trigger time OR a temporary `crontab(minute="*")` override for near-term AC verification |
| **AC-RAG04-02** | The pre-existing `monthly-cost-aggregation` scheduled task also fires (regression check — `-B` enables ALL entries, not just the new one) | worker-log tail OR temporary override |

### AC-CC — Cross-cutting (5 ACs)

| AC | Statement | Verification |
|---|---|---|
| **AC-CC-01** | Migration 024 applies cleanly on a fresh empty DB from head 0023; `alembic heads` returns single head `0024`; `alembic downgrade -1` then `alembic upgrade head` round-trips without error | fresh-DB round-trip per ADR-029 |
| **AC-CC-02** | Every v2.0 response (success and error) carries the `X-Request-Id` header matching the body `request_id` | inherited from Gateway; re-asserted here for v2.0 endpoints |
| **AC-CC-03** | ADR-033 INFO log emitted once per dropped extra field on generation payloads; dropped fields do not propagate into the prompt | log-capture test |
| **AC-CC-04** | `caller_feature` bound via `structlog.contextvars` appears on every generation-service log event in the request lifecycle (`invoke_start`, `invoke_complete`, `generation_caller_routed`, `generation_prompt_resolved`, `generation_output_parsed`) | log-capture test |
| **AC-CC-05** | Backward compatibility: v1.1 payloads (no `form_data`, no `categories_to_generate`, `locator_source="verified"`) continue to produce output that passes the v1.1 AC suite after v2.0 lands | regression run of the v1.1 golden suite |

### AC-BC — Behavioural correction (1 AC)

| AC | Statement | Verification |
|---|---|---|
| **AC-BC-01** | v2.0 ships with exactly two v4 prompt rows (playwright_runner + test_generator) for `generate_test_cases_with_inventory`. A single-row configuration is rejected at migration authoring (AC-SHARED-01 cannot pass with only one row, by definition). | structural check on `prompt_templates` after migration 024 |

**Total: 37 ACs.** All must pass before GOVERNED closure.

## §13 Open Questions

| OQ | Question | Owner | Ruling (ASP-OUT-011) |
|---|---|---|---|
| **OQ-1** | `refactor_script_locators` `changes_made` entries — line numbers or element names only? | Principal Architect | **RULED: element names only.** Line numbers create brittle ACs that break on whitespace changes; element names are stable across reformatting. Default confirmed. Implementation aligned. |
| **OQ-2** | F-01-10 30-second ceiling — handler timeout or LLM `max_tokens`? | Principal Architect | **RULED: both mechanisms required.** Primary = `max_tokens=4096` for the v4-interactive row (§9.6). Secondary = handler-level `asyncio.wait_for(..., timeout=28.0)` raising HTTP 504 on expiry, applied only when `caller_module="test_generator"`. §11 I-024-03 documents both. |
| **OQ-3** | AC-SHARED-01 enforcement — manual review or automated CI diff? | Principal Architect | **RULED: manual review at migration authoring time for v2.0.** §14 forward-note records: *"CI automation of shared fragment diff is the correct long-term mechanism — deferred to a future TSCD when the prompt registry gains a versioning API."* |

### Closed in this spec cycle

- **OQ-RAG-CACHE-01** — CLOSED. Architect ruling ASP-OUT-007, 2026-04-18 20:35 IST: Option B (5-minute TTL) is the pilot default. Implementation landed in I-RAG-02 (`CHROMA_CLIENT_TTL_SECONDS=300`). Listed here for audit completeness.

## §14 Change Log

### v2.0-draft

| Version | Date | Author | Notes |
|---|---|---|---|
| v2.0-draft (§1–§5) | 2026-04-18 | ASP Development Team | Batch 1 surfaced; five-item scope locked per ASP-OUT-007 verbatim content; migration 024 allocated as prompt-only. |
| v2.0-draft (§6–§10) | 2026-04-18 | ASP Development Team | Batch 2 surfaced; Note 2 SPLIT-by-caller ruling; three-caller matrix; `refactor_script_locators` schemas; PII policy for `script_text` (Zone 3). |
| v2.0-draft (§11–§14) | 2026-04-18 | ASP Development Team | Batch 3 surfaced; §11 checklist (I-024-01..10 + I-RAG-04); §12 37 ACs; §13 3 open questions + OQ-RAG-CACHE-01 closed; §14 this log. |
| v2.0 (accepted) | TBD | ASP Development Team + Principal Architect | Awaiting Batch 3 review + AC verification. |

### Baseline

- **v1.1** (ASP-FEAT-ASP-03, GOVERNED 2026-04-12, ASP-NOTE-005) — 32/32 AC PASS, commit `e8e3896`, PAP confirmed `1b32600`.
- **TSCD-001** (amendment to v1.1, IMPLEMENTED 2026-04-15, ASP-NOTE-006) — migration 019, dual-mode F-03-08/F-03-04, max_tokens=12288, page_type/screen_key.

### Scope items (summary)

| # | Item | Migration 024 op | Handler change | Schema change |
|---|---|---|---|---|
| S-1 | Coverage-aware generation | Prompt rules + category-rendering block | `_build_generation_instructions()` extension; parse `covered_categories` | `+categories_to_generate`; `+covered_categories` on output |
| S-2 | `form_data` seed context | Prompt form-data-block | `_build_generation_instructions()` extension | `+form_data` |
| S-3 | `locator_source="live_extracted"` | Prompt branch | Handler `locator_source` branch | Pydantic Literal widened |
| S-4 | F-01-10 third caller | Separate v4 row for `test_generator` | No dispatch change (Prompt Registry handles it) | — |
| S-5 | `refactor_script_locators` new task | v1 row seeded | New `_handle_refactor_script_locators` in generic dispatch | New Payload + Output models; `+VALID_TASKS` entry |

### Behavioural corrections from pre-governance / pre-v2.0 state

| # | Pre-v2.0 | v2.0 | Impact |
|---|---|---|---|
| **BC-1** | v1.1 left room for interpreting async conversion of F-03-08/F-03-04 as a latent v2.0 scope item | v2.0 explicitly locks "async conversion for F-03-08 AND F-03-04 is OUT OF SCOPE" in §3 non-goals and §4 Classification | No code change; explicit spec language prevents a future TSCD from treating the gap as a v2.0 oversight. |
| **BC-2** | Original ASP-OUT-007 directive proposed a single v4 row covering all five scope items + all three callers | v2.0 adopts the SPLIT-by-caller prompt architecture: two v4 rows (`playwright_runner` for F-03-08 + F-03-04, `test_generator` for F-01-10) | Dev Team ruling accepted by Architect at ASP-OUT-010. Rationale: OPS-003 mode-selection-in-prompt failure pattern. Migration 024 ops 3 + 4 split from a single INSERT. AC-SHARED-01 guards drift. |

### Forward-note entries for future specs

- **ADR-035 (proposed)** — RAG embedding-model fail-closed gate. Belongs to ASP-FEAT-ASP-02 (RAG spec), not v2.0.
- **Handler timeout secondary guard for F-01-10** — **now LANDING in v2.0 per ASP-OUT-011 OQ-2 ruling.** Primary = `max_tokens=4096`; secondary = `asyncio.wait_for(..., timeout=28.0)` raising 504 on expiry. Both required. Implementation in I-024-03. (Forward-note entry promoted to in-scope.)
- **CI automation of AC-SHARED-01** — pilot is manual review at migration authoring time. **Per ASP-OUT-011 OQ-3 ruling, promoted here as an explicit governed forward-note:** *"CI automation of shared fragment diff is the correct long-term mechanism — deferred to a future TSCD when the prompt registry gains a versioning API."* Adding this text verbatim so the constraint is tied to a prerequisite capability rather than a timeline.

---

**End of Batch 3 (§11–§14). All 14 sections drafted. 37 ACs locked. Awaiting Architect review before migration 024 alembic file authoring + implementation follows §11 checklist.**
