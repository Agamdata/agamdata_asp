"""One-shot G-PROMPT-REACH probe runner for ASP-OUT-051 verification.

Runs 20 probes (5 caller patterns × 4 F-03-02 tasks) plus the
F-03-05 refactor_script_locators probe. Prints per-probe pass/fail
and a summary tally.

Usage:
    docker compose exec -T ai-service python /app/tests/_reach_probe_f0302.py
"""
import asyncio

from app.infra.redis import init_redis
from app.registry.prompt_registry import get_prompt


PROBES = [
    ("playwright_runner", "L2"),
    ("playwright_runner", "*"),
    ("test_generator",    "L2"),
    ("test_generator",    "*"),
    ("any_other",         "L2"),
]

F0302_TASKS = [
    ("generation", "draft_steps"),
    ("generation", "suggest_preconditions"),
    ("generation", "propose_edge_cases"),
    ("nlp",        "extract_test_entities"),
]


async def main():
    await init_redis()

    print("=" * 80)
    print("F-03-02 — 5 caller patterns × 4 tasks = 20 probes")
    print("=" * 80)

    passed = 0
    for service, task in F0302_TASKS:
        for caller, mat in PROBES:
            try:
                p = await get_prompt(service, task, caller, mat)
                if p is not None:
                    passed += 1
                    caller_in_row = p.caller_module
                    mat_in_row = p.maturity_level
                    print(
                        f"PASS  {task:24s}  caller={caller:20s}  mat={mat:3s}"
                        f"  ->  row(caller={caller_in_row}, mat={mat_in_row}, v{p.version})"
                    )
                else:
                    print(
                        f"FAIL  {task:24s}  caller={caller:20s}  mat={mat:3s}"
                        f"  ->  None"
                    )
            except Exception as e:
                print(
                    f"FAIL  {task:24s}  caller={caller:20s}  mat={mat:3s}"
                    f"  ->  {e.__class__.__name__}: {e}"
                )

    print()
    print(f"F-03-02 RESULT: {passed}/{len(F0302_TASKS)*len(PROBES)} probes PASS")
    print()
    print("=" * 80)
    print("F-03-05 — refactor_script_locators probe (ASP-OUT-051)")
    print("=" * 80)

    f0305_callers = [
        ("playwright_runner", "L2"),
        ("playwright_runner", "*"),
        ("test_generator",    "L2"),
        ("any_other",         "L2"),
    ]
    for caller, mat in f0305_callers:
        try:
            p = await get_prompt(
                "generation", "refactor_script_locators", caller, mat
            )
            if p is not None:
                print(
                    f"PASS  refactor_script_locators  caller={caller:20s}  mat={mat:3s}"
                    f"  ->  row(caller={p.caller_module}, mat={p.maturity_level}, v{p.version})"
                )
            else:
                print(
                    f"FAIL  refactor_script_locators  caller={caller:20s}  mat={mat:3s}"
                    f"  ->  None"
                )
        except Exception as e:
            print(
                f"FAIL  refactor_script_locators  caller={caller:20s}  mat={mat:3s}"
                f"  ->  {e.__class__.__name__}: {e}"
            )


if __name__ == "__main__":
    asyncio.run(main())
