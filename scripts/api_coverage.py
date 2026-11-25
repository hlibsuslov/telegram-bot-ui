#!/usr/bin/env python3
"""How deeply the skill teaches each Bot API method and type and each Telegram.WebApp member.

  py -3 scripts/api_coverage.py --report                 # tables by section and the gaps by name
  py -3 scripts/api_coverage.py --check                  # fail when coverage fell below the floor
  py -3 scripts/api_coverage.py --update-floor           # record the current state as the floor
  py -3 scripts/api_coverage.py --check --against origin/main   # ...and the floor was not lowered vs a ref
  py -3 scripts/api_coverage.py --json out.json          # every symbol with its levels

Levels. A symbol has a level when its exact name is a whole identifier in that text:
  Bot API methods and types (data/bot-api/catalog.json)
    K  knowledge   references/**/*.md, except the generated registry bot-api-coverage.md and INDEX.md
    R  recipe      recipes/*.md (top level only)
    P  practice    examples/payloads/*.json or example code (examples/**/*.py|ts|tsx|js|mjs|html);
                   a method also counts in snake_case (bot.send_message)
    V  validator   scripts/validate_*.py (a special case or a `_rules_<method>` rule); report only, coarse
    N  note        has its own agent note in data/bot-api/agent-notes/*.json (scripts/api_notes.py)
    C  card        has its own note or is listed in a note's "related" (the agent meets it in a card)
  Telegram.WebApp members (data/mini-apps/webapp-catalog.json), matched by the member name
    A  api list    references/mini-apps/webapp-api.md
    G  guidance    any other references/mini-apps/*.md (top level) or references/mini-apps-bridge.md
    C  code        examples/mini-apps/**/*.ts|tsx|js|mjs|html
Name matching is coarse: a one-word name (close, Story, show) can match unrelated prose, and WebApp members
are matched without their owner (BackButton.isVisible and SettingsButton.isVisible share one mention).
In a git checkout only tracked files count (`git add` a new file first), so a local run measures what CI sees.

The floor (data/bot-api/coverage-floor.json in the skill) lists, for each measure, the symbols that do not
meet it yet. `--check` fails when any other symbol misses a measure (coverage was lost) and when a listed
symbol now meets it (the floor is stale: run --update-floor so the ratchet moves up). `--update-floor`
refuses to add a symbol to a gap list unless `--allow-new-gaps` is given (for symbols a catalog sync added).
`--against REF` also reads the floor and catalogs at a git ref (the PR base in CI) and fails when the floor
lists a gap for a symbol that existed at REF and was not a gap there: the floor cannot be lowered in a change.
"""
# run-checks: --check
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
    "method.note": ("method", lambda r: r["N"]),
    "type.card": ("type", lambda r: r["C"]),
    "webapp.guided": ("webapp", lambda r: r["G"] or r["C"]),
}


def _files(base: str, exts: tuple[str, ...], skip: set[str] = frozenset(), recursive: bool = True,
           tracked: set[str] | None = None) -> list[str]:
    """Files under `base` with these extensions; with `tracked`, only the ones git tracks."""
    if not os.path.isdir(base):
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("dist")) if recursive else []
        out += [os.path.join(dirpath, n) for n in sorted(filenames) if n.endswith(exts) and n not in skip]
    if tracked is not None:
        out = [p for p in out if os.path.normcase(os.path.normpath(p)) in tracked]
    return out


def _tracked(folder: str) -> set[str] | None:
    """Normalized paths of the files git tracks under `folder`, or None outside a git checkout."""
    try:
        res = subprocess.run(["git", "-C", folder, "ls-files", "-z"], capture_output=True)
    except OSError:
        return None
    if res.returncode != 0:
        return None
    return {os.path.normcase(os.path.normpath(os.path.join(folder, p)))
            for p in res.stdout.decode("utf-8").split("\0") if p}


def git_json(ref: str, path: str):
    """A JSON file as it is at a git ref, or None when the ref or the file is not there."""
    folder, name = os.path.split(os.path.abspath(path))
    try:
        res = subprocess.run(["git", "-C", folder, "show", f"{ref}:./{name}"], capture_output=True)
    except OSError:
        return None
    return json.loads(res.stdout.decode("utf-8")) if res.returncode == 0 else None


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
    tracked = _tracked(skill)
    know = _tokens(_files(refs, (".md",), REF_SKIP, tracked=tracked))
    recipe = _tokens(_files(os.path.join(skill, "recipes"), (".md",), recursive=False, tracked=tracked))
    practice = _tokens(_files(os.path.join(examples, "payloads"), (".json",), recursive=False, tracked=tracked)
                       + _files(examples, CODE_EXT, tracked=tracked))
    validators = _tokens([p for p in _files(os.path.join(skill, "scripts"), (".py",), recursive=False, tracked=tracked)
                          if os.path.basename(p).startswith("validate_")])

    noted, related = set(), set()
    for path in _files(os.path.join(skill, "data", "bot-api", "agent-notes"), (".json",), recursive=False,
                       tracked=tracked):
        with open(path, encoding="utf-8") as fh:
            notes = json.load(fh).get("notes") or {}
        noted.update(notes)
        related.update(r for note in notes.values() if isinstance(note, dict)
                       for r in note.get("related", []) if isinstance(r, str))

    rows = []
    for kind in ("methods", "types"):
        for name, sym in sorted(catalog[kind].items()):
            is_method = kind == "methods"
            rows.append({
                "kind": kind[:-1], "name": name, "section": sym.get("section") or "",
                "K": name in know, "R": name in recipe,
                "P": name in practice or (is_method and snake(name) in practice),
                "V": name in validators or (is_method and f"_rules_{name}" in validators),
                "N": name in noted, "C": name in noted or name in related,
            })

    mini = os.path.join(refs, "mini-apps")
    mini_refs = _files(mini, (".md",), recursive=False, tracked=tracked)
    api_list = _tokens([p for p in mini_refs if os.path.basename(p) == "webapp-api.md"])
    guide = _tokens([p for p in mini_refs if os.path.basename(p) != "webapp-api.md"]
                    + [p for p in _files(refs, (".md",), recursive=False, tracked=tracked)
                       if os.path.basename(p) == "mini-apps-bridge.md"])
    web_code = _tokens(_files(os.path.join(examples, "mini-apps"), WEB_CODE_EXT, tracked=tracked))
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


def compare(floor: dict, current: dict[str, list[str]]) -> tuple[dict, dict, list[str]]:
    """(lost: symbols missing a measure outside the floor, stale: floor entries that now meet it,
    measures the floor does not record yet)."""
    lost, stale, new = {}, {}, []
    recorded = floor.get("gaps", {})
    for name, now in current.items():
        if name not in recorded:
            new.append(name)
            continue
        before = set(recorded[name])
        lost_here, stale_here = sorted(set(now) - before), sorted(before - set(now))
        if lost_here:
            lost[name] = lost_here
        if stale_here:
            stale[name] = stale_here
    return lost, stale, new


def lowered(base_floor: dict, floor: dict, base_symbols: set[str]) -> dict[str, list[str]]:
    """Gaps the floor records that the base floor did not, for symbols that already existed at the base.
    A measure the base floor does not have yet is new and cannot be lowered."""
    out = {}
    before_all = base_floor.get("gaps", {})
    for name, names in floor.get("gaps", {}).items():
        if name not in before_all:
            continue
        before = set(before_all[name])
        extra = sorted(n for n in names if n not in before and n in base_symbols)
        if extra:
            out[name] = extra
    return out


def symbols_at(ref: str, skill: str) -> set[str] | None:
    catalog = git_json(ref, os.path.join(skill, "data", "bot-api", "catalog.json"))
    webapp = git_json(ref, os.path.join(skill, "data", "mini-apps", "webapp-catalog.json"))
    if catalog is None:
        return None
    return {*catalog.get("methods", {}), *catalog.get("types", {}), *((webapp or {}).get("members") or {})}


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
                sum(r["V"] for r in rs), sum(r["N"] for r in rs), sum(not (r["K"] or r["R"] or r["P"]) for r in rs),
                sum(r["K"] and not r["P"] for r in rs)]

    body, total = section_rows("method", method_cells)
    out.append(f"## Bot API {result['bot_api']}: methods\n")
    out.append(_table(["Section", "Methods", "K", "R", "P", "V", "Note", "Nowhere", "Text only"], body,
                      ["Total", *total]))

    def type_cells(rs):
        named = sum(1 for r in rs if r["K"] or r["R"] or r["P"])
        return [len(rs), named, sum(r["K"] for r in rs), sum(r["P"] for r in rs), sum(r["C"] for r in rs),
                len(rs) - named]

    body, total = section_rows("type", type_cells)
    out.append(f"\n## Bot API {result['bot_api']}: types\n")
    out.append(_table(["Section", "Types", "Named", "K", "P", "In a card", "Not named"], body, ["Total", *total]))

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
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
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
    ap.add_argument("--against", metavar="REF", help="with --check: also fail if the floor is lower than at this git ref")
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
        lost, _, _ = compare(load_floor(floor_path), current)
        if lost and not args.allow_new_gaps and os.path.isfile(floor_path):
            print("api coverage: refusing to lower the floor; these symbols would become new gaps:")
            _print_names("new gap", lost)
            print("Restore their coverage, or pass --allow-new-gaps if a catalog sync added them.")
            return 1
        write_floor(floor_path, result["bot_api"], current)
        print(f"api coverage: floor written to {floor_path} ({summary_line(rows)})")
    if args.check:
        floor = load_floor(floor_path)
        if not floor:
            print(f"api coverage: no floor at {floor_path}; run --update-floor")
            return 1
        lost, stale, new = compare(floor, current)
        known = {r["name"] for r in rows}
        covered = {m: [n for n in names if n in known] for m, names in stale.items()}
        gone = {m: [n for n in names if n not in known] for m, names in stale.items()}
        if lost:
            print("api coverage: FAILED, coverage fell below the floor (or the catalog gained symbols):")
            _print_names("missing", lost)
        if stale:
            print("api coverage: FAILED, the floor is stale; run `py -3 scripts/api_coverage.py --update-floor`:")
            _print_names("now covered", {m: n for m, n in covered.items() if n})
            _print_names("no longer in the catalog", {m: n for m, n in gone.items() if n})
        for name in new:
            print(f"api coverage: FAILED, the floor has no {name} yet; run `py -3 scripts/api_coverage.py --update-floor`")
        if lost or stale or new:
            status = 1
        else:
            print(f"api coverage: OK ({summary_line(rows)})")
        if args.against:
            status = max(status, _check_against(args.against, floor_path, floor, args.skill))
    return status


def _check_against(ref: str, floor_path: str, floor: dict, skill: str) -> int:
    base_floor = git_json(ref, floor_path)
    if base_floor is None:
        print(f"api coverage: no floor at {ref}; nothing to compare")
        return 0
    base_symbols = symbols_at(ref, skill)
    if base_symbols is None:
        print(f"api coverage: FAILED, no catalog at {ref}")
        return 1
    drop = lowered(base_floor, floor, base_symbols)
    if drop:
        print(f"api coverage: FAILED, the floor is lower than at {ref} for symbols that existed there:")
        _print_names("lowered", drop)
        return 1
    print(f"api coverage: floor not lowered against {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
