"""G-PROMPT-REACH 6-probe matrix for extract_invoice (I-DOC-03
verification per ASP-FEAT-ASP-04 v1.0 §9.5 and
ENGINEERING-PLAYBOOK.md §G-PROMPT-REACH expanded rule).

Seeded row: (doc_intelligence, extract_invoice, '*', '*', v1).
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
    print("extract_invoice G-PROMPT-REACH — 6-probe matrix")
    print("=" * 80)

    passed = 0
    for caller, mat in PROBES:
        try:
            p = await get_prompt("doc_intelligence", "extract_invoice",
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
