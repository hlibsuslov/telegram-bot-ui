#!/usr/bin/env python3
# run-checks:
"""Run the behavioural evals through a host CLI and grade them with an LLM judge.

  python scripts/run_behavioral.py                                   # offline check: judge prompt, calibration set
  python scripts/run_behavioral.py --execute --host claude --per-role 3 --retry-timeouts
  python scripts/run_behavioral.py --execute --ids B01,B21 --dry-run    # print the commands only
  python scripts/run_behavioral.py --calibrate --host claude            # judge the hand-labelled answers

Execution, per scenario of evals/evals.json `behavioral`:
  1. a fresh private temp project (outside the home folder, as in run_evals.py) with a copy of the
     scenario's fixture (`fixture`, default bot-project) and the skill installed, committed as the
     baseline; the host gets "<request>\n\nContext: <context>" on stdin and may edit the project
     (Claude: acceptEdits, Bash limited to python/git/node through a --settings file, no web tools;
     Codex: workspace-write sandbox). Telegram tokens are dropped from the child's environment.
  2. the final answer, the project diff against the baseline and the tools and files used are read
     from the transcript and the project.
  3. a separate judge call through the same host CLI: no tools (Claude `--tools ""`, Codex read-only
     sandbox in an empty folder), the fixed prompt evals/judge.md plus the material on stdin. It
     returns JSON verdicts: every `must` item met / not_met / not_applicable, every critical failure
     present / absent. Output that is not exactly that JSON is a judge error, never a pass. The
     judge prompt version and its sha256 go into every scenario result; the prompt text into the file.

Release gate on the chosen set: 0 critical failures and at least 85 % of the scored `must` items
met (not_applicable items are left out), and the results must be valid: no run error, unresolved
timeout, judge error, or skill copy loaded from outside the temp project. Results go to
evals/results/<date>T<HHMMSS>-behavioral-<host>-<runid>.json (calibration: -calibration-).

Calibration: evals/judge-calibration/*.json hold an answer (plus an optional diff and tool list)
for a scenario and the verdicts a person expects; --calibrate judges each once and reports the
share of items where the judge agrees (target >= 0.8).

Exit codes: 0 gate passed (calibration: agreement reached); 1 gate failed; 2 host CLI not found;
3 results not trustworthy (see above).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_evals as ev  # noqa: E402

ROOT = ev.ROOT
JUDGE_PROMPT = os.path.join(ROOT, "evals", "judge.md")
CALIBRATION = os.path.join(ROOT, "evals", "judge-calibration")
RESULTS = os.path.join(ROOT, "evals", "results")
DEFAULT_FIXTURE = "bot-project"
MUST_THRESHOLD = 0.85
CALIBRATION_TARGET = 0.8
MUST_VERDICTS = ("met", "not_met", "not_applicable")
CRITICAL_VERDICTS = ("present", "absent")
DIFF_LIMIT = 40_000
ANSWER_LIMIT = 20_000
# Bash the agent may run without a prompt (everything else is denied in print mode).
AGENT_PERMISSIONS = {"defaultMode": "acceptEdits",
                     "allow": ["Bash(python:*)", "Bash(python3:*)", "Bash(py:*)", "Bash(node:*)",
                               "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)", "Bash(ls:*)"],
                     "deny": ["WebFetch", "WebSearch"]}
TELEGRAM_SECRET = re.compile(r"^TG_|TELEGRAM|BOT_TOKEN", re.I)
# A host error that every later call would repeat: stop instead of spending the remaining calls.
USAGE_LIMIT = re.compile(r"usage limit|hit your .{0,20}limit|out of usage|rate limit|quota", re.I)


def hit_limit(error: str | None) -> bool:
    return bool(error and USAGE_LIMIT.search(error))


# ---------------------------------------------------------------- judge prompt and calibration files

def load_judge(path: str = JUDGE_PROMPT) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"---\s*\nversion:\s*(\S+)\s*\n---\s*\n", text)
    if not m:
        raise ValueError(f"{path}: needs a front matter with `version:`")
    return {"version": m.group(1), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text[m.end():]}


def load_calibration(folder: str = CALIBRATION) -> list[dict]:
    items = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            items.append({**json.load(fh), "file": os.path.basename(path)})
    return items


def check_calibration(items: list[dict], cases: dict[str, dict]) -> list[str]:
    errors = []
    for item in items:
        where = item["file"]
        case = cases.get(item.get("scenario"))
        if case is None:
            errors.append(f"{where}: unknown scenario {item.get('scenario')!r}")
            continue
        if not ev._nonempty_str(item.get("answer")):
            errors.append(f"{where}: empty answer")
        if item.get("label") not in ("good", "bad"):
            errors.append(f"{where}: label must be good|bad")
        expected = item.get("expected") or {}
        for key, allowed in (("must", MUST_VERDICTS), ("critical_failures", CRITICAL_VERDICTS)):
            got = expected.get(key)
            if not isinstance(got, list) or len(got) != len(case[key]) or any(v not in allowed for v in got):
                errors.append(f"{where}: expected.{key} needs {len(case[key])} verdict(s) from {allowed}")
    return errors


# ---------------------------------------------------------------- selection

def select(cases: list[dict], ids: str | None, roles: str | None, split: str,
           per_role: int | None, limit: int | None) -> list[dict]:
    """--ids, --roles and --split filter; --per-role keeps the first N of each role (file order)."""
    cases = ev.select_cases(cases, ids, split, None)
    if roles:
        wanted = set(roles.split(","))
        cases = [c for c in cases if c["role"] in wanted]
    if per_role:
        taken: dict[str, int] = {}
        kept = []
        for c in cases:
            if taken.get(c["role"], 0) < per_role:
                taken[c["role"]] = taken.get(c["role"], 0) + 1
                kept.append(c)
        cases = kept
    return cases[:limit] if limit else cases


def scenario_prompt(case: dict) -> str:
    return f"{case['request']}\n\nContext: {case['context']}"


# ---------------------------------------------------------------- commands

def agent_command(host: str, project: str, model: str | None, settings: str | None,
                  hidden: list[str] | None = None) -> list[str]:
    if host == "claude":
        return ["claude", *(["--model", model] if model else []), "-p", "--output-format", "stream-json",
                "--verbose", "--no-session-persistence", *ev.CLAUDE_ISOLATION, "--strict-mcp-config",
                *(["--settings", settings] if settings else []), "--permission-mode", "acceptEdits"]
    if host == "codex":
        hide = ["-c", "skills.config=[" + ", ".join(f"{{path='{p}', enabled=false}}" for p in hidden) + "]"
                ] if hidden else []
        return ["codex", "exec", *(["-m", model] if model else []), *hide, "--json", "--skip-git-repo-check",
                "--ephemeral", "-s", "workspace-write", "-C", project, "-"]
    raise ValueError(f"unsupported host {host}")


def judge_command(host: str, folder: str, model: str | None, hidden: list[str] | None = None) -> list[str]:
    """A tool-less, read-only call: Claude gets no built-in tools and no MCP servers; Codex a read-only
    sandbox in an empty folder (it has no switch that removes its shell)."""
    if host == "claude":
        return ["claude", *(["--model", model] if model else []), "-p", "--output-format", "stream-json",
                "--verbose", "--no-session-persistence", *ev.CLAUDE_ISOLATION, "--strict-mcp-config",
                "--tools", ""]
    if host == "codex":
        hide = ["-c", "skills.config=[" + ", ".join(f"{{path='{p}', enabled=false}}" for p in hidden) + "]"
                ] if hidden else []
        return ["codex", "exec", *(["-m", model] if model else []), *hide, "--json", "--skip-git-repo-check",
                "--ephemeral", "-s", "read-only", "-C", folder, "-"]
    raise ValueError(f"unsupported host {host}")


def launch(cmd: list[str], stdin_text: str, cwd: str, env: dict, timeout: int,
           host_bin: list[str] | None = None) -> tuple[str, int | str]:
    """run_evals.run_child; host_bin replaces the CLI name (tests point it at a fake host)."""
    return ev.run_child([*host_bin, *cmd[1:]] if host_bin else cmd, stdin_text, cwd, env, timeout)


def scrubbed_env(host: str, home: str) -> dict:
    env = ev.child_env(host, home)
    return {k: v for k, v in env.items() if not TELEGRAM_SECRET.search(k)}


# ---------------------------------------------------------------- workspace and diff

def git(project: str, *args: str) -> str:
    proc = subprocess.run(["git", "-C", project, "-c", "core.autocrlf=false", "-c", "core.safecrlf=false", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return proc.stdout


def prepare(host: str, fixture: str) -> tuple[str, str, str, str | None]:
    """(root, project, home, settings file): a fresh project with the fixture and the skill, committed."""
    root, project, home = ev.prepare_workspace(host, fixture)
    git(project, "add", "-A")
    git(project, "-c", "user.name=eval", "-c", "user.email=eval@localhost", "-c", "commit.gpgsign=false",
        "commit", "-q", "--no-verify", "-m", "baseline")
    settings = None
    if host == "claude":
        settings = os.path.join(root, "agent-settings.json")
        with open(settings, "w", encoding="utf-8") as fh:
            json.dump({"permissions": AGENT_PERMISSIONS}, fh)
    return root, project, home, settings


def project_diff(project: str) -> dict:
    git(project, "add", "-A")
    text = git(project, "diff", "--cached", "--no-color", "HEAD")
    files = [f for f in git(project, "diff", "--cached", "--name-only", "HEAD").splitlines() if f]
    return {"files": files, "stat": git(project, "diff", "--cached", "--stat", "HEAD").strip(),
            "text": _cut(text, DIFF_LIMIT), "truncated": len(text) > DIFF_LIMIT}


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n[... cut at {limit} characters]"


# ---------------------------------------------------------------- transcripts

def transcript(host: str, output: str) -> dict:
    """Final answer and tool calls of a stream-json (Claude) or --json (Codex) transcript."""
    answer, tools, init_tools = None, [], None
    for event in ev._events(output):
        if host == "claude":
            if event.get("type") == "system" and event.get("subtype") == "init":
                init_tools = event.get("tools")
            if event.get("type") == "result" and isinstance(event.get("result"), str):
                answer = event["result"]
            for node in ev._walk(event):
                if node.get("type") == "tool_use":
                    inp = node.get("input") or {}
                    target = next((str(inp[k]) for k in ("file_path", "command", "path", "pattern", "skill", "url")
                                   if k in inp), "")
                    tools.append({"tool": str(node.get("name")), "target": target[:300]})
        else:
            item = event.get("item") if event.get("type") == "item.completed" else None
            if not isinstance(item, dict):
                continue
            kind = item.get("type") or item.get("item_type")
            if kind == "agent_message" and isinstance(item.get("text"), str):
                answer = item["text"]
            elif kind == "command_execution":
                tools.append({"tool": "shell", "target": str(item.get("command", ""))[:300]})
            elif kind == "file_change":
                for change in item.get("changes") or []:
                    tools.append({"tool": "edit", "target": str(change.get("path", ""))[:300]})
            elif kind in ("mcp_tool_call", "web_search"):
                tools.append({"tool": kind, "target": str(item.get("tool") or item.get("query") or "")[:300]})
    return {"answer": answer, "tools": tools, "init_tools": init_tools}


def run_scenario(case: dict, host: str, model: str | None, timeout: int, hidden: list[str],
                 host_bin: list[str] | None = None) -> dict:
    """One attempt in a fresh workspace, removed afterwards."""
    root, project, home, settings = prepare(host, case.get("fixture", DEFAULT_FIXTURE))
    try:
        start = time.time()
        prompt = scenario_prompt(case)
        output, status = launch(agent_command(host, project, model, settings, hidden), prompt, project,
                                scrubbed_env(host, home), timeout, host_bin)
        info = ev.analyze_output(host, output, project)
        seen = transcript(host, output)
        timed_out = status == "timeout" and not info["error"]
        return {"prompt": prompt, "exit": status, "timed_out": timed_out,
                "error": None if timed_out else ev.run_error(info, status),
                "seconds": round(time.time() - start, 1), "model": info["model"], "tokens": info["tokens"],
                "activated": info["activated"], "copy": info["copy"], "skill_reads": info["reads"],
                "answer": _cut(seen["answer"] or "", ANSWER_LIMIT), "tools": seen["tools"],
                "diff": project_diff(project)}
    finally:
        ev.remove_tree(root)


# ---------------------------------------------------------------- judge

def _data(tag: str, text: str) -> str:
    return f"<{tag}>\n" + (text or "(empty)").replace(f"</{tag}>", f"<\\/{tag}>") + f"\n</{tag}>"


def judge_input(case: dict, run: dict, judge: dict) -> str:
    must = "\n".join(f"- M{i}: {t}" for i, t in enumerate(case["must"], 1))
    crit = "\n".join(f"- C{i}: {t}" for i, t in enumerate(case["critical_failures"], 1))
    tools = "\n".join(f"- {t['tool']}: {t['target']}" for t in run.get("tools") or []) or "(none recorded)"
    diff = run.get("diff") or {}
    scenario = f"id: {case['id']}\nrole: {case['role']}\nrequest: {case['request']}\ncontext: {case['context']}"
    return "\n\n".join([
        judge["text"].strip(), "# Material", _data("scenario", scenario),
        _data("rubric", f"must:\n{must}\ncritical_failures:\n{crit}"),
        _data("agent_final_answer", run.get("answer") or ""),
        _data("project_diff", diff.get("text") or "(no changes)"),
        _data("tools_and_files", tools)])


def _json_object(text: str):
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"):text.rfind("}") + 1]
    return json.loads(candidate) if candidate else None


def parse_verdict(text: str | None, n_must: int, n_crit: int) -> tuple[dict | None, str | None]:
    """(verdict, None) for well-formed judge output, else (None, why). Never guesses a missing verdict."""
    if not text or not text.strip():
        return None, "empty judge answer"
    try:
        data = _json_object(text)
    except ValueError as exc:
        return None, f"judge answer is not JSON: {exc}"
    if not isinstance(data, dict):
        return None, "judge answer has no JSON object"
    out = {}
    for key, prefix, n, allowed in (("must", "M", n_must, MUST_VERDICTS),
                                    ("critical_failures", "C", n_crit, CRITICAL_VERDICTS)):
        entries = data.get(key)
        if not isinstance(entries, list):
            return None, f"judge JSON has no `{key}` list"
        ids = [e.get("id") if isinstance(e, dict) else None for e in entries]
        if ids != [f"{prefix}{i}" for i in range(1, n + 1)]:
            return None, f"`{key}` ids {ids} do not match {prefix}1..{prefix}{n}"
        if any(e.get("verdict") not in allowed for e in entries):
            return None, f"`{key}` has a verdict outside {allowed}"
        out[key] = [{"id": e["id"], "verdict": e["verdict"], "evidence": str(e.get("evidence", ""))[:300]}
                    for e in entries]
    return out, None


def run_judge(case: dict, run: dict, judge: dict, host: str, model: str | None, timeout: int,
              hidden: list[str], host_bin: list[str] | None = None) -> dict:
    folder = ev.make_root()
    try:
        home = os.path.join(folder, "home")
        os.makedirs(home)
        output, status = launch(judge_command(host, folder, model, hidden), judge_input(case, run, judge),
                                folder, scrubbed_env(host, home), timeout, host_bin)
    finally:
        ev.remove_tree(folder)
    info = ev.analyze_output(host, output, None)
    seen = transcript(host, output)
    record = {"prompt_version": judge["version"], "prompt_sha256": judge["sha256"], "tokens": info["tokens"],
              "tools_available": seen["init_tools"], "raw": _cut(seen["answer"] or "", 4000), "error": None,
              "must": None, "critical_failures": None}
    if seen["tools"]:
        record["error"] = f"judge used tools: {[t['tool'] for t in seen['tools']]}"
    elif status == "timeout":
        record["error"] = "judge timeout"
    elif (error := ev.run_error(info, status)):
        record["error"] = f"judge run: {error}"
    else:
        verdict, why = parse_verdict(seen["answer"], len(case["must"]), len(case["critical_failures"]))
        if why:
            record["error"] = why
        else:
            record.update(verdict)
    return record


# ---------------------------------------------------------------- scoring and aggregation

def score(case: dict, run: dict, judgement: dict | None) -> dict:
    """Counts for one scenario and its status: run_error, timeout, judge_error or judged."""
    base = {"id": case["id"], "role": case["role"], "area": case["area"], "must_met": 0, "must_not_met": 0,
            "must_na": 0, "critical": 0}
    if run["timed_out"]:
        return {**base, "status": "timeout"}
    if run["error"]:
        return {**base, "status": "run_error"}
    if judgement is None or judgement["error"]:
        return {**base, "status": "judge_error"}
    must = [m["verdict"] for m in judgement["must"]]
    return {**base, "status": "judged", "must_met": must.count("met"), "must_not_met": must.count("not_met"),
            "must_na": must.count("not_applicable"),
            "critical": sum(c["verdict"] == "present" for c in judgement["critical_failures"])}


def _totals(rows: list[dict]) -> dict:
    met = sum(r["must_met"] for r in rows)
    scored = met + sum(r["must_not_met"] for r in rows)
    return {"scenarios": len(rows), "judged": sum(r["status"] == "judged" for r in rows),
            "must_met": met, "must_scored": scored, "must_na": sum(r["must_na"] for r in rows),
            "must_rate": round(met / scored, 3) if scored else None,
            "critical": sum(r["critical"] for r in rows)}


def aggregate(scores: list[dict], copies: list[str], threshold: float = MUST_THRESHOLD,
              selected: int | None = None) -> dict:
    """Totals, per role, and the release gate. Any scenario without a judgement, or a selected scenario
    that never ran, makes the set invalid."""
    roles = {role: _totals([s for s in scores if s["role"] == role])
             for role in ev.ROLES if any(s["role"] == role for s in scores)}
    total = _totals(scores)
    reasons = []
    for status, what in (("run_error", "errored"), ("timeout", "timed out without a finished retry"),
                         ("judge_error", "have no valid judgement")):
        bad = [s["id"] for s in scores if s["status"] == status]
        if bad:
            reasons.append(f"{len(bad)} scenario(s) {what}: {', '.join(bad)}")
    foreign = sum(c in ("other", "unknown") for c in copies)
    if foreign:
        reasons.append(f"{foreign} run(s) loaded a skill copy outside the temp project or an unidentified one")
    if not scores:
        reasons.append("no scenario selected")
    if selected is not None and selected > len(scores):
        reasons.append(f"{selected - len(scores)} selected scenario(s) not run (stopped early)")
    failed = []
    if total["critical"]:
        failed.append(f"{total['critical']} critical failure(s)")
    if total["must_rate"] is None or total["must_rate"] < threshold:
        failed.append(f"must met {total['must_rate']} < {threshold}")
    return {**total, "by_role": roles, "valid": not reasons, "invalid_reasons": reasons,
            "gate": {"threshold": threshold, "max_critical": 0, "passed": not reasons and not failed,
                     "failed": failed}}


def exit_code(summary: dict) -> int:
    if not summary["valid"]:
        return 3
    return 0 if summary["gate"]["passed"] else 1


# ---------------------------------------------------------------- orchestration

def _meta(host: str, model: str | None, judge: dict, run_id: str, now: float) -> dict:
    commit, dirty = ev.skill_git_state()
    return {"run_id": run_id, "date": time.strftime("%Y-%m-%d", time.gmtime(now)),
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "host": host,
            "cli_version": ev.tool_version(host), "model": model or "default", "skill_commit": commit,
            "skill_dirty": dirty, "judge_prompt": judge}


def write_results(kind: str, host: str, summary: dict, out_dir: str = RESULTS) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, ev.result_filename(f"{kind}-{host}", summary["run_id"]))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def execute(cases: list[dict], host: str, model: str | None, judge_model: str | None, timeout: int,
            judge_timeout: int, retry_timeouts: int = 0, dry_run: bool = False,
            host_bin: list[str] | None = None, out_dir: str = RESULTS, log=print) -> int:
    if not dry_run and not host_bin and not shutil.which(host):
        log(f"{host} CLI not found on PATH; nothing executed.")
        return 2
    judge = load_judge()
    hidden = ev.user_level_copies(host)
    if dry_run:
        for case in cases:
            log(f"{case['id']} [{case['role']}] fixture={case.get('fixture', DEFAULT_FIXTURE)}")
            ev.print_command(agent_command(host, "<temp-project>", model, "<settings.json>", hidden),
                             scenario_prompt(case))
        log("judge: " + " ".join(json.dumps(c) if not c or " " in c else c
                                 for c in judge_command(host, "<empty-folder>", judge_model, hidden)))
        return 0
    results, scores = [], []
    for case in cases:
        attempts = []
        while not attempts or (attempts[-1]["timed_out"] and len(attempts) <= retry_timeouts):
            attempts.append(run_scenario(case, host, model, timeout, hidden, host_bin))
        run = {**attempts[-1], "attempts": len(attempts)}
        judgement = None
        if not run["error"] and not run["timed_out"]:
            judgement = run_judge(case, run, judge, host, judge_model, judge_timeout, hidden, host_bin)
        row = score(case, run, judgement)
        scores.append(row)
        results.append({**row, "fixture": case.get("fixture", DEFAULT_FIXTURE), "run": run, "judge": judgement})
        log(f"{case['id']:<7} {case['role']:<14} {row['status']:<11} must {row['must_met']}/"
            f"{row['must_met'] + row['must_not_met']} (n/a {row['must_na']}) critical {row['critical']}"
            + (f" ERROR {run['error']}" if run["error"] else "")
            + (f" JUDGE {judgement['error']}" if judgement and judgement["error"] else ""))
        if hit_limit(run["error"]) or hit_limit(judgement and judgement["error"]):
            log(f"host usage limit reached: stopping, {len(cases) - len(results)} scenario(s) not run")
            break
    now = time.time()
    summary = {**_meta(host, model, judge, uuid.uuid4().hex[:6], now), "judge_model": judge_model or "default",
               "timeout_seconds": timeout, "retry_timeouts": retry_timeouts,
               **aggregate(scores, [r["run"]["copy"] for r in results], selected=len(cases)), "results": results}
    path = write_results("behavioral", host, summary, out_dir)
    for role, t in summary["by_role"].items():
        log(f"  {role:<14} must {t['must_met']}/{t['must_scored']} ({t['must_rate']}) critical {t['critical']}")
    gate = summary["gate"]
    log(f"must {summary['must_met']}/{summary['must_scored']} ({summary['must_rate']}), critical "
        f"{summary['critical']}; gate {'PASSED' if gate['passed'] else 'FAILED'}"
        + (f" ({'; '.join(gate['failed'])})" if gate["failed"] else "") + f"; wrote {path}")
    if not summary["valid"]:
        log("INVALID RESULTS: " + "; ".join(summary["invalid_reasons"]))
    return exit_code(summary)


def agreement(item: dict, judgement: dict) -> dict:
    """Items where the judge's verdict equals the expected one; a judge error agrees on nothing."""
    want = item["expected"]["must"] + item["expected"]["critical_failures"]
    base = {"file": item["file"], "scenario": item["scenario"], "label": item["label"], "items": len(want)}
    if judgement["error"]:
        return {**base, "agreed": 0, "error": judgement["error"], "disagreements": []}
    got = [m["verdict"] for m in judgement["must"]] + [c["verdict"] for c in judgement["critical_failures"]]
    return {**base, "agreed": sum(g == w for g, w in zip(got, want)), "error": None,
            "disagreements": [{"item": (judgement["must"] + judgement["critical_failures"])[i]["id"],
                               "expected": w, "judge": g} for i, (g, w) in enumerate(zip(got, want)) if g != w]}


def calibrate(host: str, judge_model: str | None, judge_timeout: int, host_bin: list[str] | None = None,
              out_dir: str = RESULTS, log=print) -> int:
    if not host_bin and not shutil.which(host):
        log(f"{host} CLI not found on PATH; nothing executed.")
        return 2
    cases = {c["id"]: c for c in ev.load()["behavioral"]}
    items = load_calibration()
    errors = check_calibration(items, cases)
    if errors:
        log("\n".join(f"FAIL: {e}" for e in errors))
        return 1
    judge = load_judge()
    hidden = ev.user_level_copies(host)
    rows = []
    for item in items:
        run = {"answer": item["answer"], "tools": item.get("tools") or [],
               "diff": {"text": item.get("diff") or ""}}
        judgement = run_judge(cases[item["scenario"]], run, judge, host, judge_model, judge_timeout, hidden, host_bin)
        row = {**agreement(item, judgement), "judge": judgement}
        rows.append(row)
        verdict = f"JUDGE ERROR {row['error']}" if row["error"] else f"{row['agreed']}/{row['items']} agreed"
        log(f"{item['file']:<28} {item['label']:<5} {verdict}")
        if hit_limit(judgement["error"]):
            log(f"host usage limit reached: stopping, {len(items) - len(rows)} answer(s) not judged")
            break
    agreed = sum(r["agreed"] for r in rows)
    total = sum(len(i["expected"]["must"]) + len(i["expected"]["critical_failures"]) for i in items)
    rate = round(agreed / total, 3) if total else 0.0
    judge_errors = sum(bool(r["error"]) for r in rows)
    now = time.time()
    summary = {**_meta(host, None, judge, uuid.uuid4().hex[:6], now), "judge_model": judge_model or "default",
               "judge_calls": len(rows), "agreed": agreed, "items": total, "agreement": rate,
               "target": CALIBRATION_TARGET, "judge_errors": judge_errors,
               "passed": rate >= CALIBRATION_TARGET and not judge_errors, "results": rows}
    path = write_results("calibration", host, summary, out_dir)
    log(f"agreement {agreed}/{total} = {rate} (target {CALIBRATION_TARGET}), {len(rows)} judge call(s), "
        f"{judge_errors} judge error(s); wrote {path}")
    return 0 if summary["passed"] else 1


def offline_check() -> list[str]:
    errors = []
    try:
        load_judge()
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    cases = {c["id"]: c for c in ev.load()["behavioral"]}
    items = load_calibration()
    if len(items) < 10:
        errors.append(f"judge calibration needs at least 10 labelled answers, found {len(items)}")
    if {i.get("label") for i in items} != {"good", "bad"}:
        errors.append("judge calibration needs both good and bad answers")
    return errors + check_calibration(items, cases)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="run scenarios and judge them (spends usage)")
    mode.add_argument("--calibrate", action="store_true", help="judge the labelled answers in evals/judge-calibration")
    ap.add_argument("--host", choices=("claude", "codex"), default="claude")
    ap.add_argument("--ids", help="comma-separated scenario ids")
    ap.add_argument("--roles", help=f"comma-separated roles from {', '.join(ev.ROLES)}")
    ap.add_argument("--split", choices=ev.SPLITS, default="all")
    ap.add_argument("--per-role", type=int, help="keep the first N scenarios of each role")
    ap.add_argument("--limit", type=int, help="run at most N scenarios")
    ap.add_argument("--model", help="model for the agent runs")
    ap.add_argument("--judge-model", help="model for the judge (default: the host's default)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per scenario run")
    ap.add_argument("--judge-timeout", type=int, default=300, help="seconds per judge call")
    ap.add_argument("--retry-timeouts", type=int, nargs="?", const=1, default=0, metavar="N",
                    help="re-run a timed-out scenario up to N times (bare flag: once)")
    ap.add_argument("--dry-run", action="store_true", help="with --execute: print the commands only")
    args = ap.parse_args(argv)

    data = ev.load()
    errors = ev.validate(data) + offline_check()
    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors))
        return 1
    judge = load_judge()
    print(f"OK: judge prompt v{judge['version']} ({judge['sha256'][:12]}), "
          f"{len(load_calibration())} calibration answers, {len(data['behavioral'])} behavioural scenarios.")
    if args.calibrate:
        return calibrate(args.host, args.judge_model, args.judge_timeout)
    if not args.execute:
        return 0
    cases = select(data["behavioral"], args.ids, args.roles, args.split, args.per_role, args.limit)
    return execute(cases, args.host, args.model, args.judge_model, args.timeout, args.judge_timeout,
                   args.retry_timeouts, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
