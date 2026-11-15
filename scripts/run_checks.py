#!/usr/bin/env python3
"""Run every offline check of the skill. No token, no network.

  python scripts/run_checks.py          # run everything
  python scripts/run_checks.py --list   # show what would run

Runs, in order:
  * validate_skill, validate_references, render_registry --check;
  * every other `scripts/*.py` that declares `# run-checks: <args>` in its first 40
    lines (for example build_adapters --check, run_evals) - new validators join by
    adding that line, without editing this file;
  * the Python unittest suite: every `tests/test_*.py` (stdlib unittest discovery);
  * Node tests: every `*.test.ts|mjs|js` under `examples/`, run with `node --test` from
    the nearest folder with a package.json. A folder whose package.json declares
    dependencies runs only when its node_modules exist (e.g. `npm ci`), otherwise it is
    reported as skipped. `.ts` tests need Node >= 22.18 (type stripping).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED = [
    ("skill", "scripts/validate_skill.py", []),
    ("references", "scripts/validate_references.py", []),
    ("registry", "scripts/render_registry.py", ["--check"]),
]
MARKER = re.compile(r"^#\s*run-checks:(.*)$")
NODE_TEST = re.compile(r"\.test\.(ts|mjs|js)$")
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}


def discovered_scripts() -> list[tuple[str, str, list[str]]]:
    fixed = {path for _, path, _ in FIXED}
    found = []
    scripts = os.path.join(ROOT, "scripts")
    for name in sorted(os.listdir(scripts)):
        rel = f"scripts/{name}"
        if not name.endswith(".py") or rel in fixed or name == "run_checks.py":
            continue
        with open(os.path.join(scripts, name), encoding="utf-8", errors="replace") as fh:
            for _, line in zip(range(40), fh):
                m = MARKER.match(line.strip())
                if m:
                    found.append((name[:-3], rel, m.group(1).split()))
                    break
    return found


def node_groups() -> list[tuple[str, list[str], bool]]:
    """(package dir, test files relative to it, needs node_modules) for examples/**."""
    groups: dict[str, list[str]] = {}
    base = os.path.join(ROOT, "examples")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if not NODE_TEST.search(name):
                continue
            pkg = dirpath
            while pkg.startswith(base) and not os.path.isfile(os.path.join(pkg, "package.json")):
                pkg = os.path.dirname(pkg)
            if not pkg.startswith(base):
                pkg = dirpath
            groups.setdefault(pkg, []).append(os.path.relpath(os.path.join(dirpath, name), pkg))
    result = []
    for pkg, tests in sorted(groups.items()):
        needs = False
        manifest = os.path.join(pkg, "package.json")
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as fh:
                data = json.load(fh)
            needs = bool(data.get("dependencies") or data.get("devDependencies"))
        result.append((pkg, [t.replace(os.sep, "/") for t in tests], needs))
    return result


def node_version(node: str) -> tuple[int, ...]:
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    return tuple(int(x) for x in re.findall(r"\d+", out)[:3]) or (0,)


def run(label: str, cmd: list[str], cwd: str = ROOT) -> bool:
    print(f"\n=== {label}: {' '.join(cmd)}")
    ok = subprocess.run(cmd, cwd=cwd).returncode == 0
    print(f"--- {label}: {'OK' if ok else 'FAILED'}")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="print the planned check groups")
    args = ap.parse_args(argv)
    py = sys.executable

    plan: list[tuple[str, list[str], str]] = [
        (label, [py, path, *extra], ROOT) for label, path, extra in FIXED + discovered_scripts()
    ]
    plan.append(("python tests", [py, "-m", "unittest", "discover", "-s", "tests", "-t", "tests"], ROOT))
    skipped: list[str] = []
    node = shutil.which("node")
    for pkg, tests, needs in node_groups():
        label = f"node tests ({os.path.relpath(pkg, ROOT).replace(os.sep, '/')})"
        if not node:
            skipped.append(f"{label}: node not found")
        elif needs and not os.path.isdir(os.path.join(pkg, "node_modules")):
            skipped.append(f"{label}: run `npm ci` in {os.path.relpath(pkg, ROOT)} first")
        elif any(t.endswith(".ts") for t in tests) and node_version(node) < (22, 18):
            skipped.append(f"{label}: needs Node >= 22.18 for .ts tests")
        else:
            plan.append((label, [node, "--test", *tests], pkg))

    if args.list:
        for label, cmd, cwd in plan:
            print(f"{label}: {' '.join(cmd)}  (in {os.path.relpath(cwd, ROOT) or '.'})")
        for s in skipped:
            print(f"SKIP {s}")
        return 0

    results = [run(label, cmd, cwd) for label, cmd, cwd in plan]
    for s in skipped:
        print(f"\n=== SKIPPED {s}")
    print(f"\n{sum(results)}/{len(results)} check groups passed"
          + (f", {len(skipped)} skipped." if skipped else "."))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
