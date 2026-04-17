# ASP-FEAT-ASP-00 v1.0 — Implementation Log

Chronological record of spec-narrative corrections, implementation rulings, and
phase-gate decisions made during implementation of ASP-FEAT-ASP-00 v1.0.
Entries are appended only. This log will be consolidated into the final
AC-VERIFICATION report at GOVERNED declaration.

---

## 2026-04-17 · Phase 1 — spec narrative correction (49-char key length)

**Context.** §10 "Key format and generation" S-1 bullet and §11 I-03 bullet
previously stated the new API key format is 50 characters. The canonical
regex `^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$` describes a 49-character string
(3-char scheme + `_` + 12-char prefix + `_` + 32-char secret = 49). Unit test
for I-03 caught the inconsistency when `assert len(raw_key) == 50` failed.

**Ruling (Chief Architect, Option A, 2026-04-17).** Regex is the governed
surface; correct the prose, not the code. Two occurrences of "50" replaced
with "49" in `docs/spec-drafts/ASP-FEAT-ASP-00-v1_0.md`. No code change.
No AC change. The .docx will be re-rendered before GOVERNED declaration.

**Status.** CLOSED.

## 2026-04-17 · Phase 1 — pre-auth `request_id=null` is expected behaviour

**Context.** RFC 7807 envelope includes `request_id` on every error response.
The Gateway router allocates `request_id` **after** auth succeeds; a 401 on
an invalid or missing API key therefore has no correlation ID available in
`request.state`.

**Ruling (Chief Architect, 2026-04-17).** This is expected and correct.
Pre-auth errors legitimately emit `request_id: null`. Post-auth errors (any
path where the router set `request.state.request_id`) emit the correlation
ID matching the `X-Request-Id` response header. AC-S5-05 verifies the null
case; AC-S5-04 verifies the populated case.

**Status.** CLOSED — noted in §11 I-RFC7807 handler docstring. No spec text
change required; the behaviour is already captured in AC-S5-05.

## 2026-04-17 · Phase 1 — test isolation note

**Context.** First-pass unit test for the RFC 7807 handler reused a shared
`scope` dict across successive `Request(scope)` constructions. Starlette's
`Request.state` mutates `scope['state']` by reference, so a second Request
from a shallow-copied scope saw the first Request's `request_id`. The test
incorrectly failed the pre-auth-null assertion.

**Resolution.** Fixed the test to construct a fresh `scope` dict per Request.
Production code unaffected — each real HTTP request has its own ASGI scope.

**Status.** CLOSED — test-only bug.
