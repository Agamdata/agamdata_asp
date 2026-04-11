# ASP Defect Register

Last updated: 2026-04-11 | Total: 11 | Open: 2 | Resolved: 7 | Already Fixed: 2

## Summary

| ID | Title | Source | Domain | Severity | Status | Reporter | Filed |
|---|---|---|---|---|---|---|---|
| ASP-DEFECT-001 | PAP contract drift — with_inventory quality regression | CONSUMER | ASP-03 | CRITICAL | RESOLVED | PAP Team | 2026-04-10 |
| ASP-DEFECT-002 | Migration branch conflict — duplicate revision 0006 | ARCHITECT | INFRASTRUCTURE | CRITICAL | RESOLVED | Chief Architect | 2026-04-10 |
| ASP-DEFECT-003 | Volume-only prompt state — migrations 0006-0011 never committed | INTERNAL | INFRASTRUCTURE | CRITICAL | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-004 | Phantom migration 0016 — deep_dive OUTPUT CONTRACT | INTERNAL | ASP-03 | HIGH | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-005 | M-1 errata — spec said X-Api-Key, codebase uses X-ASP-API-Key | ARCHITECT | GOVERNANCE | LOW | RESOLVED | Chief Architect | 2026-04-10 |
| ASP-DEFECT-006 | Lambda in to_have_url() — invalid Playwright API in generated scripts | CONSUMER | ASP-03 | HIGH | OPEN | PAP Team | 2026-04-11 |
| ASP-DEFECT-007 | Unknown task names return generic 400 instead of supported task list | CONSUMER | ASP-03 | MEDIUM | ALREADY FIXED (asp-v2) | PAP Team | 2026-04-11 |
| ASP-DEFECT-008 | locator_source restricted to 2 values on generate_test_cases | CONSUMER | ASP-03 | MEDIUM | ALREADY FIXED (asp-v2) | PAP Team | 2026-04-11 |
| ASP-DEFECT-009 | Extra payload fields cause 422 on generate_test_cases | CONSUMER | ASP-03 | LOW | RESOLVED (serene-shtern) | PAP Team | 2026-04-11 |
| ASP-DEFECT-010 | API key rotation without consumer notification | CONSUMER | PROCESS | HIGH | OPEN | PAP Team | 2026-04-11 |
| ASP-DEFECT-011 | classify_probe_result task not available to PAP | CONSUMER | ASP-01 | BLOCKING | RESOLVED (asp-v2) | PAP Team | 2026-04-11 |

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

**Fix (pending):**
Update system prompt for Python Playwright flat variant to add:
1. Rule: "NEVER use lambda in expect() assertions. Use re.compile() for partial matching."
2. Example: `expect(page).to_have_url(re.compile(r"q=Playwright"))` 
3. Add `import re` to required imports list.

Requires new migration to patch the prompt. Classified as prompt-level fix — no code change needed.

**Timeline:**
- 2026-04-11: Filed from PAP defect report
- Status: OPEN — awaiting ASP-03 governance spec (ASP-FEAT-ASP-03)

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
