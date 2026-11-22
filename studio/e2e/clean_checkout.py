#!/usr/bin/env python3
"""End-to-end acceptance on a clean checkout (offline after `npm ci`; synthetic data; no Telegram).

  py -3 studio/e2e/clean_checkout.py --repo <git url or path> [--ref feat/bot-ui-studio] --work <empty dir> [--keep]

Steps (each prints PASS/FAIL with the command it ran):
 1. clone the repository at --ref into <work>/telegram-bot-ui and run the skill installer
    into a fresh bot repository <work>/shop (project scope, Claude host);
 2. `bot-ui init` the demo project into <work>/shop/bot-ui, commit it in the bot repository;
 3. validate, simulate every scenario, render checkout.payment.confirm;
 4. start the Studio server, save a notification text change through its API exactly like
    the browser does (a bot-ui-patch/v1 from the draft), stop it; `git diff` shows one file;
 5. change checkout.payment.confirm by ID with the CLI (shorter ru/en text, a new action back
    to checkout.payment.choose) using the revision read before step 4 -> REVISION_CONFLICT;
    re-read, re-apply -> written; validate + simulate the new route;
 6. restart the Studio; the project document contains both changes;
 7. replay synthetic updates through the aiogram adapter (falls back to the raw adapter when
    aiogram is not installed) and check the confirm payload carries the new text and button;
 8. optional: build the widget and the artifact (when studio/web was built).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

RESULTS: list[tuple[str, bool, str]] = []
SHORT = {"ru": "<b>Заказ #{order.no}</b> · {order.total}\nКомментарий: {order.note}",
         "en": "<b>Order #{order.no}</b> · {order.total}\nNote: {order.note}"}
NOTIFY = {"ru": "🔔 Заказ #{order.no}: {order.status_text}. Откройте статус, чтобы узнать детали."}


def step(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"\n      {detail}" if detail else ""), flush=True)
    return ok


def sh(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1")
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env)
    if check and p.returncode != 0:
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p


def bu(clone: str, *args: str, check: bool = True) -> tuple[int, dict]:
    p = sh([sys.executable, os.path.join(clone, "studio", "bot-ui.py"), *args, "--json"], check=False)
    if check and p.returncode not in (0,):
        raise SystemExit(f"bot-ui {' '.join(args)} -> {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p.returncode, json.loads(p.stdout) if p.stdout.strip() else {}


class Studio:
    def __init__(self, clone: str, project: str) -> None:
        sys.path.insert(0, os.path.join(clone, "studio"))
        from bot_ui.server import serve
        ready, self.holder = threading.Event(), {}
        self.t = threading.Thread(target=serve, args=(project,), daemon=True,
                                  kwargs={"port": 0, "ready": ready, "holder": self.holder, "quiet": True})
        self.t.start()
        ready.wait(10)
        self.port, self.token = self.holder["studio"].port, self.holder["studio"].token

    def call(self, path: str, body: dict) -> tuple[int, dict]:
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        c.request("POST", path, json.dumps(body).encode(), {
            "Host": f"127.0.0.1:{self.port}", "Origin": f"http://127.0.0.1:{self.port}",
            "X-Bot-UI-Token": self.token, "Content-Type": "application/json"})
        r = c.getresponse()
        doc = json.loads(r.read())
        c.close()
        return r.status, doc

    def stop(self) -> None:
        self.holder["server"].shutdown()
        self.t.join(5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="feat/bot-ui-studio")
    ap.add_argument("--work", required=True)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    work = os.path.abspath(a.work)
    if os.path.exists(work) and os.listdir(work):
        raise SystemExit(f"{work} is not empty")
    os.makedirs(work, exist_ok=True)
    clone, shop = os.path.join(work, "telegram-bot-ui"), os.path.join(work, "shop")
    project = os.path.join(shop, "bot-ui")
    git = ["git", "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid", "-c", "core.autocrlf=false"]

    # 1
    sh(["git", "clone", "-q", "--branch", a.ref, a.repo, clone])
    head = sh(["git", "rev-parse", "HEAD"], cwd=clone).stdout.strip()
    os.makedirs(shop)
    sh(git + ["init", "-q"], cwd=shop)
    inst = sh([sys.executable, os.path.join(clone, "scripts", "install.py"), "--host", "claude", "--scope", "project",
               "--project", shop, "--home", os.path.join(work, "home")])
    skill_md = os.path.join(shop, ".claude", "skills", "telegram-bot-ui", "SKILL.md")
    step("1 clean clone + skill installed into the bot repository", os.path.isfile(skill_md),
         f"clone {head[:12]}; {inst.stdout.strip().splitlines()[-1] if inst.stdout.strip() else ''}")
    ref = os.path.join(shop, ".claude", "skills", "telegram-bot-ui", "references", "bot-ui-projects.md")
    step("1b installed skill carries the bot-ui route", os.path.isfile(ref))

    # 2
    code, init = bu(clone, "init", "--project", project)
    sh(git + ["add", "-A"], cwd=shop)
    sh(git + ["commit", "-qm", "bot-ui: demo shop"], cwd=shop)
    step("2 bot-ui init + commit", code == 0, f"revision {init['revision']}")

    # 3
    _, val = bu(clone, "validate", "--project", project)
    code, sim = bu(clone, "simulate", "--all", "--project", project, check=False)
    _, ren = bu(clone, "render", "checkout.payment.confirm", "--project", project)
    step("3 validate / simulate --all / render", val["summary"]["error"] == 0 and code == 0 and ren["ok"],
         f"{len(sim['results'])} scenarios ok, render status {ren['status']}")

    # 4 Studio save (the browser builds this patch from its draft with src/core/patch.ts)
    base_rev = init["revision"]
    st = Studio(clone, project)
    _, doc = st.call("/api/project", {})
    old = doc["screens"]["orders.notification"]["message"]["text"]["ru"]
    patch = {"format": "bot-ui-patch/v1", "projectId": doc["project"]["projectId"], "baseRevision": doc["revision"],
             "changes": [{"screenId": "orders.notification",
                          "ops": [{"op": "set", "path": "/message/text/ru", "value": NOTIFY["ru"], "from": old}]}]}
    status, saved = st.call("/api/save", {"patch": patch})
    st.stop()
    diff = sh(["git", "diff", "--name-only"], cwd=shop).stdout.split()
    step("4 Studio save of orders.notification -> one-file git diff", status == 200 and
         diff == ["bot-ui/screens/orders.notification.json"], f"changed: {diff}")

    # 5 agent edit by ID from the stale revision, then retry
    ops = [{"op": "set", "path": "/message/text/ru", "value": SHORT["ru"]},
           {"op": "set", "path": "/message/text/en", "value": SHORT["en"]},
           {"op": "set", "path": "/actions/methods", "value": {
               "label": {"ru": "← Способ оплаты", "en": "← Payment method"}, "type": "navigate",
               "to": "checkout.payment.choose"}},
           {"op": "set", "path": "/keyboard/rows", "value": [["pay"], ["methods"]]}]
    pf = os.path.join(work, "confirm.ops.json")
    with open(pf, "w", encoding="utf-8") as fh:
        json.dump({"ops": ops}, fh, ensure_ascii=False)
    code, conflict = bu(clone, "patch", "checkout.payment.confirm", "--patch-file", pf, "--expected-revision", base_rev,
                        "--project", project, check=False)
    step("5a stale revision -> REVISION_CONFLICT (exit 3), Studio text kept",
         code == 3 and conflict["error"]["currentRevision"] == saved["revision"])
    _, show = bu(clone, "show", "checkout.payment.confirm", "--project", project)
    code, wrote = bu(clone, "patch", "checkout.payment.confirm", "--patch-file", pf, "--expected-revision",
                     show["revision"], "--project", project)
    _, again = bu(clone, "patch", "checkout.payment.confirm", "--patch-file", pf, "--expected-revision",
                  wrote["revision"], "--project", project)
    step("5b re-read + patch written; same patch again is empty", wrote["changedFiles"] ==
         ["screens/checkout.payment.confirm.json"] and again["diff"] == "" and again["changedFiles"] == [])
    _, val = bu(clone, "validate", "--project", project)
    scen = {"scenarioId": "checkout.change-method", "locale": "ru", "context": {"delivery.method": "pickup"},
            "data": {"order.no": "4821", "order.total": "1 290 ₽"}, "handlers": {"checkout.confirm": ["ok"]},
            "steps": [{"command": "start"}, {"press": "order"}, {"press": "card"}, {"text": "Домофон 7"},
                      {"press": "methods"}, {"expect": {"screen": "checkout.payment.choose"}}, {"press": "cash"},
                      {"text": "Домофон 7"}, {"press": "pay"}, {"expect": {"screen": "checkout.payment.success"}}]}
    with open(os.path.join(project, "scenarios", "checkout.change-method.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(scen, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    code, sim = bu(clone, "simulate", "--scenario", "checkout.change-method", "--project", project, check=False)
    step("5c validate + new route simulated", val["summary"]["error"] == 0 and code == 0,
         " -> ".join(e["transition"]["to"] for e in sim["trace"] if e["transition"]))
    names = sh(["git", "diff", "--name-only"], cwd=shop).stdout.split() + \
        sh(["git", "ls-files", "--others", "--exclude-standard"], cwd=shop).stdout.split()
    step("5d git diff limited to the expected sources", sorted(names) == sorted([
        "bot-ui/screens/orders.notification.json", "bot-ui/screens/checkout.payment.confirm.json",
        "bot-ui/scenarios/checkout.change-method.json"]), f"{sorted(names)}")

    # 6 restart
    st = Studio(clone, project)
    _, doc = st.call("/api/project", {})
    st.stop()
    conf = doc["screens"]["checkout.payment.confirm"]
    step("6 Studio restart shows both changes", doc["screens"]["orders.notification"]["message"]["text"]["ru"] ==
         NOTIFY["ru"] and conf["message"]["text"]["ru"] == SHORT["ru"] and "methods" in conf["actions"])

    # 7 adapter
    sys.path.insert(0, os.path.join(clone, "studio", "adapters"))
    with open(os.path.join(clone, "studio", "fixtures", "updates", "checkout.json"), encoding="utf-8") as fh:
        fixture = json.load(fh)
    import asyncio
    import demo_bot
    try:
        import aiogram  # noqa: F401
        calls, which = asyncio.run(demo_bot.replay_aiogram(project, fixture)), "aiogram 3.31.0"
    except ImportError:
        calls, which = asyncio.run(demo_bot.replay_raw(project, fixture)), "raw tgkit (aiogram not installed)"
    checked = demo_bot.check(calls)
    confirm = next(c for c in checked if c["method"] == "sendMessage" and "Заказ #4821" in c["params"]["text"]
                   and "Комментарий" in c["params"]["text"])
    kb = confirm["params"]["reply_markup"]["inline_keyboard"]
    step(f"7 adapter ({which}) payload carries the change and passes the catalog check",
         all(c["ok"] for c in checked) and kb[1][0]["callback_data"] == "checkout.payment.confirm:methods",
         confirm["params"]["text"].replace("\n", " / "))

    # 8 optional builds
    _, b = bu(clone, "build", "--project", project, check=False)
    step("8a widget build", b.get("ok", False), "; ".join(f"{w['lang']}: {w['rawBytes']} B / {w['compressedBytes']} B zlib-9"
                                                    for w in b.get("widgets", [])))
    dist = os.path.join(clone, "studio", "web", "dist-artifact", "index.html")
    if os.path.isfile(dist):
        code, art = bu(clone, "export-snapshot", "--project", project, "--output", os.path.join(work, "studio.html"),
                       check=False)
        step("8b artifact export", code == 0, art.get("output", ""))
    else:
        print("SKIP  8b artifact export (studio/web not built in this clone)")

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed · work dir {work}")
    if not a.keep and not failed:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
