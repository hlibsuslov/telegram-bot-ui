#!/usr/bin/env python3
"""Validate skills/telegram-bot-ui/SKILL.md against the Agent Skills format.

Portable: standard library only (uses PyYAML if present, else a minimal
front-matter parser). Safe: reads local files only. Never needs a bot token,
never touches the network, never sends a Telegram message.

Checks:
  * YAML front matter present and parseable.
  * `name` present, kebab-case, <= 64 chars, matches the directory name.
  * `description` present, non-empty, <= 1024 chars, not trivially short.
  * `metadata.version`, when present, equals the plugin.json version.
  * Required router sections exist in the body.
  * Budgets (progressive disclosure): SKILL.md <= 9.5 KiB, description <= 1024 (warning
    above 900), each command playbook <= 4 KiB, references/floor.md <= 5.5 KiB, the
    invariants inside the first 15 000 characters (what survives compaction).
  * Commands (commands/index.json): every playbook exists and has Done and Without scripts
    sections, every reference path a command or playbook names exists, every reference file
    is reachable from at least one command, signals and roles name existing commands.
  * No bot token / obvious secret is embedded.
  * Packaging (formats verified in docs/hosts.md):
    - generated adapters are in sync with SKILL.md + adapters/routing.json;
    - Claude Code subagents (agents/claude/*.md): front matter, name = file name,
      known tools and colors, description length;
    - Codex custom agents (agents/codex/*.toml): name, description,
      developer_instructions (parsed with tomllib on Python >= 3.11);
    - agents/openai.yaml uses only the documented interface/policy/dependencies keys;
    - root plugin.json against the closed Agent Plugins 1.0.0 schema, and the Codex
      manifest .codex-plugin/plugin.json;
    - .claude-plugin/plugin.json and marketplace.json: names, version, agent paths,
      relative source, and that skills/ holds exactly one skill, the one below.

Exit code 0 on success, 1 on any error. Warnings do not fail the run.

Usage:  python scripts/validate_skill.py
"""
from __future__ import annotations

import json
import os
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Telegram bot token shape: <digits>:<35+ url-safe chars>
TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")

REQUIRED_SECTIONS = [
    "Start: every activation",
    "Commands",
    "Scope",
    "Invariants",
    "Terms that are easy to confuse",
    "How much process",
    "Next step",
    "Tools",
]

MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MIN_DESCRIPTION_LEN = 40
BODY_WARN_CHARS = 20000  # ~5k tokens; progressive-disclosure guideline
SKILL_MAX_BYTES = 9728  # 9.5 KiB router
DESCRIPTION_WARN_LEN = 900
PLAYBOOK_MAX_BYTES = 4096
FLOOR_MAX_BYTES = 5632
INVARIANTS_WITHIN = 15000  # characters; Claude Code re-attaches ~5000 tokens after compaction


SKILL_REL = "skills/telegram-bot-ui"


def repo_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def skill_dir() -> str:
    return os.path.join(repo_dir(), *SKILL_REL.split("/"))


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


# ---------------------------------------------------------------- packaging checks

CLAUDE_TOOLS = {"Read", "Grep", "Glob", "Edit", "Write", "Bash", "Skill", "WebFetch",
                "WebSearch", "NotebookEdit", "Agent"}
CLAUDE_COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
OPENAI_YAML_KEYS = {
    "interface": {"display_name", "short_description", "icon_small", "icon_large",
                  "brand_color", "default_prompt"},
    "policy": {"allow_implicit_invocation"},
    "dependencies": {"tools"},
}
PLUGIN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _load_json(root: str, rel: str, errors: list[str]):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        errors.append(f"{rel} missing.")
    except ValueError as exc:
        errors.append(f"{rel}: invalid JSON ({exc}).")
    return None


def check_adapters(root: str, errors: list[str]) -> None:
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        import build_adapters  # noqa: PLC0415

        bad = build_adapters.stale(build_adapters.build())
    except Exception as exc:  # report, don't crash the validator
        errors.append(f"adapters: generator failed ({exc}).")
        return
    for rel in bad:
        errors.append(f"adapters: {rel} is stale; run `python scripts/build_adapters.py`.")


def check_claude_agents(root: str, errors: list[str], warnings: list[str]) -> list[str]:
    folder = os.path.join(root, "agents", "claude")
    names = []
    for fname in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not fname.endswith(".md"):
            continue
        rel = f"agents/claude/{fname}"
        with open(os.path.join(folder, fname), encoding="utf-8") as fh:
            fm, body = split_front_matter(fh.read())
        if fm is None:
            errors.append(f"{rel}: front matter missing.")
            continue
        meta = parse_front_matter(fm)
        name = str(meta.get("name", ""))
        names.append(name)
        if name != fname[:-3] or not NAME_RE.match(name):
            errors.append(f"{rel}: name '{name}' must be kebab-case and equal the file name.")
        desc = str(meta.get("description", "")).strip()
        if len(desc) < MIN_DESCRIPTION_LEN or len(desc) > MAX_DESCRIPTION_LEN:
            errors.append(f"{rel}: description length {len(desc)} outside "
                          f"{MIN_DESCRIPTION_LEN}..{MAX_DESCRIPTION_LEN}.")
        tools = [t.strip() for t in str(meta.get("tools", "")).split(",") if t.strip()]
        unknown = sorted(set(tools) - CLAUDE_TOOLS)
        if not tools or unknown:
            errors.append(f"{rel}: tools must be a non-empty subset of known tools; unknown: {unknown}.")
        if meta.get("color") and meta["color"] not in CLAUDE_COLORS:
            errors.append(f"{rel}: color '{meta['color']}' is not a documented value.")
        if "telegram-bot-ui" not in body:
            warnings.append(f"{rel}: body does not route into the telegram-bot-ui skill.")
        if TOKEN_RE.search(body):
            errors.append(f"{rel}: possible bot token embedded.")
    if not names:
        errors.append("agents/claude: no subagents found.")
    return names


def check_codex_agents(root: str, errors: list[str], warnings: list[str]) -> None:
    folder = os.path.join(root, "agents", "codex")
    try:
        import tomllib  # noqa: PLC0415
    except ImportError:
        warnings.append("agents/codex: tomllib unavailable (Python < 3.11); TOML not parsed.")
        return
    files = sorted(f for f in os.listdir(folder) if f.endswith(".toml")) if os.path.isdir(folder) else []
    if not files:
        errors.append("agents/codex: no custom agents found.")
    for fname in files:
        rel = f"agents/codex/{fname}"
        try:
            with open(os.path.join(folder, fname), "rb") as fh:
                data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{rel}: invalid TOML ({exc}).")
            continue
        for key in ("name", "description", "developer_instructions"):
            if not str(data.get(key, "")).strip():
                errors.append(f"{rel}: required key '{key}' missing or empty.")
        if not re.match(r"^[a-z][a-z0-9_]*$", str(data.get("name", ""))):
            errors.append(f"{rel}: name should be snake_case.")
        if "$telegram-bot-ui" not in str(data.get("developer_instructions", "")):
            warnings.append(f"{rel}: instructions do not route into $telegram-bot-ui.")


def check_openai_yaml(root: str, errors: list[str]) -> None:
    path = os.path.join(root, *SKILL_REL.split("/"), "agents", "openai.yaml")
    if not os.path.isfile(path):
        return
    section = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = re.match(r"^(\s*)([A-Za-z_]+):", line)
            if not m:
                continue
            indent, key = len(m.group(1)), m.group(2)
            if indent == 0:
                section = key
                if key not in OPENAI_YAML_KEYS:
                    errors.append(f"agents/openai.yaml: unknown top-level key '{key}'.")
            elif indent == 2 and section in OPENAI_YAML_KEYS and key not in OPENAI_YAML_KEYS[section]:
                errors.append(f"agents/openai.yaml: unknown key '{section}.{key}'.")


def check_plugin(root: str, skill_name: str, agent_names: list[str],
                 errors: list[str], warnings: list[str]) -> None:
    plugin = _load_json(root, ".claude-plugin/plugin.json", errors)
    market = _load_json(root, ".claude-plugin/marketplace.json", errors)
    if plugin:
        if plugin.get("name") != skill_name:
            errors.append("plugin.json: name must equal the skill name.")
        if not plugin.get("version"):
            warnings.append("plugin.json: no version; users are not pinned to releases.")
        agents = plugin.get("agents", [])
        for rel in agents:
            if not rel.startswith("./") or not rel.endswith(".md") or ".." in rel:
                errors.append(f"plugin.json: agent path '{rel}' must be ./relative .md.")
            elif not os.path.isfile(os.path.join(root, rel[2:])):
                errors.append(f"plugin.json: agent path '{rel}' does not exist.")
        listed = sorted(os.path.basename(a)[:-3] for a in agents)
        if listed != sorted(agent_names):
            errors.append("plugin.json: agents list differs from agents/claude/*.md.")
        # The default skills/ scan must find exactly one skill: skills/<name>/SKILL.md.
        if "skills" in plugin:
            errors.append("plugin.json: a 'skills' key is not needed; the default skills/ scan finds the skill.")
        found = sorted(d for d in os.listdir(os.path.join(root, "skills"))
                       if os.path.isfile(os.path.join(root, "skills", d, "SKILL.md")))             if os.path.isdir(os.path.join(root, "skills")) else []
        if found != [skill_name]:
            errors.append(f"plugin: skills/ must hold exactly one skill '{skill_name}'; found {found}.")
        if os.path.isfile(os.path.join(root, "SKILL.md")):
            errors.append("a root SKILL.md would register the skill twice; keep it in skills/.")
        if os.path.isfile(os.path.join(root, "CLAUDE.md")):
            warnings.append("plugin: a root CLAUDE.md is not loaded by plugins.")
    if market:
        if not PLUGIN_ID_RE.match(str(market.get("name", ""))):
            errors.append("marketplace.json: invalid marketplace name.")
        if not str((market.get("owner") or {}).get("name", "")).strip():
            errors.append("marketplace.json: owner.name is required.")
        entries = market.get("plugins") or []
        if not any(p.get("name") == skill_name and p.get("source") in ("./", ".") for p in entries):
            errors.append("marketplace.json: needs an entry for the plugin with source './'.")


AGENT_PLUGINS_KEYS = {"$schema", "name", "version", "description", "author", "homepage",
                      "repository", "license", "keywords", "extensions"}
AGENT_PLUGINS_NAME_RE = re.compile(r"^(?!.*--)(?!.*\.\.)[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")


def check_portable_manifests(root: str, skill_name: str, errors: list[str]) -> None:
    """Root plugin.json against the closed Agent Plugins 1.0.0 schema; .codex-plugin/plugin.json basics."""
    ap = _load_json(root, "plugin.json", errors)
    if ap:
        if ap.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            errors.append("plugin.json: $schema must be the Agent Plugins 1.0.0 identifier.")
        if set(ap) - AGENT_PLUGINS_KEYS:
            errors.append(f"plugin.json: fields outside the Agent Plugins schema: {sorted(set(ap) - AGENT_PLUGINS_KEYS)}.")
        if not AGENT_PLUGINS_NAME_RE.match(str(ap.get("name", ""))) or ap.get("name") != skill_name:
            errors.append("plugin.json: name must be the skill name and a valid Agent Plugins name.")
        if set(ap.get("author") or {}) - {"name", "email", "url"}:
            errors.append("plugin.json: author takes only name, email and url.")
        if not all(isinstance(k, str) for k in ap.get("keywords", [])):
            errors.append("plugin.json: keywords must be strings.")
    codex = _load_json(root, ".codex-plugin/plugin.json", errors)
    if codex:
        if codex.get("name") != skill_name or codex.get("skills") != "./skills/":
            errors.append(".codex-plugin/plugin.json: name must be the skill name and skills './skills/'.")
        for key in ("version", "description"):
            if not str(codex.get(key, "")).strip():
                errors.append(f".codex-plugin/plugin.json: '{key}' is required.")
        if not str((codex.get("author") or {}).get("name", "")).strip():
            errors.append(".codex-plugin/plugin.json: author.name is required.")
        if len((codex.get("interface") or {}).get("defaultPrompt", [])) > 3:
            errors.append(".codex-plugin/plugin.json: at most 3 defaultPrompt entries are used.")
        if os.listdir(os.path.join(root, ".codex-plugin")) != ["plugin.json"]:
            errors.append(".codex-plugin/ must hold only plugin.json.")


def check_metadata_version(root: str, fm: str, errors: list[str]) -> None:
    """SKILL.md `metadata.version` (read by skill directories) must equal plugin.json `version`."""
    block = re.search(r"(?m)^metadata:[ \t]*\n((?:[ \t]+\S.*(?:\n|$))*)", fm)
    found = re.search(r"(?m)^[ \t]+version:[ \t]*[\"']?([^\"'\s]+)", block.group(1)) if block else None
    if not found:
        return
    plugin = _load_json(root, ".claude-plugin/plugin.json", errors) or {}
    if found.group(1) != plugin.get("version"):
        errors.append(f"SKILL.md metadata.version {found.group(1)} != plugin.json version "
                      f"{plugin.get('version')}; change both (adapters/routing.json drives plugin.json).")


def check_packaging(root: str, skill_name: str, errors: list[str], warnings: list[str]) -> None:
    check_adapters(root, errors)
    names = check_claude_agents(root, errors, warnings)
    check_codex_agents(root, errors, warnings)
    check_openai_yaml(root, errors)
    check_plugin(root, skill_name, names, errors, warnings)
    check_portable_manifests(root, skill_name, errors)


def _reference_files(root: str) -> list[str]:
    out = []
    for dirpath, _dirs, files in os.walk(os.path.join(root, "references")):
        for name in files:
            if name.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
    return sorted(out)


def check_commands(root: str, repo: str, errors: list[str]) -> None:
    index = _load_json(root, "commands/index.json", errors)
    if not isinstance(index, dict) or not isinstance(index.get("commands"), list):
        errors.append("commands/index.json: expected an object with a `commands` list.")
        return
    verbs, routed = set(), set()
    for c in index["commands"]:
        verb = c.get("verb")
        if not verb or verb in verbs:
            errors.append(f"commands/index.json: missing or repeated verb {verb!r}.")
            continue
        verbs.add(verb)
        for key in ("short", "does", "playbook", "sounds_like"):
            if not c.get(key):
                errors.append(f"command {verb}: missing `{key}`.")
        if not c.get("sounds_like", {}).get("en"):
            errors.append(f"command {verb}: `sounds_like.en` is empty.")
        book = c.get("playbook", "")
        path = os.path.join(root, *book.split("/"))
        if not os.path.isfile(path):
            errors.append(f"command {verb}: playbook {book} not found.")
            continue
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        if len(body.encode("utf-8")) > PLAYBOOK_MAX_BYTES:
            errors.append(f"{book} is {len(body.encode('utf-8'))} bytes (> {PLAYBOOK_MAX_BYTES}).")
        for section in ("## Done", "## Without scripts"):
            if section not in body:
                errors.append(f"{book}: missing '{section}'.")
        for ref in c.get("refs", []):
            routed.add(ref)
            if not os.path.isfile(os.path.join(root, *ref.split("/"))):
                errors.append(f"command {verb}: reference {ref} not found.")
        for ref in re.findall(r"`(references/[^`\s]+\.md)", body):
            routed.add(ref)
            if not os.path.isfile(os.path.join(root, *ref.split("/"))):
                errors.append(f"{book}: names {ref}, which does not exist.")
    for ref in _reference_files(root):
        if ref in ("references/INDEX.md", "references/floor.md") or ref in routed:
            continue
        errors.append(f"{ref} is not reachable from any command (add it to a command's refs in commands/index.json).")
    for sig in index.get("signals", []):
        if sig.get("verb") not in verbs and not str(sig.get("verb", "")).startswith("{"):
            errors.append(f"signal {sig.get('id')}: unknown command {sig.get('verb')!r}.")
    floor = os.path.join(root, "references", "floor.md")
    if not os.path.isfile(floor):
        errors.append("references/floor.md not found.")
    elif os.path.getsize(floor) > FLOOR_MAX_BYTES:
        errors.append(f"references/floor.md is {os.path.getsize(floor)} bytes (> {FLOOR_MAX_BYTES}).")
    routing = _load_json(repo, "adapters/routing.json", errors)
    for role in (routing or {}).get("roles", []):
        for verb in role.get("verbs", []):
            if verb not in verbs:
                errors.append(f"role {role.get('name')}: unknown command {verb!r}.")


def main() -> int:
    repo, root = repo_dir(), skill_dir()
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
            errors.append(f"`name` '{name}' != directory '{os.path.basename(root)}'.")

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

    # budgets
    if len(text.encode("utf-8")) > SKILL_MAX_BYTES:
        errors.append(f"SKILL.md is {len(text.encode('utf-8'))} bytes (> {SKILL_MAX_BYTES}); move detail to a playbook.")
    if desc and len(desc) > DESCRIPTION_WARN_LEN:
        warnings.append(f"`description` is {len(desc)} chars; keep it under {DESCRIPTION_WARN_LEN} to leave room.")
    pos = text.find("## Invariants")
    if pos < 0 or pos > INVARIANTS_WITHIN:
        errors.append(f"'## Invariants' must start within the first {INVARIANTS_WITHIN} characters.")
    check_commands(root, repo, errors)

    # body size (progressive disclosure)
    if len(body) > BODY_WARN_CHARS:
        warnings.append(
            f"SKILL.md body is large ({len(body)} chars); move detail to references/."
        )

    # secrets
    if TOKEN_RE.search(text):
        errors.append("possible bot token / secret embedded in SKILL.md.")

    check_packaging(repo, name, errors, warnings)
    check_metadata_version(repo, fm or "", errors)

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
