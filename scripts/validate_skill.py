#!/usr/bin/env python3
"""Validate this skill's SKILL.md against the Agent Skills format.

Portable: standard library only (uses PyYAML if present, else a minimal
front-matter parser). Safe: reads local files only. Never needs a bot token,
never touches the network, never sends a Telegram message.

Checks:
  * YAML front matter present and parseable.
  * `name` present, kebab-case, <= 64 chars, matches the directory name.
  * `description` present, non-empty, <= 1024 chars, not trivially short.
  * Required operational sections exist in the body.
  * Body is reasonably compact (progressive disclosure).
  * No bot token / obvious secret is embedded.

Exit code 0 on success, 1 on any error. Warnings do not fail the run.

Usage:  python scripts/validate_skill.py
"""
from __future__ import annotations

import os
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Telegram bot token shape: <digits>:<35+ url-safe chars>
TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")

REQUIRED_SECTIONS = [
    "Purpose",
    "When to use",
    "When NOT to use",
    "Terminology",
    "Source-of-truth policy",
    "Core workflow",
    "Definition of done",
]

MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MIN_DESCRIPTION_LEN = 40
BODY_WARN_CHARS = 20000  # ~5k tokens; progressive-disclosure guideline


def skill_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def split_front_matter(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip("\n")
    body = text[end + 4:]
    return fm, body


def parse_front_matter(fm: str) -> dict:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(fm)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    # Minimal fallback: handle `key: value` and block scalars (>, >-, |, |-).
    result: dict[str, str] = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", ">-", "|", "|-", ">+", "|+"):
            folded = val.startswith(">")
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].strip() == "" or lines[i].startswith((" ", "\t"))):
                block.append(lines[i].strip())
                i += 1
            joined = " ".join(b for b in block if b) if folded else "\n".join(block)
            result[key] = joined.strip()
            continue
        result[key] = val.strip().strip('"').strip("'")
        i += 1
    return result


def main() -> int:
    root = skill_dir()
    path = os.path.join(root, "SKILL.md")
    errors: list[str] = []
    warnings: list[str] = []

    if not os.path.isfile(path):
        print(f"FAIL: SKILL.md not found at {path}")
        return 1

    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    fm, body = split_front_matter(text)
    if fm is None:
        errors.append("YAML front matter missing or not closed with '---'.")
        meta = {}
    else:
        meta = parse_front_matter(fm)

    # name
    name = str(meta.get("name", "")).strip()
    if not name:
        errors.append("front matter: `name` is required.")
    else:
        if len(name) > MAX_NAME_LEN:
            errors.append(f"`name` too long ({len(name)} > {MAX_NAME_LEN}).")
        if not NAME_RE.match(name):
            errors.append(f"`name` must be kebab-case [a-z0-9-]; got '{name}'.")
        if name != os.path.basename(root):
            warnings.append(
                f"`name` '{name}' != directory '{os.path.basename(root)}'."
            )

    # description
    desc = str(meta.get("description", "")).strip()
    if not desc:
        errors.append("front matter: `description` is required.")
    else:
        if len(desc) > MAX_DESCRIPTION_LEN:
            errors.append(
                f"`description` too long ({len(desc)} > {MAX_DESCRIPTION_LEN})."
            )
        if len(desc) < MIN_DESCRIPTION_LEN:
            warnings.append("`description` looks too short to trigger reliably.")
        low = desc.lower()
        if "use" not in low and "when" not in low:
            warnings.append("`description` should say when to use the skill.")
        if "not use" not in low and "do not" not in low and "don't" not in low:
            warnings.append("`description` should state a boundary (when NOT to use).")

    # required sections
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"(?im)^#{{1,6}}\s+.*{re.escape(section)}", body) and \
           section.lower() not in body.lower():
            errors.append(f"missing required section: '{section}'.")

    # body size (progressive disclosure)
    if len(body) > BODY_WARN_CHARS:
        warnings.append(
            f"SKILL.md body is large ({len(body)} chars); move detail to references/."
        )

    # secrets
    if TOKEN_RE.search(text):
        errors.append("possible bot token / secret embedded in SKILL.md.")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). INVALID.")
        return 1
    print(f"\nOK: SKILL.md valid ('{name}'). {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
