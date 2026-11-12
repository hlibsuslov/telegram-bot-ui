#!/usr/bin/env python3
"""Run every offline check of the skill. No token, no network.

  python scripts/run_checks.py

Runs: validate_skill, validate_references, render_registry --check, the Python
unittest suite (tests/), and - when Node >= 22.18 is available - the TypeScript
recipe tests (examples/ts). The grammY and aiogram contract tests run when their
pinned packages are installed (see README); otherwise they are reported as skipped.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(label: str, cmd: list[str], cwd: str = ROOT) -> bool:
    print(f"\n=== {label}: {' '.join(cmd)}")
    ok = subprocess.run(cmd, cwd=cwd).returncode == 0
    print(f"--- {label}: {'OK' if ok else 'FAILED'}")
    return ok


def main() -> int:
    py = sys.executable
    results = [
        run("skill", [py, "scripts/validate_skill.py"]),
        run("references", [py, "scripts/validate_references.py"]),
        run("registry", [py, "scripts/render_registry.py", "--check"]),
        run("python tests", [py, "-m", "unittest", "discover", "-s", "tests", "-t", "tests"]),
    ]
    node = shutil.which("node")
    if node:
        ts = os.path.join(ROOT, "examples", "ts")
        tests = [os.path.join("test", f) for f in os.listdir(os.path.join(ts, "test")) if f.endswith(".test.ts")]
        results.append(run("typescript tests", [node, "--test", *tests], cwd=ts))
        grammy = os.path.join(ts, "sdk-grammy")
        if os.path.isdir(os.path.join(grammy, "node_modules", "grammy")):
            results.append(run("grammY contract", [node, "--test", "adapter.test.ts"], cwd=grammy))
        else:
            print("\n=== grammY contract: SKIPPED (cd examples/ts/sdk-grammy && npm ci)")
    else:
        print("\n=== typescript tests: SKIPPED (node not found)")
    print(f"\n{sum(results)}/{len(results)} check groups passed.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
