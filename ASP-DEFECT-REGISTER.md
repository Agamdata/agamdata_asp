# ASP Defect Register

Last updated: 2026-04-11 | Total: 5 | Open: 0 | Resolved: 5

## Summary

| ID | Title | Source | Domain | Severity | Status | Reporter | Filed |
|---|---|---|---|---|---|---|---|
| ASP-DEFECT-001 | PAP contract drift — with_inventory quality regression | CONSUMER | ASP-03 | CRITICAL | RESOLVED | PAP Team | 2026-04-10 |
| ASP-DEFECT-002 | Migration branch conflict — duplicate revision 0006 | ARCHITECT | INFRASTRUCTURE | CRITICAL | RESOLVED | Chief Architect | 2026-04-10 |
| ASP-DEFECT-003 | Volume-only prompt state — migrations 0006-0011 never committed | INTERNAL | INFRASTRUCTURE | CRITICAL | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-004 | Phantom migration 0016 — deep_dive OUTPUT CONTRACT | INTERNAL | ASP-03 | HIGH | RESOLVED | ASP Dev Team | 2026-04-10 |
| ASP-DEFECT-005 | M-1 errata — spec said X-Api-Key, codebase uses X-ASP-API-Key | ARCHITECT | GOVERNANCE | LOW | RESOLVED | Chief Architect | 2026-04-10 |

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
