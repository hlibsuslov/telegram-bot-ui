"""bot-ui simulation engine and the Python/TypeScript parity (skills/telegram-bot-ui/scripts/bot_ui/engine.py, studio/web/src/core)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _bot_ui import FIXTURES, STUDIO, TEMPLATE, ProjectCase
from bot_ui.engine import Engine, new_session, parity_view, run_scenario
from bot_ui.project import open_snapshot

CORE = os.path.join(STUDIO, "web", "src", "core")


def node_ok() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    ver = tuple(int(x) for x in re.findall(r"\d+", out)[:2])
    return node if ver >= (22, 18) else None


class Scenarios(unittest.TestCase):
    def setUp(self):
        self.snap = open_snapshot(TEMPLATE)

    def test_every_fixture_scenario_passes_and_is_deterministic(self):
        for name, sc in self.snap.scenarios.items():
            with self.subTest(name):
                a, b = run_scenario(self.snap, sc), run_scenario(self.snap, sc)
                self.assertTrue(a["ok"], [d for e in a["trace"] for d in e["diagnostics"]])
                self.assertEqual(json.dumps(parity_view(a), sort_keys=True), json.dumps(parity_view(b), sort_keys=True))

    def test_both_rule_branches(self):
        for method, target in (("pickup", "orders.pickup"), ("courier", "orders.delivery")):
            r = run_scenario(self.snap, {"locale": "ru", "context": {"delivery.method": method}, "data": {},
                                         "steps": [{"command": "status"}, {"press": "route"}]})
            tr = r["trace"][1]["transition"]
            self.assertEqual(tr["to"], target)
            self.assertEqual(tr["rule"], {"field": "delivery.method", "matched": method == "pickup",
                                          "branch": "match" if method == "pickup" else "otherwise"})
            self.assertNotIn(method, json.dumps(tr["rule"]), "the rule trace shows the branch, not the value")

    def test_retry_loading_stale_and_back_fallback(self):
        r = run_scenario(self.snap, self.snap.scenarios["checkout.retry"])
        pay = r["trace"][4]
        self.assertEqual([e["type"] for e in pay["effects"]], ["answer", "edit", "edit"])
        self.assertEqual(pay["effects"][1]["view"]["state"], "loading")
        stale = r["trace"][6]
        self.assertEqual(stale["action"]["type"], "stale")
        self.assertEqual([e["type"] for e in stale["effects"]], ["answer"])
        self.assertIsNone(stale["transition"])
        s = new_session(self.snap.project)
        eng = Engine(self.snap)
        eng.feed(s, {"command": "status"})
        back = eng.feed(s, {"press": "back"})
        self.assertEqual(back["transition"]["via"], "back-fallback")
        self.assertEqual(back["transition"]["to"], "entry.start")

    def test_notification_from_event_and_widget_fallback_outside_private(self):
        r = run_scenario(self.snap, self.snap.scenarios["orders.status"])
        first = r["trace"][0]
        self.assertEqual(first["effects"][0]["type"], "send")
        self.assertIn("courier on the way", first["effects"][0]["view"]["text"])
        last_status = r["trace"][10]
        self.assertEqual(last_status["effects"][0], {"type": "fallback", "reason": "widget_unsupported",
                                                     "screenId": "orders.status"})
        self.assertEqual(last_status["effects"][1]["kind"], "message")

    def test_text_input_limit_and_unexpected_text(self):
        s = new_session(self.snap.project, data={"order.total": "1"})
        eng = Engine(self.snap)
        eng.feed(s, {"command": "start"})
        self.assertEqual(eng.feed(s, {"text": "hello"})["effects"][0]["type"], "noop")
        eng.feed(s, {"press": "order"})
        eng.feed(s, {"press": "card"})
        long = eng.feed(s, {"text": "я" * 201})
        self.assertEqual([d["code"] for d in long["diagnostics"]], ["INPUT_TOO_LONG"])
        self.assertEqual(s["screen"], "checkout.note")
        ok = eng.feed(s, {"text": "🙂 коротко"})
        self.assertEqual(ok["transition"]["to"], "checkout.payment.confirm")


@unittest.skipUnless(node_ok(), "needs Node >= 22.18 for .ts type stripping")
class Parity(unittest.TestCase):
    def test_typescript_engine_matches_python_on_every_scenario(self):
        out = subprocess.run([node_ok(), os.path.join(CORE, "parity-cli.ts"), TEMPLATE], capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
        ts = json.loads(out)
        snap = open_snapshot(TEMPLATE)
        for name, sc in snap.scenarios.items():
            with self.subTest(name):
                self.assertEqual(json.dumps(ts[name], sort_keys=True, ensure_ascii=False),
                                 json.dumps(parity_view(run_scenario(snap, sc)), sort_keys=True, ensure_ascii=False))

    def test_typescript_lint_reports_the_failure_fixtures_like_python(self):
        cases = os.path.join(FIXTURES, "failures", "cases.json")
        out = subprocess.run([node_ok(), os.path.join(CORE, "lint-cli.ts"), TEMPLATE, cases], capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
        ts = json.loads(out)
        with open(cases, encoding="utf-8") as fh:
            for case in json.load(fh)["cases"]:
                found = {(d["code"], d["pointer"]) for d in ts[case["name"]] if d["severity"] == "error"}
                self.assertIn((case["expect"]["code"], case["expect"]["pointer"]), found, case["name"])

    def test_typescript_lint_is_clean_on_the_template(self):
        cases = os.path.join(tempfile.mkdtemp(prefix="bot-ui-lint-"), "empty-cases.json")
        with open(cases, "w", encoding="utf-8") as fh:
            json.dump({"cases": [{"name": "none", "screenId": "entry.start", "ops": []}]}, fh)
        try:
            out = subprocess.run([node_ok(), os.path.join(CORE, "lint-cli.ts"), TEMPLATE, cases], capture_output=True,
                                 text=True, encoding="utf-8", check=True).stdout
        finally:
            os.remove(cases)
        self.assertEqual(json.loads(out)["none"], [])


class Edited(ProjectCase):
    def test_saved_change_reaches_the_next_simulation(self):
        from bot_ui.store import write_patch
        snap = open_snapshot(self.root)
        write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": snap.revision, "changes": [
            {"screenId": "orders.status", "ops": [{"op": "set", "path": "/actions/route/rule/when/eq", "value": "courier"}]}]})
        r = run_scenario(open_snapshot(self.root), {"context": {"delivery.method": "courier"},
                                                    "steps": [{"command": "status"}, {"press": "route"}]})
        self.assertEqual(r["trace"][1]["transition"]["to"], "orders.pickup")


if __name__ == "__main__":
    unittest.main()
