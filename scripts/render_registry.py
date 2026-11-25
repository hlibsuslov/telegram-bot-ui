#!/usr/bin/env python3
"""Render references/bot-api-coverage.md from recipes/registry.json.

The JSON is the source of truth (tests check every row against the files it
names); the Markdown is what an agent reads. `--check` fails if they drifted.
Usage: python scripts/render_registry.py [--check]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "telegram-bot-ui")
SRC = os.path.join(ROOT, "recipes", "registry.json")
OUT = os.path.join(ROOT, "references", "bot-api-coverage.md")

INTRO = """---
summary: "{summary}"
verified: "{verified}"
bot_api: "{bot_api}"
---

# Bot API {versions_title} coverage registry

> Generated from `recipes/registry.json` by `scripts/render_registry.py` — edit the JSON.
> Verified {verified} against {source}. Newest release on that date: {newest}.
> Every bullet of these releases is one row: what changed, why it's useful, where it works, the
> skill section that teaches it, a concrete example, and the automated check that exercises it.

## Contents

{contents}

Availability is five separate questions — spec, production, Bot API server, installed SDK,
client rendering. "production" below is about Telegram's servers; SDK support is in
`sdk-compatibility.md#verified-sdk-status-2026-11-12`; client rendering is never proven offline.

Status: {statuses}

Totals: **{total} rows** — {per_version}; ready {ready}, test-server only {test}, dry-run {dry}; not covered: **{missing}**.
"""

SECTION = """
## Bot API {version}

| ID | Change | Use | Availability | Skill section | Example | Check | Status |
|---|---|---|---|---|---|---|---|
"""


def render() -> str:
    reg = json.load(open(SRC, encoding="utf-8"))
    rows = reg["rows"]
    count = lambda st: sum(r["status"] == st for r in rows)  # noqa: E731
    versions = sorted({r["version"] for r in rows}, key=lambda v: tuple(map(int, v.split("."))))
    by_version: dict[str, list[dict]] = {}
    for r in rows:
        by_version.setdefault(r["version"], []).append(r)
    summary = (f"Generated registry of every Bot API {versions[0]}-{versions[-1]} change with its use, availability, "
               "teaching section, example, check and status; read to see whether a new API feature is covered and where.")
    out = INTRO.format(summary=summary, verified=reg["verified"], bot_api=reg["newest_release"].split()[0],
                       source=reg["source"], newest=reg["newest_release"],
                       contents="\n".join(f"- [Bot API {v}](#bot-api-{v.replace('.', '')})" for v in by_version),
                       statuses="; ".join(f"**{k}** = {v}" for k, v in reg["statuses"].items()),
                       versions_title=" / ".join(versions),
                       total=len(rows), per_version=", ".join(f"{v}: {sum(r['version'] == v for r in rows)}" for v in versions),
                       ready=count("ready"),
                       test=count("ready-test-server"), dry=count("ready-dry-run"),
                       missing=sum(r["status"] not in reg["statuses"] for r in rows))
    for version, group in by_version.items():
        out += SECTION.format(version=version)
        for r in group:
            skill = r["skill"].replace("references/", "")
            out += (f"| {r['id']} | {r['change']} | {r['use']} | {r['availability']} | `{skill}` | "
                    f"`{r['example']}` | `{r['check']}` | {r['status']} |\n")
    return out


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != text:
            print("references/bot-api-coverage.md is out of date: run scripts/render_registry.py")
            return 1
        print("OK: registry markdown up to date")
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
