# F-03-03 `assess_test_quality` — Pre-build Draft

| Field | Value |
|---|---|
| Feature ID | F-03-03 (Coverage Review) |
| Target service | **ASP-03 Generation** (corrected from PAP's original mis-filing against ASP-12 per ASP-OUT-065) |
| New task | `assess_test_quality` |
| Task classification | Type B additive to an already-GOVERNED service (ASP-03 v2.0) |
| Status | **DRAFT — no implementation. Prepared in advance per ASP-OUT-066 Task 2.** |
| Trigger | PAP files PAP-ASP-REQ-ASP-03 v3.0. On file → accept + build within 1 working day per ASP-OUT-065 commitment. |
| Author | ASP Dev Team |
| Date | 2026-04-21 |

This is a **preparation document**. Finalisation awaits PAP's v3.0
filing — the Pydantic payload/result shapes below are the
directive-quoted ASP-OUT-066 Task 2 draft; minor field-name or
typing adjustments may arrive with PAP's schema confirmation.

---

## 1. Pre-write gate

| Check | Value |
|---|---|
| Current migration head | `0029` (alembic current confirmed) |
| **Migration 0030** slot availability | **FREE** (`ls alembic/versions/` tail: `0029_...`). |
| **Migration 0031** slot availability | FREE (reserved as fallback if ASP-05 pre-spec-cycle migration lands first and takes 0030 per ASP-FEAT-ASP-05 v1.0 OQ-05-4). |
| `assess_test_quality` in ASP-03 `VALID_TASKS` | **ABSENT** (clean addition slot). Current ASP-03 task set has 12 entries; assess_test_quality would be #13. |
| `TestQualityAssessmentPayload` class name collision | **NONE** (grep repo-wide: zero matches). |
| `TestQualityAssessmentResult` class name collision | **NONE** (grep repo-wide: zero matches). |
| Existing `StepContext` in `app/schemas/generation_schemas.py` | **PRESENT** — governed under F-03-02 (ASP-OUT-036). Reusable here. |
| G-PROMPT-REACH strategy | Seed at `caller_module='*'`, `maturity_level='*'` following the F-03-02 post-fix pattern (single wildcard row reachable from every caller × maturity). 6-probe matrix at migration time per the expanded playbook rule. |
| Loop-affinity pre-spec check (per ASP-OUT-064) | N/A — `generate_*` handlers in ASP-03 are synchronous (not async Celery tasks). No `asyncio.run()` path, no shared-pool risk. |

---

## 2. Draft Pydantic models (ASP-OUT-066 Task 2 verbatim)

**Location on file:** `app/schemas/generation_schemas.py` (new models appended to the existing F-03-02 block). `StepContext` reused from that block — no redefinition.

```python
# app/schemas/generation_schemas.py — APPEND at end, under F-03-02 block

class TestQualityAssessmentPayload(BaseModel):
    """F-03-03 / PAP-ASP-REQ-ASP-03 v3.0 Coverage Review input.

    Shape per ASP-OUT-066 Task 2 draft. Directive-quoted field list;
    final types/names confirmed on PAP v3.0 filing.
    """
    model_config = ConfigDict(extra="ignore")
    screen_key:      str
    module_key:      str
    title:           str
    objective:       str
    category:        str
    priority:        str
    steps:           List[StepContext]      # reused from F-03-02 block
    preconditions:   List[str] = []
    expected_result: str


class TestQualityAssessmentResult(BaseModel):
    """Five dimension scores (0.0–1.0) + weighted overall + actionable
    suggestions list. Per ASP-OUT-066 Task 2 draft."""
    model_config = ConfigDict(extra="ignore")
    step_count_adequacy:       float
    precondition_completeness: float
    assertion_coverage:        float
    edge_case_presence:        float
    overall_quality_score:     float
    suggestions:               List[str] = []
```

**Notes on the shape as drafted**

- **Five dimension scores + overall_quality_score.** The prompt's STRICT RULE 2 says overall is the weighted mean of the FOUR dimensions (step_count_adequacy, precondition_completeness, assertion_coverage, edge_case_presence). The Pydantic model does not enforce this arithmetic relationship — a handler post-check (warning-only) could verify; not required for governance. Flag to Architect at spec-write if stricter enforcement is desired.
- **`suggestions: list[str] = []`** — empty list allowed if the test is already high-quality. The prompt's "2-5 items" rule is advisory; the model does not enforce a min-length.
- **`steps: List[StepContext]` is non-optional and has no default** (contra F-03-02's `existing_steps: list[StepContext] = []`). Rationale: a test with zero steps has nothing to assess; a missing `steps` field is a valid 422 on the payload. Worth confirming against PAP's v3.0 schema — they may want `steps` to default to `[]` for partial-asset assessment.
- **`extra="ignore"`** on both models per ADR-033 (generation service convention).

---

## 3. Draft system prompt (ASP-OUT-066 Task 2 verbatim)

**Migration seed body** — to land in migration 0030 (or 0031 if ASP-05 migration lands first):

```
You are a test quality assessor. Given a test asset, evaluate its
quality across five dimensions.

STRICT RULES:
1. All scores are 0.0 to 1.0.
2. overall_quality_score is the weighted mean of the four
   dimension scores.
3. suggestions are actionable improvements (2-5 items).
4. Return ONLY valid JSON.

Output schema:
{
  "step_count_adequacy":       float,
  "precondition_completeness": float,
  "assertion_coverage":        float,
  "edge_case_presence":        float,
  "overall_quality_score":     float,
  "suggestions":               [str]
}
```

**User prompt template** (Jinja-free `str.format` style, consistent with the F-03-02 prompt patterns):

```
Screen: {screen_key} / Module: {module_key}
Category: {category} | Priority: {priority}

Title: {title}
Objective: {objective}

Steps:
{steps}

Preconditions (may be empty):
{preconditions}

Expected result:
{expected_result}

Assess the quality of this test asset per the output schema.
```

Handler pre-render: `steps` and `preconditions` rendered as indented JSON (same convention as the three F-03-02 tasks in `app/services/generation.py::handle()` — `elif task in ("draft_steps", "suggest_preconditions", "propose_edge_cases"):`).

---

## 4. Planned implementation skeleton (for rapid deployment when PAP files)

When PAP-ASP-REQ-ASP-03 v3.0 is filed and accepted, the following six
touches ship as a single commit or tight sequence:

1. **`app/schemas/generation_schemas.py`** — append `TestQualityAssessmentPayload` + `TestQualityAssessmentResult`. Reuse `StepContext` from the F-03-02 block.
2. **`app/services/generation.py`:**
   - `VALID_TASKS` → add `"assess_test_quality"`.
   - `TASK_OUTPUT_SCHEMAS` → add `TestQualityAssessmentResult`.
   - `TASK_PAYLOAD_VALIDATORS` → add `TestQualityAssessmentPayload`.
   - `TASK_MAX_TOKENS` → add `2048` (suggestions list is short; five floats are negligible).
   - Message-build branch — extend the existing F-03-02 `elif task in (...)` block to include `"assess_test_quality"`; add `expected_result` to the placeholder set.
3. **`app/api/capabilities.py`** — add `("generation", "assess_test_quality") → TestQualityAssessmentPayload` to `TASK_SCHEMA_MODELS`.
4. **Migration 0030** (or 0031) — one `INSERT` per the F-03-02 pattern (`service_type='generation'`, `caller_module='*'`, `maturity_level='*'`, `version=1`, `is_active=TRUE`, `ab_variant=NULL`).
5. **AC suite** — `tests/test_f0303.py` with at minimum:
   - Valid payload → 200, all five dimension scores + overall in [0.0, 1.0] bounds.
   - overall_quality_score weighted-mean consistency (warn-only in Pydantic; tight assertion in AC).
   - suggestions list 2-5 items (AC-level assertion; LLM drift tolerated via AC wording).
   - Empty preconditions list → 200, no validation error.
   - Missing `steps` field → 422.
   - Regression: existing ASP-03 tasks unaffected.
6. **OpenAPI snapshot + governance sync + ASP-NOTE-014** at the closure commit.

---

## 5. Blocking dependencies (before build can start)

- **PAP files PAP-ASP-REQ-ASP-03 v3.0** with the formal schema confirmed.
  - Any field-name or typing delta from this draft must be reconciled before build.
- **Architect issues the v3.0 acceptance directive** (expected text: "ACCEPTED + build within 1 working day per ASP-OUT-065 commitment; allocate migration NNNN").
- Migration number allocation — 0030 vs 0031 per ASP-FEAT-ASP-05 v1.0 OQ-05-4 resolution.

---

## 6. Governance trail

- Trigger: PAP F-03-03 filed (originally against ASP-12 — mis-targeting).
- Corrected: **ASP-OUT-065** sent to PAP, directing re-file against ASP-03.
- Commitment: acceptance + build within 1 working day on v3.0 arrival.
- Prep: **ASP-OUT-066 Task 2** — this document.
- Cross-reference: F-03-02 (ASP-OUT-036) established the `StepContext` + `extra="ignore"` + wildcard-prompt-seed pattern that F-03-03 inherits.

---

## 7. Status

- Draft models authored (directive-verbatim; 0 code changes).
- Prompt draft authored (directive-verbatim).
- Collision checks clean.
- Migration slot available.
- **Awaiting PAP v3.0 filing.** Implementation does NOT begin until Architect green light.
