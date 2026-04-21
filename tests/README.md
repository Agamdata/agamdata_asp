# ASP Test Suite

Conventions, fixtures, and the governed reference probe runners used
by the ASP test harness.

## Layout

| File | Purpose |
|---|---|
| `conftest.py` | Shared fixtures (`authed_client`, `mock_db_session`, `mock_anthropic`, `mock_prompt_registry`, `mock_rag`). Aligned with migration 023 schema (`tenant_api_keys` junction); `test_api_key` follows the new-format `asp_<prefix12>_<secret32>` pattern. See `c27279b` for the migration 023 alignment commit. |
| `test_rag_v1.py` | ASP-FEAT-ASP-02 v1.0 26-AC suite (9 phases). |
| `test_f0302.py` | F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 16-AC suite (5 blocks). |
| `test_gateway.py` | ASP-FEAT-ASP-00 v1.0 AC suite. |
| `test_nlp.py` | NLP service regression suite. |
| `test_generation.py` · `test_generation_ac.py` · `test_generation_v2.py` | Generation service regression + v1.1/v2.0 ACs. |
| `test_cost_meter.py` | ASP-08 Cost Meter regression. |
| `test_suggest_screen_mapping.py` | BP-10 / PAP-ASP-REQ-ASP-01 v2.0 AC suite. |
| `phase3_gate.py` · `phase4_gate.py` · `step5_handler_unit.py` | ASP-FEAT-ASP-00 v1.0 Gateway phase gates. |
| `_reach_probe_f0302.py` | **Governed reference G-PROMPT-REACH probe runner.** See below. |

## Running

All suites are designed to run **inside the `ai-service` container**:

```bash
docker compose exec -T ai-service bash -c \
  "cd /app && python -m pytest tests/<file>.py -x -v"
```

Reason: `pytest` is not installed in the repo's host Python env; the
container has `pytest` + the full asyncpg + chromadb + anthropic
stack wired for import. `pytest-asyncio` is pre-configured in
`pytest.ini`.

Copy files into the container when iterating on tests:

```bash
docker compose cp tests/<file>.py ai-service:/app/tests/
```

## Pre-existing test-isolation flake

`tests/test_nlp.py::test_ac19_cost_meter_resilience` passes in
isolation but fails under multi-module ordering — see
**ASP-DEFECT-023**. LOW severity; test-only. Scheduled for next
maintenance slot.

## G-PROMPT-REACH probe runner — governed pattern

**File:** `tests/_reach_probe_f0302.py`
**Shipped:** 2026-04-21 (ASP-OUT-051 P1 fix)
**Governed by:** `ENGINEERING-PLAYBOOK.md` §G-PROMPT-REACH (expanded
rule, 2026-04-21).

### When to use

Every time a migration modifies the `prompt_templates` table —
whether inserting, deactivating, or updating prompt rows — the
migration author MUST run a reach probe against the live DB before
committing. The probe must resolve the intended row for every
expected caller_module, not just the seeded one.

### How to use

**Copy `_reach_probe_f0302.py` and adapt it for the new migration's
task set.** The file is a minimal runnable standalone script that:

1. Calls `app.infra.redis.init_redis()` so the registry's Redis
   cache path is available.
2. Iterates a caller × maturity × task matrix.
3. Calls `app.registry.prompt_registry.get_prompt(...)` for each
   combination.
4. Prints per-probe PASS/FAIL with the resolved row's
   `(caller_module, maturity_level, version)` triple.
5. Tallies final result.

### Minimum required probe matrix

Per `ENGINEERING-PLAYBOOK.md` §G-PROMPT-REACH (expanded rule), every
new/modified `prompt_templates` row must be reach-probed against **at
minimum** the following `caller_module` values:

| Caller value | Why |
|---|---|
| The seeded caller (the migration's own INSERT) | Correctness of the immediate INSERT |
| `playwright_runner` | Canonical PAP caller for generation + NLP tasks |
| `test_generator` | Canonical PAP F-01-10 interactive-panel caller |
| `"*"` catch-all probe | Confirms any unexpected caller resolves via level-4 fallback |

Two maturities are typically sufficient: `L2` (handler default) and
`*` (maturity wildcard). For every task under test, run the Cartesian
product.

### Running the existing F-03-02 probe

```bash
docker compose exec -T ai-service bash -c \
  "cd /app && PYTHONPATH=/app python tests/_reach_probe_f0302.py"
```

Expected output: `F-03-02 RESULT: 20/20 probes PASS`.

### Why this exists

ASP-OUT-014 (migration 024, maturity axis) and ASP-OUT-051
(migrations 026/027, caller axis) were the same class of regression.
Both surfaced as production 500s because the G-PROMPT-REACH gate was
run with insufficient coverage — only the seeded values were probed.
The expanded rule forces wider coverage; this file is the reference
pattern for fulfilling that rule.

**Do not treat this probe runner as a one-off. Every future
prompt-templates migration must ship a copy-adapted version of
it, run it live, and embed the probe output in the commit message.**

## Conventions

- Test class names: `Test<Block>`. Test method names:
  `test_ac_<prefix>_<nn>_<short_description>`.
- Anthropic mocking via `mock_anthropic` fixture from `conftest.py`;
  build responses with a local `_mock_anth_response(text, ...)`
  helper where more shape is needed.
- Prompt-registry mocking via `mock_prompt_registry` fixture for
  pure-unit tests, or a test-local `@pytest.fixture(autouse=True)`
  that patches `app.registry.prompt_registry.get_prompt` +
  `get_prompt_variant` (see `test_f0302.py` for the shape).
- HTTP endpoint tests: use `authed_client` (TestClient with a valid
  new-format `X-ASP-API-Key` header pre-set). Negative-auth tests
  use plain `client` and supply an invalid header — the real
  `verify_api_key` path rejects with 401.
- Stop-on-first-failure during AC verification runs: `pytest -x`.

## ADR references

- ADR-029 — fresh-DB round-trip gate for migrations. Any PR that
  touches `alembic/versions/` must show an `alembic upgrade head`
  from an empty DB in the test log before merge.
- ADR-030 — capabilities + schemas endpoints. Tests must register
  `TASK_SCHEMA_MODELS` entries for every new task reachable via the
  Gateway.
- ADR-034 — OpenAPI snapshot per migration head. Run
  `python -c 'import json; from app.main import app;
   print(json.dumps(app.openapi(), indent=2))' >
   docs/openapi/asp-openapi-<head>.json` on the container after
  applying a migration; commit the snapshot alongside the migration.
