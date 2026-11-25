#!/usr/bin/env python3
"""How deeply the skill teaches each Bot API method and type and each Telegram.WebApp member.

  py -3 scripts/api_coverage.py --report                 # tables by section and the gaps by name
  py -3 scripts/api_coverage.py --check                  # fail when coverage fell below the floor
  py -3 scripts/api_coverage.py --update-floor           # record the current state as the floor
  py -3 scripts/api_coverage.py --json out.json          # every symbol with its levels

Levels. A symbol has a level when its exact name is a whole identifier in that text:
  Bot API methods and types (data/bot-api/catalog.json)
    K  knowledge   references/**/*.md, except the generated registry bot-api-coverage.md and INDEX.md
    R  recipe      recipes/*.md
    P  practice    examples/payloads/*.json or example code (examples/**/*.py|ts|tsx|js|mjs|html);
                   a method also counts in snake_case (bot.send_message)
    V  validator   scripts/validate_*.py (a special case or a `_rules_<method>` rule)
  Telegram.WebApp members (data/mini-apps/webapp-catalog.json), matched by the member name
    A  api list    references/mini-apps/webapp-api.md
    G  guidance    any other references/mini-apps/*.md or references/mini-apps-bridge.md
    C  code        examples/mini-apps/**/*.ts|tsx|js|mjs|html
Name matching is coarse: a one-word name (close, Story, show) can match unrelated prose.

The floor (data/bot-api/coverage-floor.json in the skill) lists, for each measure, the symbols that do not
meet it yet. `--check` fails when any other symbol misses a measure (coverage was lost) and when a listed
symbol now meets it (the floor is stale: run --update-floor so the ratchet moves up). `--update-floor`
refuses to add a symbol to a gap list unless `--allow-new-gaps` is given (for symbols a catalog sync added).
"""
# run-checks: --check
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "telegram-bot-ui")
FLOOR_REL = os.path.join("data", "bot-api", "coverage-floor.json")
SKIP_DIRS = {"node_modules", "__pycache__", ".git"}
REF_SKIP = {"bot-api-coverage.md", "INDEX.md"}
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".mjs", ".html")
WEB_CODE_EXT = (".ts", ".tsx", ".js", ".mjs", ".html")
IDENT = re.compile(r"[A-Za-z0-9_]+")

# measure -> (row kind, predicate). Each one is ratcheted by the floor.
MEASURES = {
    "method.K": ("method", lambda r: r["K"]),
    "method.P": ("method", lambda r: r["P"]),
    "type.named": ("type", lambda r: r["K"] or r["R"] or r["P"]),
    "webapp.guided": ("webapp", lambda r: r["G"] or r["C"]),
}


def _files(base: str, exts: tuple[str, ...], skip: set[str] = frozenset()) -> list[str]:
    if not os.path.isdir(base):
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("dist"))
        out += [os.path.join(dirpath, n) for n in sorted(filenames) if n.endswith(exts) and n not in skip]
    return out


def _tokens(paths: list[str]) -> set[str]:
    words: set[str] = set()
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            words.update(IDENT.findall(fh.read()))
    return words


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def measure(skill: str = SKILL) -> dict:
    """Every Bot API symbol and WebApp member with its levels."""
    def load(*parts):
        with open(os.path.join(skill, *parts), encoding="utf-8") as fh:
            return json.load(fh)

    catalog, webapp = load("data", "bot-api", "catalog.json"), load("data", "mini-apps", "webapp-catalog.json")
    refs = os.path.join(skill, "references")
    examples = os.path.join(skill, "examples")
    know = _tokens(_files(refs, (".md",), REF_SKIP))
    recipe = _tokens(_files(os.path.join(skill, "recipes"), (".md",)))
    practice = _tokens(_files(os.path.join(examples, "payloads"), (".json",)) + _files(examples, CODE_EXT))
    validators = _tokens([p for p in _files(os.path.join(skill, "scripts"), (".py",))
                          if os.path.basename(p).startswith("validate_")])

    rows = []
    for kind in ("methods", "types"):
        for name, sym in sorted(catalog[kind].items()):
            is_method = kind == "methods"
            rows.append({
                "kind": kind[:-1], "name": name, "section": sym.get("section") or "",
                "K": name in know, "R": name in recipe,
                "P": name in practice or (is_method and snake(name) in practice),
                "V": name in validators or (is_method and f"_rules_{name}" in validators),
            })

    mini = os.path.join(refs, "mini-apps")
    api_list = _tokens([os.path.join(mini, "webapp-api.md")] if os.path.isfile(os.path.join(mini, "webapp-api.md")) else [])
    guide_paths = [p for p in _files(mini, (".md",)) if os.path.basename(p) != "webapp-api.md"]
    bridge = os.path.join(refs, "mini-apps-bridge.md")
    guide = _tokens(guide_paths + ([bridge] if os.path.isfile(bridge) else []))
    web_code = _tokens(_files(os.path.join(examples, "mini-apps"), WEB_CODE_EXT))
    for key, member in sorted(webapp["members"].items()):
        short = member.get("name") or key.split(".")[-1]
        rows.append({"kind": "webapp", "name": key, "section": member.get("kind") or "",
                     "A": short in api_list, "G": short in guide, "C": short in web_code})
    return {"bot_api": catalog["meta"].get("bot_api_version", ""), "rows": rows}


def gaps(rows: list[dict]) -> dict[str, list[str]]:
    out = {}
    for measure_name, (kind, ok) in MEASURES.items():
        out[measure_name] = sorted(r["name"] for r in rows if r["kind"] == kind and not ok(r))
    return out


def compare(floor: dict, current: dict[str, list[str]]) -> tuple[dict, dict]:
    """(lost: symbols missing a measure outside the floor, stale: floor entries that now meet it)."""
    lost, stale = {}, {}
    recorded = floor.get("gaps", {})
    for name, now in current.items():
        before = set(recorded.get(name, []))
        lost_here, stale_here = sorted(set(now) - before), sorted(before - set(now))
        if lost_here:
            lost[name] = lost_here
        if stale_here:
            stale[name] = stale_here
    return lost, stale


def _count(rows, kind, ok):
    picked = [r for r in rows if r["kind"] == kind]
    return sum(1 for r in picked if ok(r)), len(picked)


def summary_line(rows: list[dict]) -> str:
    parts = []
    for name, (kind, ok) in MEASURES.items():
        have, total = _count(rows, kind, ok)
        parts.append(f"{name} {have}/{total}")
    return ", ".join(parts)


def _table(header: list[str], body: list[list], total: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    lines.append("| " + " | ".join(f"**{c}**" for c in total) + " |")
    return "\n".join(lines)


def report(result: dict) -> str:
    rows = result["rows"]
    out = []
    by_section: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_section[(r["kind"], r["section"])].append(r)

    def section_rows(kind, cells):
        sections = sorted((s for k, s in by_section if k == kind), key=lambda s: -len(by_section[(kind, s)]))
        body = [[s or "-", *cells(by_section[(kind, s)])] for s in sections]
        return body, cells([r for r in rows if r["kind"] == kind])

    def method_cells(rs):
        return [len(rs), sum(r["K"] for r in rs), sum(r["R"] for r in rs), sum(r["P"] for r in rs),
                sum(r["V"] for r in rs), sum(not (r["K"] or r["R"] or r["P"]) for r in rs),
                sum(r["K"] and not r["P"] for r in rs)]

    body, total = section_rows("method", method_cells)
    out.append(f"## Bot API {result['bot_api']}: methods\n")
    out.append(_table(["Section", "Methods", "K", "R", "P", "V", "Nowhere", "Text only"], body, ["Total", *total]))

    def type_cells(rs):
        named = sum(1 for r in rs if r["K"] or r["R"] or r["P"])
        return [len(rs), named, sum(r["K"] for r in rs), sum(r["P"] for r in rs), len(rs) - named]

    body, total = section_rows("type", type_cells)
    out.append(f"\n## Bot API {result['bot_api']}: types\n")
    out.append(_table(["Section", "Types", "Named", "K", "P", "Not named"], body, ["Total", *total]))

    def web_cells(rs):
        return [len(rs), sum(r["A"] for r in rs), sum(r["G"] for r in rs), sum(r["C"] for r in rs),
                sum(not (r["G"] or r["C"]) for r in rs)]

    body, total = section_rows("webapp", web_cells)
    out.append("\n## Telegram.WebApp members\n")
    out.append(_table(["Kind", "Members", "In webapp-api.md", "Guidance", "Code", "Neither guidance nor code"],
                      body, ["Total", *total]))

    methods = [r for r in rows if r["kind"] == "method"]
    nowhere = [r["name"] for r in methods if not (r["K"] or r["R"] or r["P"])]
    text_only = [r["name"] for r in methods if r["K"] and not r["P"]]
    silent = [r["name"] for r in rows if r["kind"] == "webapp" and not (r["G"] or r["C"])]
    out.append(f"\nMethods named nowhere ({len(nowhere)}): {', '.join(nowhere) or '-'}")
    out.append(f"\nMethods in text only, no example ({len(text_only)}): {', '.join(text_only) or '-'}")
    out.append(f"\nWebApp members with neither guidance nor code ({len(silent)}): {', '.join(silent) or '-'}")
    return "\n".join(out)


def load_floor(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_floor(path: str, bot_api: str, current: dict[str, list[str]]) -> None:
    data = {
        "$comment": "Generated by scripts/api_coverage.py --update-floor. Each list names the symbols that do not "
                    "meet the measure yet; --check fails if any other symbol misses it, and if a listed one now "
                    "meets it. The lists only shrink.",
        "bot_api": bot_api,
        "gaps": current,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def _print_names(title: str, groups: dict[str, list[str]]) -> None:
    for name, names in groups.items():
        print(f"  {title} {name} ({len(names)}): {', '.join(names)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true", help="print the coverage tables and the gaps")
    ap.add_argument("--check", action="store_true", help="fail when coverage differs from the floor")
    ap.add_argument("--update-floor", action="store_true", help="record the current state as the floor")
    ap.add_argument("--allow-new-gaps", action="store_true",
                    help="with --update-floor: accept symbols that are not covered and not in the floor yet")
    ap.add_argument("--json", metavar="PATH", help="write every symbol with its levels")
    ap.add_argument("--skill", default=SKILL, help=argparse.SUPPRESS)
    ap.add_argument("--floor", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    floor_path = args.floor or os.path.join(args.skill, FLOOR_REL)

    result = measure(args.skill)
    rows, current = result["rows"], gaps(result["rows"])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
    if args.report or not (args.check or args.update_floor or args.json):
        print(report(result))

    status = 0
    if args.update_floor:
        lost, _ = compare(load_floor(floor_path), current)
        if lost and not args.allow_new_gaps and os.path.isfile(floor_path):
            print("api coverage: refusing to lower the floor; these symbols would become new gaps:")
            _print_names("new gap", lost)
            print("Restore their coverage, or pass --allow-new-gaps if a catalog sync added them.")
            return 1
        write_floor(floor_path, result["bot_api"], current)
        print(f"api coverage: floor written to {os.path.relpath(floor_path, ROOT)} ({summary_line(rows)})")
    if args.check:
        floor = load_floor(floor_path)
        if not floor:
            print(f"api coverage: no floor at {floor_path}; run --update-floor")
            return 1
        lost, stale = compare(floor, current)
        if lost:
            print("api coverage: FAILED, coverage fell below the floor (or the catalog gained symbols):")
            _print_names("missing", lost)
        if stale:
            print("api coverage: FAILED, the floor is stale; run `py -3 scripts/api_coverage.py --update-floor`:")
            _print_names("now covered", stale)
        if lost or stale:
            status = 1
        else:
            print(f"api coverage: OK ({summary_line(rows)})")
    return status


if __name__ == "__main__":
    sys.exit(main())
