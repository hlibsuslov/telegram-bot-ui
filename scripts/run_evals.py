#!/usr/bin/env python3
# run-checks:
"""Validate the eval set, or execute its activation cases against a host CLI.

  python scripts/run_evals.py                      # validate evals/evals.json (offline)
  python scripts/run_evals.py --execute --host claude [--ids P1,PUB4] [--limit 10] [--model M]
  python scripts/run_evals.py --execute --host codex --runs 3 --split validation --retry-timeouts
  python scripts/run_evals.py --execute --host codex --dry-run   # print the commands only

Validation checks structure, unique ids, coverage (every capability area has English,
Russian and no-method-named positives; negatives exist in both languages; every Bot API domain
in DOMAINS has 6-10 cases in en, ru and uk with positives and near misses; the required
behavioural topics and transfer tasks are present), that every `routes_to` path exists in
the skill folder, that a `fixture` names a folder in evals/fixtures, and that every id also
appears in the human-readable tables in evals/*.md.

Execution installs the skill into a throwaway project folder (never the user profile),
runs each activation prompt through the host's non-interactive mode with write tools
disabled, and records whether the agent loaded the skill and WHICH copy it loaded. It
spends the account's usage and needs the CLI to be logged in. Results go to
evals/results/<date>T<HHMMSS>-<host>-<runid>.json and are never merged into evals.json
automatically. Behavioural tasks run and are graded by scripts/run_behavioral.py (an LLM judge
with the fixed prompt evals/judge.md); this script only validates them (role, fixture, rubric).

Isolation, so a user-level copy of the skill cannot answer for the project copy:
  claude  --setting-sources project,local drops the user settings, user skills and user
          plugins (login is untouched); the throwaway project lives outside the home folder
          because Claude Code also collects `.claude/skills` from every parent folder.
  codex   the child gets an empty HOME/USERPROFILE (hides ~/.agents/skills where Codex honours
          it) and CODEX_HOME set to the real Codex home (login keeps working; no auth file is
          read or copied). Codex still loads `$CODEX_HOME/skills` and, on Windows, resolves
          ~/.agents/skills from the OS profile, so any copy of the skill found there is switched
          off for the run with `-c skills.config=[{path=..., enabled=false}]` (the file is
          never touched).
Whatever the isolation misses is caught by the loaded-copy check: the path of the
SKILL.md that was really loaded is classified `project`, `other` or `none` (`unknown` when
the skill was called but no path shows); any `other` or `unknown`, or a run that errored,
makes the summary `"valid": false` and the exit code 3.

A timeout is not a miss: the run is not scored (`ok` null) and is counted under `timeouts`.
Unresolved timeouts also make the summary invalid; `--retry-timeouts [N]` re-runs a timed-out
run up to N times and the last attempt counts, so the results are valid once a retry finishes.

A case with `"fixture": "<name>"` runs in a project that holds a copy of evals/fixtures/<name>
(a small bot), for requests that only make sense inside a bot repository.

Per activated positive the runner also records the first skill file read after SKILL.md, the
first commands/<verb>.md playbook read, and whether the case is routed: its first read is one
of the case's `routes_to`, or its first playbook is one or names one in its `refs` in
skills/telegram-bot-ui/commands/index.json. Plus token counts.

Exit codes: 0 all cases correct and valid; 1 some case missed; 2 host CLI not found;
3 results not trustworthy (another copy loaded, a run errored or timed out without a retry).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(ROOT, "evals", "evals.json")
SKILL_NAME = "telegram-bot-ui"
SKILL_DIR = os.path.join(ROOT, "skills", SKILL_NAME)
PLAYBOOK_INDEX = os.path.join(SKILL_DIR, "commands", "index.json")
FIXTURES = os.path.join(ROOT, "evals", "fixtures")
FIXTURE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
CAPABILITY_AREAS = ("ui", "use-cases", "publishing", "agent-ops", "widgets", "api-lookup", "mini-apps")
LANGS = ("en", "ru")              # every area needs positives in these
ALLOWED_LANGS = LANGS + ("uk",)    # extra languages a case may use
REQUIRED_BEHAVIORAL = ("B20", "B21", "B22", "B30", "B31", "B32", "B40", "B41", "B42",
                       "B50", "B51", "B52", "B60")
# The agent role a behavioural task exercises (agents/claude/telegram-<role>.md); results aggregate per role.
ROLES = ("designer", "builder", "reviewer", "publisher", "widget-builder")
TRANSFER_AREAS = ("publishing", "agent-ops", "widgets", "use-cases", "api-lookup")
# Bot API domains with agent cards (data/bot-api/agent-notes/<domain>.json), plus payments and Mini App
# events: each needs 6-10 cases in every allowed language, positives and near misses.
DOMAINS = ("messages", "editing", "bot-settings", "chat-admin", "chat-info", "forums", "business", "stickers",
           "platform", "inline-widgets", "payments", "rich", "mini-app-events")
DOMAIN_CASES = (6, 10)
SPLITS = ("train", "validation", "all")
TRAIN_PERCENT = 60


def load() -> dict:
    with open(EVALS, encoding="utf-8") as fh:
        return json.load(fh)


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _str_list(v, allow_empty=False) -> bool:
    return isinstance(v, list) and (allow_empty or bool(v)) and all(_nonempty_str(x) for x in v)


def validate(data: dict, md_text: str | None = None) -> list[str]:
    errors: list[str] = []
    for key in ("version", "skill", "areas", "runs", "activation", "behavioral"):
        if key not in data:
            errors.append(f"missing top-level key '{key}'")
    if errors:
        return errors
    areas = set(data["areas"])
    seen: set[str] = set()

    def check_id(item, where):
        cid = item.get("id")
        if not _nonempty_str(cid):
            errors.append(f"{where}: missing id")
            return "?"
        if cid in seen:
            errors.append(f"duplicate id {cid}")
        seen.add(cid)
        return cid

    def check_fixture(item, cid):
        if "fixture" in item:
            fixture = item["fixture"]
            if not (isinstance(fixture, str) and FIXTURE_NAME.fullmatch(fixture)
                    and os.path.isdir(os.path.join(FIXTURES, fixture))):
                errors.append(f"{cid}: fixture must name a folder in evals/fixtures: {fixture!r}")

    for a in data["activation"]:
        cid = check_id(a, "activation")
        if a.get("area") not in areas:
            errors.append(f"{cid}: unknown area {a.get('area')!r}")
        if a.get("lang") not in ALLOWED_LANGS:
            errors.append(f"{cid}: lang must be one of {ALLOWED_LANGS}")
        if not _nonempty_str(a.get("prompt")):
            errors.append(f"{cid}: empty prompt")
        if a.get("expect") not in ("activate", "skip"):
            errors.append(f"{cid}: expect must be activate|skip")
        if not isinstance(a.get("names_method"), bool):
            errors.append(f"{cid}: names_method must be boolean")
        if not _str_list(a.get("routes_to"), allow_empty=True):
            errors.append(f"{cid}: routes_to must be a list of paths")
        else:
            for route in a["routes_to"]:
                if not os.path.exists(os.path.join(SKILL_DIR, *route.split("/"))):
                    errors.append(f"{cid}: routes_to path does not exist in the skill: {route}")
        check_fixture(a, cid)
        if a.get("expect") == "skip" and (a.get("area") != "out-of-scope" or a.get("routes_to")):
            errors.append(f"{cid}: negative cases use area out-of-scope and no routes")
        if a.get("expect") == "activate" and (a.get("area") == "out-of-scope" or not a.get("routes_to")):
            errors.append(f"{cid}: positive cases need a capability area and routes_to")

    pos = [a for a in data["activation"] if a.get("expect") == "activate"]
    neg = [a for a in data["activation"] if a.get("expect") == "skip"]
    for area in CAPABILITY_AREAS:
        mine = [a for a in pos if a.get("area") == area]
        for lang in LANGS:
            if not any(a.get("lang") == lang for a in mine):
                errors.append(f"coverage: no {lang} positive activation case for area {area}")
        if not any(a.get("names_method") is False for a in mine):
            errors.append(f"coverage: area {area} has no positive case that avoids method names")
    for lang in LANGS:
        if not any(a.get("lang") == lang for a in neg):
            errors.append(f"coverage: no {lang} negative activation case")
    for a in data["activation"]:
        if "domain" in a and a["domain"] not in DOMAINS:
            errors.append(f"{a.get('id')}: unknown domain {a['domain']!r}")
    low, high = DOMAIN_CASES
    for domain in DOMAINS:
        mine = [a for a in data["activation"] if a.get("domain") == domain]
        if not low <= len(mine) <= high:
            errors.append(f"coverage: domain {domain} has {len(mine)} case(s), needs {low}-{high}")
        missing = [lang for lang in ALLOWED_LANGS if not any(a.get("lang") == lang for a in mine)]
        if missing:
            errors.append(f"coverage: domain {domain} has no case in {', '.join(missing)}")
        for expect, what in (("activate", "positive"), ("skip", "near miss")):
            if not any(a.get("expect") == expect for a in mine):
                errors.append(f"coverage: domain {domain} has no {what}")

    behavioral_ids: dict[str, dict] = {}
    for b in data["behavioral"]:
        cid = check_id(b, "behavioral")
        behavioral_ids[cid] = b
        if b.get("area") not in areas or b.get("area") == "out-of-scope":
            errors.append(f"{cid}: behavioural area must be a capability area")
        if b.get("role") not in ROLES:
            errors.append(f"{cid}: role must be one of {ROLES}")
        check_fixture(b, cid)
        if b.get("lang") not in ALLOWED_LANGS:
            errors.append(f"{cid}: lang must be one of {ALLOWED_LANGS}")
        for key in ("request", "context"):
            if not _nonempty_str(b.get(key)):
                errors.append(f"{cid}: empty {key}")
        for key in ("must", "critical_failures"):
            if not _str_list(b.get(key)):
                errors.append(f"{cid}: {key} must be a non-empty list of strings")
        if "transfer" in b:
            t = b["transfer"]
            if not isinstance(t, dict) or not _nonempty_str(t.get("variation")):
                errors.append(f"{cid}: transfer needs a variation")
    for b in data["behavioral"]:
        of = (b.get("transfer") or {}).get("of")
        if of and of not in behavioral_ids:
            errors.append(f"{b.get('id')}: transfer.of refers to unknown id {of}")
    for cid in REQUIRED_BEHAVIORAL:
        if cid not in behavioral_ids:
            errors.append(f"coverage: required behavioural task {cid} missing")
    for area in TRANSFER_AREAS:
        if not any(b.get("transfer") and b.get("area") == area for b in data["behavioral"]):
            errors.append(f"coverage: no transfer task for area {area}")

    for r in data["runs"]:
        for key in ("date", "host", "model", "skill_commit", "cases", "results_file"):
            if key not in r:
                errors.append(f"runs entry missing '{key}'")

    if md_text is not None:
        for cid in sorted(seen):
            if f"| {cid} |" not in md_text:
                errors.append(f"{cid}: not listed in evals/*.md tables")
    return errors


def md_tables() -> str:
    parts = []
    for name in ("activation-evals.md", "behavioral-evals.md"):
        with open(os.path.join(ROOT, "evals", name), encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


# ---------------------------------------------------------------- case selection

def split_of(case_id: str) -> str:
    """Deterministic 60/40 split by a hash of the id: stable across runs, machines and new cases."""
    bucket = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16) % 100
    return "train" if bucket < TRAIN_PERCENT else "validation"


def select_cases(cases: list[dict], ids: str | None, split: str, limit: int | None) -> list[dict]:
    if ids:
        wanted = set(ids.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    if split != "all":
        cases = [c for c in cases if split_of(c["id"]) == split]
    return cases[:limit] if limit else cases


def passes(correct_runs: int, runs: int) -> bool:
    """A case passes when at least ceil(N/2) of its runs are correct."""
    return correct_runs >= math.ceil(runs / 2)


def result_filename(host: str, run_id: str, when: float | None = None) -> str:
    stamp = time.strftime("%Y-%m-%dT%H%M%S", time.gmtime(when))
    return f"{stamp}-{host}-{run_id}.json"


# ---------------------------------------------------------------- reading a transcript

READ_ONLY_DENY = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch"
CLAUDE_ISOLATION = ["--setting-sources", "project,local"]
BASE_DIR = re.compile(r"Base directory for this skill:[ \t]*([^\r\n]+)")
READ_VERB = re.compile(r"\b(cat|sed|head|tail|less|more|nl|bat|type|get-content|gc|rg|grep|awk|"
                       r"select-string|sls)\b", re.I)
SKILL_PATH = re.compile(r"""[^\s'"`|;&<>()=,]*telegram-bot-ui/[^\s'"`|;&<>()=,]+""")
# A path in a shell command: quoted without nested quotes (spaces allowed, taken whole) or bare. Quoted
# first, so "C:/Users/Some One/.codex/skills/telegram-bot-ui/SKILL.md" is not cut down to a relative tail.
COMMAND_PATH = re.compile(r"""(?P<q>["'])(?P<quoted>[^"']*telegram-bot-ui/[^"']+)(?P=q)|(?P<bare>"""
                          + SKILL_PATH.pattern + ")")
PATH_START = re.compile(r"^(?:[A-Za-z]:/|/|~|\$|%|\.{0,2}/)")   # a quoted string that is a path, not a command line
TOKENS_USED = re.compile(r"tokens used\s*[:\n]\s*([\d,]+)", re.I)


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _events(output: str):
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def _slashes(path: str) -> str:
    return re.sub(r"[\\/]+", "/", path)


def _canon(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def inside(path: str, folder: str) -> bool:
    p, f = _canon(path), _canon(folder)
    return p == f or p.startswith(f + os.sep)


def skill_relative(path: str) -> str | None:
    """`.../telegram-bot-ui/references/x.md` -> `references/x.md`; None outside a skill folder."""
    norm = "/" + _slashes(path)
    marker = f"/{SKILL_NAME}/"
    at = norm.rfind(marker)
    if at == -1:
        return None
    return norm[at + len(marker):] or None


def _skill_dir_of(path: str) -> str:
    """Folder of the skill a SKILL.md path belongs to."""
    return _slashes(path).rsplit("/", 1)[0]


def _codex_read_paths(command: str) -> list[str]:
    """Skill files a shell command reads (cat / sed / Get-Content ...), in order."""
    if not READ_VERB.search(command):
        return []
    paths: list[str] = []
    for m in COMMAND_PATH.finditer(_slashes(command)):
        quoted = m.group("quoted")
        if quoted is None:
            paths.append(m.group("bare"))
        elif PATH_START.match(quoted):
            paths.append(quoted)
        else:   # a quoted command line such as "cat path": read the paths inside it
            paths.extend(SKILL_PATH.findall(quoted))
    return [p for p in paths if re.search(r"\.[A-Za-z0-9]{1,5}$", p)]


def analyze_output(host: str, output: str, project: str | None) -> dict:
    """What a transcript shows: activation, which copy loaded, the skill files read after
    SKILL.md, tokens and whether the run finished. Pure: no I/O besides path resolution."""
    steps: list[tuple[str, str]] = []   # ("skill", "") | ("loaded", dir) | ("read", path)
    model, tokens, finished, error = None, None, False, None
    codex_usage = {"input": 0, "output": 0, "cached": 0}
    saw_codex_usage = False
    for event in _events(output):
        kind = event.get("type")
        if host == "claude":
            if kind == "system" and event.get("subtype") == "init":
                model = event.get("model") or model
            if kind == "result":
                finished = True
                usage = event.get("usage") or {}
                cached = usage.get("cache_read_input_tokens") or 0
                if usage:
                    tokens = {"input": (usage.get("input_tokens") or 0) + cached
                              + (usage.get("cache_creation_input_tokens") or 0),
                              "output": usage.get("output_tokens") or 0, "cached": cached}
                if event.get("is_error"):
                    error = str(event.get("result") or event.get("subtype") or "error")[:200]
            for node in _walk(event):
                if node.get("type") != "tool_use":
                    continue
                inp = node.get("input") or {}
                if node.get("name") == "Skill" and SKILL_NAME in json.dumps(inp):
                    steps.append(("skill", ""))
                elif node.get("name") == "Read":
                    steps.append(("read", str(inp.get("file_path", ""))))
            if kind == "user":
                for text in _strings(event):
                    for found in BASE_DIR.findall(text):
                        if SKILL_NAME in found.lower():
                            steps.append(("loaded", found.strip().strip("'\"")))
        else:
            if kind == "turn.completed":
                finished, saw_codex_usage = True, True
                usage = event.get("usage") or {}
                codex_usage["input"] += usage.get("input_tokens") or 0
                codex_usage["output"] += usage.get("output_tokens") or 0
                codex_usage["cached"] += usage.get("cached_input_tokens") or 0
            elif kind in ("turn.failed", "error"):
                error = str(event.get("message") or event.get("error") or kind)[:200]
            for node in _walk(event):
                command = node.get("command") or node.get("cmd")
                if isinstance(command, list):
                    command = " ".join(str(c) for c in command)
                if isinstance(command, str):
                    steps.extend(("read", p) for p in _codex_read_paths(command))
    if host == "codex":
        if saw_codex_usage:
            tokens = codex_usage
        elif (m := TOKENS_USED.search(output)):
            tokens = {"total": int(m.group(1).replace(",", ""))}
            finished = True

    loaded: list[str] = []
    first_load = None
    for i, (kind, value) in enumerate(steps):
        if kind == "loaded":
            found = value
        elif kind == "read" and os.path.basename(_slashes(value)) == "SKILL.md" and SKILL_NAME in value:
            found = _skill_dir_of(value)
        elif kind == "skill":
            found = None
        else:
            continue
        if first_load is None:
            first_load = i
        if found and found not in loaded:
            loaded.append(found)

    def project_copy(path: str) -> bool:
        if project is None:
            return False
        if host == "codex" and not os.path.isabs(path) and not path.startswith(("~", "$")):
            return inside(os.path.join(project, path), project)   # relative to the child's folder; `..` can leave it
        return inside(path, project)

    activated = first_load is not None
    if not activated:
        copy = "none"
    elif not loaded:
        copy = "unknown"
    elif any(not project_copy(p) for p in loaded):
        copy = "other"
    else:
        copy = "project"

    reads: list[str] = []
    if first_load is not None:
        for kind, value in steps[first_load:]:
            rel = skill_relative(value) if kind == "read" else None
            if rel and rel != "SKILL.md":
                reads.append(rel)
    return {"activated": activated, "copy": copy, "loaded": loaded, "reads": reads,
            "tokens": tokens, "model": model, "finished": finished, "error": error}


def skill_loaded(host: str, output: str) -> bool:
    """Did the transcript load the skill? Claude: a Skill call or a read of its SKILL.md."""
    return analyze_output(host, output, None)["activated"]


def playbook_refs(index_path: str = PLAYBOOK_INDEX) -> dict[str, list[str]]:
    """commands/<verb>.md -> reference paths it names, from commands/index.json when it exists.

    The skill's index is {"commands": [{"verb", "playbook", "refs"}]}; also accepted: {verb: {refs}},
    {"commands": {verb: {refs}}} or a list of {"verb"|"name"|"id", "playbook"|"file"|"path", "refs"}
    (the playbook defaults to commands/<verb>.md)."""
    try:
        with open(index_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    entries = data.get("commands", data) if isinstance(data, dict) else data
    if isinstance(entries, dict):
        entries = [{"verb": k, **v} for k, v in entries.items() if isinstance(v, dict)]
    out: dict[str, list[str]] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("refs"), list):
            continue
        verb = entry.get("verb") or entry.get("name") or entry.get("id")
        file = (entry.get("playbook") or entry.get("file") or entry.get("path")
                or (f"commands/{verb}.md" if verb else None))
        if file:
            out[_slashes(str(file))] = [_slashes(str(r)) for r in entry["refs"]]
    return out


def _route_match(rel: str, route: str) -> bool:
    return rel.startswith(route) if route.endswith("/") else rel == route


def first_playbook(reads: list[str]) -> str | None:
    """The first commands/<verb>.md read: the command the agent picked (commands/index.json is the table)."""
    return next((r for r in reads if r.startswith("commands/") and r.endswith(".md")), None)


def route_check(reads: list[str], routes_to: list[str], playbooks: dict[str, list[str]]) -> tuple[str | None, bool]:
    """(first skill file read after SKILL.md, whether the case is routed correctly).

    Routed: the case's route is SKILL.md itself (loading the skill is enough); or the first file read is a
    route; or the first playbook read is a route or names one in its index `refs`. The router's choice is
    the first playbook, so a wrong playbook stays a miss even if the right reference is read later."""
    first = reads[0] if reads else None
    if "SKILL.md" in routes_to:
        return first, True
    if first is None:
        return None, False
    if any(_route_match(first, r) for r in routes_to):
        return first, True
    book = first_playbook(reads)
    if book is None:
        return first, False
    named = [book, *playbooks.get(book, [])]
    return first, any(_route_match(ref, r) for ref in named for r in routes_to)


# ---------------------------------------------------------------- running a host

def host_command(host: str, prompt: str, project: str, model: str | None, via_stdin: bool = False,
                 hidden_copies: list[str] | None = None) -> list[str]:
    """The child command. With via_stdin the prompt is sent on stdin instead of argv: Windows
    npm shims (.cmd) cannot carry newlines or quotes in an argument. hidden_copies (Codex) are
    SKILL.md paths of user-level copies to switch off for this run."""
    if host == "claude":
        model_args = ["--model", model] if model else []
        return ["claude", *model_args, "-p", *([] if via_stdin else [prompt]),
                "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                *CLAUDE_ISOLATION, "--disallowedTools", READ_ONLY_DENY]
    if host == "codex":
        model_args = ["-m", model] if model else []
        # TOML literal strings (single quotes) survive the Windows .cmd shim; double quotes would not.
        hide = ["-c", "skills.config=[" + ", ".join(f"{{path='{p}', enabled=false}}" for p in hidden_copies) + "]"
                ] if hidden_copies else []
        return ["codex", "exec", *model_args, *hide, "--json", "--skip-git-repo-check", "--ephemeral",
                "-s", "read-only", "-C", project, "-" if via_stdin else prompt]
    raise ValueError(f"unsupported host {host}")


def codex_home() -> str:
    return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def user_level_copies(host: str) -> list[str]:
    """SKILL.md of user-level copies of the skill that Codex would load next to the project copy
    ($CODEX_HOME/skills and ~/.agents/skills). Found on disk, never read, never changed."""
    if host != "codex":
        return []
    bases = (os.path.join(codex_home(), "skills"), os.path.join(os.path.expanduser("~"), ".agents", "skills"))
    found = [os.path.join(base, SKILL_NAME, "SKILL.md").replace("\\", "/") for base in bases]
    return [p for p in dict.fromkeys(found) if os.path.isfile(p) and "'" not in p]


def child_env(host: str, empty_home: str) -> dict[str, str]:
    env = dict(os.environ)
    if host == "codex":
        # A fresh HOME hides ~/.agents/skills; CODEX_HOME keeps the login. Only the folder is named.
        env.update(HOME=empty_home, USERPROFILE=empty_home, CODEX_HOME=codex_home())
        env.pop("HOMEDRIVE", None)
        env.pop("HOMEPATH", None)
    return env


def private_folder(path: str) -> bool:
    """Leave the current user as the only one with access: ProgramData, Public and the drive root let
    other local users add files, and a project folder that others can write to could carry a hook."""
    if os.name != "nt":
        return True
    user = os.environ.get("USERNAME")
    if not user:
        return False
    domain = os.environ.get("USERDOMAIN")
    who = domain + "\\" + user if domain else user
    done = subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", f"{who}:(OI)(CI)F"], capture_output=True)
    return done.returncode == 0


def make_root() -> str:
    """A new temp folder outside the real home folder: Claude Code collects `.claude/skills` from
    every parent of the working folder, so a project under ~ would still see ~/.claude/skills."""
    home = os.path.expanduser("~")
    system_drive = os.environ.get("SystemDrive")
    for base in (tempfile.gettempdir(), os.environ.get("ProgramData"), os.environ.get("PUBLIC"),
                 system_drive + os.sep if system_drive else None):
        if not base or inside(base, home):
            continue
        try:
            root = tempfile.mkdtemp(prefix="tgui-evals-", dir=base)
        except OSError:
            continue
        if private_folder(root):
            return root
        shutil.rmtree(root, ignore_errors=True)
    print("warning: no private temp folder outside the home folder; using one under it, "
          "so a user-level copy of the skill may be visible to the runs.")
    return tempfile.mkdtemp(prefix="tgui-evals-")


def copy_fixture(name: str, project: str) -> None:
    """Copy evals/fixtures/<name> (a small bot project) into the run's project folder."""
    shutil.copytree(os.path.join(FIXTURES, name), project, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def prepare_workspace(host: str, fixture: str | None = None) -> tuple[str, str, str]:
    """(root, project, home): the skill installed in the project (a copy of the fixture, if any);
    home stays empty."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import install  # noqa: PLC0415

    root = make_root()
    project, home = os.path.join(root, "project"), os.path.join(root, "home")
    os.makedirs(project)
    os.makedirs(home)
    if fixture:
        copy_fixture(fixture, project)
    inst = install.Installer(home=home, project=project, dry_run=False, link=False)
    inst.install(host, "project", agents=False, instructions=False)
    if shutil.which("git"):
        subprocess.run(["git", "init", "-q", project], check=False)
    return root, project, home


def remove_tree(path: str) -> None:
    def make_writable(func, target, _exc):   # git objects are read-only on Windows
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)
    else:
        shutil.rmtree(path, onerror=make_writable)


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":   # the .cmd shim spawns the real CLI as a child
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        proc.kill()


def run_error(info: dict, status: int | str) -> str | None:
    """Why a run is not clean, or None: a transcript that ends well still fails when the CLI exits non-zero."""
    if info["error"]:
        return info["error"]
    if status == "timeout":
        return "timeout"
    if not info["finished"]:
        return f"no final event (exit {status})"
    return f"exit {status} after the final event" if status else None


def run_child(cmd: list[str], stdin_text: str, cwd: str, env: dict, timeout: int) -> tuple[str, int | str]:
    # Windows npm installs the CLI as a .cmd shim that CreateProcess can't find by name.
    cmd = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
    # Bytes in and out: text mode would turn the prompt's newlines into CRLF on Windows.
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    status: int | str = "timeout"
    try:
        out, err = proc.communicate(stdin_text.encode("utf-8"), timeout=timeout)
        status = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
    return (out + err).decode("utf-8", errors="replace"), status


def tool_version(host: str) -> str:
    try:
        proc = subprocess.run([shutil.which(host) or host, "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30, check=False)
        return (proc.stdout or proc.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def skill_git_state() -> tuple[str, bool]:
    """(short HEAD commit, whether skills/telegram-bot-ui has uncommitted changes)."""
    def git(*args: str) -> str:
        try:
            proc = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=30, check=False)
            return proc.stdout.strip() if proc.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""
    return git("rev-parse", "--short", "HEAD") or "unknown", bool(git("status", "--porcelain", "--", SKILL_DIR))


def score_run(case: dict, info: dict, status: int | str, playbooks: dict[str, list[str]]) -> dict:
    """One attempt's record. A timeout is not a miss: `ok` and `route_ok` stay None (not scored); an error
    the transcript shows (usage limit, crash) still wins over the timeout and is an error."""
    timed_out = status == "timeout" and not info["error"]
    error = None if timed_out else run_error(info, status)
    first_read, route_ok = info["reads"][0] if info["reads"] else None, None
    if info["activated"] and case["expect"] == "activate" and not timed_out:
        first_read, route_ok = route_check(info["reads"], case["routes_to"], playbooks)
    ok = None if timed_out else (not error and info["activated"] == (case["expect"] == "activate"))
    return {"activated": info["activated"], "ok": ok, "copy": info["copy"], "loaded": info["loaded"],
            "first_read": first_read, "playbook": first_playbook(info["reads"]), "route_ok": route_ok,
            "tokens": info["tokens"], "error": error, "timed_out": timed_out, "exit": status}


def describe_run(case: dict, run: dict, label: str) -> str:
    route = "-" if run["route_ok"] is None else (
        "ok" if run["route_ok"] else f"MISS first={run['first_read']} playbook={run['playbook']}")
    verdict = "TIMEOUT" if run["timed_out"] else ("ok" if run["ok"] else "MISS")
    return (f"{case['id']:<6} {label} expect={case['expect']:<8} activated={run['activated']!s:<5} "
            f"copy={run['copy']:<7} route={route} {verdict}" + (f" ERROR {run['error']}" if run["error"] else ""))


def run_case(case: dict, runs: int, attempt, retry_timeouts: int = 0, log=print) -> dict:
    """Run a case `runs` times; a run whose attempt timed out is retried up to `retry_timeouts` times and
    the last attempt is scored. Every attempt's loaded copy is kept (`attempt_copies`): a skill copy
    outside the temp project taints validity even when a later retry loaded the right one. The case passes on a majority of its scored (not timed-out) runs; with no
    scored run it has no verdict (`ok` None)."""
    case_runs = []
    for n in range(1, runs + 1):
        attempts: list[dict] = []
        while not attempts or (attempts[-1]["timed_out"] and len(attempts) <= retry_timeouts):
            attempts.append(attempt())
            retry = f" retry {len(attempts) - 1}/{retry_timeouts}" if len(attempts) > 1 else ""
            log(describe_run(case, attempts[-1], f"run {n}/{runs}{retry}"))
        case_runs.append({**attempts[-1], "attempts": len(attempts),
                          "timeouts": sum(a["timed_out"] for a in attempts),
                          "attempt_copies": [a["copy"] for a in attempts]})
    scored = [r for r in case_runs if r["ok"] is not None]
    correct = sum(r["ok"] for r in scored)
    return {"id": case["id"], "expect": case["expect"], "ok": passes(correct, len(scored)) if scored else None,
            "correct_runs": correct, "scored_runs": len(scored), "runs": case_runs}


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def summarize(results: list[dict]) -> dict:
    """Case-level counts, route accuracy, mean tokens, copies, timeouts and validity from per-case results.
    Cases without a verdict (every run timed out) are `unscored`, never a false positive or negative."""
    flat = [r for case in results for r in case["runs"]]
    copies = {k: sum(r["copy"] == k for r in flat) for k in ("project", "other", "none", "unknown")}
    # A retry replaces the scored attempt, never the copy an earlier attempt loaded.
    earlier = [c for r in flat for c in r.get("attempt_copies", [r["copy"]])[:-1]]
    tainted = {k: copies[k] + earlier.count(k) for k in ("other", "unknown")}
    errors = sum(bool(r["error"]) for r in flat)
    unresolved = sum(bool(r.get("timed_out")) for r in flat)
    timeouts = {"unresolved": unresolved,
                "retried": sum(bool(r.get("timeouts")) and not r.get("timed_out") for r in flat),
                "attempts": sum(r.get("timeouts", int(bool(r.get("timed_out")))) for r in flat)}
    routed = [r for case in results if case["expect"] == "activate" for r in case["runs"]
              if r["activated"] and r["route_ok"] is not None]
    with_tokens = [r["tokens"] for r in flat if r["tokens"] and "input" in r["tokens"]]
    reasons = []
    if tainted["other"]:
        reasons.append(f"{tainted['other']} attempt(s) loaded a copy of the skill outside the temp project")
    if tainted["unknown"]:
        reasons.append(f"{tainted['unknown']} attempt(s) activated but the loaded copy could not be identified")
    if errors:
        reasons.append(f"{errors} run(s) errored")
    if unresolved:
        reasons.append(f"{unresolved} run(s) timed out without a finished retry (not counted as misses)")
    return {
        "cases": len(results), "correct": sum(c["ok"] is True for c in results),
        "true_positive": sum(c["expect"] == "activate" and c["ok"] is True for c in results),
        "false_positive": sum(c["expect"] == "skip" and c["ok"] is False for c in results),
        "false_negative": sum(c["expect"] == "activate" and c["ok"] is False for c in results),
        "unscored": sum(c["ok"] is None for c in results),
        "copies": copies, "errors": errors, "timeouts": timeouts,
        "route_accuracy": {"correct": sum(bool(r["route_ok"]) for r in routed), "of": len(routed)},
        "mean_tokens": ({"input": _mean([t["input"] for t in with_tokens]),
                         "output": _mean([t["output"] for t in with_tokens]), "runs": len(with_tokens)}
                        if with_tokens else None),
        "valid": not reasons, "invalid_reasons": reasons}


def print_command(cmd: list[str], prompt: str) -> None:
    print(" ".join(json.dumps(c) if " " in c else c for c in cmd))
    print(f"  stdin: {json.dumps(prompt, ensure_ascii=False)}")


def execute(cases: list[dict], host: str, model: str | None, timeout: int, dry_run: bool,
            runs: int = 1, split: str = "all", retry_timeouts: int = 0) -> int:
    if not dry_run and not shutil.which(host):
        print(f"{host} CLI not found on PATH; nothing executed.")
        return 2
    hidden = user_level_copies(host)
    if dry_run:
        for case in cases:
            print_command(host_command(host, case["prompt"], "<temp-project>", model, True, hidden),
                          case["prompt"])
            if case.get("fixture"):
                print(f"  fixture: evals/fixtures/{case['fixture']} copied into the temp project")
        return 0
    for path in hidden:
        print(f"note: switching off the user-level copy {path} for these runs (file untouched).")
    playbooks = playbook_refs()
    workspaces: dict[str | None, tuple[str, str, str]] = {}   # fixture -> (root, project, home)
    results, models = [], []
    try:
        for case in cases:
            fixture = case.get("fixture")
            if fixture not in workspaces:
                workspaces[fixture] = prepare_workspace(host, fixture)
            _, project, home = workspaces[fixture]
            env = child_env(host, home)

            def attempt(case=case, project=project, env=env) -> dict:
                start = time.time()
                output, status = run_child(host_command(host, case["prompt"], project, model, True, hidden),
                                           case["prompt"], project, env, timeout)
                info = analyze_output(host, output, project)
                models.append(info["model"])
                return {**score_run(case, info, status, playbooks), "seconds": round(time.time() - start, 1)}

            results.append(run_case(case, runs, attempt, retry_timeouts, log=lambda text: print(text, flush=True)))
    finally:
        for root, _, _ in workspaces.values():
            remove_tree(root)

    commit, dirty = skill_git_state()
    run_id = uuid.uuid4().hex[:6]
    now = time.time()
    summary = {"run_id": run_id, "date": time.strftime("%Y-%m-%d", time.gmtime(now)),
               "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "host": host,
               "cli_version": tool_version(host), "model": model or "default",
               "model_reported": next((m for m in models if m), None), "runs_per_case": runs,
               "split": split, "timeout_seconds": timeout, "retry_timeouts": retry_timeouts,
               "skill_commit": commit, "skill_dirty": dirty, **summarize(results), "results": results}
    out_dir = os.path.join(ROOT, "evals", "results")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, result_filename(host, run_id, now))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    route, tokens, waits = summary["route_accuracy"], summary["mean_tokens"], summary["timeouts"]
    print(f"\n{summary['correct']}/{len(results)} correct (TP {summary['true_positive']}, "
          f"FP {summary['false_positive']}, FN {summary['false_negative']}, unscored {summary['unscored']}); "
          f"route {route['correct']}/{route['of']}; "
          f"timeouts {waits['attempts']} (retried {waits['retried']}, unresolved {waits['unresolved']}); "
          + (f"mean tokens in {tokens['input']} out {tokens['output']}; " if tokens else "tokens n/a; ")
          + f"copies {summary['copies']}; wrote {out}")
    if not summary["valid"]:
        print("INVALID RESULTS, do not compare: " + "; ".join(summary["invalid_reasons"])
              + ("" if retry_timeouts or not waits["unresolved"] else "; rerun with --retry-timeouts"))
        return 3
    return 0 if summary["correct"] == len(results) else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--execute", action="store_true", help="run activation cases against a host CLI")
    ap.add_argument("--host", choices=("claude", "codex"), default="claude")
    ap.add_argument("--ids", help="comma-separated case ids (default: all activation cases)")
    ap.add_argument("--split", choices=SPLITS, default="all",
                    help="deterministic 60/40 train/validation split by a hash of the case id")
    ap.add_argument("--runs", type=int, default=1, help="runs per case; a case passes when >= ceil(N/2) are correct")
    ap.add_argument("--limit", type=int, help="run at most N cases")
    ap.add_argument("--model", help="model passed to the host CLI")
    ap.add_argument("--timeout", type=int, default=240, help="seconds per run")
    ap.add_argument("--retry-timeouts", type=int, nargs="?", const=1, default=0, metavar="N",
                    help="re-run a timed-out run up to N times (bare flag: once); the run is valid if a retry finishes")
    ap.add_argument("--dry-run", action="store_true", help="with --execute: print commands only")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.runs < 1:
        ap.error("--runs must be at least 1")
    if args.retry_timeouts < 0:
        ap.error("--retry-timeouts must be 0 or more")

    data = load()
    errors = validate(data, md_tables())
    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors))
        print(f"\n{len(errors)} error(s) in evals/evals.json.")
        return 1
    n_act, n_beh = len(data["activation"]), len(data["behavioral"])
    print(f"OK: evals.json valid ({n_act} activation, {n_beh} behavioural cases, "
          f"{len(data['runs'])} recorded agent run(s)).")
    if not args.execute:
        return 0
    cases = select_cases(data["activation"], args.ids, args.split, args.limit)
    return execute(cases, args.host, args.model, args.timeout, args.dry_run, args.runs, args.split,
                   args.retry_timeouts)


if __name__ == "__main__":
    sys.exit(main())
