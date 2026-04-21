# ASP-FEAT-ASP-04 v1.0 — Implementation Log

Rolling narrative log for the ASP-FEAT-ASP-04 v1.0 implementation
cycle. Complements `ASP-FEAT-ASP-04-v1_0.md` (the governed spec
draft) by recording per-commit narrative, surfaced issues, and
routing-protocol gaps.

---

## I-DOC-01 — DEFECT-024 fix (commit `e0a1244`)

Ported `app/services/doc_intelligence.py` off sync psycopg2 via the
DEFECT-022 playbook (per-invocation `create_async_engine` +
`engine.dispose()`). ADR-006 + ADR-010 fixes bundled (I-DOC-08 +
I-DOC-09) per §11 same-file-touch economy.

Three async helpers now own the DB-touching path:
`_async_update_job_status`, `_async_emit_cost`, `_async_fetch_prompt`.
Celery task drives each via `asyncio.run()`; no pool is reused across
`asyncio.run()` boundaries, honouring `ENGINEERING-PLAYBOOK.md` §12
loop-affinity rule.

**9-invocation stress test — AC-DOC-S1-01 PASS:**

```
[1/9] PASS  caller=crm                  task=extract_document
[2/9] PASS  caller=crm                  task=classify_document
[3/9] PASS  caller=playwright_runner    task=extract_document
[4/9] PASS  caller=crm                  task=classify_document
[5/9] PASS  caller=crm                  task=extract_document
[6/9] PASS  caller=playwright_runner    task=classify_document
[7/9] PASS  caller=crm                  task=extract_document
[8/9] PASS  caller=crm                  task=classify_document
[9/9] PASS  caller=playwright_runner    task=extract_document
RESULT: 9/9 PASS
```

One asyncpg-specific tightening surfaced during stress-test
bring-up: the initial `_async_update_job_status` used the same bind
param (`:status`) in both an SET-clause position and a CASE-expression
position, which triggered asyncpg's `AmbiguousParameterError`
("inconsistent types deduced for parameter $1"). Fix was to split
the UPDATE into a terminal-state branch and a non-terminal-state
branch, so each bind param is referenced in exactly one positional
context. Docstring documents the reason.

ADR-006 compliance: cost emission wrapped in `try/except` at the
Celery task boundary. Double-failure path (primary exception +
DB-error during failure-status update) also wrapped.

ADR-010 compliance: five transition events — `asp_doc_job_running`,
`_completed`, `_failed`, `asp_doc_cost_emission_failed`,
`asp_doc_job_status_update_failed`.

Cross-tenant `file_key` error upgraded from `HTTPException(400)` to
`HTTPException(403)` with RFC 7807 envelope per
ASP-FEAT-ASP-04 v1.0 §10.0 (ASP-OUT-054 Q-1 ruling). Minor tightening
bundled into the same touch to avoid a follow-up commit.

**Pre-I-DOC-10 confirmations (per ASP-OUT-055 ask):**

| Check | Result |
|---|---|
| OQ-1 `tesseract-ocr` in Dockerfile | ❌ not yet — bundled into I-DOC-07 commit per §13 OQ-1 |
| Jinja2 availability | ✅ 3.1.6 via FastAPI transitive |
| pdf.js CDN reachability | ✅ HTTP 200 HEAD from container |

---

## Routing gaps — protocol adherence log

Three routing-protocol gaps observed across the ASP governance cycle
to date. Logged here for traceability; the two prior entries live in
`ASP-FEAT-ASP-02-v1_0-IMPL-LOG.md` (ASP-02 spec cycle). This entry
captures the third.

### Gap 3 — DEV-IN-055 duplicate report (ASP-OUT-059, 2026-04-21)

**What happened.** After shipping I-DOC-01 (commit `e0a1244`, 9/9
stress test PASS) the ASP Dev Team produced DEV-IN-055 as the
stop-and-report milestone required by ASP-OUT-055. The Principal
Architect had already received the equivalent information and ruled
on it in ASP-OUT-056, which closed DEFECT-024 and authorised
I-DOC-02..05 to proceed. The duplicate DEV-IN-055 arrived at the
Architect AFTER ASP-OUT-056 was already OPEN — violating the
ASP-OUT-006 duplicate-prevention protocol (*"check ASP-COMMS-LOG
before forwarding; if already logged with a ruling, do not forward"*).

**Immediate remediation.** ASP-OUT-056 rulings stand. DEFECT-024 is
RESOLVED per the existing ruling. Active sequence continues at
I-DOC-02.

**Why it happened (Dev Team perspective).** ASP-OUT-056 was not
visible at the moment DEV-IN-055 was produced — the Architect's
ASP-OUT-056 ruling had not reached the ASP session by the time
DEV-IN-055 was sent. The COMMS-LOG pre-check that ASP-OUT-006
mandates would have caught the duplicate if ASP-OUT-056 had been
logged in the COMMS-LOG entries visible to the ASP session at that
moment. This is a session-synchronisation gap, not an intent-level
protocol violation — but the effect is the same.

**Tightening for future cycles.** Dev Team adherence has been to
check the COMMS-LOG before every outbound, which DID happen before
DEV-IN-055. The gap is that ASP-OUT-056 was not yet present in the
logged state available to the ASP session. This is a reinforcement
of the session-routing gap class previously observed at
ASP-OUT-023 / ASP-OUT-028 (gaps 1 and 2) — the remediation for
those gaps was COMMS-LOG placeholder entries marking them as
"Architect-filed; did not reach this session". Gap 3 is the inverse
direction — *Dev-team-side* outbound that races an *Architect-side*
OPEN not yet mirrored into the ASP session.

**No corrective commit beyond this entry.** The IMPL log captures
the gap. No code change, no COMMS-LOG rewrite — the duplicate and
its routing history are recorded and future cycles can reference
this entry if the pattern recurs.

### Gaps 1 and 2 — reference

Recorded in `ASP-FEAT-ASP-02-v1_0-IMPL-LOG.md` and
`ASP-COMMS-LOG.md` as:

- **Gap 1 (2026-04-18 19:30 IST / 20:10 IST)** — routing gaps during
  I-RAG-02 + Stream A sequence; consolidated entry in the ASP-02
  IMPL log.
- **Gap 2 (ASP-OUT-028, 2026-04-20)** — Architect-filed placeholder
  that did not reach the ASP session; superseded by ASP-OUT-029.

Gap 3 (this entry) is distinct in direction: Dev → Architect with a
duplicate, rather than Architect → Dev with a missing arrival.

---

*(Subsequent I-DOC-02..12 entries will append below as each commit
lands.)*
