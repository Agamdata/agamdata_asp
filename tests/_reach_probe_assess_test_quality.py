"""F-03-03 G-PROMPT-REACH 6-probe matrix for assess_test_quality
(Commit B verification per ENGINEERING-PLAYBOOK §G-PROMPT-REACH
expanded rule).

Seeded row: (generation, assess_test_quality, '*', '*', v1).
Probe matrix: seeded caller + playwright_runner + test_generator +
'*' catch-all × maturities (L2, '*').
"""
import asyncio

from app.infra.redis import init_redis
from app.registry.prompt_registry import get_prompt


PROBES = [
    ("playwright_runner", "L2"),
    ("playwright_runner", "*"),
    ("test_generator",    "L2"),
    ("test_generator",    "*"),
    ("*",                 "L2"),
    ("*",                 "*"),
]


async def main():
    await init_redis()

    print("=" * 80)
    print("assess_test_quality G-PROMPT-REACH — 6-probe matrix")
    print("=" * 80)

    passed = 0
    for caller, mat in PROBES:
        try:
            p = await get_prompt("generation", "assess_test_quality",
                                 caller, mat)
            if p is not None:
                passed += 1
                print(f"PASS  caller={caller:20s} mat={mat:3s}"
                      f"  ->  row(caller={p.caller_module}, mat={p.maturity_level}, v{p.version})")
            else:
                print(f"FAIL  caller={caller:20s} mat={mat:3s}  ->  None")
        except Exception as e:
            print(f"FAIL  caller={caller:20s} mat={mat:3s}  ->  "
                  f"{e.__class__.__name__}: {e}")

    print()
    print(f"RESULT: {passed}/{len(PROBES)} probes PASS")


if __name__ == "__main__":
    asyncio.run(main())
