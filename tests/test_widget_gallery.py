"""Gallery handlers: demo contract, authorization, stale revisions, duplicate queries, answer
exactly once within the size limit, shared votes per (widget_id, from.id), payload drift."""
import json
import os
import subprocess
import sys
import unittest

import _paths
from tgkit.transport import FakeTransport, TelegramErrorResponse
from widget_gallery import SPECS, GalleryBot, parse, query
from widget_gallery import h_api_browser

SECRET_WORDS = ("token", "bearer", "api_key", "apikey", "password", "secret")


def answers(t):
    return [json.loads(p["data"]) for p in t.params_of("answerWidgetQuery")]


class Demos(unittest.TestCase):
    def test_every_widget_has_a_handler_and_a_complete_demo(self):
        built = {n[:-5] for n in os.listdir(os.path.join(_paths.EXAMPLES, "widgets", "src")) if n.endswith(".html")}
        self.assertEqual(built, set(SPECS))
        for name, spec in SPECS.items():
            with self.subTest(widget=name):
                d = spec.demo
                for key in ("caption", "send", "fallback", "states", "queries"):
                    self.assertIn(key, d)
                self.assertIn("default", d["states"])
                self.assertTrue(d["send"].get("allow_queries"))
                self.assertLessEqual(len(d["caption"]), 1024)
                for row in d["fallback"]["inline_keyboard"]:
                    for b in row:
                        if "callback_data" in b:
                            self.assertLessEqual(len(b["callback_data"].encode()), 64)
                for st_name, st in d["states"].items():
                    for v in st.values():
                        text = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
                        self.assertLessEqual(len(text.encode()), 900, f"{st_name} leaves no room for the answer")
                        self.assertFalse(any(w in text.lower() for w in SECRET_WORDS))
                for q in d["queries"]:
                    self.assertLessEqual(len(q.encode()), 64)

    def test_data_grammar(self):
        a = parse("pick:1:1030@7")
        self.assertEqual((a.verb, a.arg, a.rev), ("pick", "1:1030", 7))
        self.assertEqual(parse("x@y").rev, None)


class Invariants(unittest.TestCase):
    def setUp(self):
        h_api_browser.use_api(h_api_browser.MockTicketsApi())

    def run_queries(self, name, state="default"):
        t = FakeTransport()
        bot = GalleryBot(t)
        msg = bot.send(name, 111111111, state=state)
        wid = (msg.get("widget") or {}).get("id")
        for i, data in enumerate(SPECS[name].demo["queries"]):
            bot.handle(query(data, message_id=msg["message_id"], qid=f"{name}{i}", widget_id=wid))
        return t, bot, msg

    def test_every_demo_query_is_answered_exactly_once_within_1024_bytes(self):
        for name, spec in SPECS.items():
            for state in spec.demo["states"]:
                with self.subTest(widget=name, state=state):
                    t, bot, _ = self.run_queries(name, state)
                    ids = [p["widget_query_id"] for p in t.params_of("answerWidgetQuery")]
                    self.assertEqual(len(ids), len(spec.demo["queries"]))
                    self.assertEqual(len(ids), len(set(ids)))
                    for p in t.params_of("answerWidgetQuery"):
                        self.assertLessEqual(len(p["data"].encode()), 1024)

    def test_invalid_data_is_refused_not_crashed(self):
        for name in SPECS:
            with self.subTest(widget=name):
                t = FakeTransport()
                bot = GalleryBot(t)
                msg = bot.send(name, 111111111)
                bot.handle(query("zz:%%%", message_id=msg["message_id"], qid="bad",
                                 widget_id=(msg.get("widget") or {}).get("id")))
                self.assertIn(answers(t)[0].get("err"), ("bad_request", "not_allowed"))

    def test_duplicate_update_is_skipped(self):
        t = FakeTransport()
        bot = GalleryBot(t)
        msg = bot.send("metrics-dashboard", 111111111)
        upd = query("p:7d", message_id=msg["message_id"], qid="same")
        self.assertEqual([bot.handle(upd), bot.handle(upd)], ["ok", "duplicate"])
        self.assertEqual(len(t.params_of("answerWidgetQuery")), 1)
        self.assertEqual(len(t.params_of("editMessageWidgetData")), 1)

    def test_only_the_owner_may_act(self):
        for name, spec in SPECS.items():
            if not spec.owner_only:
                continue
            with self.subTest(widget=name):
                t = FakeTransport()
                bot = GalleryBot(t)
                msg = bot.send(name, 111111111)
                q = query(spec.demo["queries"][0], user=999, chat=111111111, message_id=msg["message_id"], qid="x")
                self.assertEqual(bot.handle(q), "denied")
                self.assertEqual(answers(t), [{"ok": False, "err": "not_allowed"}])
                self.assertEqual(t.params_of("editMessageWidgetData"), [])

    def test_stale_verbs_refuse_an_old_revision_and_send_the_fresh_state(self):
        for name, spec in SPECS.items():
            for verb in spec.stale_verbs:
                data = next((q for q in spec.demo["queries"] if parse(q).verb == verb and parse(q).rev is not None), None)
                if data is None:
                    continue
                with self.subTest(widget=name, verb=verb):
                    t = FakeTransport()
                    bot = GalleryBot(t)
                    msg = bot.send(name, 111111111)
                    key = f"msg:111111111:{msg['message_id']}"
                    bot.store.records[key].revision = 5          # someone else changed it meanwhile
                    bot.handle(query(parse(data).raw.rsplit("@", 1)[0] + "@4", message_id=msg["message_id"], qid="s"))
                    a = answers(t)[0]
                    self.assertEqual(a["err"], "stale")
                    self.assertEqual(a["s"]["r"], 5)
                    self.assertEqual(t.params_of("editMessageWidgetData"), [])

    def test_failed_edit_is_answered_and_not_committed(self):
        t = FakeTransport()
        bot = GalleryBot(t)
        msg = bot.send("settings-panel", 111111111)
        key = f"msg:111111111:{msg['message_id']}"
        before = dict(bot.store.records[key].state)
        t.script("editMessageWidgetData", TelegramErrorResponse(429, "Too Many Requests: retry after 2", 2))
        data = next(q for q in SPECS["settings-panel"].demo["queries"] if q.startswith("tg:"))
        self.assertEqual(bot.handle(query(data, message_id=msg["message_id"], qid="f")), "edit_failed")
        self.assertFalse(answers(t)[0]["ok"])
        self.assertEqual(bot.store.records[key].state, before)

    def test_shared_votes_are_one_per_user_and_widget_and_coalesced(self):
        t = FakeTransport()
        now = [100.0]
        bot = GalleryBot(t, clock=lambda: now[0])
        wid = bot.send("leaderboard", 555)["widget"]["id"]
        for i, (user, opt) in enumerate([(1, 0), (2, 0), (1, 1), (1, 1)]):
            bot.handle(query(f"v:{opt}", user=user, message_id=1, qid=f"v{i}", widget_id=wid))
            now[0] += 0.2
        bot.flush(now[0] + 5)
        counts = [o[1] for o in json.loads(t.params_of("editSharedWidgetData")[-1]["public_data"])["poll"]["o"]]
        base = [o[1] for o in SPECS["leaderboard"].state()["poll"]["o"]]
        self.assertEqual(counts[0] - base[0], 1)          # user 1 moved to option 1
        self.assertEqual(counts[1] - base[1], 1)
        self.assertLessEqual(len(t.params_of("editSharedWidgetData")), 2)
        self.assertEqual(len(t.params_of("answerWidgetQuery")), 4)

    def test_api_browser_never_leaks_backend_credentials_or_ids(self):
        t, bot, msg = self.run_queries("api-browser")
        sent = json.dumps(t.calls, ensure_ascii=False).lower()
        self.assertNotIn("bearer", sent)
        self.assertNotIn('"u7"', sent)                     # backend account id stays server-side


class Payloads(unittest.TestCase):
    def test_widget_recipe_payloads_match_the_code(self):
        r = subprocess.run([sys.executable, os.path.join(_paths.EXAMPLES, "python", "export_widget_payloads.py"),
                            "--check"], capture_output=True, text=True, cwd=_paths.ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
