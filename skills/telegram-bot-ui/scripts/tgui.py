#!/usr/bin/env python3
"""One offline entry point for the telegram-bot-ui skill (standard library only, no bot token).

  py -3 <skill>/scripts/tgui.py <group> ...        (python3 outside Windows)

Project state (read and written in the user's bot repository, --root, default "."):
  context  [--refresh] [--json]       saved facts, map, findings, Studio requests, signals (<= 2 KB)
  next     [--json]                   the 2-3 best next commands for this project, with reasons
  doctor   [--json] [--fix]           skill copies and versions, catalog age, context and map health
  findings add|close|list             audit findings in bot-ui/context/findings.json
  requests list|add|take|done|reject  Studio requests in bot-ui/context/requests/
  check    changed                    validators for every changed Telegram file (git)
  hook     post-edit|install|uninstall  quiet check after an edit; opt-in Claude Code hook

Tools (pass-through to the skill's scripts; every group takes --help):
  lookup   show|search|accepts|skeleton|since|version   Bot API catalog
  webapp   show|search|since|gates|theme|meta|check|sync  Telegram.WebApp catalog
  check    payload|keyboard|rich|widget|copy|icons|miniapp|refs FILE ...
  examples --query "<intent>" [--context ...] [--json]
  profile  probe|scaffold|check                         style profile
  map      init|import|list|show|validate|patch|set|apply-patch|simulate|render|build|studio|
           export-snapshot|inventory|emoji              bot-ui map (no Telegram, no token)
  post     validate|preview|publish                     channel posts (dry run by default)
  emoji    resolve|suggest|verify|capture|apply|strip   premium emoji packs
  widget   build|preview|lint|design                    HTML widgets
  miniapp  lint|rework|layout|style|preview|star        Mini Apps
  data     SPEC                                         data views split into messages
  agent    notify|progress|ask|approve|send-file|report|listen   the agent's own bot
  sync     bot-api|webapp                               refresh a catalog (the only network use)

Exit codes: 0 ok, 1 findings or validation errors, 2 usage, 3 revision conflict, 4 refused.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPTS)
INDEX = os.path.join(SKILL, "commands", "index.json")
CONTEXT_SCHEMA = "bot-ui-context/v1"
FINDINGS_SCHEMA = "bot-ui-findings/v1"
REQUEST_SCHEMA = "bot-ui-request/v1"
CATALOG_MAX_AGE_DAYS = 30
CONTEXT_LIMIT = 2048

PASS = {
    "lookup": ["tg_api_lookup.py"],
    "webapp": ["webapp_lookup.py"],
    "examples": ["example_library.py"],
    "profile": ["style_profile.py"],
    "post": ["tg_post.py"],
    "emoji": ["emoji_packs.py"],
    "data": ["data_view.py"],
}
SUB = {
    "check": {"payload": "validate_payload.py", "keyboard": "validate_keyboard.py", "rich": "validate_rich.py",
              "widget": "validate_widget.py", "copy": "audit_copy.py", "icons": "audit_icons.py",
              "miniapp": "miniapp_lint.py", "refs": "validate_references.py"},
    "widget": {"build": "build_widget.py", "preview": "preview_widget.py", "lint": "widget_lint.py",
               "design": "widget_design.py"},
    "miniapp": {"lint": "miniapp_lint.py", "rework": "miniapp_rework.py", "layout": "miniapp_layout.py",
                "style": "miniapp_style.py", "preview": "preview_miniapp.py", "star": "fetch_telegram_star.py"},
    "sync": {"bot-api": "sync_bot_api.py", "webapp": "webapp_lookup.py"},
}
TELEGRAM_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".php", ".rb", ".java", ".kt", ".cs", ".json",
                ".html", ".md", ".yaml", ".yml", ".ftl", ".po"}
CODE_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".bot-ui"}


# ---------------------------------------------------------------- helpers

def _out(obj, as_json: bool, text: str) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2) if as_json else text)


def _run(script: str, args: list[str], env: dict | None = None) -> int:
    return subprocess.call([sys.executable, os.path.join(SCRIPTS, script), *args], env=env)


def _capture(script: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _git(root: str, *args: str) -> str | None:
    if not shutil.which("git"):
        return None
    proc = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return proc.stdout.strip() if proc.returncode == 0 else None


def _today() -> dt.date:
    return dt.date.today()


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _index() -> dict:
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


def skill_version(skill_md: str | None = None) -> str:
    try:
        with open(skill_md or os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            head = fh.read(4096)
    except OSError:
        return "?"
    m = re.search(r'^\s+version:\s*"?([^"\n]+)"?', head, re.M)
    return m.group(1).strip() if m else "unknown"


def catalog_meta() -> dict:
    path = os.path.join(SKILL, "data", "bot-api", "catalog.json")
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4096)
    except OSError:
        return {}
    ver = re.search(r'"bot_api_version":\s*"([^"]+)"', head)
    fetched = re.search(r'"fetched_at":\s*"(\d{4}-\d{2}-\d{2})"', head)
    return {"botApi": ver.group(1) if ver else "?", "fetched": fetched.group(1) if fetched else None}


def _sys_path() -> None:
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)


# ---------------------------------------------------------------- project state

class Project:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.map_root = os.path.join(self.root, "bot-ui")
        self.ctx = os.path.join(self.map_root, "context")

    def path(self, *parts: str) -> str:
        return os.path.join(self.ctx, *parts)

    @property
    def has_map(self) -> bool:
        return os.path.isfile(os.path.join(self.map_root, "project.json"))

    def map_state(self) -> dict | None:
        if not self.has_map:
            return None
        _sys_path()
        from bot_ui.project import open_snapshot
        from bot_ui.validate import summary, validate
        snap = open_snapshot(self.map_root)
        diags = validate(snap)
        return {"screens": len(snap.screens) if hasattr(snap, "screens") else None, "revision": snap.revision,
                **summary(diags)}

    def context(self) -> dict | None:
        return _read_json(self.path("context.json"))

    def profile_path(self) -> str | None:
        for p in (self.path("profile.json"), os.path.join(self.root, "docs", "telegram-ui", "profile.json")):
            if os.path.isfile(p):
                return p
        return None

    def findings(self) -> dict:
        data = _read_json(self.path("findings.json"))
        return data if isinstance(data, dict) and isinstance(data.get("items"), list) else {
            "schema": FINDINGS_SCHEMA, "items": []}

    def requests(self) -> list[dict]:
        out = []
        for p in sorted(glob.glob(self.path("requests", "*.json"))):
            data = _read_json(p)
            if isinstance(data, dict) and data.get("schema") == REQUEST_SCHEMA:
                out.append(data)
        return out

    def based_on(self) -> dict:
        state = self.map_state() if self.has_map else None
        return {"commit": _git(self.root, "rev-parse", "--short", "HEAD"), "date": _today().isoformat(),
                "skill": skill_version(), "botApi": catalog_meta().get("botApi"),
                "mapRevision": state["revision"] if state else None}


def probe(root: str) -> dict:
    _sys_path()
    import style_profile
    return style_profile.probe(root)


def telegram_code(res: dict) -> bool:
    if res.get("sdk"):
        return True
    return any(v.get("count", 0) for v in (res.get("touchpoints") or {}).values() if isinstance(v, dict))


def code_roots(res: dict) -> list[str]:
    roots = set()
    for v in (res.get("touchpoints") or {}).values():
        for s in (v.get("samples") or []) if isinstance(v, dict) else []:
            first = s.split(":")[0].replace("\\", "/").split("/")[0]
            roots.add(first)
    return sorted(roots)[:10]


def changed_since(root: str, commit: str | None, paths: list[str]) -> list[str] | None:
    if not commit:
        return None
    out = _git(root, "diff", "--name-only", f"{commit}..HEAD", "--", *(paths or ["."]))
    return None if out is None else [l for l in out.splitlines() if l.strip()]


def uncommitted(root: str) -> list[str] | None:
    out = _git(root, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return None
    files = []
    for line in out.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.replace("\\", "/"))
    return files


def is_telegram_file(root: str, rel: str) -> bool:
    if rel.startswith("bot-ui/"):
        return not rel.startswith("bot-ui/context/") and not rel.startswith("bot-ui/.bot-ui/")
    if os.path.splitext(rel)[1].lower() not in TELEGRAM_EXT:
        return False
    text = _head(os.path.join(root, rel))
    return bool(text and TELEGRAM_MARK.search(text))


TELEGRAM_MARK = re.compile(r"inline_keyboard|InlineKeyboard|reply_markup|ReplyKeyboard|callback_data|aiogram|telegraf|"
                           r"grammy|python-telegram-bot|telegram\.ext|TelegramWidget|Telegram\.WebApp|sendMessage|"
                           r"parse_mode|telebot|tgkit")


def _head(path: str, limit: int = 200_000) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return None


def collect(root: str, use_probe: bool = True) -> dict:
    """Everything `context` and `next` need, computed offline."""
    prj = Project(root)
    ctx = prj.context()
    facts = probe(prj.root) if use_probe else {}
    findings = [f for f in prj.findings()["items"] if f.get("status") == "open"]
    findings.sort(key=lambda f: (f.get("severity", "P9"), f.get("id", "")))
    requests = [r for r in prj.requests() if r.get("status") == "queued"]
    mstate = prj.map_state()
    meta = catalog_meta()
    signals: dict[str, dict] = {}
    has_code = telegram_code(facts) if use_probe else True
    if requests:
        signals["REQUESTS_QUEUED"] = {"n": len(requests), "screen": requests[0].get("sid") or "-"}
    urgent = [f for f in findings if f.get("severity") in ("P0", "P1")]
    if urgent:
        signals["FINDINGS_OPEN"] = {"n": len(urgent), "summary": urgent[0].get("summary", ""),
                                    "screen": urgent[0].get("screenId") or "-",
                                    "fixWith": urgent[0].get("fixWith") or "improve"}
    pending = [f for f in (uncommitted(prj.root) or []) if is_telegram_file(prj.root, f)]
    if pending:
        signals["UNCOMMITTED_CHANGES"] = {"n": len(pending), "files": pending[:5]}
    if ctx:
        commit = (ctx.get("basedOn") or {}).get("commit")
        changed = changed_since(prj.root, commit, (ctx.get("code") or {}).get("roots") or [])
        changed = [c for c in (changed or []) if not c.startswith("bot-ui/context/")]
        if changed:
            signals["CONTEXT_STALE"] = {"n": len(changed), "commit": commit, "files": changed[:5]}
    if mstate and mstate.get("error"):
        signals["MAP_INVALID"] = {"n": mstate["error"]}
    if has_code and not ctx:
        signals["NO_CONTEXT"] = {}
    if has_code and not prj.has_map:
        signals["MAP_MISSING"] = {"sdk": ", ".join(sorted({s["sdk"] for s in facts.get("sdk", [])})) or "?"}
    if use_probe and not has_code:
        signals["NO_TELEGRAM_CODE"] = {}
    if meta.get("fetched"):
        age = (_today() - dt.date.fromisoformat(meta["fetched"])).days
        if age > CATALOG_MAX_AGE_DAYS:
            signals["CATALOG_STALE"] = {"n": age}
    return {"project": prj, "context": ctx, "facts": facts, "findings": findings, "requests": requests,
            "map": mstate, "catalog": meta, "signals": signals}


# ---------------------------------------------------------------- context / next

def cmd_context(args) -> int:
    prj = Project(args.root)
    if args.refresh:
        facts = probe(prj.root)
        doc = {
            "schema": CONTEXT_SCHEMA,
            "basedOn": prj.based_on(),
            "bot": {"sdk": [{k: s.get(k) for k in ("sdk", "package", "version")} for s in facts.get("sdk", [])][:5],
                    "locales": sorted(facts.get("locales", {}))[:10],
                    "miniApp": bool(facts.get("mini_app"))},
            "code": {"roots": code_roots(facts)},
            "touchpoints": {k: v.get("count", 0) for k, v in (facts.get("touchpoints") or {}).items()
                            if isinstance(v, dict)},
        }
        _write_json(prj.path("context.json"), doc)
        print(f"wrote {os.path.relpath(prj.path('context.json'), prj.root)} (commit it with the bot)", file=sys.stderr)
    data = collect(prj.root)
    summary = context_summary(data)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(context_text(summary))
    return 0


def context_summary(data: dict) -> dict:
    prj: Project = data["project"]
    ctx = data["context"] or {}
    meta = data["catalog"]
    return {
        "skill": {"version": skill_version(), "botApi": meta.get("botApi"), "catalog": meta.get("fetched"),
                  "path": SKILL},
        "project": {"root": prj.root, "commit": _git(prj.root, "rev-parse", "--short", "HEAD"),
                    "sdk": sorted({f"{s['sdk']} {s.get('version') or ''}".strip()
                                   for s in data["facts"].get("sdk", [])})[:3],
                    "locales": sorted(data["facts"].get("locales", {}))[:6]},
        "map": data["map"],
        "context": {"saved": (ctx.get("basedOn") or {}).get("date"), "commit": (ctx.get("basedOn") or {}).get("commit"),
                    "profile": os.path.relpath(prj.profile_path(), prj.root) if prj.profile_path() else None}
        if data["context"] or prj.profile_path() else None,
        "findings": {"open": len(data["findings"]),
                     "first": [{k: f.get(k) for k in ("id", "severity", "screenId", "summary", "fixWith")}
                               for f in data["findings"][:3]]},
        "requests": {"queued": len(data["requests"]),
                     "first": [{k: r.get(k) for k in ("id", "sid", "text")} for r in data["requests"][:3]]},
        "signals": sorted(data["signals"], key=_signal_rank),
    }


def _signal_rank(sid: str) -> int:
    order = [s["id"] for s in _index()["signals"]]
    return order.index(sid) if sid in order else len(order)


def context_text(s: dict) -> str:
    sk, pr = s["skill"], s["project"]
    lines = [f"telegram-bot-ui {sk['version']} · Bot API {sk['botApi']} (catalog {sk['catalog']})",
             f"project: {pr['root']} · git {pr['commit'] or 'none'} · sdk: {', '.join(pr['sdk']) or 'not detected'}"
             + (f" · locales: {', '.join(pr['locales'])}" if pr["locales"] else "")]
    if s["map"]:
        m = s["map"]
        lines.append(f"map: bot-ui/ · revision {m['revision'][:19]}… · {m['error']} error(s), {m['warning']} warning(s)")
    else:
        lines.append("map: none")
    c = s["context"]
    lines.append(f"context: saved {c['saved']} at {c['commit']}" + (f" · profile {c['profile']}" if c["profile"] else "")
                 if c else "context: none saved yet")
    f = s["findings"]
    lines.append(f"findings: {f['open']} open" + "".join(
        f"\n  {x['id']} {x['severity']} {x['screenId'] or '-'}: {x['summary']} -> {x['fixWith']}" for x in f["first"]))
    r = s["requests"]
    lines.append(f"Studio requests: {r['queued']} queued" + "".join(
        f"\n  {x['id']} {x['sid'] or '-'}: {x['text'][:80]}" for x in r["first"]))
    lines.append("signals: " + (" ".join(s["signals"]) or "none"))
    text = "\n".join(lines)
    return text if len(text) <= CONTEXT_LIMIT else text[:CONTEXT_LIMIT - 1] + "…"


def suggestions(data: dict, limit: int = 3) -> list[dict]:
    idx = _index()
    out = []
    for spec in idx["signals"]:
        vals = data["signals"].get(spec["id"])
        if vals is None:
            continue
        fmt = {k: v for k, v in vals.items() if not isinstance(v, list)}
        verb = spec["verb"].format(**fmt) if "{" in spec["verb"] else spec["verb"]
        out.append({"signal": spec["id"], "verb": verb, "why": spec["say"].format_map(_Default(fmt))})
        if len(out) >= limit:
            break
    return out


class _Default(dict):
    def __missing__(self, key):
        return "?"


def cmd_next(args) -> int:
    data = collect(args.root)
    sugg = suggestions(data)
    menu = [{"verb": c["verb"], "does": c["does"]} for c in _index()["commands"] if c["verb"] != "start"]
    if args.json:
        print(json.dumps({"suggestions": sugg, "menu": menu}, ensure_ascii=False, indent=2))
        return 0
    if not sugg:
        print("Nothing urgent found. Pick any command:")
    for i, s in enumerate(sugg, 1):
        print(f"{i}. {s['verb']}: {s['why']}")
    print("menu: " + " · ".join(m["verb"] for m in menu))
    return 0


# ---------------------------------------------------------------- findings / requests

def finding_id(screen: str, rule: str, where: str) -> str:
    return "F-" + hashlib.sha1(f"{screen}|{rule}|{where}".encode("utf-8")).hexdigest()[:8]


def cmd_findings(args) -> int:
    prj = Project(args.root)
    data = prj.findings()
    items = data["items"]
    if args.action == "list":
        rows = [f for f in items if not args.open or f.get("status") == "open"]
        _out(rows, args.json, "\n".join(f"{f['id']} {f['status']:8} {f['severity']} {f.get('screenId') or '-'}: "
                                        f"{f['summary']}" for f in rows) or "no findings")
        return 0
    if args.action == "add":
        if not (args.severity and args.rule and args.summary):
            print("findings add needs --severity, --rule and --summary", file=sys.stderr)
            return 2
        fid = finding_id(args.screen or "", args.rule, args.where or "")
        row = next((f for f in items if f["id"] == fid), None)
        fields = {"id": fid, "severity": args.severity, "screenId": args.screen, "where": args.where,
                  "rule": args.rule, "summary": args.summary, "fixWith": args.fix, "status": "open"}
        if row:
            row.update(fields)
        else:
            items.append({**fields, "openedAt": _today().isoformat(), "closedAt": None, "reason": None})
    else:  # close
        row = next((f for f in items if f["id"] == args.id), None)
        if row is None:
            print(f"no finding {args.id}", file=sys.stderr)
            return 1
        row.update({"status": args.status, "closedAt": _today().isoformat(), "reason": args.reason})
        fid = args.id
    data.update({"schema": FINDINGS_SCHEMA, "basedOn": prj.based_on(), "items": items})
    _write_json(prj.path("findings.json"), data)
    print(fid)
    return 0


def cmd_requests(args) -> int:
    prj = Project(args.root)
    if args.action == "list":
        rows = [r for r in prj.requests() if not args.status or r.get("status") == args.status]
        _out(rows, args.json, "\n".join(f"{r['id']} {r['status']:8} {r.get('sid') or '-'}: {r['text']}" for r in rows)
             or "no Studio requests")
        return 0
    if args.action == "add":
        if not args.text:
            print("requests add needs --text", file=sys.stderr)
            return 2
        rid = "rq-" + hashlib.sha1(f"{args.screen}|{args.text}|{dt.datetime.now().isoformat()}".encode()).hexdigest()[:10]
        state = prj.map_state()
        doc = {"schema": REQUEST_SCHEMA, "id": rid, "sid": args.screen, "text": args.text,
               "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "baseRevision": state["revision"] if state else None, "status": "queued", "result": None}
        _write_json(prj.path("requests", f"{rid}.json"), doc)
        print(rid)
        return 0
    path = prj.path("requests", f"{args.id}.json")
    doc = _read_json(path)
    if not isinstance(doc, dict):
        print(f"no request {args.id}", file=sys.stderr)
        return 1
    status = {"take": "taken", "done": "done", "reject": "rejected"}[args.action]
    if args.action == "take" and doc.get("status") != "queued":
        print(f"{args.id} is {doc.get('status')}, not queued", file=sys.stderr)
        return 4
    doc.update({"status": status, "result": args.result if args.action != "take" else doc.get("result")})
    _write_json(path, doc)
    print(f"{args.id} {status}")
    return 0


# ---------------------------------------------------------------- checks of changed files

def check_file(root: str, rel: str, seen: set | None = None) -> tuple[str, int, str] | None:
    """(checker, exit code, short output) for one file, or None when no checker applies.
    `seen` collects bot-ui roots already validated, so a map is checked once per run."""
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        return None
    ext = os.path.splitext(rel)[1].lower()
    norm = rel.replace("\\", "/")
    if "/bot-ui/" in f"/{norm}" and ext == ".json" and "/context/" not in f"/{norm}":
        _sys_path()
        from bot_ui.project import find_root
        mroot = find_root(os.path.dirname(full))
        if not mroot or (seen is not None and mroot in seen):
            return None
        if seen is not None:
            seen.add(mroot)
        env = dict(os.environ, PYTHONPATH=SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", ""))
        proc = subprocess.run([sys.executable, "-m", "bot_ui", "validate", "--project", mroot], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env=env)
        return "map validate", proc.returncode, (proc.stdout + proc.stderr).strip()
    text = _head(full)
    if text is None:
        return None
    if ext == ".json" and re.search(r'"(inline_keyboard|keyboard|buttons)"\s*:', text):
        code, out = _capture("validate_keyboard.py", [full])
        if "unrecognised markup" in out:
            return None
        return "check keyboard", code, out
    if ext == ".html" and "TelegramWidget" in text:
        code, out = _capture("validate_widget.py", [full])
        return "check widget", code, out
    if ext in (".html", ".js", ".jsx", ".ts", ".tsx") and "Telegram.WebApp" in text:
        code, out = _capture("miniapp_lint.py", [full])
        return "check miniapp", code, out
    return None


def _problems(out: str, limit: int = 3) -> list[str]:
    lines = [l.strip() for l in out.splitlines() if re.match(r"\s*(FAIL|ERROR|WARN)\b", l, re.I)]
    return lines[:limit]


def cmd_check_changed(args) -> int:
    root = os.path.abspath(args.root)
    files = uncommitted(root)
    if files is None:
        print("not a git repository (or git is missing): name the files to check instead", file=sys.stderr)
        return 2
    results, seen = [], set()
    for rel in files:
        res = check_file(root, rel, seen)
        if res:
            results.append({"file": rel, "checker": res[0], "exit": res[1], "problems": _problems(res[2])})
    failed = [r for r in results if r["exit"] not in (0,)]
    text = "\n".join(f"{'FAIL' if r['exit'] else 'ok  '} {r['checker']:15} {r['file']}"
                     + "".join(f"\n      {p}" for p in r["problems"]) for r in results) or "no changed Telegram files"
    _out({"checked": results, "failed": len(failed)}, args.json, text)
    return 1 if failed else 0


# ---------------------------------------------------------------- hook

def cmd_hook(args) -> int:
    if args.action == "post-edit":
        return hook_post_edit(args)
    return hook_install(args, remove=args.action == "uninstall")


def hook_post_edit(args) -> int:
    """Never blocks: prints at most three lines of advice for Claude Code, always exits 0."""
    path = args.file
    if not path and not sys.stdin.isatty():
        try:
            event = json.loads(sys.stdin.read() or "{}")
            path = (event.get("tool_input") or {}).get("file_path")
        except ValueError:
            path = None
    if not path or os.path.splitext(path)[1].lower() not in {".json", ".html", ".js", ".jsx", ".ts", ".tsx"}:
        return 0
    try:
        root = os.path.dirname(os.path.abspath(path))
        res = check_file(root, os.path.basename(path))
    except Exception:  # a hook must never break the edit loop
        return 0
    if not res or (res[1] == 0 and not _problems(res[2])):
        return 0
    lines = _problems(res[2]) or [f"{res[0]} exited {res[1]}"]
    note = f"telegram-bot-ui {res[0]} on {os.path.basename(path)}: " + " | ".join(lines)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note[:600]}}))
    return 0


def hook_install(args, remove: bool) -> int:
    if args.host != "claude":
        print("Only Claude Code hooks are written automatically. In other hosts run "
              "`tgui.py check changed` before finishing (the skill's Start step 5 says so).", file=sys.stderr)
        return 4
    settings = os.path.join(os.path.abspath(args.root), ".claude", "settings.json")
    data = _read_json(settings) if os.path.isfile(settings) else {}
    if data is None:
        print(f"{settings} is not valid JSON; nothing written", file=sys.stderr)
        return 4
    command = f'"{sys.executable}" "{os.path.abspath(__file__)}" hook post-edit'
    hooks = data.setdefault("hooks", {}).setdefault("PostToolUse", [])
    kept = [h for h in hooks if not any("tgui.py" in (x.get("command") or "") for x in h.get("hooks", []))]
    if not remove:
        kept.append({"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": command}]})
    data["hooks"]["PostToolUse"] = kept
    if not kept:
        del data["hooks"]["PostToolUse"]
    if args.dry_run:
        print(json.dumps(data, indent=2))
        return 0
    _write_json(settings, data)
    print(f"{'removed from' if remove else 'wrote'} {settings}")
    return 0


# ---------------------------------------------------------------- doctor

def other_copies(root: str) -> list[dict]:
    home = os.path.expanduser("~")
    patterns = [os.path.join(home, d, "skills", "telegram-bot-ui")
                for d in (".claude", ".agents", ".codex", ".cursor", ".gemini", ".copilot")]
    patterns += [os.path.join(root, d, "skills", "telegram-bot-ui")
                 for d in (".claude", ".agents", ".cursor", ".gemini", ".github")]
    patterns += [os.path.join(home, ".claude", "plugins", "cache", "*", "telegram-bot-ui", "*", "skills",
                              "telegram-bot-ui"),
                 os.path.join(home, ".claude", "plugins", "marketplaces", "*", "skills", "telegram-bot-ui")]
    mine = os.path.realpath(SKILL)
    with open(os.path.join(SKILL, "SKILL.md"), "rb") as fh:
        my_hash = hashlib.sha256(fh.read()).hexdigest()
    seen, out = set(), []
    for pat in patterns:
        for d in glob.glob(pat):
            md = os.path.join(d, "SKILL.md")
            real = os.path.realpath(d)
            if not os.path.isfile(md) or real == mine or real in seen:
                continue
            seen.add(real)
            with open(md, "rb") as fh:
                same = hashlib.sha256(fh.read()).hexdigest() == my_hash
            out.append({"path": d, "version": skill_version(md), "same": same})
    return out


def doctor(root: str) -> dict:
    findings = []
    mine = skill_version()
    plugin = os.path.join(SKILL, "..", "..", ".claude-plugin", "plugin.json")
    pdata = _read_json(plugin) if os.path.isfile(plugin) else None
    if pdata and pdata.get("version") != mine:
        findings.append({"id": "VERSION_MISMATCH", "severity": "mention",
                         "message": f"SKILL.md says {mine}, plugin.json says {pdata.get('version')}",
                         "fix": "bump both in the same release"})
    for c in other_copies(os.path.abspath(root)):
        if c["same"]:
            continue
        findings.append({"id": "OTHER_COPY", "severity": "mention",
                         "message": f"{c['path']} holds telegram-bot-ui {c['version']} (this copy {mine}); a host "
                                    f"that reads that folder loads the other version",
                         "fix": "update or remove it (in a clone: py -3 scripts/install.py --host <host> --scope "
                                "<user|project>)"})
    meta = catalog_meta()
    if meta.get("fetched"):
        age = (_today() - dt.date.fromisoformat(meta["fetched"])).days
        if age > CATALOG_MAX_AGE_DAYS:
            findings.append({"id": "CATALOG_STALE", "severity": "route",
                             "message": f"Bot API catalog fetched {meta['fetched']} ({age} days ago)",
                             "fix": "tgui.py sync bot-api (network), then lookup version"})
    prj = Project(root)
    old = os.path.join(prj.root, "docs", "telegram-ui", "profile.json")
    if os.path.isfile(old) and not os.path.isfile(prj.path("profile.json")):
        findings.append({"id": "PROFILE_OLD_PATH", "severity": "auto",
                         "message": "style profile at docs/telegram-ui/profile.json",
                         "fix": "doctor --fix copies it to bot-ui/context/profile.json"})
    for name, schema in (("context.json", CONTEXT_SCHEMA), ("findings.json", FINDINGS_SCHEMA)):
        p = prj.path(name)
        if os.path.isfile(p):
            data = _read_json(p)
            if not isinstance(data, dict) or data.get("schema") != schema:
                findings.append({"id": "CONTEXT_SCHEMA", "severity": "mention",
                                 "message": f"bot-ui/context/{name} is not {schema}",
                                 "fix": "regenerate it (context --refresh) or fix it by hand"})
    state = prj.map_state() if prj.has_map else None
    if state and state.get("error"):
        findings.append({"id": "MAP_INVALID", "severity": "route",
                         "message": f"bot-ui map has {state['error']} validation error(s)",
                         "fix": "tgui.py map validate --project bot-ui"})
    return {"skill": {"version": mine, "path": SKILL, **meta}, "findings": findings}


def cmd_doctor(args) -> int:
    res = doctor(args.root)
    if args.fix:
        prj = Project(args.root)
        for f in res["findings"]:
            if f["id"] == "PROFILE_OLD_PATH":
                os.makedirs(prj.ctx, exist_ok=True)
                shutil.copyfile(os.path.join(prj.root, "docs", "telegram-ui", "profile.json"), prj.path("profile.json"))
                f["fixed"] = True
    sk = res["skill"]
    text = [f"telegram-bot-ui {sk['version']} at {sk['path']} · Bot API {sk.get('botApi')} "
            f"(catalog {sk.get('fetched')})"]
    text += [f"[{f['severity']}] {f['id']}: {f['message']}\n    fix: {f['fix']}" for f in res["findings"]]
    if not res["findings"]:
        text.append("no problems found")
    _out(res, args.json, "\n".join(text))
    return 1 if any(not f.get("fixed") for f in res["findings"]) else 0


# ---------------------------------------------------------------- dispatch

def run_map(rest: list[str]) -> int:
    _sys_path()
    from bot_ui.cli import main as bot_ui_main
    return bot_ui_main(rest)


def run_agent(rest: list[str]) -> int:
    env = dict(os.environ)
    lib = os.path.join(SKILL, "examples", "python")
    env["PYTHONPATH"] = lib + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call([sys.executable, "-m", "agent_bridge", *rest], env=env)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tgui.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="group")

    def own(name, func, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--root", default=".", help="the bot's repository (default: current folder)")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=func)
        return p

    p = own("context", cmd_context, "saved project context and signals")
    p.add_argument("--refresh", action="store_true", help="re-detect facts and write bot-ui/context/context.json")
    own("next", cmd_next, "the 2-3 best next commands")
    p = own("doctor", cmd_doctor, "health of the skill copy, catalog, context and map")
    p.add_argument("--fix", action="store_true", help="apply the `auto` fixes")
    p = own("findings", cmd_findings, "audit findings (bot-ui/context/findings.json)")
    p.add_argument("action", choices=("add", "close", "list"))
    p.add_argument("id", nargs="?")
    p.add_argument("--severity", choices=("P0", "P1", "P2", "P3"))
    p.add_argument("--screen")
    p.add_argument("--rule")
    p.add_argument("--where")
    p.add_argument("--summary")
    p.add_argument("--fix", default="improve", help="command that fixes it")
    p.add_argument("--status", default="fixed", choices=("fixed", "wontfix", "orphaned"))
    p.add_argument("--reason")
    p.add_argument("--open", action="store_true")
    p = own("requests", cmd_requests, "Studio requests (bot-ui/context/requests/)")
    p.add_argument("action", choices=("list", "add", "take", "done", "reject"))
    p.add_argument("id", nargs="?")
    p.add_argument("--screen")
    p.add_argument("--text")
    p.add_argument("--result")
    p.add_argument("--status", choices=("queued", "taken", "done", "rejected"))
    p = own("hook", cmd_hook, "post-edit check; install or remove the Claude Code hook")
    p.add_argument("action", choices=("post-edit", "install", "uninstall"))
    p.add_argument("--file")
    p.add_argument("--host", default="claude")
    p.add_argument("--dry-run", action="store_true")
    for name in (*PASS, *SUB, "map", "agent"):
        sub.add_parser(name, help=f"see `tgui.py {name} --help`", add_help=False)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    group, rest = argv[0], argv[1:]
    if group in PASS:
        return _run(PASS[group][0], rest)
    if group == "check" and rest[:1] == ["changed"]:
        ap = argparse.ArgumentParser(prog="tgui.py check changed")
        ap.add_argument("--root", default=".")
        ap.add_argument("--json", action="store_true")
        return cmd_check_changed(ap.parse_args(rest[1:]))
    if group in SUB:
        table = SUB[group]
        if not rest or rest[0] in ("-h", "--help"):
            print(f"usage: tgui.py {group} {{{'|'.join(table)}{'|changed' if group == 'check' else ''}}} ...")
            return 0 if rest else 2
        if rest[0] not in table:
            print(f"unknown {group} command {rest[0]!r}; one of: {', '.join(table)}", file=sys.stderr)
            return 2
        args = rest[1:]
        if group == "sync" and rest[0] == "webapp":
            args = ["sync", *args]
        return _run(table[rest[0]], args)
    if group == "map":
        return run_map(rest)
    if group == "agent":
        return run_agent(rest)
    args = parser().parse_args(argv)
    if not getattr(args, "func", None):
        print(__doc__)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
