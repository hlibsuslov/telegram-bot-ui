#!/usr/bin/env python3
"""Validate the eval set, or execute its activation cases against a host CLI.

  python scripts/run_evals.py                      # validate evals/evals.json (offline)
  python scripts/run_evals.py --execute --host claude [--ids P1,PUB4] [--limit 10] [--model M]
  python scripts/run_evals.py --execute --host codex --dry-run   # print the commands only

Validation checks structure, unique ids, coverage (every capability area has English,
Russian and no-method-named positives; negatives exist in both languages; the required
behavioural topics and transfer tasks are present) and that every id also appears in
the human-readable tables in evals/*.md.

Execution installs the skill into a throwaway project folder (never the user profile),
runs each activation prompt through the host's non-interactive mode with write tools
disabled, and records whether the agent loaded the skill. It spends the account's usage
and needs the CLI to be logged in; results go to evals/results/<date>-<host>.json and are
never merged into evals.json automatically. Behavioural tasks are graded by a person
(see evals/behavioral-evals.md); this script does not grade them.
"""
# run-checks:
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(ROOT, "evals", "evals.json")
CAPABILITY_AREAS = ("ui", "use-cases", "publishing", "agent-ops", "widgets", "api-lookup", "mini-apps")
LANGS = ("en", "ru")              # every area needs positives in these
ALLOWED_LANGS = LANGS + ("uk",)    # extra languages a case may use
REQUIRED_BEHAVIORAL = ("B20", "B21", "B22", "B30", "B31", "B32", "B40", "B41", "B42",
                       "B50", "B51", "B52", "B60")
TRANSFER_AREAS = ("publishing", "agent-ops", "widgets", "use-cases", "api-lookup")


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

    behavioral_ids: dict[str, dict] = {}
    for b in data["behavioral"]:
        cid = check_id(b, "behavioral")
        behavioral_ids[cid] = b
        if b.get("area") not in areas or b.get("area") == "out-of-scope":
            errors.append(f"{cid}: behavioural area must be a capability area")
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


# ---------------------------------------------------------------- execution

READ_ONLY_DENY = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch"


def host_command(host: str, prompt: str, project: str, model: str | None) -> list[str]:
    if host == "claude":
        model_args = ["--model", model] if model else []
        return ["claude", *model_args, "-p", prompt, "--output-format", "stream-json", "--verbose",
                "--no-session-persistence", "--disallowedTools", READ_ONLY_DENY]
    if host == "codex":
        model_args = ["-m", model] if model else []
        return ["codex", "exec", *model_args, "--json", "--skip-git-repo-check", "--ephemeral",
                "-s", "read-only", "-C", project, prompt]
    raise ValueError(f"unsupported host {host}")


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def skill_loaded(host: str, output: str) -> bool:
    """Did the transcript load the skill? Claude: a Skill call or a read of its SKILL.md."""
    norm = output.replace("\\\\", "/").replace("\\", "/")
    if host == "codex":
        return "telegram-bot-ui/SKILL.md" in norm
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for node in _walk(event):
            if node.get("type") != "tool_use":
                continue
            args = json.dumps(node.get("input", {})).replace("\\\\", "/")
            if node.get("name") == "Skill" and "telegram-bot-ui" in args:
                return True
            if node.get("name") == "Read" and "telegram-bot-ui/SKILL.md" in args:
                return True
    return False


def prepare_project(host: str) -> str:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import install  # noqa: PLC0415

    project = tempfile.mkdtemp(prefix="tgui-evals-")
    home = tempfile.mkdtemp(prefix="tgui-evals-home-")
    inst = install.Installer(home=home, project=project, dry_run=False, link=False)
    inst.install(host, "project", agents=False, instructions=False)
    if shutil.which("git"):
        subprocess.run(["git", "init", "-q", project], check=False)
    return project


def execute(cases: list[dict], host: str, model: str | None, timeout: int, dry_run: bool) -> int:
    if not dry_run and not shutil.which(host):
        print(f"{host} CLI not found on PATH; nothing executed.")
        return 2
    project = prepare_project(host) if not dry_run else "<temp-project>"
    results = []
    for case in cases:
        cmd = host_command(host, case["prompt"], project, model)
        if dry_run:
            print(" ".join(json.dumps(c) if " " in c else c for c in cmd))
            continue
        start = time.time()
        try:
            # Windows npm installs the CLI as a .cmd shim that CreateProcess can't find by name.
            cmd = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
            proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            output, status = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            output, status = "", "timeout"
        activated = skill_loaded(host, output)
        ok = activated == (case["expect"] == "activate")
        results.append({"id": case["id"], "expect": case["expect"], "activated": activated,
                        "ok": ok, "exit": status, "seconds": round(time.time() - start, 1)})
        print(f"{case['id']:<6} expect={case['expect']:<8} activated={activated!s:<5} {'ok' if ok else 'MISS'}")
    if dry_run:
        return 0
    tp = sum(r["activated"] and r["expect"] == "activate" for r in results)
    fp = sum(r["activated"] and r["expect"] == "skip" for r in results)
    fn = sum(not r["activated"] and r["expect"] == "activate" for r in results)
    summary = {"host": host, "model": model or "default",
               "date": time.strftime("%Y-%m-%d", time.gmtime()),
               "cases": len(results), "correct": sum(r["ok"] for r in results),
               "true_positive": tp, "false_positive": fp, "false_negative": fn, "results": results}
    out_dir = os.path.join(ROOT, "evals", "results")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{summary['date']}-{host}.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2)
        fh.write("\n")
    print(f"\n{summary['correct']}/{len(results)} correct (TP {tp}, FP {fp}, FN {fn}); wrote {out}")
    return 0 if summary["correct"] == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--execute", action="store_true", help="run activation cases against a host CLI")
    ap.add_argument("--host", choices=("claude", "codex"), default="claude")
    ap.add_argument("--ids", help="comma-separated case ids (default: all activation cases)")
    ap.add_argument("--limit", type=int, help="run at most N cases")
    ap.add_argument("--model", help="model passed to the host CLI")
    ap.add_argument("--timeout", type=int, default=240, help="seconds per case")
    ap.add_argument("--dry-run", action="store_true", help="with --execute: print commands only")
    args = ap.parse_args(argv)

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
    cases = data["activation"]
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]
    return execute(cases, args.host, args.model, args.timeout, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
