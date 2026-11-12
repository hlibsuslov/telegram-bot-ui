#!/usr/bin/env python3
"""Render references/bot-api-10.3-10.4.md from recipes/registry.json.

The JSON is the source of truth (tests check every row against the files it
names); the Markdown is what an agent reads. `--check` fails if they drifted.
Usage: python scripts/render_registry.py [--check]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "recipes", "registry.json")
OUT = os.path.join(ROOT, "references", "bot-api-10.3-10.4.md")

INTRO = """# Bot API 10.3 / 10.4 coverage registry

> Generated from `recipes/registry.json` by `scripts/render_registry.py` — edit the JSON.
> Verified {verified} against {source}. Newest release on that date: {newest}.
> Every bullet of both releases is one row: what changed, why it's useful, where it works, the
> skill section that teaches it, a concrete example, and the automated check that exercises it.

Availability is five separate questions — spec, production, Bot API server, installed SDK,
client rendering. "production" below is about Telegram's servers; SDK support is in
`sdk-compatibility.md#verified-sdk-status-2026-11-12`; client rendering is never proven offline.

Status: {statuses}

Totals: **{total} rows** — 10.3: {n3}, 10.4: {n4}; ready {ready}, test-server only {test}, dry-run {dry}; not covered: **{missing}**.

| ID | Change | Use | Availability | Skill section | Example | Check | Status |
|---|---|---|---|---|---|---|---|
"""


def render() -> str:
    reg = json.load(open(SRC, encoding="utf-8"))
    rows = reg["rows"]
    count = lambda st: sum(r["status"] == st for r in rows)  # noqa: E731
    out = INTRO.format(verified=reg["verified"], source=reg["source"], newest=reg["newest_release"],
                       statuses="; ".join(f"**{k}** = {v}" for k, v in reg["statuses"].items()),
                       total=len(rows), n3=sum(r["version"] == "10.3" for r in rows),
                       n4=sum(r["version"] == "10.4" for r in rows), ready=count("ready"),
                       test=count("ready-test-server"), dry=count("ready-dry-run"),
                       missing=sum(r["status"] not in reg["statuses"] for r in rows))
    for r in rows:
        skill = r["skill"].replace("references/", "")
        out += (f"| {r['id']} | {r['change']} | {r['use']} | {r['availability']} | `{skill}` | "
                f"`{r['example']}` | `{r['check']}` | {r['status']} |\n")
    return out


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != text:
            print("references/bot-api-10.3-10.4.md is out of date: run scripts/render_registry.py")
            return 1
        print("OK: registry markdown up to date")
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
