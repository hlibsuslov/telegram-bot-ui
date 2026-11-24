"""bot-ui: an existing bot's premium emoji packs come with it (import-used, import --emoji-packs)."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

from _bot_ui import FIXTURES
from bot_ui import emoji
from bot_ui.cli import main
from bot_ui.importer import import_bot
from bot_ui.project import open_snapshot

SHOP = os.path.join(FIXTURES, "aiogram_shop")
HOME, CART, FIRE, OTHER, GONE = "5000000000000000001", "5000000000000000002", "5000000000000000003", \
    "5000000000000000004", "5000000000000000099"

BOT = f'''
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()
ICONS = {{"spare": "{OTHER}", "gone": "{GONE}"}}
CHAT_ID = "1234567890123456789"  # a long digit string outside an emoji map is not an emoji id


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer('<tg-emoji emoji-id="{FIRE}">🔥</tg-emoji> Hello', parse_mode="HTML", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Home", callback_data="home", icon_custom_emoji_id="{HOME}"),
                          InlineKeyboardButton(text="Cart", callback_data="cart", icon_custom_emoji_id="{CART}")]]))


@router.callback_query(F.data == "home")
async def home(query) -> None:
    await query.message.edit_text("Home")


@router.callback_query(F.data == "cart")
async def cart(query) -> None:
    await query.message.edit_text("Cart")
'''

PACKS = {
    "line_icons": [(HOME, "🏠"), (CART, "🛒"), (OTHER, "⭐")],
    "fire_fx": [(FIRE, "🔥")],
}


def sticker_set(name: str) -> dict:
    return {"name": name, "title": name.replace("_", " ").title(), "sticker_type": "custom_emoji",
            "stickers": [{"custom_emoji_id": cid, "emoji": e, "file_id": f"F{cid}"} for cid, e in PACKS[name]]}


class FakeBot:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "getCustomEmojiStickers":
            owner = {cid: n for n, items in PACKS.items() for cid, _ in items}
            return [{"custom_emoji_id": cid, "set_name": owner[cid], "emoji": "x"} for cid in params["custom_emoji_ids"]
                    if cid in owner]
        if method == "getStickerSet":
            return sticker_set(params["name"])
        return {"file_path": f"stickers/{params['file_id']}.webp"}

    def download(self, path):
        return b"RIFF\x1a\x00\x00\x00WEBPVP8L"


class BotCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bot-ui-used-")
        self.src = os.path.join(self.tmp, "бот")
        os.makedirs(self.src)
        with open(os.path.join(self.src, "bot.py"), "w", encoding="utf-8") as fh:
            fh.write(BOT)
        self.root = os.path.join(self.src, "bot-ui")
        self.res = import_bot(self.src, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lib(self) -> dict:
        with open(os.path.join(self.root, *emoji.LIBRARY.split("/")), encoding="utf-8") as fh:
            return json.load(fh)


class ImportFindsIds(BotCase):
    def test_ids_from_screens_constants_and_texts_go_to_the_import_map(self):
        with open(os.path.join(self.root, "import-map.json"), encoding="utf-8") as fh:
            found = json.load(fh)["customEmoji"]
        self.assertEqual(set(found), {HOME, CART, FIRE, OTHER, GONE})
        self.assertTrue(all(w.startswith("bot.py:") for w in found.values()))
        self.assertEqual(self.res["stats"]["customEmoji"], 5)
        self.assertIn("emoji-packs", {i["kind"] for i in self.res["report"]})
        snap = open_snapshot(self.root)
        self.assertEqual(set(emoji.missing_ids(snap, emoji.load_library(self.root))), {HOME, CART, FIRE, OTHER, GONE})

    def test_shop_fixture_ids_are_found_without_network(self):
        tmp = tempfile.mkdtemp(prefix="bot-ui-shop-")
        try:
            res = import_bot(SHOP, os.path.join(tmp, "bot-ui"), dry_run=True)
            self.assertGreaterEqual(res["stats"]["customEmoji"], 3)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ImportUsed(BotCase):
    def test_every_used_pack_is_imported_and_button_icons_get_their_meaning(self):
        bot = FakeBot()
        res = emoji.import_used(self.root, open_snapshot(self.root), bot=bot)
        self.assertEqual(sorted(p["pack"] for p in res["packs"]), ["fire_fx", "line_icons"])
        self.assertEqual([u["id"] for u in res["unresolved"]], [GONE])
        self.assertEqual(res["failed"], [])
        lookups = [p for m, p in bot.calls if m == "getCustomEmojiStickers"]
        self.assertEqual(len(lookups), 1, "one batched lookup for all ids")
        lib = self.lib()
        self.assertEqual(set(lib["packs"]), {"fire_fx", "line_icons"})
        self.assertEqual({a["slot"]: a["id"] for a in res["adopted"]}, {"home": HOME, "cart": CART})
        self.assertEqual(lib["icons"]["home"]["set"], "line_icons")
        self.assertNotIn(FIRE, {i["id"] for i in lib["icons"].values()}, "text emoji are not adopted as icons")
        self.assertEqual(emoji.missing_ids(open_snapshot(self.root), emoji.load_library(self.root)), [GONE])
        before = self.lib()
        again = emoji.import_used(self.root, open_snapshot(self.root), bot=FakeBot())
        self.assertEqual((again["packs"], again["adopted"]), ([], []))
        self.assertEqual(self.lib()["icons"], before["icons"], "a second run keeps the map")

    def test_one_failing_pack_does_not_stop_the_others(self):
        bot = FakeBot()
        real = bot.call

        def call(method, params):
            if method == "getStickerSet" and params["name"] == "fire_fx":
                raise emoji.EmojiError("TELEGRAM_ERROR", "getStickerSet: STICKERSET_INVALID")
            return real(method, params)

        bot.call = call
        res = emoji.import_used(self.root, open_snapshot(self.root), bot=bot, map_icons=False)
        self.assertEqual([p["pack"] for p in res["packs"]], ["line_icons"])
        self.assertEqual([f["pack"] for f in res["failed"]], ["fire_fx"])
        self.assertEqual(res["adopted"], [])
        self.assertEqual(self.lib()["icons"], {})

    def test_large_bots_are_looked_up_in_batches_of_200(self):
        bot = FakeBot()
        emoji.sets_of([str(5 * 10 ** 18 + i) for i in range(450)], bot=bot)
        self.assertEqual([len(p["custom_emoji_ids"]) for m, p in bot.calls], [200, 200, 50])

    def test_through_the_resolver(self):
        res_mock = mock.Mock(host="bot-ui.example")
        res_mock.sets_of.side_effect = lambda ids: {cid: n for n, items in PACKS.items() for cid, _ in items if cid in ids}
        res_mock.pack.side_effect = lambda name: {"ok": True, "name": name, "title": name, "emoji": [
            {"id": cid, "fallback": e, "format": "static", "adaptive": False, "preview": None} for cid, e in PACKS[name]]}
        res_mock.picture.return_value = None
        res = emoji.import_used(self.root, open_snapshot(self.root), resolver=res_mock)
        self.assertEqual(sorted(p["pack"] for p in res["packs"]), ["fire_fx", "line_icons"])
        self.assertEqual(self.lib()["packs"]["line_icons"]["source"], "resolver")

    def test_an_older_resolver_without_the_lookup_asks_for_a_token(self):
        err = urllib.error.HTTPError("u", 400, "bad", {"Content-Type": "application/json"}, None)
        err.read = lambda n=-1: b'{"ok":false,"error":{"code":"PACK_NAME","message":"a pack name is letters"}}'
        with mock.patch.object(emoji._OPENER, "open", side_effect=err), self.assertRaises(emoji.EmojiError) as cm:
            emoji._Resolver("https://bot-ui.example/api/emoji-pack").sets_of([HOME])
        self.assertEqual(cm.exception.code, "RESOLVER_NO_IDS")
        self.assertIn("BOT_TOKEN", cm.exception.message)

    def test_cli_import_used(self):
        out = io.StringIO()
        with mock.patch.object(emoji, "_transport", return_value=(FakeBot(), None)), redirect_stdout(out):
            code = main(["emoji", "import-used", "--project", self.root])
        self.assertEqual(code, 0)
        self.assertIn("line_icons", out.getvalue())
        self.assertIn("icon map: home", out.getvalue())


if __name__ == "__main__":
    unittest.main()
