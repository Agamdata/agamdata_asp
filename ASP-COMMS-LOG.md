# ASP-COMMS-LOG — ASP ↔ Consumer Open-Thread Register

Chronological record of cross-team threads between ASP and consumer modules
(currently: PAP). Numbering mirrors PAP's `ASP-OUT-NNN` convention so that a
single identifier resolves on both sides. Entries are state-tracked
(`OPEN` / `CLOSED` / `SUPERSEDED`) with dates, references, and — for
closed items — a one-line resolution summary.

**Governance:** this file is a governance document per ADR-026 / ADR-026.2.
Canonical location: repo root (`asp/ASP-COMMS-LOG.md`, git-tracked).
Mirrored to `asp-projects/00-index/`, `asp-projects/00-index/communication/`,
and `asp-projects/01-master/` on every update. Divergence between copies
is a governance defect.

**Back-population note:** this log was created 2026-04-18 from existing
session threads. Two items were active at creation: ASP-OUT-003 (OPEN) and
ASP-OUT-004 (CLOSED). Earlier threads (ASP-OUT-001, ASP-OUT-002) predate
this log — if PAP references them, we will back-populate them on request.

---

## Summary

| ID | Subject | Filed | State | Last update |
|---|---|---|---|---|
| ASP-OUT-003 | `suggest_screen_mapping` lead time (PAP W-5 blocker) | 2026-04-18 | **CLOSED** | 2026-04-18 (PAP-ASP-REQ-ASP-01 v2.0 ACCEPTED; build starts under ASP-OUT-020) |
| ASP-OUT-004 | PAP-ASP-REQ-ASP-03 v2.0 acceptance (form_data amendment + coverage-aware scope) | 2026-04-17 | **CLOSED** | 2026-04-18 |
| ASP-OUT-006 | Communication protocol update — milestone-only reporting + MSG-ID tagging + COMMS-LOG pre-check | 2026-04-18 | **CLOSED** (ACCEPTED, effective immediately) | 2026-04-18 20:30 IST |
| ASP-OUT-007 | I-RAG-02 rulings + Stream A Batch 1 directive (warmup Option C, OQ-RAG-CACHE-01 Option B, migration 024 pre-write gate rulings, Batch 1 §1–§5 verbatim content, L2-override deactivation) | 2026-04-18 20:35 IST | **CLOSED** | 2026-04-18 (DEV-IN-007 milestone report) |
| ASP-OUT-008 | Status check — I-RAG-02 build + smoke + two-commit sequence overdue | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-008 stop-and-report + DEV-IN-007 milestone report) |
| ASP-OUT-009 | Batch 1 review ruling (ACCEPTED with 2 notes) + Batch 2 green light + I-RAG-03 directive | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-009 milestone report; I-RAG-03 complete; Batch 2 accepted at ASP-OUT-010) |
| ASP-OUT-010 | Batch 2 review ruling (ACCEPTED with 3 notes) + Batch 3 green light + I-RAG-04 checklist integration | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-010 milestone report; Batch 3 accepted at ASP-OUT-011) |
| ASP-OUT-011 | Batch 3 review ruling (ACCEPTED) + OQ-1/2/3 rulings + migration 024 green light (pre-write gate first — v3 prompt extraction) + I-RAG-04 go | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-011 + DEV-IN-012 milestone reports; v3 prompts surfaced; OQ rulings applied; I-RAG-04 complete) |
| ASP-OUT-012 | v4 prompt content ruling + DEFECT-022 disposition (Option B + C) + migration 024 implementation sequence | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-012 + DEV-IN-013 + DEV-IN-014 milestone reports; migration 024 applied; Pydantic + handler + VALID_TASKS shipped) |
| ASP-OUT-013 | Migration 024 confirmed clean + Rule 8 ruling (no Rule 8) + Steps 4–5 green light | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-013 stop-and-report + DEV-IN-014 resume; Rule 8 §9.2 clarification applied) |
| ASP-OUT-014 | CRITICAL migration 024 regression ruling — Option A get_prompt_variant fallback chain | 2026-04-18 | **CLOSED** | 2026-04-18 (DEV-IN-014 milestone; 4-level fallback implemented + verified; PAP production path restored) |
| ASP-OUT-015 | Steps 4+5 confirmed clean + G-PROMPT-REACH gate directive + Step 8 green light (37-AC verification across 8 phases) | 2026-04-18 | **CLOSED** | 2026-04-18 (37/37 PASS on re-run; Steps 9+10 shipped; v2.0 GOVERNED) |
| ASP-OUT-016 | AC-S1-04 ruling — Option A field_validator on categories_to_generate (empty list → 422) + re-run protocol | 2026-04-18 | **CLOSED** | 2026-04-18 (Commit 13 validator shipped + verified; AC-S1-04 PASS on re-run) |
| ASP-OUT-017 | AC-S1-07 ruling — Option B + repurpose (uniqueness, not order) + §9 CATEGORIES_SCHEMA note + re-run | 2026-04-18 | **CLOSED** | 2026-04-18 (37/37 PASS — ASP-NOTE-009 v2.0 governance closure) |
| ASP-OUT-019 | Architect's formal PAP notification of BP-10 readiness — outbound; no Dev Team action | 2026-04-18 | **CLOSED** | 2026-04-18 (per ASP-OUT-021 clarification — PAP ack arrives through standard channel; Dev Team responsibility ends at shipping BP-10) |
| ASP-OUT-020 | suggest_screen_mapping build (PAP-ASP-REQ-ASP-01 v2.0 ACCEPTED; ASP-OUT-003 closed). Pydantic + migration 025 + handler + 8 ACs. | 2026-04-18 | **CLOSED** | 2026-04-18 (8/8 AC PASS — ASP-NOTE-010 closure; Commits A+B+C+D shipped) |
| ASP-OUT-021 | BP-10 confirmed + ASP-OUT-019 cleanup + DEFECT-022 deferred-to-maintenance note + ASP-02 Batch 2 authoring directive | 2026-04-18 | **OPEN** | 2026-04-18 (DEV-IN-021 in flight — see Batch 1 gap surface) |

Totals as of 2026-04-19 03:00 IST: **1 OPEN** (ASP-OUT-021), **16 CLOSED** (incl. ASP-OUT-019 per ASP-OUT-021 clarification).

---

## Open threads

### ASP-OUT-003 — `suggest_screen_mapping` lead time — OPEN

- **Mirrors:** PAP's ASP-OUT-003
- **Filed:** 2026-04-18 18:45 IST by Principal Architect, ASP
- **Blocks:** PAP W-5 lead time ruling; PAP-ASP-REQ-ASP-01 v2.0 formal acceptance
- **Subject:** PAP asked ASP to confirm whether `suggest_screen_mapping` exists in ASP-01 today (i.e. "exists, just ungoverned" — fast path) or must be built from scratch (build required, estimate lead time).
- **Scope boundaries:** ASP-01 NLP only. Not a Gateway change, not a RAG change, not a Generation change.

**ASP Dev Team reply (2026-04-18 18:47 IST, two minutes post-request):**

| Finding | Evidence |
|---|---|
| `suggest_screen_mapping` does not exist in any form | Zero matches repo-wide for `screen_map\|suggest_screen\|map_screen\|screen_suggest` across `*.py`, `*.md`, `*.json`, `*.yml` |
| Current NLP `VALID_TASKS` | `{nl_to_sql, intent_extraction, entity_recognition, sentiment, language_detection, classify_probe_result}` — 6 tasks (`app/services/nlp.py:35–42`) |
| Complexity classification | **SIMPLE** — fits existing `_handle_generic` dispatch branch; no new infrastructure, no cross-service dependencies |
| Lead time estimate | **~2 working days** end-to-end from caller integration requirement in hand to GOVERNED status |

**Required artefacts for implementation (once unblocked):**

1. Caller integration requirement from PAP (payload fields + expected output fields + use-case justification) — `PAP-ASP-REQ-ASP-01 v2.0` or a v1.1 amendment.
2. Spec vehicle ruling — ASP-FEAT-ASP-01 v1.3 additive amendment OR ASP-TSCD-002 against v1.2. Dev Team recommendation: v1.3 (matches v1.1 → v1.2 precedent; task addition, not change to existing task).
3. Migration: provisional 025 per ADR-028 (number not allocated until migration is written; may become 024 or 025 depending on timing vs coverage-aware generation migration).
4. Pydantic schemas in `app/schemas/nlp_schemas.py`: `SuggestScreenMappingPayload` + `SuggestScreenMappingOutput` with `ConfigDict(extra="forbid")`.
5. Handler wiring: add task to `VALID_TASKS` and `TASK_OUTPUT_SCHEMAS`; no new dispatch branch required (generic path).
6. Prompt template seed in `prompt_templates` (per ADR-005 / ADR-027).
7. AC suite: 4–6 ACs (happy path, payload validation, extra-field rejection, cross-tenant 404, structlog + cost_event, GOVERNED closure).

**Governance classification:** Type B additive (ADR-023). No 90-day window. 5-business-day review.

**ADR-031 (phantom resurrection) applicability:** does NOT apply. `suggest_screen_mapping` is a net-new task; it has never existed and was never deleted.

**Blast radius:** zero for existing NLP tasks; zero for non-NLP services.

**Current state (2026-04-18 evening):**

- Waiting on (a) Principal Architect ruling on spec vehicle choice, (b) PAP's caller integration requirement delivery.
- No implementation started. Hold on pilot environment remains.

**Cross-references:**

- Session codebase check transcript — delivered directly in Architect message thread, 2026-04-18 18:47 IST.
- Current governance head: commit `f274be4` (migration 0023).
- `ASP-FEAT-ASP-01 v1.2` — current GOVERNED spec for ASP-01 (2026-04-10, ASP-NOTE-002).
- `ASP-FEAT-ASP-00 v1.0` — Gateway governance closure (2026-04-18, ASP-NOTE-008).

---

## Closed threads

### ASP-OUT-014 — CRITICAL migration 024 regression + Option A fallback ruling — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP (response to DEV-IN-013 stop-and-report)
- **State at filing:** OPEN (CRITICAL — production-path regression)
- **Scope:** After migration 024 applied, PAP production path (`playwright_runner/L2/inventory`) hit PromptNotFoundError because `get_prompt_variant` required exact `(caller, maturity)` match and v4 rows were at `maturity="*"`. Architect ruled Option A: add 4-level fallback chain to `get_prompt_variant` mirroring `get_prompt`.

**Resolution (Commit 11, `e9b0a99`):**

- `app/registry/prompt_registry.py` — `get_prompt_variant` rewritten with priority-ordered SQL: `(caller, mat) → (caller, *) → (*, mat) → (*, *)`, `LIMIT 1`. `ab_variant` remains exact — loud failure preserved for unknown variants.
- Verification T-A1..T-A5 all PASS: PAP F-03-08/F-03-04 path restored, F-01-10 path works, unknown-caller/unknown-variant correctly fail loud.
- Spec §9.2 note on rule numbering (Rule 8 gap clarification): Rules 6 + 7 are system-prompt additions; FORM_DATA_BLOCK is a user-prompt addition; Rule 9 is v4-interactive-only; no Rule 8.

**Impl-log entry recorded under ASP-FEAT-ASP-02-v1_0-IMPL-LOG.md** (critical regression + fix narrative + T-A1..T-A5 verification matrix + cache-hygiene note).

---

### ASP-OUT-013 — Migration 024 confirmed clean + Rule 8 ruling + Steps 4–5 green light — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **Scope:** Migration 024 accepted post-fresh-DB verification; Rule 8 numbering gap ruled (no Rule 8 intended — my directive authoring was inconsistent); Steps 4 and 5 green-lit with detailed Pydantic and handler-change instructions.

**Resolution:**

- §9.2 note on rule numbering added (Commit 12).
- Step 4 (I-024-02 Pydantic) shipped as Commit 10 (`81afb83`): 8/8 Pydantic verification PASS.
- Step 5 (I-024-03..07 handlers) shipped as Commit 11 (`e9b0a99`): 11/11 targeted unit tests PASS (includes ASP-OUT-014 Option A fix surfaced during Step 5 verification).

**DEV-IN-013 was a stop-and-report after Step 5 unit tests surfaced the regression** — Architect responded with ASP-OUT-014 Option A ruling; Step 5 resumed and completed.

---

### ASP-OUT-012 — v4 prompt content ruling + DEFECT-022 disposition + migration 024 implementation sequence — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **State at filing:** OPEN (10-step implementation sequence; DEFECT-022 filed; migration 024 + Pydantic + handler + AC verification + OpenAPI + .docx)
- **Scope:** Full v2.0 implementation rollout.

**DEFECT-022 disposition applied (Option B + C combined) — Commit `d4f2214`:**
- Filed as ASP-DEFECT-022 (cost aggregator `psycopg2` import failure) with HIGH severity, OPEN status, fix deferred outside v2.0 scope.
- `monthly-cost-aggregation` entry commented out in `app/worker.py beat_schedule` per Option C — prevents daily beat dispatch of the broken task.
- 4-way sha256-verified sync.

**V4 prompt content ruling applied:**
- v3 STRICT RULES 1–5 preserved verbatim in both v4 rows.
- RULE 6 (CATEGORIES_SCHEMA) + RULE 7 (LOCATOR_SOURCE_BRANCH) added to both v4 rows with shared-fragment markers.
- RULE 9 (interactive) added to test_generator row only per directive.
- `covered_categories` added to OUTPUT_CONTRACT_V3 at top level alongside `missing_locators`.
- FORM_DATA_BLOCK added to user-prompt template (shared between both v4 rows).
- refactor_script_locators v1 system + user prompts written verbatim from directive.

**Rule 8 gap (directive inconsistency):** Q1 said "Add new rules as 6, 7, 8 in order" but concrete content was provided only for RULE 6 (CATEGORIES_SCHEMA) and RULE 7 (LOCATOR_SOURCE_BRANCH). FORM_DATA_BLOCK is in the user-prompt (not a system-prompt rule). Q3 provided RULE 9 for test_generator. **Dev Team proceeded with 6, 7, (and 9 for test_generator only). No RULE 8 materialised.** Flagged for Architect confirmation; easy one-line migration amendment if a concrete RULE 8 is supplied later.

**§7.3/§7.4 alignment:** Spec's Batch 2 §7 used field names `script_text`/`locator_inventory`/`changes_summary` that did not match the directive's authoritative prompt placeholders (`script_body`/`locator_diff`/`changes_made`). Spec amended in this commit; `RefactorScriptLocatorsPayload` and `RefactorScriptLocatorsResult` now reflect directive names. AC-S5-01..08 field references updated. `LocatorDiffItem` helper model added.

**Migration 024 implementation sequence progress:**

| Step | State |
|---|---|
| I-024-01 alembic file written | ✅ `alembic/versions/0024_v4_prompts_coverage_form_live_extracted_refactor.py` |
| Fresh-DB round-trip per ADR-029 | ✅ empty → 0001..0024 → downgrade 0024→0023 → upgrade 0023→0024 (all `Running upgrade/downgrade` lines visible) |
| Apply to live DB | ✅ `alembic current = 0024 (head)` |
| All five operations verified | ✅ (5 rows on post-migration query) |
| ChromaDB untouched | ✅ prompt-only migration |
| Pydantic changes (I-024-02) | ⏳ Next commit in this turn |
| Handler changes (I-024-03..07) | ⏳ Next commit in this turn |
| AC verification 37 ACs (I-024-08) | ⏳ Separate milestone |
| OpenAPI snapshot (I-024-10) | ⏳ After I-024-08 |
| .docx render + governance sync | ⏳ After AC verification complete |

**State at this milestone:** OPEN. Remaining steps: Pydantic changes, handler changes, AC verification, OpenAPI export, .docx render, final governance sync. Next commits continue in this turn OR next turn.

---

### ASP-OUT-011 — Batch 3 review + migration 024 green light (pre-write gate) + I-RAG-04 execution — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **State at filing:** OPEN (pre-write gate for I-024-01 — Architect needs v3 prompt content before ruling on v4 additions)
- **Scope:** Batch 3 accepted; OQ-1/2/3 ruled; migration 024 green-lit pending v3 prompt extraction; I-RAG-04 instructed to execute alongside.

**OQ rulings applied (in Commit 6 of this turn):**

- **OQ-1 (refactor changes_made format):** RULED element names only. §13 table updated.
- **OQ-2 (F-01-10 30s ceiling):** RULED both mechanisms required — `max_tokens=4096` primary + `asyncio.wait_for(..., timeout=28.0)` raising 504 secondary guard applied only when `caller_module="test_generator"`. §11 I-024-03 now documents both. §13 table updated.
- **OQ-3 (AC-SHARED-01 enforcement):** RULED manual review at migration authoring time for v2.0. §14 forward-note records the CI-automation deferral and its prerequisite ("prompt registry versioning API"). §13 table updated.

**Pre-write gate — v3 prompt values extracted from live DB:**

- `system_prompt` length 1865 bytes; `user_prompt_template` length 296 bytes.
- Surfaced verbatim in DEV-IN-011 milestone report for Architect review.
- Migration 024 alembic file authoring held pending Architect ruling on v4 additions that build on v3.

**I-RAG-04 COMPLETE:**

- `docker-compose.yml` celery-worker command updated: `celery -A app.worker worker -B --loglevel=info` (added `-B`, dropped `--concurrency=4`).
- Recreated; beat started (`[INFO/Beat] beat: Starting...`).
- Both beat entries loaded in the live worker.
- `app.ontology.manager.run_ontology_sync` end-to-end via `.delay()`: SUCCESS.
- `asp.cost_aggregator` end-to-end via `send_task`: **FAILURE — `No module named 'psycopg2'`.** Pre-existing latent bug (aggregator uses sync Postgres driver; pilot uses asyncpg). Never observed before because beat was never active. Surfaced to Architect for ruling on defect filing / scope disposition.

**State at this milestone:** OPEN. Awaiting Architect rulings on:

1. v4 additions to the v3 prompt base (I-024-01 migration file authoring blocks on this).
2. Disposition of the pre-existing cost-aggregator `psycopg2` bug (file as ASP-DEFECT-022 / defer / disable entry).

---

### ASP-OUT-010 — Batch 2 review ruling + Batch 3 green light + I-RAG-04 checklist integration — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **State at filing:** OPEN (awaiting Batch 3 surface for review)
- **Scope:** Three Batch 2 notes + Batch 3 detailed authoring guidance + I-RAG-04 integration into §11.

**Three Batch 2 notes applied (in Commit 5 of this turn):**

1. **§7 — 17 vs 16 field count:** Architect confirmed 17 is authoritative; earlier "16" was a directive count error. §7.1 header rewritten; reconciliation logged in ASP-FEAT-ASP-02-v1_0-IMPL-LOG.md as "Architect field count corrected to 17 per Pydantic model authority."
2. **§9 — Four named shared fragments:** Governed invariant locked — "Shared fragments must be identical across both rows. Any divergence is a prompt drift defect." Explicit statement added to §9.2; AC-SHARED-01 in §12 enforces via post-migration SQL scan + diff.
3. **§10 — script_text PII policy:** accepted as written; AC on no-persistence added in §12 as AC-S2-04 with a cross-reference from S-5.

**Batch 3 §11/§12/§13/§14 drafted:**

- §11: Ten I-024-NN items (migration, Pydantic, handler extensions, new task, AC verification, governance sync, OpenAPI snapshot) + I-RAG-04 for the pre-existing celery -B gap.
- §12: **37 ACs** (exceeding the 36-minimum target): S-1 (8) + S-2 (4, including AC-FORM-01/02 from v2.0 acceptance + the no-persistence AC) + S-3 (4, including OPS-009 switch trigger) + S-4 (4) + S-5 (8) + AC-SHARED-01 (1) + I-RAG-04 (2) + AC-CC cross-cutting (5) + AC-BC behavioural correction (1).
- §13: 3 open questions (OQ-1 refactor line-numbers vs element-names, OQ-2 F-01-10 30s enforcement mechanism, OQ-3 AC-SHARED-01 enforcement mode), all with pilot defaults. OQ-RAG-CACHE-01 closed (Option B 5-min TTL ruling already applied in I-RAG-02).
- §14: v2.0-draft log + v1.1 + TSCD-001 baseline; five-scope-item summary table; BC-1 (async deferred) + BC-2 (split-by-caller) behavioural corrections; forward-note entries (ADR-035, handler timeout secondary guard, CI automation of AC-SHARED-01).

**State at this milestone:** OPEN until Architect reviews Batch 3 and rules on:
- OQ-1, OQ-2, OQ-3 (defaults provided; override if desired)
- Any §11 checklist adjustments
- Any §12 AC additions or re-scoping
- Green light to begin migration 024 authoring + implementation

---

### ASP-OUT-009 — Batch 1 review ruling + Batch 2 green light + I-RAG-03 directive — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **State at filing:** OPEN (awaiting Batch 2 surface + I-RAG-03 completion report)
- **Scope:** Three items bundled.

**Item 1 — Batch 1 review:** ACCEPTED with two notes.
- Note 1: §4 must explicitly lock async conversion for F-03-08 AND F-03-04 as OUT OF SCOPE in non-goals. Applied in Commit 3 (Batch 2) — §3 out-of-scope item amended; §4 Classification "Mode" row rewritten to call out v2.0 fully synchronous and async-deferred.
- Note 2: Rule on single-row-for-all-scope-items vs split-by-caller (F-01-10 → test_generator caller_module) before writing v4 prompt text. **Dev Team ruling: SPLIT by caller.** Rationale: OPS-003 demonstrated mode-selection-in-prompt unreliability; Prompt Registry's resolution key is designed for caller-module split; shared fragments maintained across rows with AC-SHARED-01 (Batch 3 AC) to detect drift. §5 migration-024 operations expanded from 4 ops to 5 (two v4 INSERTs, one per caller_module). §9 Prompt Design documents the split and the shared-fragment contract.

**Item 2 — Batch 2 (§6–§10):** surfaced in Commit 3.
- §6 API Contract: common envelope + three calling modes (F-03-08 batch, F-03-04 single-TC, F-01-10 interactive) + `refactor_script_locators` subsection + error matrix.
- §7 Request/Response Detail: `GenerateTestCasesWithInventoryPayload` v2 documented as **17 fields** (discrepancy with Architect's "16" flagged for review — Dev Team counted form_data + categories_to_generate as two new fields on top of 15 baseline = 17; Architect may have intended 16 with one field counted elsewhere; Pydantic model is authoritative once accepted). Full `RefactorScriptLocatorsPayload` / `Output` schemas authored. `covered_categories` on output model. `locator_source: Literal["verified", "live_extracted"]` confirmed as Pydantic-only (G-2).
- §8 Caller Integration: three-caller matrix, `refactor_script_locators` integration, F-01-10 guidance on `missing_locators` + low-confidence live_extracted handling.
- §9 LLM and Prompt Design: Note 2 ruling baked in (SPLIT). Shared fragments enumerated. v4-batch / v4-interactive / refactor_script_locators prompt structures drafted. `max_tokens` per caller + task.
- §10 Security: tenant isolation unchanged. ADR-033 extra-field behaviour unchanged. **New policy** on `refactor_script_locators.script_text` PII handling (Zone 3 caller responsibility; ASP does not persist; DEBUG logs are privileged; no new security surface).

**Item 3 — I-RAG-03 Celery beat schedule:** implemented in Commit 4.
- Gate met: `run_ontology_sync` was a plain function, wrapped as Celery task `app.ontology.manager.run_ontology_sync` with optional args.
- Cron-path (no args) logs `ontology_sync_scheduled_trigger` as pilot no-op; follow-up spec task extends to iterate active tenants.
- Manual-path (full args) retains existing behaviour; partial-args raises ValueError.
- `ontology-sync-daily` beat entry registered with `crontab(hour=2, minute=0)` and `options={"queue": "celery"}`.
- Verified in-process: beat_schedule dict carries entry; `celery_app.tasks["app.ontology.manager.run_ontology_sync"]` resolves to a Task object; cron no-op returns None; full-args roundtrip upserts 1 chunk and cleans up.
- **Pre-existing gap flagged (not fixed in I-RAG-03):** `docker-compose.yml` celery-worker command lacks `-B`. No beat process is actually running. Follow-up: add `-B` flag when RAG spec §11 requires scheduler execution.

**State at this milestone:** Still OPEN — Architect's review of Batch 2 and ruling on AC-SHARED-01, the 17-vs-16 field count reconciliation, and any §6–§10 notes are required before Batch 3 starts.

---

### ASP-OUT-008 — Status check: I-RAG-02 + Stream A milestone overdue — CLOSED 2026-04-18

- **Filed:** 2026-04-18 by Principal Architect, ASP
- **State at filing:** OPEN (immediate response required)
- **Scope:** Status verification on four items — build completion, `alembic current` post-build, I-RAG-02 smoke test, commit 1/commit 2 push state.

**Dev Team response (DEV-IN-008, same day):**

Filed a stop-and-report per standing rule reporting "build never ran" based on zero bytes in the background log, stale image creation timestamp (2026-04-16), and no `docker build` process in `ps -ef`. All three signals were consistent with a stalled build BUT were equally consistent with an in-progress BuildKit invocation (BuildKit suppresses non-TTY stdout, tags the image only at export time, and runs in `dockerd` not as a shell child). The build was in fact running the whole time and completed normally 446.8s later with image creation `2026-04-18T08:26:55Z`, sentence-transformers preload present, and `dim=384` load verified.

**Lesson captured in the ASP-FEAT-ASP-02 IMPL-LOG** (routing gaps + recovery-cost entry). For future Dockerfile-rebuild operations: completion is only safe to claim when EITHER (a) `docker compose build` exits in the foreground OR (b) image creation-time changes AND a functional probe against the new image succeeds. Log-file-size and process-listing are not reliable signals.

**Post-build state (this milestone):**

- `alembic current` returns `0023 (head)` cleanly post-swap ✅
- I-RAG-02 smoke test: **7/7 PASS**
- Commit 1 (I-RAG-02) + Commit 2 (Stream A pre-write gate + Batch 1 skeleton) pushed — see DEV-IN-007 milestone report for hashes.

**State at closure:** CLOSED. Both items ASP-OUT-007 and ASP-OUT-008 resolve in this milestone report.

---

### ASP-OUT-007 — I-RAG-02 rulings + Stream A Batch 1 directive — CLOSED 2026-04-18

- **Filed:** 2026-04-18 20:35 IST by Principal Architect, ASP
- **State at filing:** OPEN (awaiting I-RAG-02 completion report + Batch 1 draft)
- **Scope:** Restated the 19:30 and 20:10 IST directives (neither delivered to this session), locked rulings on warmup, cache TTL, embedding-snapshot disposition, L2-override deactivation, migration 024 shape, and Batch 1 verbatim content for §1–§5.

**Rulings locked:**

1. **Warmup Option C** — sentence-transformers + Dockerfile build-step preload. Implementation on disk matches.
2. **OQ-RAG-CACHE-01 Option B** — 5-minute TTL (`CHROMA_CLIENT_TTL_SECONDS=300`). Implementation on disk matches.
3. **`_check_embedding_model_snapshot`** — warn-on-drift, **not** fail-closed. ADR-035 governs fail-closed in the RAG spec (ASP-FEAT-ASP-02), not in the v2.0 Generation amendment.
4. **L2-override row (`e92c4809`, v1)** — deactivate in migration 024 alongside the v3 canonical row (`e6c88ca5`).
5. **G-2 `locator_source`** — Pydantic Literal only; no PG enum; no DB type change.
6. **G-5 `alembic current` pre-build error** — expected; resolves post-build via `COPY . .`. Confirmed `0023 (head)` clean post-build in this milestone.
7. **Two-commit plan approved.**
8. **Batch 1 §1–§5 verbatim content** provided by Architect and used as-is in the draft.

**Dev Team response (DEV-IN-007 — this milestone report):**

Completion artefacts:

- Commit 1: I-RAG-02 code + Dockerfile + impl-log routing-gaps entry + impl-log I-RAG-02 entry + ASP-COMMS-LOG updates. Smoke test 7/7 PASS.
- Commit 2: Stream A pre-write gate logged + Batch 1 skeleton surfaced at `docs/spec-drafts/ASP-FEAT-ASP-03-v2_0.md` with §1–§5 populated per Architect's verbatim content.
- 3-way sync (ASP-COMMS-LOG and any governance doc touches).

**State at closure:** CLOSED.

---

### ASP-OUT-006 — Communication protocol update — CLOSED 2026-04-18

- **Filed:** 2026-04-18 20:30 IST by Principal Architect, ASP
- **State at filing:** CLOSED (ACCEPTED, effective immediately — informational acceptance, not an action gate)
- **Scope:** Standing communication protocol between Principal Architect and ASP Development Team.

**Three protocol changes locked:**

1. **Milestone-only reporting.** Dev Team reports at milestone completion only — not after every step. One consolidated report per stream milestone per session. Interim progress reports (like the one I sent at 20:25 IST enumerating each file touched) are superseded by this rule.
2. **COMMS-LOG pre-check before any outbound.** Dev Team checks `ASP-COMMS-LOG.md` before forwarding any item to Product Leadership. If the item is already logged with a ruling, the forward does not go out.
3. **MSG-ID tagging.** Every outbound message carries an MSG-ID matching its `ASP-COMMS-LOG.md` entry (e.g. `MSG-ID: ASP-OUT-NNN`).

**Dev Team acknowledgment:** rules applied from this entry forward. The next Dev Team milestone report (likely the consolidated I-RAG-02 + Stream A Migration 024 pre-write gate report after the in-flight Dockerfile build completes) will carry `MSG-ID: DEV-IN-NNN` and will fold in this commit's hash per the Architect's instruction.

---

### ASP-OUT-004 — PAP-ASP-REQ-ASP-03 v2.0 acceptance — CLOSED 2026-04-18

- **Mirrors:** PAP's ASP-OUT-004
- **Filed:** 2026-04-17 by Principal Architect, ASP (form_data amendment ruling)
- **Subject:** Formal acceptance of PAP-ASP-REQ-ASP-03 v2.0 scope:
  - `form_data` additive field on `GenerateTestCasesWithInventoryPayload`
  - Coverage-aware generation (conditional on PAP Q-1/Q-2 answers)
  - `locator_source="live_extracted"` enum extension
- **Classification:** Type B additive per ADR-023. Consumer-isolated (ADR-033 `extra="ignore"` covered the interim silent-drop behaviour). Response schema unchanged. No cross-consumer review required.

**Closure summary (Principal Architect, 2026-04-18):**

- **form_data:** accepted into v2.0. Schema addition + prompt rendering block defined. Two ACs locked (AC-FORM-01 value appears in generated test case step, AC-FORM-02 absence → 200 with prior behaviour). ADR-033 silent-drop is the interim behaviour until migration 024 lands. **F-01-12 complete on PAP's side.**
- **Coverage-aware generation:** scope accepted; activation still pending PAP Q-1 (`locator_source` semantics — `live` vs `verified` vs `live_extracted`) and PAP Q-2 (`engine_version` / `page_profiles` — prompt substitution vs metadata only).
- **`locator_source` enum:** migration 023 did NOT extend the enum (Gateway-only scope); the extension will land in migration 024 alongside coverage-aware generation. Explicit instruction to PAP: **do NOT switch `PAP_F0110_LOCATOR_SOURCE` to `live_extracted` until migration 024 is applied and confirmed.**
- **Migration 024:** provisional allocation; blocks on PAP Q-1/Q-2 answers.

**ASP Dev Team standing:** no implementation. Forward-note recorded in the ASP-FEAT-ASP-00 v1.0 implementation log under "v2.0 forward-note — form_data amendment (migration 024, NOT 023)". Amendment log entry C-15 (PAP-ASP-REQ-ASP-03 v2.0 change table) is PAP-side; ASP owes nothing on that artefact.

**State at closure:**

- From ASP side: **CLOSED**. No further action pending.
- From PAP side: open until migration 024 ships.
- The v2.0 acceptance itself is complete; implementation is bound to migration 024's prerequisites.

**Cross-references:**

- Principal Architect ruling on form_data amendment: 2026-04-17 (session transcript).
- Clarifying ruling on `locator_source` / migration 023 scope: 2026-04-18 (session transcript).
- `ASP-FEAT-ASP-03 v1.1` — current GOVERNED spec for ASP-03 (2026-04-12, ASP-NOTE-005).
- `ASP-FEAT-ASP-03 v2.0` — in preparation, blocks on Q-1/Q-2.
- Implementation-log entries:
  - `docs/spec-drafts/ASP-FEAT-ASP-00-v1_0-IMPL-LOG.md` — "v2.0 forward-note — form_data amendment (migration 024, NOT 023)"

---

## Conventions

- **Numbering:** strictly ascending, mirrors PAP's `ASP-OUT-NNN` labels. Do not recycle numbers. A superseded thread retains its original ID with a `SUPERSEDED by ASP-OUT-NNN` state marker.
- **State transitions:** `OPEN → CLOSED` only. A re-opened item gets a new ID and cross-references the original.
- **Ownership:** ASP-side content is authored by the ASP Development Team and reviewed by the Principal Architect. PAP-side content is mirrored from PAP's ASP-OUT log; any divergence is reconciled at next comms sync.
- **Append-only:** this file is append-only within a calendar year. Yearly archival rolls closed threads into `ASP-COMMS-LOG-<year>.md` if the register grows past 50 entries.

## Last Updated

2026-04-18 23:45 IST — CLOSED ASP-OUT-012/013/014. Migration 024 applied + v2.0 Pydantic + v2.0 handler shipped. Critical regression surfaced and fixed mid-session (ASP-OUT-014 Option A — 4-level fallback chain in get_prompt_variant). PAP production path restored. All 11 Step 5 unit tests PASS. Totals: 1 OPEN (ASP-OUT-003), 10 CLOSED.
