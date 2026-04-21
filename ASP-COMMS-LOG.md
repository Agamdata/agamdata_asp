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
| ASP-OUT-021 | BP-10 confirmed + ASP-OUT-019 cleanup + DEFECT-022 deferred-to-maintenance note + ASP-02 Batch 2 authoring directive | 2026-04-18 | **CLOSED** | 2026-04-18 (superseded by ASP-OUT-022 which corrected the Batch 1 gap and fast-tracked DEFECT-022) |
| ASP-OUT-022 | ASP-FEAT-ASP-02 Batch 1 authoring + DEFECT-022 asyncpg port (parallel) | 2026-04-18 | **CLOSED** | 2026-04-19 (Batch 1 ACCEPTED per ASP-OUT-024 §1–§5 rulings; DEFECT-022 RESOLVED via per-invocation engine) |
| ASP-OUT-023 | (Architect-filed; did not reach this session — routing gap noted per ASP-OUT-024) | 2026-04-19 | **CLOSED** | 2026-04-19 (superseded by ASP-OUT-024) |
| ASP-OUT-024 | Batch 1 rulings (§1–§5, incl. ChunkMetadata extra="forbid" comment) + Batch 2 authoring green light + loop-affinity lesson to ENGINEERING-PLAYBOOK + single consolidated doc-only commit directive | 2026-04-19 | **CLOSED** | 2026-04-19 (DEV-IN-024 milestone shipped commit afd0d2a; Batch 2 surfaced for review) |
| ASP-OUT-025 | Batch 2 review ruling (ACCEPTED with 3 verbatim-alignment notes) + Batch 3 (§11–§14) green light + I-RAG-05/06/07 post-acceptance sequencing | 2026-04-19 | **CLOSED** | 2026-04-19 (DEV-IN-025 milestone shipped commit b348951; Batch 3 surfaced for review) |
| ASP-OUT-026 | Batch 3 review ruling (ACCEPTED) + I-RAG-05/06/07 green light + AC-S3-02 verbatim wording | 2026-04-19 | **CLOSED** | 2026-04-19 (Commits E/F/G shipped 5cebcbf/81e07dd/223543c; AC-S3-02 verbatim confirmed) |
| ASP-OUT-027 | I-RAG-08 directive (26-AC verification suite tests/test_rag_v1.py; §8.2 write-time boundary rule; COMMS-LOG + 4-way sync) | 2026-04-19 | **CLOSED** | 2026-04-20 (DEV-IN-029 milestone — 26/26 AC PASS; Commit H shipped this entry) |
| ASP-OUT-028 | (Architect-filed; did not reach this session — routing gap noted per ASP-OUT-029) | 2026-04-20 | **CLOSED** | 2026-04-20 (superseded by ASP-OUT-029) |
| ASP-OUT-029 | Pending-work summary + single active directive clarification (all pending work contained in ASP-OUT-027: Commits H/I/J) | 2026-04-20 | **CLOSED** | 2026-04-20 (DEV-IN-029 milestone shipped — Commits H/I/J delivered as baf5a78/9064f93/f7d1cfa; ASP-02 + ASP-12 GOVERNED; ASP-NOTE-011 issued) |
| ASP-OUT-030 | ASP-02 v1.0 GOVERNED acknowledgement + single conftest.py cleanup directive (authed_client fixture migration 023 schema alignment) + next-queue summary | 2026-04-20 | **CLOSED** | 2026-04-20 (DEV-IN-030 shipped commit c27279b — 87 passed / 1 skipped / 0 failed; 61 previously-broken tests restored) |
| ASP-OUT-031 | Session-complete acknowledgement; ASP-OUT-030 closed; standing-by for next session | 2026-04-20 | **CLOSED** | 2026-04-20 (acknowledgement only; no Dev Team action) |
| ASP-OUT-033 | PAP-ASP-REQ-ASP-02 v1.0 inbound (MVP-3 integration; 2 services / 4 tasks); conditional acceptance pending PAP task-split confirmation | 2026-04-21 | **OPEN** | 2026-04-21 (awaiting PAP ack; no Dev Team build action — pre-assessment only in OUT-034) |
| ASP-OUT-034 | PAP-ASP-REQ-ASP-02 v1.0 pre-assessment directive — run three pre-write gates (migration number availability, VALID_TASKS state, payload field collisions) without writing any migration or implementation code | 2026-04-21 | **CLOSED** | 2026-04-21 (pre-assessment absorbed into ASP-OUT-036 build) |
| ASP-OUT-033 | PAP-ASP-REQ-ASP-02 v1.0 inbound (MVP-3 integration; 2 services / 4 tasks); conditional acceptance pending PAP task-split confirmation | 2026-04-21 | **CLOSED** | 2026-04-21 (PAP confirmed task-split; build green light issued at ASP-OUT-036) |
| ASP-OUT-035 | (Architect-filed; superseded by ASP-OUT-036 directive) | 2026-04-21 | **CLOSED** | 2026-04-21 (superseded) |
| ASP-OUT-036 | F-03-02 BUILD GREEN LIGHT — four tasks across NLP (extract_test_entities) + Generation (draft_steps, suggest_preconditions, propose_edge_cases); migrations 026 + 027; 16 ACs minimum; commit sequence A→B→C→D→E | 2026-04-21 | **CLOSED** | 2026-04-21 (confirmed clean per ASP-OUT-040; 16/16 AC PASS; 102 passed / 1 skipped; ASP-NOTE-012 issued) |
| ASP-OUT-037 | (Architect-filed; superseded by ASP-OUT-040 confirmation + defect-filing directive) | 2026-04-21 | **CLOSED** | 2026-04-21 (superseded) |
| ASP-OUT-040 | F-03-02 confirmation + ASP-DEFECT-023 filing directive (pre-existing test_ac19_cost_meter_resilience multi-module ordering flake — LOW, test-only) + standing-by for next-queue priority ordering | 2026-04-21 | **CLOSED** | 2026-04-21 (DEFECT-023 filed commit 3f208f7; standing-by period ended with ASP-OUT-041) |
| ASP-OUT-041 | ASP-FEAT-ASP-04 + ASP-13 Doc Intelligence demo pre-spec survey directive — run two parallel surveys (ASP-04 backend + ASP-13 dashboard) for the invoice-upload/classify/extract/review demo; report as single consolidated survey; no spec writing until review complete | 2026-04-21 | **CLOSED** | 2026-04-21 (survey accepted per ASP-OUT-042; all 11 gaps confirmed as spec input; DEV-IN-041 shipped commit cf09432) |
| ASP-OUT-042 | Survey rulings Q-1..Q-6 + DEFECT-024 filing + Batch 1 §1–§5 green light | 2026-04-21 | **HELD** | 2026-04-21 (DEFECT-024 filed 6f5711c; Batch 1 surfaced e0fc201; put on hold by ASP-OUT-045 P1) |
| ASP-OUT-045 | P1 — invoke path 500 on F-03-02 tasks; diagnostic sequence; stop-all-other-work | 2026-04-21 | **CLOSED** | 2026-04-21 (root cause located source-side: migrations 026/027 seeded prompt rows at caller_module='test_generator' only; PAP invoking from other caller → PromptNotFoundError → 500; superseded by ASP-OUT-051 fix ruling) |
| ASP-OUT-049 | (Architect-filed; superseded by ASP-OUT-051 ruling) | 2026-04-21 | **CLOSED** | 2026-04-21 (superseded) |
| ASP-OUT-046 | (Architect-filed during P1 window; superseded by ASP-OUT-053 close-out) | 2026-04-21 | **CLOSED** | 2026-04-21 |
| ASP-OUT-047 | ASP-FEAT-ASP-04 Batch 2 (§6–§10) authoring directive (queued during P1; active after ASP-OUT-053 resume) | 2026-04-21 | **CLOSED** | 2026-04-21 (resumed under ASP-OUT-053 — active work item until Batch 2 surfaced) |
| ASP-OUT-048 | (Architect-filed during P1 window; superseded by ASP-OUT-053 close-out) | 2026-04-21 | **CLOSED** | 2026-04-21 |
| ASP-OUT-050 | PAP notification of the P1 unblock — outbound; no Dev Team action beyond delivering fix | 2026-04-21 | **CLOSED** | 2026-04-21 (PAP notified; both Block 3 runs unblocked per Chief Architect PAP DEV-OUT-053) |
| ASP-OUT-051 | P1 FIX ruling — Option A wildcard rows in migration 028; expanded G-PROMPT-REACH; F-03-05 probe; round-trip; playbook + defect-register updates | 2026-04-21 | **CLOSED** | 2026-04-21 (P1 confirmed clean per ASP-OUT-053; migration 0028 shipped commit ce01e55; 20/20 reach + F-03-05 playwright_runner reach PASS) |
| ASP-OUT-052 | (Architect-filed PAP notification; superseded by ASP-OUT-053 close-out) | 2026-04-21 | **CLOSED** | 2026-04-21 |
| ASP-OUT-053 | P1 closed; ASP-OUT-042 resumes as ASP-04 Batch 2 active work item; refactor_script_locators maintenance note in SCHEMA-CURRENT (no migration, no defect); tests/README governed-probe-runner pointer | 2026-04-21 | **CLOSED** | 2026-04-21 (DEV-IN-053 shipped commits dc86c7e + 706deb3; Batch 2 surfaced for review) |
| ASP-OUT-054 | Batch 2 review ruling — ACCEPTED with four rulings + Batch 3 §11–§14 green light | 2026-04-21 | **CLOSED** | 2026-04-21 (Batch 3 shipped commit 40f578b; spec draft complete) |
| ASP-OUT-055 | Batch 3 accepted; §6.1 20MB→10MB OQ-2 correction mandate for I-DOC-05; IMPLEMENTATION GREEN LIGHT starting I-DOC-01 | 2026-04-21 | **CLOSED** | 2026-04-21 (DEV-IN-055 superseded by ASP-OUT-056 ruling which accepted the stop-and-report and authorised I-DOC-02..05; I-DOC-01 shipped commit e0a1244) |
| ASP-OUT-056 | I-DOC-01 ACCEPTED + DEFECT-024 RESOLVED + I-DOC-02..05 green light | 2026-04-21 | **CLOSED** | 2026-04-21 (milestone-1 report accepted per ASP-OUT-060; I-DOC-01..05 shipped commits ad4beac/e0a1244/dcaab73/2b55f60/07d29b1) |
| ASP-OUT-057 | (Architect-filed; routing mirror of ASP-OUT-056; not independently actioned) | 2026-04-21 | **CLOSED** | 2026-04-21 (absorbed into ASP-OUT-056) |
| ASP-OUT-058 | (Architect-filed; routing mirror of ASP-OUT-056; not independently actioned) | 2026-04-21 | **CLOSED** | 2026-04-21 (absorbed into ASP-OUT-056) |
| ASP-OUT-059 | DEV-IN-055 duplicate acknowledgement + third routing-gap log directive + "proceed per ASP-OUT-056" | 2026-04-21 | **CLOSED** | 2026-04-21 (milestone-1 report delivered + accepted per ASP-OUT-060; routing gap 3 logged in ASP-04 IMPL-LOG) |
| ASP-OUT-060 | Milestone 1 confirmed + python-multipart playbook addendum + I-DOC-06/07/10 green light | 2026-04-21 | **CLOSED** | 2026-04-21 (milestone-2 report delivered + accepted per ASP-OUT-061; Stream A+B shipped commit 9a0bbd1; playbook shipped 2cd77df) |
| ASP-OUT-061 | Milestone 2 confirmed + MinIO OQ-5 spec amendment + demo run-book + v1.1 candidate + I-DOC-11 + I-DOC-12 + .docx green light | 2026-04-21 | **CLOSED** | 2026-04-21 (32/32 PASS; spec + governance + .docx shipped; GOVERNED per ASP-OUT-063 ruling) |
| ASP-OUT-062 | (Architect-filed; PAP notification of ASP-FEAT-ASP-04 v1.0 GOVERNED) | 2026-04-21 | **CLOSED** | 2026-04-21 (outbound; no Dev Team action) |
| ASP-OUT-063 | Loop-affinity platform audit directive | 2026-04-21 | **CLOSED** | 2026-04-21 (audit accepted per ASP-OUT-064; DEFECT-025 CRITICAL filed then remediated in ASP-OUT-064) |
| ASP-OUT-064 | DEFECT-025 remediation + §12 playbook + DEFECT-023 fix | 2026-04-21 | **CLOSED** | 2026-04-21 (both defects RESOLVED per ASP-OUT-066; 9/9 PASS + 103 passed sweep; platform clean) |
| ASP-OUT-065 | Architect → PAP — F-03-03 service-naming correction + 1-working-day accept+build commitment | 2026-04-21 | **CLOSED** | 2026-04-22 (PAP v3.0 matched pre-prepared ASP-OUT-066 Task 2 draft; no schema delta; commitment met via commits 7ff2042/3f0e38e/a7f48c2/0bfb340; closed per ASP-OUT-074) |
| ASP-OUT-066 | Platform-clean acknowledgement + ASP-05 pre-spec survey (Task 1) + F-03-03 assess_test_quality prep (Task 2) — no implementation | 2026-04-21 | **CLOSED** | 2026-04-21 (prep draft used as authoritative build sequence per ASP-OUT-070 resend) |
| ASP-OUT-068 | (Architect-filed; routing gap — did not reach this session. Build sequence inferred from ASP-OUT-066 Task 2 prep draft per ASP-OUT-070 twice-sent confirmation) | 2026-04-21 | **CLOSED** | 2026-04-21 (superseded by ASP-OUT-070 explicit continue instruction) |
| ASP-OUT-069 | (Architect-filed; routing gap — did not reach this session) | 2026-04-21 | **CLOSED** | 2026-04-21 (superseded by ASP-OUT-070 confirmation) |
| ASP-OUT-070 | PAP F-03-03 authorisation confirmation — build sequence | 2026-04-21 | **CLOSED** | 2026-04-21 (Commits A/B/C/D shipped; 15/15 AC PASS; ASP-NOTE-014 issued; closed alongside DEV-IN-070 duplicate acknowledgement via ASP-OUT-073) |
| ASP-OUT-071 | (Architect-filed; PAP notification of F-03-03 BUILT — outbound; did not reach ASP session) | 2026-04-21 | **CLOSED** | 2026-04-21 (routing gap; no Dev Team action required) |
| ASP-OUT-072 | (Architect-filed; ASP-05 pre-spec survey directive with 8 enumerated items — did not reach ASP session) | 2026-04-21 | **CLOSED** | 2026-04-21 (routing gap; superseded by ASP-OUT-073 "proceed per ASP-OUT-072" confirmation — survey delivered via post-F-03-03 refresh of the existing 3d1bbec survey) |
| ASP-OUT-073 | DEV-IN-070 duplicate acknowledgement + fifth routing-gap log directive + proceed per ASP-OUT-072 | 2026-04-21 | **CLOSED** | 2026-04-22 (DEV-IN-073 survey refresh accepted per ASP-OUT-074; eight ASP-OUT-072 items confirmed covered by existing §1–§12; gap 5 logged) |
| ASP-OUT-074 | DEV-IN-073 confirmation + ASP-05 Batch 1 green light | 2026-04-22 | **OPEN** | 2026-04-22 (Batch 1 §1–§5 surfaced commit dbb4e53; awaiting review) |
| ASP-OUT-075 | URGENT dashboard login form + cookie-aware auth (demo unblock) | 2026-04-21 | **OPEN** | 2026-04-22 (login form shipped 6fe63de; server-side classify+extract kickoff + webhook-resilience wrap shipped in follow-up hot-fix — user-confirmed extraction PASS on live invoice: SADANAND DISA / 60,000 INR / 1 line item) |

Totals as of 2026-04-22: **2 OPEN** (ASP-OUT-074, ASP-OUT-075), **64 CLOSED**. **2 OPEN defects** (DEFECT-026 HIGH MODEL_ENHANCED 404; DEFECT-027 MEDIUM fire_webhook loop-affinity, mitigated).

---

## Open threads

### ASP-OUT-034 — PAP-ASP-REQ-ASP-02 v1.0 pre-assessment — OPEN

- **Filed:** 2026-04-21 by Principal Architect, ASP
- **Parallel to:** ASP-OUT-033 (PAP-ASP-REQ-ASP-02 v1.0 inbound; awaiting PAP task-split confirmation).
- **Scope:** Pre-write gate only. **No migration files or implementation code.** Gate results surfaced for Architect review; build blocked until PAP confirms task split AND Architect issues explicit green light.

**Directive recap:**

PAP-ASP-REQ-ASP-02 v1.0 proposes:
- **ASP-03 Generation** — 3 new tasks (`draft_steps`, `suggest_preconditions`, `propose_edge_cases`) sharing a `DraftTestContentPayload` (`screen_key`, `module_key`, `title`, `objective`, `category`, `priority`, `existing_steps: list[StepContext]`, `preconditions: list[str]`; `StepContext: {step_no, action, expected}`). Three result models: `DraftStepsResult`, `SuggestPreconditionsResult`, `ProposeEdgeCasesResult`.
- **ASP-02/ASP-01 NLP** — 1 new task (`extract_test_entities`) with `ExtractTestEntitiesPayload(text, context: TestEntityContext)` where `TestEntityContext: {screen_key, module_key, category}`. Result: `ExtractTestEntitiesResult(entities: TestEntities, confidence: float)` with `TestEntities: {required_fields, actions, validation_cases, success_outcomes}`.
- **Migrations:** 026 (ASP-03 three prompts) + 027 (NLP one prompt).
- **Quality tier:** `standard` (Haiku) for all four tasks.

> **Service-naming note for the record:** the Architect directive labels the NLP task as "ASP-02 (nlp)" — however, ASP-02 in the repo is the RAG service (just governed under ASP-FEAT-ASP-02 v1.0). NLP is ASP-01. I am **not** acting on this ambiguity; flagging it here so the Architect can confirm the target service in the build green-light directive. The build blueprint itself unambiguously targets the NLP service (`app/services/nlp.py`, `app/schemas/nlp_schemas.py`, VALID_TASKS set).

**Pre-write gate results:**

**Gate 1 — Migration number availability.** ✅ **PASS**
- Current migration head: `0025` (confirmed in-repo at `alembic/versions/` and live in DB via `alembic heads` + `alembic current` — both return `0025 (head)`).
- Numbers `0026` and `0027` both free — no files present at those revision IDs; no branching.

**Gate 2 — VALID_TASKS current state on both services.** ✅ **PASS** (no collisions; clean addition slots)

ASP-01 NLP (`app/services/nlp.py:37-45`) — current 7 tasks:
```
nl_to_sql, intent_extraction, entity_recognition, sentiment,
language_detection, classify_probe_result, suggest_screen_mapping
```
- `extract_test_entities` **absent** ✓ clean addition.

ASP-03 Generation (`app/services/generation.py:72-82`) — current 9 tasks:
```
draft_email, summarise_customer, generate_quote_narrative,
suggest_fields, draft_whatsapp, generate_test_cases,
generate_playwright_script, generate_test_cases_with_inventory,
refactor_script_locators
```
- `draft_steps`, `suggest_preconditions`, `propose_edge_cases` **all absent** ✓ three clean slots.

**Gate 3 — Payload field / class name conflicts.** ✅ **PASS with two naming-drift flags**

Class name scan — `DraftTestContentPayload`, `StepContext`, `DraftStepsResult`, `SuggestPreconditionsResult`, `ProposeEdgeCasesResult`, `ExtractTestEntitiesPayload`, `ExtractTestEntitiesResult`, `TestEntityContext`, `TestEntities`: **zero pre-existing definitions** repo-wide.

Field name re-use map (semantically compatible — no code collisions):

| Proposed field | Pre-existing use | Compatibility |
|---|---|---|
| `screen_key` | `GenerateTestCasesWithInventoryPayload.screen_key` (v1.1 CHG-06), `RefactorScriptLocatorsPayload.screen_key` (v2.0) | ✓ same semantic (caller-supplied page identifier) |
| `module_key` | `AvailableModule.module_key` + `suggested_module_key` (NLP BP-10) | ✓ same semantic |
| `category` | `TestCaseOutput.category: str = "Functional"` | ✓ same semantic |
| `preconditions` | `TestCaseOutput.preconditions: list[str]` | ✓ identical shape |
| `action` | `StepOutput.action: str` | ✓ same semantic |

**Naming-drift flags surfaced for Architect ruling before build begins:**

1. **`StepContext.step_no` vs existing `StepOutput.step_number`** — same semantic concept (ordinal step index), two different names. Options:
   - (a) Honour PAP's `step_no` verbatim — introduces intra-repo naming inconsistency.
   - (b) Map to existing `step_number` in the Pydantic model with a PAP-visible alias.
   - (c) Rename existing `StepOutput.step_number` → `step_no` (breaking change, out of scope).
   - **Recommend (a) with an inline comment.** Zero-risk path for PAP; documented drift is acceptable Zone 1 detail.

2. **`DraftTestContentPayload.priority: str` vs existing `TestCaseOutput.priority: Literal['Critical','High','Medium','Low']`** — PAP-filed `priority` is loose `str`; existing output model constrains to a four-value Literal. Options:
   - (a) Honour PAP's loose `str` on the payload — accept any incoming priority string; output path's Literal remains authoritative when the LLM emits new test cases.
   - (b) Tighten payload to the same Literal — rejects payloads with non-canonical priority. Stronger input validation; may surface PAP casing issues.
   - **Recommend (b) with `field_validator(mode='before')` normalising case** — mirrors the existing `normalise_priority` validator on `TestCaseOutput`. Consistent with ADR-008 `extra="forbid"` posture.

**Standing:** No migration files written. No handler code written. No Pydantic models added. No prompt rows seeded. Awaiting:
- PAP confirmation of task-split (blocks ASP-OUT-033 closure).
- Architect build green light (blocks ASP-OUT-034 transition to build execution).
- Architect rulings on naming-drift flags 1 and 2 (recommended paths noted).
- Architect clarification on the "ASP-02 (nlp)" vs "ASP-01 NLP" service-naming note.

**Cross-references:**
- `app/services/nlp.py` — NLP VALID_TASKS
- `app/services/generation.py` — Generation VALID_TASKS
- `app/schemas/nlp_schemas.py` — `AvailableModule`, `module_key` existing use
- `app/schemas/generation_schemas.py` — `screen_key` existing use
- `app/models/generation_outputs.py` — `StepOutput`, `TestCaseOutput` naming-drift references

---

### ASP-OUT-033 — PAP-ASP-REQ-ASP-02 v1.0 inbound conditional acceptance — OPEN

- **Filed:** 2026-04-21 by Principal Architect, ASP
- **Awaiting:** PAP confirmation of the four-task split (`draft_steps`, `suggest_preconditions`, `propose_edge_cases`, `extract_test_entities`).
- **Dev Team action:** none (thread is Architect↔PAP). Pre-assessment work is tracked under ASP-OUT-034.

---

### ASP-OUT-030 — ASP-02 v1.0 GOVERNED acknowledgement + conftest cleanup + next-queue — CLOSED 2026-04-20

- **Filed:** 2026-04-20 by Principal Architect, ASP
- **Supersedes:** ASP-OUT-029 (CLOSED — 0 open before this cleanup)
- **Subject:** Architect acknowledgement of ASP-FEAT-ASP-02 v1.0 governance closure (26/26 AC PASS; ASP-NOTE-011). Single outstanding cleanup: `tests/conftest.py` `authed_client` fixture alignment with migration 023 (`tenants.api_key_hash` column dropped; authoritative source is `tenant_api_keys` junction). Plus next-session governance queue for the 9 remaining ungoverned services (no action until priority order is confirmed).

**Cleanup applied this turn:**

- `tests/conftest.py` updated:
  - `test_api_key` now returns a new-format key `asp_<prefix12>_<secret32>` (ASP-FEAT-ASP-00 v1.0 §10 / ADR-032 mechanics; format validated by `app.utils.key_generator.is_new_format`).
  - `test_api_key_prefix` fixture added (12-char base36 prefix).
  - `mock_db_session` constructs a valid `Tenant` + `TenantApiKey` pair (no `api_key_hash=...` kwarg on Tenant). Session mock shaped for BOTH Gateway paths: `scalar_one_or_none()` for new-format fast path; `scalars().all()` for legacy-prefix fallback.
  - `session.get(Tenant, ...)` AsyncMock added to satisfy the Gateway's post-bcrypt tenant lookup.
  - Real auth path is preserved: negative-auth tests like `test_ac20_invalid_api_key_401` continue to exercise the wrong-key → 401 path correctly.

**Regression sweep (docker compose exec ai-service pytest):**

- `tests/test_rag_v1.py` (I-RAG-08)      26/26 PASS (1 skipped — AC-S1-03 host-only)
- `tests/test_nlp.py`                    37/37 PASS (was 0/N ERROR before fix)
- `tests/test_generation.py`             11/11 PASS
- `tests/test_generation_ac.py`          13/13 PASS

**Totals:** 87 passed, 1 skipped, 0 failed.

**Cross-references:**

- `tests/conftest.py` — fixture rewrite
- `app/models/db_models.py` — `Tenant` (migration 023 schema) + `TenantApiKey`
- `app/utils/key_generator.py` — new-format key template
- Gateway spec §10 / ADR-032 mechanics

**Next-queue (recorded for informational traceability — no action pending):**

9 ungoverned services in Architect-specified priority order:
1. ASP-04 Doc Intelligence (async, Celery, serves LogiCRM)
2. ASP-05 Prediction (async, Celery)
3. ASP-06 Prompt Registry (platform infra, all services depend on it)
4. ASP-07 Context Store (platform infra)
5. ASP-08 Cost Meter (platform infra, ADR-006 enforced)
6. ASP-09 Webhook Service (async delivery)
7. ASP-10 Cost Aggregator (DEFECT-022 resolved — ready to govern)
8. ASP-11 Model Router (ADR-017 governs)
9. ASP-13 Dashboard Intelligence

**No action until Product Leadership confirms priority for the next session.**

---

### ASP-OUT-029 — ASP-FEAT-ASP-02 v1.0 closing sequence (Commits H/I/J) — CLOSED 2026-04-20

- **Filed:** 2026-04-20 by Principal Architect, ASP
- **Supersedes:** ASP-OUT-027 (single active directive — all pending work contained in that ticket); ASP-OUT-028 (routing-gap placeholder, superseded)
- **Subject:** Three-commit close-out for ASP-FEAT-ASP-02 v1.0 — Commit H (I-RAG-08 AC suite), Commit I (I-RAG-09 governance sync), Commit J (I-RAG-10 .docx render).

**Scope recap from Architect directive (reference):**

1. **Commit H** — `tests/test_rag_v1.py` with 26 ACs across 9 phases; §8.2 write-time boundary rule sentence in spec; COMMS-LOG state transitions; 4-way sync. **STOP-ON-FIRST-FAILURE discipline.**
2. **Commit I** — ASP-SCHEMA-CURRENT.md + ASP-INDEX.md (ASP-02/ASP-12 → GOVERNED, governed count 4/14 → 6/14) + ASP-ADR.md (ADR-004 defence-in-depth annotation) + ASP-DEFECT-REGISTER.md (0 open confirmation) + 4-way sync.
3. **Commit J** — `.docx` render via the docx skill to `asp-projects/04-features/02-RAG/ASP-FEAT-ASP-02-v1_0.docx`.

**DEV-IN-029 milestone status (this turn — partial):**

- Commit H: **SHIPPED**. 26/26 ACs PASS (AC-S1-03 verified from host — `asp_chroma_data:/chroma/data` mounted on both `ai-service` and `celery-worker`; all other 25 ACs passed inside container via `pytest -x`). Spec §7.5 event table extended with `rag_retrieve_start`, `rag_chunks_returned`, `rag_upsert_failed`, `rag_chunk_metadata_validation_failed`. §8.2 write-time boundary rule sentence added.
- Commit I: pending this turn.
- Commit J: pending this turn.

**Nothing else pending** per Architect's ASP-OUT-029 clarification:
- DEFECT-022: RESOLVED (d158221)
- suggest_screen_mapping: LIVE (58c4232)
- Migration 024: GOVERNED (18ab7c6)
- Gateway spec: GOVERNED (f274be4)
- Open defects: 0
- Only open work is the RAG spec completion (this OUT-029).

**Cross-references:**

- `tests/test_rag_v1.py` — 26-AC suite
- `docs/spec-drafts/ASP-FEAT-ASP-02-v1_0.md` — §7.5 + §8.2 updates
- `app/services/rag.py` — +3 structlog events (rag_retrieve_start/returned/upsert_failed)

---

### ASP-OUT-025 — ASP-FEAT-ASP-02 Batch 2 acceptance + Batch 3 authoring — OPEN

- **Filed:** 2026-04-19 by Principal Architect, ASP
- **Supersedes:** ASP-OUT-024 (Batch 2 authoring directive; now CLOSED)
- **Subject:** Batch 2 ACCEPTED with three verbatim-alignment notes. Green light for Batch 3 (§11–§14) + post-acceptance implementation sequencing of S-4/S-5/S-6.

**Three notes applied this turn:**

1. **Note 1 — §6.1 Zone 1 permanence statement.** Paraphrase replaced with Architect's verbatim wording: *"The absence of RAG from `GET /api/v1/ai/capabilities` is correct and permanent per ADR-001. Any future TSCD proposing gateway exposure of RAG requires a Zone reclassification ADR before it can proceed."*
2. **Note 2 — §8.2 fail-open vs fail-closed distinction.** CONFIRMED PRESENT as originally authored. Both paths are explicitly named in the §8.2 table: fail-closed for `RAGCollectionMissingError` → 503, fail-open for empty retrieve result → NLP proceeds with empty `schema_context`. No amendment needed.
3. **Note 3 — §10.4 ADR-004 statement.** Verbatim Architect wording inserted as a governed statement block: *"`exclude_tables` enforcement at the ChromaDB metadata filter layer is the primary mechanism (ADR-004). The NLP prompt's `{exclude_tables}` placeholder is defence-in-depth only and must not be treated as the sole enforcement gate."*

**One-line confirmation:** All three notes now present verbatim in the spec as written.

**Batch 3 (§11–§14) authored this turn:**

- **§11 Implementation Checklist** — 10 items (I-RAG-01..10) with commit references for complete items and NOT YET markers for S-4/S-5/S-6/AC/sync/.docx items. Post-acceptance sequencing: I-RAG-05 → I-RAG-06 → I-RAG-07 → I-RAG-08 → I-RAG-09 → I-RAG-10, independent commits.
- **§12 Acceptance Criteria** — 26 ACs across 8 blocks (S-1 persistence 4, S-2 EF binding 4, S-3 metadata snapshot 2, S-4 Pydantic 3, S-5 tenant defence 3, S-6 fail-closed 3, S-7 beat 3, ADR-004 compliance 2, cross-cutting 2). 100 % pass required before GOVERNED.
- **§13 Open Questions** — 4 items, all deferred or closed: OQ-1 (ADR-035 fail-closed EF mismatch — DEFERRED), OQ-2 (HttpClient migration — DEFERRED to Atrium), OQ-3 (per-tenant EF — DEFERRED), OQ-RAG-CACHE-01 (CLOSED Option B 5-min TTL).
- **§14 Change Log** — G-1..G-10 gap matrix resolution table; Stream B commit chain listed; DEFECT-022 resolution noted; governance trail ASP-OUT-021..025; anticipated v1.1 candidates.

**Standing after this turn:**

- Spec draft complete (Batches 1+2+3) pending Architect review of §11–§14.
- No implementation this turn — S-4/S-5/S-6 remain spec-only.
- Awaiting Architect acceptance of Batch 3 to begin I-RAG-05 implementation.

**Cross-references:**

- `docs/spec-drafts/ASP-FEAT-ASP-02-v1_0.md` — full draft (§1–§14)
- `ENGINEERING-PLAYBOOK.md` §12 — loop-affinity pattern (applied AC-S7-02 coverage)
- `app/cost/aggregator.py` — DEFECT-022 reference implementation

---

### ASP-OUT-024 — ASP-FEAT-ASP-02 Batch 1 rulings + Batch 2 authoring + loop-affinity lesson — OPEN

- **Filed:** 2026-04-19 by Principal Architect, ASP
- **Supersedes:** ASP-OUT-021 (Batch 2 authoring directive), ASP-OUT-022 (Batch 1 authoring + DEFECT-022 asyncpg port), ASP-OUT-023 (routing-gap placeholder)
- **Subject:** Close-out of Batch 1 review + green light for Batch 2 §6–§10 authoring + process housekeeping.

**Architect rulings applied this turn:**

1. **§1–§4 Batch 1 ACCEPTED** as authored (scope, responsibilities, dependencies, config boundaries).
2. **§5 Data Models ACCEPTED with one clarifying comment** — `ChunkMetadata` retains `extra="forbid"`. Comment added above `model_config` line stating: *Zone 1 internal — extra="forbid" intentional. Drift between ASP-12 write contract and ASP-02 read contract must fail loudly.*
3. **Defence-in-depth tenant_id in `where=` filter ACCEPTED** — kept as primary isolation belt alongside ADR-004 metadata layer.
4. **RAGCollectionMissingError → 503 fail-closed ACCEPTED** — distinct from empty-retrieve fail-open.
5. **Batch 2 (§6 API Contract, §7 Request/Response Detail, §8 Caller Integration, §9 LLM/Prompt N/A, §10 Security) green-lit** — authored this turn.
6. **ENGINEERING-PLAYBOOK loop-affinity lesson directive** — asyncpg connections carry event loop affinity; use per-invocation `create_async_engine()` + `engine.dispose()` for Celery beat tasks using `asyncio.run()`. Verbatim text added under §12 Celery & Async Patterns.
7. **Commit discipline** — single consolidated doc-only commit at end of Batch 2 (this turn) covering: Batch 2 §6–§10, §5 ChunkMetadata comment, ENGINEERING-PLAYBOOK loop-affinity lesson, COMMS-LOG state transitions.
8. **No implementation** — S-4/S-5/S-6 items specified by Batch 2 remain spec-only until Batch 3 acceptance per governance discipline.

**DEV-IN-024 milestone status (this turn):**

- Batch 2 §6–§10 authored in `docs/spec-drafts/ASP-FEAT-ASP-02-v1_0.md`.
- §5 ChunkMetadata comment added per ruling 2.
- ENGINEERING-PLAYBOOK §12 updated per ruling 6.
- COMMS-LOG state transitions applied per ruling 7.
- 4-way sha256 governance sync pending this commit.
- Awaiting Architect review of Batch 2 before Batch 3 (§11–§14) authoring.

**Cross-references:**
- `docs/spec-drafts/ASP-FEAT-ASP-02-v1_0.md` — spec draft (Batch 1 + Batch 2)
- `ENGINEERING-PLAYBOOK.md` §12 — loop-affinity pattern
- `app/cost/aggregator.py` — governed per-invocation engine reference implementation
- `ASP-DEFECT-REGISTER.md` — DEFECT-022 RESOLVED (asyncpg port)

---

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

2026-04-18 23:45 IST — CLOSED ASP-OUT-012/013/014. Migration 024 applied + v2.0 Pydantic + v2.0 handler shipped. Critical regression surfaced and fixed mid-session (ASP-OUT-014 Option A — 4-level fallback chain in get_prompt_variant). PAP production path restored. All 11 Step 5 unit tests PASS.

2026-04-19 — CLOSED ASP-OUT-022 (Batch 1 ACCEPTED; DEFECT-022 RESOLVED via per-invocation asyncpg engine) and ASP-OUT-023 (routing-gap placeholder, superseded). OPENED ASP-OUT-024 (Batch 1 rulings §1–§5 + Batch 2 §6–§10 authoring + loop-affinity lesson to ENGINEERING-PLAYBOOK).

2026-04-19 (later) — CLOSED ASP-OUT-024 (commit afd0d2a shipped; Batch 2 surfaced for review). OPENED ASP-OUT-025 (Batch 2 ACCEPTED with 3 verbatim-alignment notes; Batch 3 §11–§14 authored; I-RAG-05/06/07 post-acceptance sequence).

2026-04-20 — CLOSED ASP-OUT-025 (commit b348951 shipped; Batch 3 surfaced). CLOSED ASP-OUT-026 (Batch 3 ACCEPTED; I-RAG-05/06/07 shipped 5cebcbf/81e07dd/223543c). CLOSED ASP-OUT-027 (I-RAG-08 AC suite 26/26 PASS; Commit H shipped). CLOSED ASP-OUT-028 (routing-gap placeholder). OPENED ASP-OUT-029 (RAG spec closing sequence — Commit H complete; Commits I/J in flight).

2026-04-20 (later) — CLOSED ASP-OUT-029 (Commits H/I/J shipped baf5a78/9064f93/f7d1cfa; ASP-02 + ASP-12 GOVERNED; ASP-NOTE-011 issued; 5/14 services governed). OPENED ASP-OUT-030 (GOVERNED acknowledgement + conftest.py migration 023 cleanup + next-queue summary).

2026-04-20 (session close) — CLOSED ASP-OUT-030 (c27279b shipped; 87 passed / 1 skipped; 61 previously-broken tests restored). CLOSED ASP-OUT-031 (session-complete acknowledgement; no Dev Team action). Session closed. Totals: 0 OPEN, 26 CLOSED.

2026-04-21 — OPENED ASP-OUT-033 (PAP-ASP-REQ-ASP-02 v1.0 inbound; conditional acceptance pending PAP task-split ack; Architect↔PAP thread; no Dev Team build action). OPENED ASP-OUT-034 (pre-assessment directive; three pre-write gates with stop-before-build rule). DEV-IN-034 milestone: Gate 1 (migration numbers 0026/0027 free) PASS; Gate 2 (no VALID_TASKS collision on either service) PASS; Gate 3 (zero class-name conflicts + field name reuse is semantically consistent) PASS with two naming-drift flags surfaced for Architect ruling (`step_no` vs `step_number`; `priority: str` vs `Literal`). Service-naming ambiguity flagged: directive says "ASP-02 (nlp)" but ASP-02 is the RAG service; NLP is ASP-01. No migration or handler code written. Totals: 2 OPEN (ASP-OUT-033, ASP-OUT-034), 27 CLOSED.
