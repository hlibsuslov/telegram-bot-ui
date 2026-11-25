"""tgui.py: the single entry point, project context, findings, Studio requests, signals, hook."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _paths

import tgui

TGUI = os.path.join(_paths.ROOT, "scripts", "tgui.py")
NL = "\n"


def run(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, TGUI, *args], cwd=cwd, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tgui-test-")
        with open(os.path.join(self.tmp, "bot.py"), "w", encoding="utf-8") as fh:
            fh.write("from aiogram.types import InlineKeyboardButton\nB = InlineKeyboardButton(text='Pay', "
                     "callback_data='pay')\n")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q", self.tmp], check=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finding_ids_are_stable_and_updates_do_not_duplicate(self):
        self.assertEqual(tgui.finding_id("s", "r", "f:1"), tgui.finding_id("s", "r", "f:1"))
        self.assertNotEqual(tgui.finding_id("s", "r", "f:1"), tgui.finding_id("s", "r", "f:2"))
        for summary in ("Two primary buttons", "Two primary buttons on the confirm screen"):
            r = run("findings", "add", "--severity", "P1", "--screen", "start", "--rule", "one-primary",
                    "--where", "bot.py:2", "--summary", summary, "--root", self.tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
        items = json.load(open(os.path.join(self.tmp, "bot-ui", "context", "findings.json"), encoding="utf-8"))
        self.assertEqual(items["schema"], "bot-ui-findings/v1")
        self.assertEqual(len(items["items"]), 1)
        self.assertIn("confirm screen", items["items"][0]["summary"])
        fid = items["items"][0]["id"]
        self.assertEqual(run("findings", "close", fid, "--root", self.tmp).returncode, 0)
        self.assertEqual(run("findings", "list", "--open", "--json", "--root", self.tmp).stdout.strip(), "[]")

    def test_signals_rank_requests_before_findings_and_next_runs_nothing(self):
        run("findings", "add", "--severity", "P1", "--screen", "start", "--rule", "r", "--where", "bot.py:2",
            "--summary", "Dead end", "--fix", "fix", "--root", self.tmp)
        rid = run("requests", "add", "--screen", "start", "--text", "Shorten", "--root", self.tmp).stdout.strip()
        self.assertTrue(rid.startswith("rq-"))
        out = json.loads(run("next", "--json", "--root", self.tmp).stdout)
        verbs = [s["verb"] for s in out["suggestions"]]
        self.assertEqual(verbs[:2], ["map", "fix"])
        self.assertLessEqual(len(out["suggestions"]), 3)
        self.assertEqual(run("requests", "take", rid, "--root", self.tmp).returncode, 0)
        self.assertEqual(run("requests", "take", rid, "--root", self.tmp).returncode, 4)  # not queued any more
        self.assertEqual(run("requests", "done", rid, "--result", "ok", "--root", self.tmp).returncode, 0)

    def test_context_text_stays_under_the_limit(self):
        for i in range(40):
            run("requests", "add", "--screen", f"s{i}", "--text", "x" * 300, "--root", self.tmp)
        r = run("context", "--root", self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLessEqual(len(r.stdout.strip()), tgui.CONTEXT_LIMIT)
        self.assertIn("REQUESTS_QUEUED", r.stdout)

    def test_refresh_writes_context_outside_the_map_revision(self):
        self.assertEqual(run("map", "init", "--project", os.path.join(self.tmp, "bot-ui")).returncode, 0)
        before = json.loads(run("map", "validate", "--project", os.path.join(self.tmp, "bot-ui"), "--json").stdout)
        self.assertEqual(run("context", "--refresh", "--root", self.tmp).returncode, 0)
        run("findings", "add", "--severity", "P2", "--rule", "r", "--summary", "s", "--root", self.tmp)
        after = json.loads(run("map", "validate", "--project", os.path.join(self.tmp, "bot-ui"), "--json").stdout)
        self.assertEqual(before["revision"], after["revision"])
        ctx = json.load(open(os.path.join(self.tmp, "bot-ui", "context", "context.json"), encoding="utf-8"))
        self.assertEqual(ctx["schema"], "bot-ui-context/v1")

    def test_map_init_keeps_a_saved_review(self):
        run("findings", "add", "--severity", "P2", "--rule", "r", "--summary", "s", "--root", self.tmp)
        r = run("map", "init", "--project", os.path.join(self.tmp, "bot-ui"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "bot-ui", "context", "findings.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "bot-ui", "project.json")))

    def test_hook_is_silent_on_other_files_and_short_on_a_bad_keyboard(self):
        quiet = run("hook", "post-edit", stdin=json.dumps({"tool_input": {"file_path": os.path.join(self.tmp, "a.txt")}}))
        self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))
        kb = os.path.join(self.tmp, "kb.json")
        with open(kb, "w", encoding="utf-8") as fh:
            json.dump({"inline_keyboard": [[{"text": "A", "callback_data": "a", "style": "primary"},
                                             {"text": "B", "callback_data": "b", "style": "primary"}]]}, fh)
        loud = run("hook", "post-edit", stdin=json.dumps({"tool_input": {"file_path": kb}}))
        self.assertEqual(loud.returncode, 0)
        note = json.loads(loud.stdout)["hookSpecificOutput"]
        self.assertEqual(note["hookEventName"], "PostToolUse")
        self.assertIn("primary", note["additionalContext"])
        self.assertLessEqual(len(note["additionalContext"]), 600)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_check_changed_routes_payloads_rich_messages_and_posts_and_counts_what_it_cannot_check(self):
        def put(name, text):
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)

        def changed():
            r = run("check", "changed", "--json", "--root", self.tmp)
            return r.returncode, json.loads(r.stdout), r

        code, out, r = changed()  # only bot.py (handler code) changed: no checker reads it
        self.assertEqual((code, out["checked"], out["unchecked"]), (0, [], ["bot.py"]), r.stdout)
        text = run("check", "changed", "--root", self.tmp).stdout
        self.assertIn("1 changed file(s) not checkable offline", text)
        self.assertNotIn("no changed Telegram files", text)
        put("payload.json", json.dumps({"method": "sendMessage", "params": {"chat_id": 1, "text": "x", "bogus": 1}}))
        put("rich.json", json.dumps({"rich_message": {"html": '<tg-button type="url" url="https://t.me" style="link">x</tg-button>'}}))
        put("steps.json", json.dumps({"steps": [{"method": "sendRichMessage", "params": {"chat_id": 1, "rich_message": {
            "html": '<tg-button type="pay">Pay</tg-button>'}}}]}))
        put("post.md", "---" + NL + "kind: announcement" + NL + "---" + NL + NL + "# Title" + NL + NL +
            "[button: Go](javascript:alert(1))" + NL)
        put("README.md", "# My bot" + NL + NL + "Nothing Telegram-specific to validate here." + NL)
        put("package.json", json.dumps({"name": "bot", "html": "<p>x</p>", "markdown": "y"}))
        code, out, r = changed()
        by_file = {c["file"]: c for c in out["checked"]}
        self.assertEqual(sorted(by_file), ["payload.json", "post.md", "rich.json", "steps.json"], r.stdout)
        self.assertEqual({f: c["checker"] for f, c in by_file.items()},
                         {"payload.json": "check payload", "rich.json": "check rich", "post.md": "post validate",
                          "steps.json": "check payload"})
        self.assertTrue(all(c["exit"] == 1 for c in by_file.values()), by_file)
        self.assertTrue(any("RICH_BUTTON_TYPE" in p for p in by_file["steps.json"]["problems"]), by_file["steps.json"])
        self.assertEqual((code, out["failed"], out["unchecked"]), (1, 4, ["bot.py"]))

    def test_hook_install_is_idempotent_and_reversible(self):
        for _ in range(2):
            self.assertEqual(run("hook", "install", "--root", self.tmp).returncode, 0)
        settings = json.load(open(os.path.join(self.tmp, ".claude", "settings.local.json"), encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["PostToolUse"]), 1)
        self.assertEqual(run("hook", "uninstall", "--root", self.tmp).returncode, 0)
        settings = json.load(open(os.path.join(self.tmp, ".claude", "settings.local.json"), encoding="utf-8"))
        self.assertNotIn("PostToolUse", settings["hooks"])
        self.assertEqual(run("hook", "install", "--host", "codex", "--root", self.tmp).returncode, 4)


class Dispatch(unittest.TestCase):
    def test_every_group_answers_help(self):
        groups = [*tgui.PASS, *tgui.SUB, "map", "context", "next", "doctor", "findings", "requests", "hook"]
        for group in groups:
            with self.subTest(group=group):
                r = run(group, "--help")
                self.assertEqual(r.returncode, 0, f"{group}: {r.stdout[-300:]} {r.stderr[-300:]}")

    def test_unknown_subcommand_is_a_usage_error(self):
        self.assertEqual(run("check", "nonsense").returncode, 2)

    def test_doctor_reports_copies_with_another_version(self):
        home = tempfile.mkdtemp(prefix="tgui-home-")
        try:
            old = os.path.join(home, ".claude", "skills", "telegram-bot-ui")
            os.makedirs(old)
            with open(os.path.join(old, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write('---\nname: telegram-bot-ui\nmetadata:\n  version: "2.2.1"\n---\n')
            env = dict(os.environ, HOME=home, USERPROFILE=home)
            r = subprocess.run([sys.executable, TGUI, "doctor", "--json", "--root", home], capture_output=True,
                               text=True, encoding="utf-8", env=env)
            found = [f for f in json.loads(r.stdout)["findings"] if f["id"] == "OTHER_COPY"]
            self.assertTrue(found and "2.2.1" in found[0]["message"])
            self.assertEqual(r.returncode, 1)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_suggestions_format_every_signal(self):
        data = {"signals": {s["id"]: {"n": 2, "screen": "x", "summary": "y", "fixWith": "improve", "commit": "abc"}
                            for s in tgui._index()["signals"]}}
        sugg = tgui.suggestions(data, limit=99)
        self.assertEqual(len(sugg), len(tgui._index()["signals"]))
        self.assertTrue(all("{" not in s["why"] and "?" not in s["verb"] for s in sugg))


if __name__ == "__main__":
    unittest.main()
