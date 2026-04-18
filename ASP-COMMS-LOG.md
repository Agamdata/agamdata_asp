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
| ASP-OUT-003 | `suggest_screen_mapping` lead time (PAP W-5 blocker) | 2026-04-18 | **OPEN** | 2026-04-18 18:47 IST |
| ASP-OUT-004 | PAP-ASP-REQ-ASP-03 v2.0 acceptance (form_data amendment + coverage-aware scope) | 2026-04-17 | **CLOSED** | 2026-04-18 |
| ASP-OUT-006 | Communication protocol update — milestone-only reporting + MSG-ID tagging + COMMS-LOG pre-check | 2026-04-18 | **CLOSED** (ACCEPTED, effective immediately) | 2026-04-18 20:30 IST |

Totals as of 2026-04-18 20:30 IST: **1 OPEN** (ASP-OUT-003), **2 CLOSED** (ASP-OUT-004, ASP-OUT-006).

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

2026-04-18 20:30 IST — added ASP-OUT-006 protocol update (CLOSED/ACCEPTED). Totals: 1 OPEN (ASP-OUT-003), 2 CLOSED (ASP-OUT-004, ASP-OUT-006).
