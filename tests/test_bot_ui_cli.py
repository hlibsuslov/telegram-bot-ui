"""bot-ui CLI from a clean folder: bootstrap, exact IDs, JSON shapes, exit codes, snapshot export."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from _bot_ui import CLI


def run(*args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd, env=env)
    return p.returncode, p.stdout, p.stderr


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bot-ui-cli-")
        self.root = os.path.join(self.tmp, "новый бот", "bot-ui")
        code, out, err = run("init", "--project", self.root, "--json")
        self.assertEqual(code, 0, err)
        self.init = json.loads(out)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def j(self, *args):
        code, out, err = run(*args, "--project", self.root, "--json")
        return code, json.loads(out) if out.strip() else None, err

    def test_init_publishes_a_complete_validated_tree_and_never_overwrites(self):
        self.assertEqual(self.init["projectId"], "demo-shop")
        self.assertIn("screens/checkout.payment.confirm.json", self.init["files"])
        self.assertFalse([n for n in os.listdir(os.path.dirname(self.root)) if "bot-ui-init" in n], "no staging left")
        code, out, _ = run("init", "--project", self.root, "--json")
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"]["code"], "TARGET_NOT_EMPTY")

    def test_list_show_exact_id_and_similar(self):
        code, doc, _ = self.j("list")
        self.assertEqual(code, 0)
        self.assertEqual(len(doc["screens"]), 10)
        code, doc, _ = self.j("show", "checkout.payment.confirm")
        self.assertEqual(doc["file"], "screens/checkout.payment.confirm.json")
        self.assertEqual(doc["revision"], self.init["revision"])
        self.assertEqual(doc["incoming"], [{"screenId": "checkout.note", "actionId": None, "via": "input"}])
        self.assertEqual({o["to"] for o in doc["outgoing"]}, {"checkout.payment.success", "checkout.payment.error"})
        code, doc, _ = self.j("show", "checkout.payment")
        self.assertEqual(code, 1)
        self.assertEqual(doc["error"]["code"], "SCREEN_NOT_FOUND")
        self.assertIn("checkout.payment.confirm", doc["error"]["similar"])

    def test_set_is_idempotent_and_conflicts_with_exit_3(self):
        rev = self.init["revision"]
        value = "<b>Подтвердите #{order.no}</b> · {order.total} · {order.note}"
        code, doc, _ = self.j("set", "checkout.payment.confirm", "/message/text/ru", value, "--expected-revision", rev)
        self.assertEqual(code, 0)
        self.assertEqual(doc["changedFiles"], ["screens/checkout.payment.confirm.json"])
        new = doc["revision"]
        code, doc, _ = self.j("set", "checkout.payment.confirm", "/message/text/ru", value, "--expected-revision", new)
        self.assertEqual((code, doc["changedFiles"], doc["diff"], doc["revision"]), (0, [], "", new))
        code, doc, err = self.j("set", "checkout.payment.confirm", "/message/text/ru", "x", "--expected-revision", rev)
        self.assertEqual(code, 3)
        self.assertEqual(doc["error"]["currentRevision"], new)
        self.assertIn("REVISION_CONFLICT", err)
        code, doc, _ = self.j("set", "checkout.payment.confirm", "/message/text/ru", value, "--expected-revision", rev,
                              "--dry-run")
        self.assertEqual(code, 3, "dry run checks the revision too")

    def test_validate_simulate_render_build(self):
        code, doc, _ = self.j("validate")
        self.assertEqual((code, doc["summary"]["error"]), (0, 0))
        code, doc, _ = self.j("simulate", "--all")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(r["scenarioId"] for r in doc["results"]),
                         ["checkout.happy", "checkout.retry", "orders.status"])
        code, doc, _ = self.j("simulate", "--scenario", "orders.status", "--context", "delivery.method=pickup")
        self.assertEqual(code, 1, "the courier expectation fails on the pickup branch")
        code, doc, _ = self.j("render", "checkout.payment.confirm", "--locale", "en")
        self.assertEqual(code, 0)
        self.assertEqual(doc["status"], "static")
        self.assertEqual(doc["request"]["params"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"],
                         "checkout.payment.confirm:pay")
        out = os.path.join(self.tmp, "build")
        code, doc, _ = self.j("build", "--output", out)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(out, "order-status.ru.html")))
        with open(os.path.join(out, "order-status.en.payload.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["method"], "sendWidget")

    def test_snapshot_export_has_no_local_paths(self):
        out = os.path.join(self.tmp, "snapshot.json")
        code, _, err = self.j("export-snapshot", "--format", "json", "--output", out)
        self.assertEqual(code, 0, err)
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        doc = json.loads(text)
        self.assertEqual(doc["format"], "bot-ui-snapshot/v1")
        self.assertEqual(doc["baseRevision"], self.init["revision"])
        for needle in (self.tmp, os.path.basename(self.tmp), "новый бот", os.environ.get("USERNAME", "\0")):
            self.assertNotIn(needle, text)
        self.assertNotIn("index.html", text, "widget sources stay out of the artifact")

    def test_import_refuses_a_bot_without_router_handlers(self):
        src = os.path.join(self.tmp, "custom-bot")
        os.makedirs(src)
        with open(os.path.join(src, "app.py"), "w", encoding="utf-8") as fh:
            fh.write("async def on_update(update):\n    if update.get('text') == '/start':\n        return 'hi'\n")
        target = os.path.join(self.tmp, "imported", "bot-ui")
        code, doc, _ = self.j("import", "--source", src, "--into", target)
        self.assertEqual(code, 1)
        self.assertEqual(doc["error"]["code"], "NO_HANDLERS_FOUND")
        self.assertFalse(os.path.exists(target), "nothing is created")

    def test_project_is_found_from_the_bot_repository_root(self):
        code, out, _ = run("list", "--json", cwd=os.path.dirname(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["projectId"], "demo-shop")


if __name__ == "__main__":
    unittest.main()
