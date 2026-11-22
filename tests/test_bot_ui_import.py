"""bot-ui import of an existing aiogram bot: deterministic, read-only on the bot, valid project."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest

from _bot_ui import FIXTURES
from bot_ui.engine import run_scenario
from bot_ui.importer import import_bot, report_markdown
from bot_ui.project import open_snapshot
from bot_ui.validate import validate

SHOP = os.path.join(FIXTURES, "aiogram_shop")


def tree_hash(root: str) -> str:
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "bot-ui")
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                h.update(os.path.relpath(path, root).encode() + fh.read())
    return h.hexdigest()


class ImportShop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="bot-ui-import-")
        cls.bot = os.path.join(cls.tmp, "кофейня бот")
        shutil.copytree(SHOP, cls.bot)
        cls.before = tree_hash(cls.bot)
        t0 = time.perf_counter()
        cls.res = import_bot(cls.bot, os.path.join(cls.bot, "bot-ui"))
        cls.seconds = time.perf_counter() - t0
        cls.root = cls.res["project"]
        cls.snap = open_snapshot(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def screen(self, sid):
        return self.snap.screens[sid]

    def test_bot_code_is_unchanged_and_project_is_valid(self):
        self.assertEqual(tree_hash(self.bot), self.before)
        self.assertEqual([d.code for d in validate(self.snap) if d.severity == "error"], [])
        self.assertEqual(self.res["stats"]["handlers"], 39)
        self.assertGreaterEqual(self.res["stats"]["screens"], 40)
        self.assertLess(self.seconds, 10)
        self.assertFalse([n for n in os.listdir(self.bot) if "bot-ui-import" in n], "no staging folder left")

    def test_entry_points_and_deep_link(self):
        eps = {e["id"]: e for e in self.snap.project["entryPoints"]}
        self.assertEqual(eps["start"]["screen"], "start.start")
        self.assertEqual(eps["start-link"]["type"], "deeplink")
        self.assertEqual(eps["start-link"]["screen"], "promo.start_ref")
        self.assertIn("hello", {e.get("command") for e in eps.values()}, "router.message.register(...)")

    def test_arrows_keep_the_old_callback_data(self):
        start = self.screen("start.start")
        menu = start["actions"]["menu"]
        self.assertEqual((menu["type"], menu["to"], menu["callbackData"]), ("navigate", "catalog.catalog", "catalog"))
        self.assertEqual(menu["icon"], {"customEmojiId": "5370869711888194012"})
        self.assertEqual(menu["style"], "primary")
        cat = self.screen("catalog.catalog")
        self.assertEqual(cat["keyboard"]["rows"], [["coffee", "tea"], ["desserts", "merch"], ["search"], ["main_menu"]])
        self.assertEqual(cat["actions"]["coffee"]["to"], "catalog.cat_coffee")
        self.assertEqual(cat["actions"]["coffee"]["callbackData"], "cat:coffee")
        self.assertEqual(self.screen("catalog.cat_coffee")["actions"]["latte"]["to"], "catalog.item_latte")

    def test_media_of_every_kind_by_file_id_or_url(self):
        kinds = {sid: s["message"]["media"]["type"] for sid, s in self.snap.screens.items() if s["message"].get("media")}
        self.assertEqual(sorted(set(kinds.values())),
                         ["animation", "audio", "photo", "sticker", "video", "video_note", "voice"])
        self.assertEqual(self.screen("catalog.cat_coffee")["message"]["media"]["file"], {"fileId": "AgACAgIAAxkBAAICoffee01"})
        self.assertEqual(self.screen("start.about")["message"]["media"]["file"], {"url": "https://example.com/roastery.jpg"})
        self.assertNotIn("text", self.screen("cart.pay")["message"], "a sticker has no caption")
        prices = self.screen("support.prices")["message"]["media"]["file"]
        self.assertEqual(prices, {"field": "media.support_prices"}, "a local upload becomes a field, never a file")
        self.assertIn("media-file", {i["kind"] for i in self.res["report"]})

    def test_custom_emoji_kept_with_its_fallback_and_eligibility_reported(self):
        text = self.screen("start.start")["message"]["text"]["en"]
        self.assertIn('<tg-emoji emoji-id="5368324170671202286">☕</tg-emoji>', text)
        self.assertEqual(self.snap.project["capabilities"]["customEmoji"], "none")
        self.assertIn("CUSTOM_EMOJI_INELIGIBLE", {d.code for d in validate(self.snap)})

    def test_gettext_catalog_becomes_locales(self):
        self.assertEqual(self.snap.project["locales"], ["en", "ru"])
        self.assertEqual(self.screen("profile.profile")["message"]["text"], {"en": "Your profile", "ru": "Ваш профиль"})
        self.assertIn("untranslated", {i["kind"] for i in self.res["report"]})

    def test_branches_become_handler_outcomes_with_the_happy_path_first(self):
        self.assertEqual(self.screen("cart.cart")["kind"], "menu")
        self.assertEqual(self.screen("cart.cart.alt1")["kind"], "empty")
        pay = self.snap.project["handlers"]["cart.pay"]
        self.assertEqual(pay["outcomes"], ["main", "alt1"])
        btn = self.screen("cart.checkout_phone")["actions"]["pay_6_30"]
        self.assertEqual(btn["type"], "handler")
        self.assertEqual(btn["outcomes"], {"main": "cart.pay", "alt1": "cart.pay.alt1"})
        self.assertEqual(self.screen("cart.pay.alt1")["kind"], "error")

    def test_fsm_states_become_inputs_and_toasts_become_answers(self):
        self.assertEqual(self.screen("cart.checkout")["input"]["to"], "cart.checkout_address")
        self.assertEqual(self.screen("cart.checkout")["keyboard"]["type"], "force_reply")
        self.assertEqual(self.screen("cart.checkout_address")["input"]["to"], "cart.checkout_phone")
        add = self.screen("catalog.item_latte")["actions"]["add_to_cart"]
        self.assertEqual((add["type"], add["text"]["en"]), ("answer", "Added to cart ✅"))

    def test_reply_keyboard_buttons_route_by_text(self):
        lang = self.screen("profile.language")
        self.assertEqual(lang["keyboard"]["type"], "reply")
        self.assertEqual(lang["actions"]["english"]["to"], "profile.lang_en")

    def test_report_is_short_and_points_at_lines(self):
        md = report_markdown(self.res)
        self.assertLess(len(self.res["report"]), 12)
        self.assertLess(len(md), 3000, "the agent reads this instead of the bot's code")
        for item in self.res["report"]:
            if item["file"]:
                self.assertTrue(os.path.isfile(os.path.join(self.bot, item["file"])), item)
        self.assertIn({"kind": "computed-keyboard", "file": "handlers/catalog.py"},
                      [{k: i[k] for k in ("kind", "file")} for i in self.res["report"]])

    def test_smoke_scenarios_run(self):
        self.assertGreaterEqual(len(self.snap.scenarios), 4)
        for name, sc in self.snap.scenarios.items():
            with self.subTest(name):
                self.assertTrue(run_scenario(self.snap, sc)["ok"])

    def test_import_is_deterministic(self):
        other = os.path.join(self.tmp, "second")
        shutil.copytree(SHOP, other)
        res = import_bot(other, os.path.join(other, "bot-ui"), project_id=self.snap.project["projectId"])
        self.assertEqual(open_snapshot(res["project"]).revision, self.snap.revision)


class Reimport(unittest.TestCase):
    def test_reimport_keeps_edits_and_adds_only_new_handlers(self):
        tmp = tempfile.mkdtemp(prefix="bot-ui-reimport-")
        try:
            bot = os.path.join(tmp, "bot")
            shutil.copytree(SHOP, bot)
            res = import_bot(bot, os.path.join(bot, "bot-ui"))
            root = res["project"]
            from bot_ui.store import write_patch
            snap = open_snapshot(root)
            write_patch(root, {"format": "bot-ui-patch/v1", "baseRevision": snap.revision, "changes": [
                {"screenId": "start.help", "ops": [{"op": "set", "path": "/message/text/en", "value": "Edited in Studio"}]}]})
            with open(os.path.join(bot, "handlers", "extra.py"), "w", encoding="utf-8") as fh:
                fh.write("from aiogram import Router\nfrom aiogram.filters import Command\nrouter = Router()\n\n"
                         "@router.message(Command('hours'))\nasync def hours(message):\n"
                         "    await message.answer('Open 8:00-20:00')\n")
            again = import_bot(bot, root)
            self.assertEqual(again["added"], ["extra.hours"])
            self.assertIn("start.help", again["kept"])
            fresh = open_snapshot(root)
            self.assertEqual(fresh.screens["start.help"]["message"]["text"]["en"], "Edited in Studio")
            self.assertEqual(again["diff"].count("+++ b/"), 1)
            with open(os.path.join(root, "import-map.json"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["handlers"]["handlers/extra.py::hours"], "extra.hours")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
