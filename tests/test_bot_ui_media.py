"""bot-ui media of every Telegram kind and custom (premium) emoji: render, edits, adapters, parity."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from _bot_ui import FIXTURES, STUDIO, TEMPLATE
from bot_ui import render
from bot_ui.engine import Engine, _edit_ok, new_session, parity_view, run_scenario
from bot_ui.importer import import_bot
from bot_ui.project import open_snapshot
from bot_ui.skill import load
from test_bot_ui_engine import require_node

try:
    import aiogram  # noqa: F401
    HAVE_AIOGRAM = True
except ImportError:
    HAVE_AIOGRAM = False

P = {"defaultLocale": "en", "locales": ["en"], "fields": {"media.x": {"type": "string", "source": "data"}}}


def screen(media=None, text="Caption <b>bold</b>", kb="inline", **extra):
    s = {"id": "s.x", "kind": "result", "message": {"id": "main", "format": "regular.html"},
         "keyboard": {"type": kb, "rows": [["go"]]},
         "actions": {"go": {"label": {"en": "Go"}, "type": "navigate", "to": "s.x",
                            "icon": {"customEmojiId": "5368324170671202286"}}}, **extra}
    if text is not None:
        s["message"]["text"] = {"en": text}
    if media:
        s["message"]["media"] = media
    return s


class Render(unittest.TestCase):
    def setUp(self):
        vp = load("validate_payload")
        self.v = vp.Validator(vp.load_catalog(vp.DATA_DIR))

    def req(self, scr, **kw):
        r = render.bot_request(render.render_screen(P, scr, locale="en", values={"media.x": "AgACAgIAAxkBAAIZ"}), 7, **kw)
        rep = self.v.check_request(r["method"], r["params"])
        self.assertTrue(rep.ok, (r, rep.errors))
        return r

    def test_every_media_kind_maps_to_its_send_method(self):
        for t, method in render.MEDIA_TYPES.items():
            with self.subTest(t):
                text = None if t in ("sticker", "video_note") else "Caption <b>bold</b>"
                r = self.req(screen({"type": t, "file": {"fileId": "AgACAgIAAxkBAAIZ"}}, text=text))
                self.assertEqual(r["method"], method)
                self.assertEqual(r["params"][t], "AgACAgIAAxkBAAIZ")
                if t in render.CAPTION_MEDIA:
                    self.assertEqual((r["params"]["caption"], r["params"]["parse_mode"]), ("Caption <b>bold</b>", "HTML"))
                else:
                    self.assertNotIn("caption", r["params"])
                self.assertEqual(r["params"]["reply_markup"]["inline_keyboard"][0][0]["icon_custom_emoji_id"],
                                 "5368324170671202286")

    def test_url_field_and_spoiler(self):
        r = self.req(screen({"type": "animation", "file": {"url": "https://example.com/a.gif"}, "spoiler": True}))
        self.assertEqual((r["params"]["animation"], r["params"]["has_spoiler"]), ("https://example.com/a.gif", True))
        r = self.req(screen({"type": "photo", "file": {"field": "media.x"}}))
        self.assertEqual(r["params"]["photo"], "AgACAgIAAxkBAAIZ")
        r = self.req(screen({"type": "voice", "file": {"fileId": "AwACAgIAAxkBAAIZ"}, "spoiler": True}))
        self.assertNotIn("has_spoiler", r["params"], "voice cannot be a spoiler")

    def test_edit_media_and_refusal(self):
        r = self.req(screen({"type": "photo", "file": {"fileId": "AgACAgIAAxkBAAIZ"}}), edit_message_id=42)
        self.assertEqual(r["method"], "editMessageMedia")
        self.assertEqual(r["params"]["media"], {"type": "photo", "media": "AgACAgIAAxkBAAIZ",
                                                "caption": "Caption <b>bold</b>", "parse_mode": "HTML"})
        with self.assertRaises(ValueError):
            render.bot_request(render.render_screen(P, screen({"type": "voice", "file": {"fileId": "AwACAgIAAxkB"}})), 7,
                               edit_message_id=1)

    def test_reply_keyboard_icon(self):
        r = self.req(screen(kb="reply"))
        self.assertEqual(r["params"]["reply_markup"]["keyboard"][0][0],
                         {"text": "Go", "icon_custom_emoji_id": "5368324170671202286"})

    def test_edit_matrix(self):
        self.assertTrue(_edit_ok(None, None))
        self.assertTrue(_edit_ok(None, "photo"), "text -> media: editMessageMedia")
        self.assertTrue(_edit_ok("photo", "video"))
        self.assertFalse(_edit_ok("photo", None), "media -> text is impossible")
        for t in ("voice", "video_note", "sticker"):
            self.assertFalse(_edit_ok(None, t))
            self.assertFalse(_edit_ok(t, "photo"))


class ImportedShop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="bot-ui-media-")
        bot = os.path.join(cls.tmp, "shop")
        shutil.copytree(os.path.join(FIXTURES, "aiogram_shop"), bot)
        cls.root = import_bot(bot, os.path.join(bot, "bot-ui"), project_id="coffee-point")["project"]
        cls.snap = open_snapshot(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_engine_falls_back_from_a_photo_to_text(self):
        s = new_session(self.snap.project)
        eng = Engine(self.snap)
        eng.feed(s, {"command": "start"})
        eng.feed(s, {"press": "menu"})
        photo = eng.feed(s, {"press": "coffee"})
        self.assertEqual(photo["effects"][-1]["view"]["media"], "photo")
        back = eng.feed(s, {"press": "back"})  # photo message -> text catalog: Telegram cannot edit that
        self.assertEqual([e["type"] for e in back["effects"]], ["answer", "fallback", "send"])
        self.assertEqual(back["effects"][1]["reason"], "edit_kind")

    def test_raw_adapter_sends_media_and_icons_that_pass_the_catalog(self):
        from demo_bot import check
        from raw_adapter import RawBot
        bot = RawBot(self.root)
        u = {"id": 5, "is_bot": False, "first_name": "U", "language_code": "en"}
        c = {"id": 5, "type": "private"}

        def cb(n, mid, data):
            return {"update_id": n, "callback_query": {"id": f"q{n}", "from": u, "chat_instance": "x", "data": data,
                                                       "message": {"message_id": mid, "date": 1, "chat": c, "text": "."}}}
        ups = [{"update_id": 1, "message": {"message_id": 1, "date": 1, "chat": c, "from": u, "text": "/start"}},
               cb(2, 1001, "catalog"), cb(3, 1001, "cat:coffee"), cb(4, 1002, "catalog"), cb(5, 1003, "menu"),
               cb(6, 1003, "support"), cb(7, 1003, "support:voice")]

        async def go():
            for x in ups:
                await bot.handle(x)
        asyncio.run(go())
        methods = [m for m, _ in bot.transport.calls]
        self.assertIn("sendPhoto", methods)
        self.assertIn("sendVoice", methods)
        self.assertEqual([c for c in check(bot.transport.calls) if not c["ok"]], [])
        start = bot.transport.calls[0][1]
        self.assertEqual(start["reply_markup"]["inline_keyboard"][0][0]["icon_custom_emoji_id"], "5370869711888194012")
        self.assertIn("<tg-emoji emoji-id=", start["text"])

    @unittest.skipUnless(HAVE_AIOGRAM, "aiogram==3.31.0 not installed")
    def test_aiogram_serialises_media(self):
        from demo_bot import check, replay_aiogram
        fixture = {"updates": [
            {"update_id": 1, "message": {"message_id": 1, "date": 1, "chat": {"id": 5, "type": "private"},
                                         "from": {"id": 5, "is_bot": False, "first_name": "U"}, "text": "/hello"}},
            {"update_id": 2, "message": {"message_id": 2, "date": 1, "chat": {"id": 5, "type": "private"},
                                         "from": {"id": 5, "is_bot": False, "first_name": "U"}, "text": "/playlist"}}]}
        calls = asyncio.run(replay_aiogram(self.root, fixture))
        self.assertEqual([m for m, _ in calls], ["sendVideoNote", "sendAudio"])
        self.assertEqual([c for c in check(calls) if not c["ok"]], [])

    def test_typescript_parity_on_the_imported_bot(self):
        out = subprocess.run([require_node(self), os.path.join(STUDIO, "web", "src", "core", "parity-cli.ts"), self.root],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        ts = json.loads(out)
        for name, sc in self.snap.scenarios.items():
            with self.subTest(name):
                self.assertEqual(json.dumps(ts[name], sort_keys=True, ensure_ascii=False),
                                 json.dumps(parity_view(run_scenario(self.snap, sc)), sort_keys=True, ensure_ascii=False))

    def test_template_still_has_no_media_or_warnings(self):
        from bot_ui.validate import validate
        self.assertEqual([d.to_json() for d in validate(open_snapshot(TEMPLATE))], [])


if __name__ == "__main__":
    unittest.main()
