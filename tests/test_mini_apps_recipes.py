"""Mini App recipes R90-R99: the bot/server scenarios run and check themselves, the payload files match the code,
every captured request is valid against the Bot API snapshot, and the bot-side module keeps its invariants."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest

import _paths
import tg_api_lookup as lookup
import validate_payload as vp

sys.path.insert(0, os.path.join(_paths.EXAMPLES, "python", "recipes"))
sys.path.insert(0, os.path.join(_paths.EXAMPLES, "mini-apps", "bot"))
import r90_99_mini_apps as r  # noqa: E402
from bot_side import MiniAppBot  # noqa: E402
from tgkit.transport import FakeTransport  # noqa: E402

V = vp.Validator(lookup.Api().cat)
PAYLOADS = os.path.join(_paths.EXAMPLES, "payloads")


class Scenarios(unittest.TestCase):
    def test_all_scenarios_self_check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            sys.argv, saved = [r.__file__], sys.argv
            try:
                r.main()
            finally:
                sys.argv = saved

    def test_payload_files_match_the_code(self):
        res = subprocess.run([sys.executable, os.path.join(_paths.EXAMPLES, "python", "export_mini_app_payloads.py"), "--check"],
                             capture_output=True, text=True, cwd=_paths.ROOT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_every_step_is_a_valid_request(self):
        names = [n for n in os.listdir(PAYLOADS) if n.startswith("r9") and n.endswith(".json")]
        self.assertEqual(len(names), 10)
        for name in names:
            with open(os.path.join(PAYLOADS, name), encoding="utf-8") as fh:
                doc = json.load(fh)
            for i, step in enumerate(doc["steps"]):
                with self.subTest(payload=name, step=i):
                    rep = V.check_request(step["method"], step["params"])
                    self.assertTrue(rep.ok, rep.errors)


class BotSide(unittest.TestCase):
    def bot(self):
        t = FakeTransport()
        return t, MiniAppBot(t, bot_username="@coffee_bot", app_url="https://c.example.com/app", app_short_name="pickup")

    def test_links_validate_start_param_and_mode(self):
        _, b = self.bot()
        self.assertEqual(b.link("order-12", mode="fullscreen"), "https://t.me/coffee_bot/pickup?startapp=order-12&mode=fullscreen")
        for bad in ("order 12", "x" * 513, "../x", ""):
            with self.assertRaises(ValueError):
                b.link(bad)
        with self.assertRaises(ValueError):
            b.link("ok", mode="half")

    def test_query_answered_once_and_write_access_gate(self):
        t, b = self.bot()
        self.assertTrue(b.answer_query_once("q1", {"type": "article", "id": "1", "title": "t", "input_message_content": {"message_text": "x"}}))
        self.assertFalse(b.answer_query_once("q1", {}))
        self.assertFalse(b.answer_query_once("", {}))
        self.assertFalse(b.notify(1, "hi"))
        b.on_write_access_allowed({"from": {"id": 1}, "write_access_allowed": {}})
        self.assertTrue(b.notify(1, "hi"))
        self.assertEqual([m for m, _ in t.calls], ["answerWebAppQuery", "sendMessage"])

    def test_web_app_data_limits(self):
        t, b = self.bot()
        big = {"chat": {"id": 1}, "web_app_data": {"data": "x" * 5000}}
        self.assertIsNone(b.on_web_app_data(big, lambda d: d))
        self.assertEqual(t.calls, [])  # oversized data is dropped before parsing

    def test_join_request_needs_a_query_id(self):
        t, b = self.bot()
        self.assertIsNone(b.join_request({"chat_join_request": {"chat": {"id": -1}}}))
        b.join_request({"chat_join_request": {"query_id": "J1"}})
        b.join_request({"chat_join_request": {"query_id": "J2"}}, verify_in_app=False)
        self.assertEqual([m for m, _ in t.calls], ["sendChatJoinRequestWebApp", "answerChatJoinRequestQuery"])


if __name__ == "__main__":
    unittest.main()
