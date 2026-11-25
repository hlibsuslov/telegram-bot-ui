"""bot-ui adapters: aiogram 3.31.0 and raw tgkit over one Runtime, test transports only."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import sys
import unittest

from _bot_ui import CORE, FIXTURES, STUDIO, ProjectCase
from bot_ui.project import open_snapshot
from bot_ui.store import write_patch

try:
    import aiogram  # noqa: F401
    HAVE_AIOGRAM = True
except ImportError:
    HAVE_AIOGRAM = False

with open(os.path.join(FIXTURES, "updates", "checkout.json"), encoding="utf-8") as _fh:
    FIXTURE = json.load(_fh)
EXPECTED_METHODS = ["sendMessage", "answerCallbackQuery", "editMessageText", "answerCallbackQuery", "sendMessage",
                    "sendMessage", "answerCallbackQuery", "editMessageText", "editMessageText", "answerCallbackQuery",
                    "editMessageText", "answerCallbackQuery", "sendWidget", "answerCallbackQuery", "sendMessage",
                    "answerCallbackQuery", "answerCallbackQuery", "sendWidget"]


def raw_bot(root, fixture=FIXTURE):
    from demo_bot import demo_runtime_kw
    from raw_adapter import RawBot
    return RawBot(root, **demo_runtime_kw(fixture))


def replay(bot, updates):
    async def go():
        for u in updates:
            await bot.handle(u)
    asyncio.run(go())
    return bot.transport.calls


class Raw(ProjectCase):
    def test_fixture_replay_methods_and_catalog_check(self):
        from demo_bot import check
        calls = replay(raw_bot(self.root), FIXTURE["updates"])
        self.assertEqual([m for m, _ in calls], EXPECTED_METHODS)
        bad = [c for c in check(calls) if not c["ok"]]
        self.assertEqual(bad, [])
        # stale (legacy) callback: one answer with the project's stale text, nothing else
        self.assertEqual(calls[15], ("answerCallbackQuery", {"callback_query_id": "q7",
                                                             "text": "Эта кнопка устарела — откройте последнее сообщение."}))
        # inaccessible message (date 0): Back falls back to a new message instead of an edit
        self.assertEqual(calls[17][0], "sendWidget")

    def test_studio_save_reaches_the_next_payload(self):
        bot = raw_bot(self.root)
        replay(bot, FIXTURE["updates"][:4])  # up to the confirm screen
        confirm = bot.transport.calls[-1][1]["text"]
        self.assertIn("внимательно проверьте", confirm)
        snap = open_snapshot(self.root)
        write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": snap.revision, "changes": [
            {"screenId": "checkout.payment.error", "ops": [
                {"op": "set", "path": "/message/text/ru", "value": "⚠️ <b>Не прошло</b> — попробуйте ещё раз."}]}]})
        n = len(bot.transport.calls)
        replay(bot, FIXTURE["updates"][4:5])  # pay -> retry outcome -> error screen
        sent = bot.transport.calls[n:]
        self.assertEqual([m for m, _ in sent], ["answerCallbackQuery", "editMessageText", "editMessageText"])
        self.assertEqual(sent[-1][1]["text"], "⚠️ <b>Не прошло</b> — попробуйте ещё раз.")
        self.assertEqual(sent[-1][1]["message_id"], 1003)

    def test_user_text_is_escaped_in_html(self):
        upd = copy.deepcopy(FIXTURE["updates"][:4])
        upd[3]["message"]["text"] = "<script>alert(1)</script> & ко"
        calls = replay(raw_bot(self.root), upd)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; ко", calls[-1][1]["text"])

    def test_inline_message_id_callback_edits_by_inline_id(self):
        bot = raw_bot(self.root)
        cq = {"update_id": 50, "callback_query": {"id": "qi", "from": {"id": 5, "is_bot": False, "first_name": "U"},
                                                   "chat_instance": "c", "inline_message_id": "AAAA-inline",
                                                   "data": "entry.start:order"}}
        calls = replay(bot, [cq])
        self.assertEqual(calls[0][0], "answerCallbackQuery")
        self.assertEqual(calls[1][0], "editMessageText")
        self.assertEqual(calls[1][1]["inline_message_id"], "AAAA-inline")
        self.assertNotIn("chat_id", calls[1][1])

    def test_group_context_gets_the_widget_fallback(self):
        upd = {"update_id": 60, "message": {"message_id": 9, "date": 1, "text": "/status",
                                            "chat": {"id": -100, "type": "supergroup", "title": "G"},
                                            "from": {"id": 5, "is_bot": False, "first_name": "U"}}}
        calls = replay(raw_bot(self.root), [upd])
        self.assertEqual([m for m, _ in calls], ["sendMessage"])
        self.assertIn("inline_keyboard", calls[0][1]["reply_markup"])

    def test_restart_adopts_an_old_keyboard(self):
        calls = replay(raw_bot(self.root), [FIXTURE["updates"][1]])  # press "order" with no session
        self.assertEqual([m for m, _ in calls], ["answerCallbackQuery", "editMessageText"])
        self.assertEqual(calls[1][1]["message_id"], 1001)

    def test_notification_event(self):
        bot = raw_bot(self.root)

        async def go():
            return await bot.notify(111111111, "order.status_changed", {"order.status_text": "курьер в пути"})
        res = asyncio.run(go())
        self.assertEqual(res["requests"][0][0], "sendMessage")
        self.assertIn("курьер в пути", res["requests"][0][1]["text"])


class Placement(ProjectCase):
    """L15: the Runtime serves only the Studio adapters, so it ships with them, not in the skill,
    and the documented demo command runs from a checkout without extra import paths."""

    def test_runtime_lives_beside_the_adapters(self):
        self.assertFalse(os.path.exists(os.path.join(CORE, "bot_ui", "runtime.py")))
        self.assertTrue(os.path.isfile(os.path.join(STUDIO, "adapters", "runtime.py")))

    def test_demo_bot_replays_without_extra_paths(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        r = subprocess.run([sys.executable, os.path.join(STUDIO, "adapters", "demo_bot.py"), "--project", self.root,
                            "--replay", os.path.join(FIXTURES, "updates", "checkout.json"), "--raw", "--json"],
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=self._tmp, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertEqual([c["method"] for c in json.loads(r.stdout)], EXPECTED_METHODS)


@unittest.skipUnless(HAVE_AIOGRAM, "aiogram==3.31.0 not installed (pip install -r skills/telegram-bot-ui/examples/python/sdk_aiogram/requirements.txt)")
class Aiogram(ProjectCase):
    def test_aiogram_serialises_the_same_payloads_as_the_raw_adapter(self):
        from demo_bot import check, replay_aiogram
        calls = asyncio.run(replay_aiogram(self.root, FIXTURE))
        self.assertEqual([m for m, _ in calls], EXPECTED_METHODS)
        self.assertEqual([c for c in check(calls) if not c["ok"]], [])
        raw = replay(raw_bot(self.root), FIXTURE["updates"])
        self.assertEqual(json.dumps(calls, sort_keys=True, ensure_ascii=False),
                         json.dumps(raw, sort_keys=True, ensure_ascii=False))
        self.assertEqual(aiogram.__version__, "3.31.0")


class AiogramSkip(unittest.TestCase):
    """Without aiogram only the aiogram replay is skipped; Placement needs the standard library only."""

    def test_only_the_aiogram_case_skips_without_aiogram(self):
        code = ("import sys, unittest; sys.modules['aiogram'] = None; "
                "suite = unittest.defaultTestLoader.loadTestsFromNames("
                "['test_bot_ui_adapter.Placement', 'test_bot_ui_adapter.Aiogram']); "
                "r = unittest.TextTestRunner(stream=open(__import__('os').devnull, 'w')).run(suite); "
                "print(sorted(t.id().split('.')[1] for t, _ in r.skipped), r.testsRun, "
                "len(r.failures) + len(r.errors))")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                           cwd=os.path.dirname(os.path.abspath(__file__)), timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertEqual(r.stdout.strip(), "['Aiogram'] 3 0")


if __name__ == "__main__":
    unittest.main()
