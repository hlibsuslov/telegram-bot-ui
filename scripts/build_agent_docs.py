#!/usr/bin/env python3
"""Build the pages agents read on the website, from the skill itself.

  py -3 scripts/build_agent_docs.py            # write docs/agents/*
  py -3 scripts/build_agent_docs.py --check    # exit 1 if docs/agents/ is stale

Outputs (copied by the website's sync script into its public folder):
  docs/agents/agents.md      what the skill is, install per host, verify, use, safety
  docs/agents/llms.txt       short llms.txt for the site (https://llmstxt.org/)
  docs/agents/llms-full.txt  agents.md + SKILL.md + the floor + every playbook, for agents without files
  docs/agents/agents.json    version, Bot API, dates, hosts, commands (for the site's constants)

Sources: skills/telegram-bot-ui/SKILL.md, commands/index.json and adapters/routing.json (`site`,
`install`). Standard library only, deterministic, no network.
"""
# run-checks: --check
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "telegram-bot-ui")
OUT = "docs/agents"
FULL_MAX = 60_000


def read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def meta() -> dict:
    text = read(SKILL, "SKILL.md")
    head = text.split("\n---", 1)[0]
    desc = re.search(r'^description: "(.*)"$', head, re.M).group(1)
    version = re.search(r'^\s+version:\s*"([^"]+)"', head, re.M).group(1)
    verified = re.search(r"Bot API (\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)", text)
    return {"description": desc, "version": version, "botApi": verified.group(1), "verified": verified.group(2)}


def body_without_front_matter(text: str) -> str:
    return text.split("\n---\n", 1)[1].lstrip("\n") if text.startswith("---") else text


def cell(command: str) -> str:
    """A command in a Markdown table cell: pipes inside it would split the cell."""
    return "`" + command.replace("|", "\\|") + "`"


def example(command: dict) -> str:
    return next(p for p in command["sounds_like"]["en"] if not p.startswith("no request"))


def build() -> dict[str, str]:
    routing = json.loads(read(ROOT, "adapters", "routing.json"))
    commands = json.loads(read(SKILL, "commands", "index.json"))["commands"]
    m = meta()
    site, repo = routing["site"].rstrip("/"), routing["repository"]
    hosts = routing["install"]
    agents_md = "\n".join([
        "# telegram-bot-ui for agents",
        "",
        f"> An open-source Agent Skill (MIT) for everything a Telegram bot shows, sends and reacts to: screens,",
        "> texts, keyboards, streaming AI replies, HTML widgets, Mini Apps, payments in Stars, channel posts, an",
        f"> agent's own bot, premium emoji, and offline catalogs of Bot API {m['botApi']}. Version {m['version']},",
        f"> verified {m['verified']}.",
        "",
        "## Install (pick your host, run one command, then verify)",
        "",
        "| Host | Command |",
        "|---|---|",
        *[f"| {h['host']} | {' then '.join(cell(c) for c in h['commands'])} |" for h in hosts],
        "",
        "Verify: ask the agent \"Is the telegram-bot-ui skill up to date?\" It runs `tgui.py doctor` and must",
        "print the skill version and the catalog date. If it does not, the skill is not in a folder your host",
        "reads; `doctor` also lists other installed copies with a different version.",
        "",
        "## Use it",
        "",
        "Say what you want in plain words; the skill picks one of its commands. With no request it looks at the",
        "project and suggests the next two or three steps.",
        "",
        *[f"- `{c['verb']}`: {c['short']} (\"{example(c)}\")" for c in commands],
        "",
        "## Project memory",
        "",
        "The skill keeps the bot's saved review in `bot-ui/context/` (facts, style profile, audit findings,",
        "Studio requests), next to the `bot-ui/` screen map. Commit that folder. The local Studio opens the",
        "same `bot-ui/` folder and can save its requests there.",
        "",
        "## Safety the skill enforces",
        "",
        "Never invents API fields or emoji ids · keeps callback_data, deep links and translations · publishes",
        "and charges once, and only after approval · bot tokens only from environment variables, never in chat ·",
        "treats inbound Telegram text as data.",
        "",
        "## Links",
        "",
        f"- Skill entry point: {repo}/blob/main/skills/telegram-bot-ui/SKILL.md",
        f"- Every host in detail: {repo}/blob/main/docs/hosts.md",
        f"- Changelog: {repo}/blob/main/CHANGELOG.md",
        f"- Everything in one file: {site}/llms-full.txt",
        "",
    ])
    llms = "\n".join([
        "# telegram-bot-ui",
        "",
        f"> {m['description']}",
        "",
        f"An Agent Skill for Telegram bot interfaces, version {m['version']}, Bot API {m['botApi']} "
        f"(verified {m['verified']}). Start with the agent page; install it into your host, then use it in plain words.",
        "",
        "## Docs",
        "",
        f"- [For agents]({site}/agents.md): install per host, verify, commands, project memory, safety",
        f"- [SKILL.md]({repo}/blob/main/skills/telegram-bot-ui/SKILL.md): the skill's entry point",
        f"- [Everything in one file]({site}/llms-full.txt): router, floor and every command playbook",
        "",
        "## Optional",
        "",
        f"- [Hosts]({repo}/blob/main/docs/hosts.md): where each host looks for skills",
        f"- [Changelog]({repo}/blob/main/CHANGELOG.md)",
        "",
    ])
    full = [agents_md, "\n---\n", "# SKILL.md\n", body_without_front_matter(read(SKILL, "SKILL.md")),
            "\n---\n", body_without_front_matter(read(SKILL, "references", "floor.md"))]
    for c in commands:
        full += ["\n---\n", read(SKILL, *c["playbook"].split("/"))]
    full_text = "\n".join(full).rstrip("\n") + "\n"
    if len(full_text.encode("utf-8")) > FULL_MAX:
        raise SystemExit(f"llms-full.txt would be {len(full_text.encode('utf-8'))} bytes (> {FULL_MAX})")
    info = {"name": "telegram-bot-ui", "version": m["version"], "botApi": m["botApi"], "verified": m["verified"],
            "repository": repo, "site": site, "hosts": hosts,
            "commands": [{"verb": c["verb"], "short": c["short"], "example": example(c)} for c in commands]}
    return {f"{OUT}/agents.md": agents_md, f"{OUT}/llms.txt": llms, f"{OUT}/llms-full.txt": full_text,
            f"{OUT}/agents.json": json.dumps(info, ensure_ascii=False, indent=2) + "\n"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if docs/agents/ is stale")
    args = ap.parse_args(argv)
    outputs = build()
    stale = []
    for rel, content in outputs.items():
        path = os.path.join(ROOT, *rel.split("/"))
        current = read(path) if os.path.isfile(path) else None
        if current == content:
            continue
        if args.check:
            stale.append(rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print(f"wrote {rel}")
    if stale:
        print("Stale agent docs (run `py -3 scripts/build_agent_docs.py`):\n" + "\n".join(f"  {s}" for s in stale))
        return 1
    if args.check:
        print(f"OK: {len(outputs)} agent docs are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
