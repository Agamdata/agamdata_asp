# ASP Defect Register

Last updated: 2026-04-16 | Total: 17 | Open: 0 | Mitigated: 1 | Resolved: 14 | Already Fixed: 2

## Summary

| ID | Title | Source | Domain | Severity | Status | Reporter | Filed |
|---|---|---|---|---|---|---|---|
| ASP-DEFECT-001 | PAP contract drift — with_inventory quality regression | CONSUMER | ASP-03 | CRITICAL | RESOLVED | PAP Team | 2026-04-10 |
| ASP-DEFECT-002 | Migration branch conflict — duplicate revision 0006 | ARCHITECT | INFRASTRUCTURE | CRITICAL | RESOLVED | Chief Architect | 2026-04-10 |
| ASP-DEFECT-003 | Volume-only prompt state — migrations 0006-0011 never committed | INTERNAL | INFRASTRUCTURE | CRITICAL | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-004 | Phantom migration 0016 — deep_dive OUTPUT CONTRACT | INTERNAL | ASP-03 | HIGH | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-005 | M-1 errata — spec said X-Api-Key, codebase uses X-ASP-API-Key | ARCHITECT | GOVERNANCE | LOW | RESOLVED | Chief Architect | 2026-04-10 |
| ASP-DEFECT-006 | Lambda in to_have_url() — invalid Playwright API in generated scripts | CONSUMER | ASP-03 | HIGH | RESOLVED (verified, e8e3896) | PAP Team | 2026-04-11 |
| ASP-DEFECT-007 | Unknown task names return generic 400 instead of supported task list | CONSUMER | ASP-03 | MEDIUM | ALREADY FIXED (asp-v2) | PAP Team | 2026-04-11 |
| ASP-DEFECT-008 | locator_source restricted to 2 values on generate_test_cases | CONSUMER | ASP-03 | MEDIUM | ALREADY FIXED (asp-v2) | PAP Team | 2026-04-11 |
| ASP-DEFECT-009 | Extra payload fields cause 422 on generate_test_cases | CONSUMER | ASP-03 | LOW | RESOLVED (serene-shtern) | PAP Team | 2026-04-11 |
| ASP-DEFECT-010 | API key rotation without consumer notification | CONSUMER | PROCESS | HIGH | OPEN | PAP Team | 2026-04-11 |
| ASP-DEFECT-011 | classify_probe_result task not available to PAP | CONSUMER | ASP-01 | BLOCKING | RESOLVED (asp-v2) | PAP Team | 2026-04-11 |
| ASP-DEFECT-012 | generate_test_cases_with_inventory latency 74-86s — outside ADR-018 envelope | INTERNAL | ASP-03 | HIGH | MITIGATED — pending Option 4 (async) | ASP Dev Team | 2026-04-15 |
| ASP-DEFECT-013 | TestCaseOutput.seed_data rejects LLM null — coerce to {} | INTERNAL | ASP-03 | LOW | RESOLVED (1c3d655) | ASP Dev Team | 2026-04-15 |
| ASP-DEFECT-016 | Anthropic 529 Overloaded surfaced to caller as 500 (no retry) | CONSUMER | ASP-03/ASP-00 | MEDIUM | RESOLVED | PAP Operations | 2026-04-16 |
| ASP-DEFECT-017 | generation_parse_failed at line 918 — max_tokens truncation | CONSUMER | ASP-03 | HIGH | RESOLVED | PAP Operations | 2026-04-16 |
| ASP-DEFECT-018 | StepOutput.locator rejects null — non-element steps fail validation | CONSUMER | ASP-03 | CRITICAL | RESOLVED | PAP Operations | 2026-04-16 |
| ASP-DEFECT-019 | LLM ignores test case count instruction — handler enforcement required | INTERNAL | ASP-03 | HIGH | RESOLVED (migration 022 + handler) | ASP Dev Team | 2026-04-16 |

---

## Defect Entries

### ASP-DEFECT-001 — PAP contract drift — with_inventory quality regression

- **ID:** ASP-DEFECT-001
- **Filed:** 2026-04-10
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-03
- **Severity:** CRITICAL
- **Status:** RESOLVED
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation (generate_test_cases_with_inventory)

**Description:**
PAP called `generate_test_cases_with_inventory` but received degraded output — snapshot-style fallback tests instead of structured inventory-referenced test cases. The reconstituted prompt from the `with_inventory` path was not available because migrations 0006-0011 (which seeded it) were never committed to git. When the serene-shtern containers were replaced by asp-v2 containers, the prompt row was lost.

**Reproducer:**
POST /api/v1/ai/invoke with `task=generate_test_cases_with_inventory`, `locator_inventory` populated. Response contained snapshot-style test cases without inventory locator references.

**Root cause:**
Three stacked governance failures (see ASP-NOTE-004): (1) migrations 0006-0011 never committed, (2) duplicate revision 0006 between branches, (3) phantom deep_dive migration referencing unimplemented task.

**Fix:**
ASP-NOTE-004 Phase 1: Extracted prompts from serene-shtern volume (commit c52be9c).
ASP-NOTE-004 Phase 2: Reconstituted prompt via migration 0016, healed chain (commit ae4ea51). Merged generation service code (commit f8d6c0e).

**Verification:**
Synthetic PAP call with structured inventory payload (4 elements: first_name, email, phone, submit). Response: 5 test cases (Critical, Negative, Validation, Accessibility, E2E), inventory locators used verbatim, `missing_locators` correctly populated with 6 dynamic elements. Structured path confirmed working — not snapshot fallback.

**Lessons / Prevention:**
ADR-027 (all prompts via committed migrations), ADR-029 (fresh-DB gate in CI). Added to ENGINEERING-PLAYBOOK.md common mistakes table.

**Timeline:**
- 2026-04-10: PAP reported quality regression
- 2026-04-10: ASP-NOTE-004 issued by Chief Architect
- 2026-04-10: Phase 1 archive complete (c52be9c)
- 2026-04-11: Phase 2 plan submitted and approved
- 2026-04-11: Phase 2 executed — migration chain reconciled, synthetic PAP call verified
- 2026-04-11: RESOLVED

---

### ASP-DEFECT-002 — Migration branch conflict — duplicate revision 0006

- **ID:** ASP-DEFECT-002
- **Filed:** 2026-04-10
- **Source:** ARCHITECT
- **Reporter:** Chief Architect
- **Domain:** INFRASTRUCTURE
- **Severity:** CRITICAL
- **Status:** RESOLVED
- **Affected consumers:** All (migration chain integrity)
- **Affected services:** All (Alembic chain)

**Description:**
Branch `claude/asp-v2` created migration 0006 (classify_probe_result) with `down_revision='0005'`. Branch `claude/serene-shtern` had a different set of migrations from 0006 onward (generation prompts). Merging would produce a multi-head Alembic state — a blocking defect.

**Reproducer:**
`alembic heads` would return two heads if both branches' migrations coexisted.

**Root cause:**
New branch (`claude/asp-v2`) was created from the base commit (`08a0199`) which only had migrations 0001-0005. The NLP governance work assigned the next available number (0006) without checking the serene-shtern branch's chain.

**Fix:**
ASP-NOTE-004 Phase 2: Renamed asp-v2's 0006 to 0017 (end of reconciled chain). Healed 0012's down_revision from 0011 to 0005.

**Verification:**
Fresh-DB: `alembic upgrade head` succeeds, `alembic heads` returns single head (0017), round-trip downgrade+upgrade clean.

**Lessons / Prevention:**
ADR-029 (fresh-DB gate). Always check all branches for migration head before assigning new revision numbers.

**Timeline:**
- 2026-04-10: Identified during deep dive investigation
- 2026-04-11: Fixed in Phase 2 (commit ae4ea51)
- 2026-04-11: RESOLVED

---

### ASP-DEFECT-003 — Volume-only prompt state — migrations 0006-0011 never committed

- **ID:** ASP-DEFECT-003
- **Filed:** 2026-04-10
- **Source:** INTERNAL
- **Reporter:** ASP Dev Team
- **Domain:** INFRASTRUCTURE
- **Severity:** CRITICAL
- **Status:** RESOLVED
- **Affected consumers:** PAP (generate_test_cases_with_inventory prompt lost on fresh DB)
- **Affected services:** ASP-03 Generation, ASP-06 Prompt Registry

**Description:**
Migrations 0006 through 0011 existed only in the running serene-shtern Docker PostgreSQL volume. They were never committed to git. When the serene-shtern containers were stopped and asp-v2 started with a fresh volume, 6 migrations worth of prompt seeds were lost. Production DB state was the only source of truth — a Critical governance violation.

**Reproducer:**
Fresh DB: `alembic upgrade head` skipped from 0005 to 0012. 0012's `down_revision='0011'` pointed to a phantom. Chain broken.

**Root cause:**
Development velocity during initial build phase prioritized running state over committed state. Prompts were iterated on via direct DB inserts or uncommitted migration files that existed only in the Docker build context.

**Fix:**
Phase 1: Extracted all 24 prompt rows from serene-shtern volume (commit c52be9c).
Phase 2: Reconstituted the critical `with_inventory` prompt via migration 0016. Healed 0012's down_revision. Skipped non-critical rows from 0006-0011 (already covered by 0012-0015).

**Verification:**
Post-reconciliation: `SELECT COUNT(*) FROM prompt_templates WHERE service_type='generation'` returns 12 (matches archive). All tasks callable via API.

**Lessons / Prevention:**
ADR-027 (all prompts via committed migrations — strengthens ADR-005). ADR-029 (fresh-DB CI gate would have caught this on first PR).

**Timeline:**
- 2026-04-10: Discovered during deep dive
- 2026-04-10: Phase 1 archive (c52be9c)
- 2026-04-11: Phase 2 reconstitution (ae4ea51)
- 2026-04-11: RESOLVED

---

### ASP-DEFECT-004 — Phantom migration 0016 — deep_dive OUTPUT CONTRACT

- **ID:** ASP-DEFECT-004
- **Filed:** 2026-04-10
- **Source:** INTERNAL
- **Reporter:** ASP Dev Team
- **Domain:** ASP-03
- **Severity:** HIGH
- **Status:** RESOLVED
- **Affected consumers:** None (migration was never applied)
- **Affected services:** ASP-03 Generation (aspirational)

**Description:**
Migration `0016_output_contract_deep_dive.py` was committed to the serene-shtern branch. It applied the OUTPUT CONTRACT to a `generate_test_cases_deep_dive` prompt row that did not exist. The migration's `upgrade()` raised `RuntimeError` if the row was absent. It was never applied (serene-shtern DB was at 0015). The task `generate_test_cases_deep_dive` had zero implementation: no handler, no payload model, no prompt row, zero cost_events.

**Reproducer:**
`alembic upgrade 0016` on serene-shtern DB would raise: `RuntimeError: 0016: prompt row for task='generate_test_cases_deep_dive' does not exist`.

**Root cause:**
Pre-written migration for unimplemented task. Violated the principle that migrations describe executed reality, not planned work.

**Fix:**
ASP-NOTE-004 ruling: delete phantom migration. File never existed in asp-v2 working tree — no git rm needed, just not cherry-picked.

**Verification:**
`ls alembic/versions/0016_output_contract_deep_dive.py` returns "No such file". New 0016 is the reconstitution migration.

**Lessons / Prevention:**
ADR-028 (migrations = executed reality, not planned work).

**Timeline:**
- 2026-04-10: Discovered during deep dive
- 2026-04-11: Confirmed phantom — never applied, never cherry-picked
- 2026-04-11: RESOLVED

---

### ASP-DEFECT-005 — M-1 errata — spec said X-Api-Key, codebase uses X-ASP-API-Key

- **ID:** ASP-DEFECT-005
- **Filed:** 2026-04-10
- **Source:** ARCHITECT
- **Reporter:** Chief Architect
- **Domain:** GOVERNANCE
- **Severity:** LOW
- **Status:** RESOLVED
- **Affected consumers:** None (codebase was never changed)
- **Affected services:** ASP-00 Gateway (auth.py)

**Description:**
ASP-FEAT-ASP-01 v1.2 spec Section 6.3 and AC-20 incorrectly stated the API key header as `X-Api-Key`. The codebase uses `X-ASP-API-Key` (FastAPI parameter `x_asp_api_key` in `app/gateway/auth.py:9`). The dev team's review finding M-1 contained a factual error about the header name, and the Architect accepted the amendment without codebase verification.

**Reproducer:**
N/A — the incorrect spec text was never implemented. Codebase was correct throughout.

**Root cause:**
Spec amendment from review finding was not independently verified against live codebase before acceptance.

**Fix:**
ASP-NOTE-002 errata section corrected the canonical header to `X-ASP-API-Key`. Recorded in ASP-INDEX naming quick-ref. Future rename classified as Type C breaking change per ASP-GOV-CONSUMPTION-002.

**Verification:**
`grep "x_asp_api_key" app/gateway/auth.py` confirms canonical header. No code change needed.

**Lessons / Prevention:**
Spec amendments from review findings must be independently verified against live codebase before acceptance.

**Timeline:**
- 2026-04-10: Identified during ASP-NOTE-002 AC review
- 2026-04-10: Corrected in errata section of ASP-NOTE-002
- 2026-04-10: RESOLVED

---

### ASP-DEFECT-006 — Lambda in to_have_url() — invalid Playwright API in generated scripts

- **ID:** ASP-DEFECT-006
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-03
- **Severity:** HIGH
- **Status:** OPEN
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation (`generate_playwright_script` task, Python output)

**Description:**
Generated Python Playwright scripts use `lambda` functions with `expect().to_have_url()` and `expect().to_have_text()`. Playwright's assertion API only accepts `string` or `re.Pattern` — not callables. Scripts crash at runtime with `playwright._impl._errors.Error: value must be a string or regular expression`.

**Example (broken):**
`expect(page).to_have_url(lambda url: "q=Playwright+testing" in url or "q=Playwright%20testing" in url)`

**Expected:**
`expect(page).to_have_url(re.compile(r"q=Playwright\+testing|q=Playwright%20testing"))`

**Root cause:**
Python Playwright script generation system prompt (migration 0013, `playwright_python_pytest_flat` variant) does not include a rule prohibiting `lambda` in assertion calls, and does not include `re.compile()` examples for partial URL matching.

**PAP workaround:**
Post-generation regex sanitizer in `backend/api/execution.py` — transforms lambda patterns to `re.compile()`.

**Fix (applied):**
Migration 0018 (`ban_lambda_in_playwright_python`) amends the python_playwright_pytest_flat prompt: lambda banned in expect() assertions, `import re` added to required imports, `re.compile()` example added, "no markdown fences" rule added. Folded into ASP-FEAT-ASP-03 v1.1. Verification deferred to AC-Lambda-01..03 in 29-AC suite.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- 2026-04-11: Folded into ASP-FEAT-ASP-03 v1.0/v1.1 as migration 0018
- 2026-04-11: Migration 0018 applied (commit 580dbe1)
- 2026-04-11: AC-Lambda-01..03 PASS (commit e8e3896, 32/32 suite)
- 2026-04-11: RESOLVED (verified) — per ASP-NOTE-005 Section 4 immediate flip
- 2026-04-11: PAP confirms downstream removal — execution.py regex sanitizer will be removed once Gate 8 integration test confirms lambda absence in generated scripts. Sanitizer was a band-aid for this exact prompt defect.

---

### ASP-DEFECT-007 — Unknown task names return generic 400 instead of supported task list

- **ID:** ASP-DEFECT-007
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-03
- **Severity:** MEDIUM
- **Status:** ALREADY FIXED on `claude/asp-v2`
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation

**Description:**
PAP reported that calling `task='generate_test_cases_with_inventory'` returned HTTP 400 with generic error. This occurred because the serene-shtern code was not merged into asp-v2 at the time of their test.

**Current state (post-merge f8d6c0e):**
`generate_test_cases_with_inventory` IS in `VALID_TASKS` and IS fully functional. Synthetic PAP call verified in Phase 2 Step 4 (5 test cases returned).

`generate_test_cases_deep_dive` is intentionally NOT implemented (ASP-NOTE-004 ruling: phantom task deleted). PAP should use `generate_test_cases_with_inventory` for verified-locator paths.

**Remaining enhancement (ADR-030):**
Error messages for unknown tasks should return the supported task list. Current: `"Unknown generation task: X"`. Better: `"Unknown task 'X'. Supported: ['generate_test_cases', 'generate_test_cases_with_inventory', ...]"`. This is tracked as ADR-030 (capability discovery endpoint).

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- 2026-04-11: ALREADY FIXED — `with_inventory` functional on asp-v2 post-merge. `deep_dive` intentionally absent per ruling.

---

### ASP-DEFECT-008 — locator_source restricted to 2 values on generate_test_cases

- **ID:** ASP-DEFECT-008
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-03
- **Severity:** MEDIUM
- **Status:** ALREADY FIXED on `claude/asp-v2`
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation

**Description:**
PAP reported that `generate_test_cases` only accepts `locator_source='snapshot'` or `'inferred'`, and cannot accept `'verified'`.

**Current state (post-merge f8d6c0e):**
This is by design — task-specific schemas:
- `generate_test_cases` → `Literal["snapshot", "inferred"]` (baseline, no verified locators)
- `generate_test_cases_with_inventory` → `Literal["verified"]` (verified-locator path)

PAP should use `task='generate_test_cases_with_inventory'` (not `generate_test_cases`) when they have verified locator data. This is the correct API — the task name controls the path, not the `locator_source` value on the wrong task.

**Communication to PAP:**
`locator_source='verified'` is accepted on the `generate_test_cases_with_inventory` task, which is now live. PAP's workaround (packing inventory into `snapshot_text` on the baseline task) can be removed.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- 2026-04-11: ALREADY FIXED — correct task is `generate_test_cases_with_inventory` which accepts `'verified'`

---

### ASP-DEFECT-009 — Extra payload fields cause 422 on generate_test_cases

- **ID:** ASP-DEFECT-009
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-03
- **Severity:** LOW
- **Status:** RESOLVED (serene-shtern code merged)
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation

**Description:**
PAP reported that extra payload fields (`locator_inventory`, `screen_key`, `engine_version`) cause HTTP 422 on `generate_test_cases`.

**Current state (post-merge f8d6c0e):**
The merged serene-shtern code already changed `GenerateTestCasesPayload` from `ConfigDict(extra="forbid")` to `ConfigDict(extra="ignore")`. Extra fields are silently dropped.

Verified in `app/models/request.py:68`:
```python
model_config = ConfigDict(extra="ignore")   # caller may send metadata fields; ignore unknown
```

Same applies to `GeneratePlaywrightScriptPayload` and `GenerateTestCasesWithInventoryPayload`.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- 2026-04-11: RESOLVED — already `extra="ignore"` on all generation payload models in merged code

---

### ASP-DEFECT-010 — API key rotation without consumer notification

- **ID:** ASP-DEFECT-010
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** PROCESS
- **Severity:** HIGH
- **Status:** OPEN
- **Affected consumers:** PAP (all consumers)
- **Affected services:** ASP-00 Gateway (auth)

**Description:**
PAP reported two key rotations during this sprint with no advance notification. Each caused a complete generation outage until PAP manually updated their `.env`.

**Root cause:**
Key rotation happened as a side-effect of DB volume destruction during ASP-NOTE-004 Phase 2 remediation. No formal key rotation SOP exists. No consumer notification process.

**PAP's requested fixes:**
(A) Notify PAP before key rotation with the new key.
(B) Support key overlap period — accept both old and new key for 24 hours.
(C) Provide a key management endpoint for proactive validation.

**Dev team assessment:**
- (A) is immediately implementable as a process change — no code needed.
- (B) requires multi-key support in auth.py (multiple active hashes per tenant). Moderate code change.
- (C) is tracked under ADR-030 (capability discovery endpoint).

**Proposed SOP (immediate):**
1. Before any DB volume destruction: document all active tenant keys.
2. After recreation: re-create tenants and notify consumers with new keys BEFORE they attempt calls.
3. Add to ENGINEERING-PLAYBOOK.md common mistakes table.

**Fix (longer term):**
Multi-key support or key overlap period requires ASP-00 Gateway governance spec (ASP-FEAT-ASP-00). Deferred to that spec.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- Status: OPEN — immediate SOP to be added to playbook; code-level fix deferred to ASP-00 spec

**Governance trail:** Principle locked as ADR-032 (ASP-FEAT-ASP-03 v1.1 cycle, 2026-04-11). Mechanics deferred to ASP-FEAT-ASP-00 v1.0 next sprint. Defect remains OPEN until ASP-00 spec implements multi-key support and notification SOP.

---

### ASP-DEFECT-011 — classify_probe_result task not available to PAP

- **ID:** ASP-DEFECT-011
- **Filed:** 2026-04-11
- **Source:** CONSUMER
- **Reporter:** PAP Team
- **Domain:** ASP-01
- **Severity:** BLOCKING (PAP F-02-13 Pass 2)
- **Status:** RESOLVED on `claude/asp-v2`
- **Affected consumers:** PAP
- **Affected services:** ASP-01 NLP Service

**Description:**
PAP reported `classify_probe_result` task not available. PAP F-02-13 (Behavioral Probe) requires this task for Pass 2. 4 ACs blocked.

**Current state (post-governance):**
`classify_probe_result` is IMPLEMENTED and GOVERNED (25/25 ACs PASS, ASP-NOTE-002). Migration 0017 seeds the prompt template. Handler in `app/services/nlp.py`. Pydantic schemas in `app/schemas/nlp_schemas.py`.

**Verification:**
```sql
SELECT COUNT(*) FROM prompt_templates WHERE task='classify_probe_result';
-- Result: 1
```
`VALID_TASKS` in nlp.py includes `classify_probe_result`. Handler `_handle_classify_probe_result()` fully implemented with payload validation, visible_text warning, prompt substitution, and extract_json() parsing.

**Communication to PAP:**
Task is live. PAP can begin F-02-13 Pass 2. Use `caller_module='playwright_runner'`, `quality_tier='standard'`. See ASP-FEAT-ASP-01 v1.2 Section 6.8 for full payload contract.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- 2026-04-11: RESOLVED — task is GOVERNED (ASP-NOTE-002), live on asp-v2

---

### ASP-DEFECT-012 — generate_test_cases_with_inventory latency 74-86s — outside ADR-018 envelope

- **ID:** ASP-DEFECT-012
- **Filed:** 2026-04-15
- **Source:** INTERNAL (discovered I-TSCD001-05, Finding F-01)
- **Reporter:** ASP Dev Team
- **Domain:** ASP-03
- **Severity:** HIGH
- **Status:** MITIGATED — pending Option 4 (async conversion)
- **Affected consumers:** PAP
- **Affected services:** ASP-03 Generation (generate_test_cases_with_inventory)

**Root cause:**
Task generates ~6,400 output tokens (5 test cases + Playwright scripts). At claude-sonnet-4-6 throughput, this is structurally 74-86s. The task was classified as synchronous (inheriting ASP-03 general profile) without measuring output volume. ADR-018 synchronous envelope (2-10s) was set against NLP-class calls, not generation-class calls of this volume.

**Measurements (post-migration 019, max_tokens=8192):**

| Call | Wall Time | Input Tokens | Output Tokens | Model |
|------|-----------|-------------|---------------|-------|
| 1/3 | 85.7s | ~1505 | ~6388 | claude-sonnet-4-6 |
| 2/3 | 74.2s | ~1505 | ~6388 | claude-sonnet-4-6 |
| 3/3 | 74.0s | ~1505 | ~6388 | claude-sonnet-4-6 |

**Immediate mitigation (applied):**
max_tokens reduced from 32,000 to 8,192 (ASP-TSCD-001 CHG-04). Does not change throughput; removes runaway ceiling. Gateway timeout increase to 120s pending PAP notification and acknowledgement.

**Temporary operating state:**
74-86s latency documented in ASP-FEAT-ASP-03 spec as known non-conformance. PAP operates with 120s HTTP client timeout (Gate 8 already demonstrated operation at this latency). ASP-GOV-CONSUMPTION-002 notification required.

**Short-term path:**
PAP A/B test at quality_tier=standard (Haiku). If quality acceptable, latency drops to ~15-25s. PAP-initiated, no ASP code change. (Option 2 — conditionally accepted by Principal Architect.)

**Long-term resolution (DEFECT closes here):**
Option 4 — async conversion of generate_test_cases_with_inventory. Requires PAP-ASP-REQ-ASP-03 v1.2. Type C change, 90-day deprecation. Scoped for future sprint. DEFECT-012 remains MITIGATED until GOVERNED.

**Mitigation options ruled by Principal Architect (2026-04-15):**

| Option | Verdict |
|---|---|
| 1 — Reduce output volume | REJECTED — insufficient improvement, adds PAP coordination for no envelope gain |
| 2 — Haiku A/B test | CONDITIONALLY ACCEPTED — PAP-initiated, quality validation required |
| 3 — Parallel generation | REJECTED — 5× cost amplification unjustifiable |
| 4 — Convert to async | ACCEPTED — long-term, formally queued. Type C change. |
| 5 — Accept + document | ACCEPTED with conditions — honest documentation, PAP notification, DEFECT not closed |

**PAP communication:** REQUIRED before Gateway timeout change goes to production. Zone 2 shared contract change per ASP-GOV-CONSUMPTION-002.

**Atrium-transition relevance:** AVOID — Atrium should classify generate_test_cases_equivalent as async from day one. Do not inherit ASP's synchronous misclassification.

**Timeline:**
- 2026-04-15: Filed from I-TSCD001-05 latency investigation
- 2026-04-15: 5 mitigation options submitted to Principal Architect
- 2026-04-15: Rulings received. Options 1,3 REJECTED. Options 2,4,5 ACCEPTED.
- 2026-04-15: Status → MITIGATED. Pending Option 4 (async conversion).

**Queued work item:**
```
QUEUED: generate_test_cases_with_inventory async conversion
Trigger: PAP files PAP-ASP-REQ-ASP-03 v1.2 requesting async pattern
Owner: ASP Dev Team (implementation); Chief Architect Atrium (TSCD authorship)
ADR: ADR-018 compliant resolution
Defect: DEFECT-012 closes when this is GOVERNED
Note: If PAP bundles with deep_dive (ADR-031 activation), scope as v2.0 not v1.2
```

---

### ASP-DEFECT-013 — TestCaseOutput.seed_data rejects LLM null — coerce to {}

- **ID:** ASP-DEFECT-013
- **Filed:** 2026-04-15
- **Source:** INTERNAL (discovered during TSCD-001 AC-T07 verification)
- **Reporter:** ASP Dev Team
- **Domain:** ASP-03
- **Severity:** LOW
- **Status:** RESOLVED (commit 1c3d655 — coerce_seed_data validator)
- **Affected consumers:** PAP (intermittent 500 on with_inventory calls)
- **Affected services:** ASP-03 Generation

**Description:**
`TestCaseOutput.seed_data` typed as `dict` with `Field(default_factory=dict)`. When the LLM explicitly returns `seed_data: null` (common for tag=unknown payloads or read-only pages), Pydantic rejected with `ValidationError: Input should be an object, input_value=None`. This caused intermittent 500s depending on LLM output variability.

**Root cause:**
`default_factory=dict` only applies when the field is absent from input. When the LLM explicitly includes `"seed_data": null`, Pydantic receives `None` as input and rejects it because the type is `dict`, not `dict | None`.

**Fix:**
1. Changed type to `dict | None = Field(default_factory=dict)`
2. Added `coerce_seed_data` field_validator: `None → {}`
Applied inline during TSCD-001 AC-T07 verification. No migration required.

**Atrium-transition relevance:** REPLICATE — Atrium generation response models should default all optional dict fields to `{}` rather than rejecting null LLM output.

**Timeline:**
- 2026-04-15: Discovered during AC-T07 (tag=unknown payload produced null seed_data)
- 2026-04-15: Fixed in commit 1c3d655 (coerce_seed_data validator)
- 2026-04-15: RESOLVED

---

### ASP-DEFECT-016 — Anthropic 529 Overloaded surfaced to caller as 500

- **ID:** ASP-DEFECT-016
- **Filed:** 2026-04-16
- **Source:** CONSUMER (PAP Operations, 18:03:45Z)
- **Domain:** ASP-03 / ASP-00 Gateway
- **Severity:** MEDIUM
- **Status:** RESOLVED

**Root cause:** ASP had zero retry logic for Anthropic 529 (Overloaded) responses. HTTP 529 is a documented transient Anthropic capacity condition. Instead of retrying with backoff and returning 502 when exhausted, ASP passed the error through as unhandled 500. PAP's retry logic was miscalibrated — they backed off from ASP when they should have retried.

**Fix:** Created `app/utils/llm_retry.py` — shared retry utility wrapping all Anthropic API calls. Pattern: 3 retries, exponential backoff [1s, 2s, 4s], retryable statuses: 529, 500, 502, 503, 504, connection errors. Non-retryable: 400, 401, 422 (fail immediately). On exhaustion: 502 with RFC 7807 detail. Applied to both `app/services/generation.py` and `app/services/nlp.py`.

**Atrium-transition relevance:** REPLICATE — platform-level concern in LLM client layer, not per-service.

**Timeline:**
- 2026-04-16: Filed from PAP Operations report
- 2026-04-16: Investigation confirmed zero 529 handling in codebase
- 2026-04-16: Shared llm_retry.py utility created, both services updated
- 2026-04-16: RESOLVED — 58/58 regression PASS

---

### ASP-DEFECT-017 — generation_parse_failed at line 918 — max_tokens truncation

- **ID:** ASP-DEFECT-017
- **Filed:** 2026-04-16
- **Source:** CONSUMER (PAP Operations, 18:19:49Z)
- **Domain:** ASP-03
- **Severity:** HIGH
- **Status:** RESOLVED

**Root cause:** LLM output for complex inventory (GitHub homepage, 8+ elements) produced 30,532 chars (~8,000+ tokens), hitting the 8,192 max_tokens ceiling. Output was truncated mid-JSON at line 918 (139 open braces, 136 close braces — 3 unclosed). The truncation guard specified in TSCD-001 CHG-04 was NOT implemented — the code had only the generic `generation_parse_failed` log with no distinction between truncation and organic parse errors.

**Fix (two parts):**
1. **Truncation guard implemented:** Checks `response.stop_reason == 'max_tokens'` before attempting JSON parse. Logs `generation_truncated` (distinct from `generation_parse_failed`) with max_tokens and raw_length. Returns 500 with explicit "Generation output exceeded token limit" detail.
2. **max_tokens raised:** 8,192 → 12,288 for `generate_test_cases_with_inventory`. The 8,192 ceiling was calibrated from Phase 2 (6,428 tokens) but complex inventories exceed it. 12,288 covers observed 8,000+ token outputs with headroom.

**Connection to DEFECT-012:** Further evidence that complex generation calls need async conversion. Truncation risk + latency together make synchronous untenable for complex assets.

**Atrium-transition relevance:** REPLICATE — distinguish truncation from organic parse errors as separate structlog events with different responses.

**Timeline:**
- 2026-04-16: Filed from PAP Operations report (18:19:49Z failure)
- 2026-04-16: Investigation confirmed truncation (30,532 chars, 139 vs 136 braces)
- 2026-04-16: Truncation guard + max_tokens=12288 implemented
- 2026-04-16: RESOLVED — 58/58 regression PASS

---

### ASP-DEFECT-018 — StepOutput.locator rejects null — non-element steps fail validation

- **ID:** ASP-DEFECT-018
- **Filed:** 2026-04-16
- **Source:** CONSUMER (PAP Operations OPS-004)
- **Domain:** ASP-03
- **Severity:** CRITICAL (blocks all test generation)
- **Status:** RESOLVED

**Root cause:** `StepOutput.locator` typed as `str` (non-nullable) in the v3 schema changes (migration 020). LLM correctly returns `null` for navigate/assert/wait steps that have no element locator. Pydantic rejected with `Input should be a valid string, input_value=None`. Migration 020 prompt schema did not specify null as valid for non-element steps. AC suite lacked null-locator test coverage.

**Fix:** Changed `locator: str = ""` to `locator: Optional[str] = None` in `StepOutput`. Also fixed `description: str = ""` to `description: Optional[str] = None` for the same reason.

**Additional fix found during investigation:** Migration 019 inserted the `*` row without `ab_variant='inventory'`. The handler resolves via `get_prompt_variant(ab_variant="inventory")` which couldn't find the `*` row, falling back to the L2/v1 row. Fixed by setting `ab_variant='inventory'` on the `*` row. Migration 020 updated to include `ab_variant='inventory'` in the SET clause.

**Prevention:** Add null-locator ACs to permanent regression suite.

**Atrium-transition relevance:** REPLICATE — all step/action schemas must allow null locators for non-element actions from day one.

**Timeline:**
- 2026-04-16: Filed from PAP Operations OPS-004
- 2026-04-16: Schema fix applied (Optional[str] = None)
- 2026-04-16: ab_variant mismatch discovered and fixed
- 2026-04-16: RESOLVED

---

### ASP-DEFECT-019 — LLM ignores test case count instruction — handler enforcement required

- **ID:** ASP-DEFECT-019
- **Filed:** 2026-04-16
- **Source:** INTERNAL (AC-020-02 verification failure)
- **Domain:** ASP-03
- **Severity:** HIGH
- **Status:** RESOLVED (migration 022 + handler enforcement, commit 141b34f)

**Root cause:** LLM (Sonnet) does not reliably follow count instructions regardless of placement or framing. Tested: user prompt variable (v3 migration 020), system prompt hard-constraint (migration 021), system prompt schema-violation framing (migration 021). All three approaches produced 5 test cases when "EXACTLY ONE" was specified.

**Investigation sequence:**
1. Migration 020: `{generation_instructions}` in user prompt → 5 TCs (FAIL)
2. Migration 021: Rule 3 hard-constraint framing in system prompt → 5 TCs (FAIL)
3. max_tokens=800: Truncated mid-JSON, `repair_json()` couldn't recover (FAIL)
4. max_tokens=2048: Still truncated mid-JSON at 7,657 chars (FAIL)

**Principal Architect ruling:** "The fix is not stronger wording. LLM count instructions are unreliable. Count enforcement moves to handler post-processing."

**Fix (migration 022 + handler):**
- Migration 022: Rule 3 reverted to neutral wording. Prompt guides, doesn't enforce.
- `_enforce_test_case_count()`: F-03-04 → truncate to 1 TC post-parse. Logs `test_case_count_truncated`.
- max_tokens stays at 12,288 for all modes. Per-mode cap abandoned (truncated JSON unparseable).

**Atrium-transition relevance:** REPLICATE — never rely on LLM instructions for count enforcement. Always use handler post-processing for output count constraints.

**Timeline:**
- 2026-04-16: AC-020-02 failed (5 TCs instead of 1)
- 2026-04-16: Migration 021 (system prompt hard-constraint) — still failed
- 2026-04-16: max_tokens caps tested (800, 2048) — truncated JSON unparseable
- 2026-04-16: Principal Architect ruling: handler enforcement
- 2026-04-16: Migration 022 + handler _enforce_test_case_count()
- 2026-04-16: AC-020-02 PASS (1 TC), AC-TRUNC-01 PASS (truncation logged)
- 2026-04-16: RESOLVED
