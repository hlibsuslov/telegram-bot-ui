"""bot-ui premium emoji library: import by link, icon map, validation, the agent brief, Studio API."""
from __future__ import annotations

import base64
import http.client
import json
import os
import threading
import unittest
import urllib.error
from unittest import mock

from _bot_ui import ROOT, ProjectCase
from bot_ui import emoji
from bot_ui.artifact import snapshot_document
from bot_ui.project import open_snapshot
from bot_ui.server import serve
from bot_ui.validate import validate

FIXTURE = os.path.join(ROOT, "skills", "telegram-bot-ui", "examples", "python", "icons", "fixtures", "demo_line_icons.json")
TOKEN = "123456789:AAEXAMPLEexampleEXAMPLEexample1234"
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00/\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00"


def fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class FakeBot:
    """getStickerSet/getFile/download without a network; records what was asked."""

    def __init__(self, sticker_set: dict):
        self.set = sticker_set
        self.calls: list[tuple[str, dict]] = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "getStickerSet":
            return self.set
        return {"file_path": f"stickers/{params['file_id']}.webp"}

    def download(self, path):
        return WEBP


def live_set() -> dict:
    st = fixture()["result"]
    for s in st["stickers"]:
        s["file_id"] = f"F{s['custom_emoji_id']}"
    st["stickers"][1]["is_animated"] = True
    st["stickers"][1]["thumbnail"] = {"file_id": "T2"}
    st["stickers"][2]["is_animated"] = True  # no thumbnail: no picture, the fallback shows
    return st


class Links(unittest.TestCase):
    def test_pack_links_and_names(self):
        for text in ("https://t.me/addemoji/demo_line_icons", "t.me/addemoji/demo_line_icons/", "tg://addemoji?set=demo_line_icons",
                     " demo_line_icons ", "https://telegram.me/addemoji/demo_line_icons?x=1"):
            self.assertEqual(emoji.parse_pack_link(text), "demo_line_icons", text)
        for bad in ("", "https://evil.example/addemoji/x", "t.me/addemoji/../x", "a b", "x" * 65):
            with self.assertRaises(emoji.EmojiError, msg=bad):
                emoji.parse_pack_link(bad)

    def test_sticker_set_must_be_an_emoji_pack(self):
        st = fixture()["result"]
        st["sticker_type"] = "regular"
        with self.assertRaises(emoji.EmojiError) as cm:
            emoji.pack_from_sticker_set(st)
        self.assertEqual(cm.exception.code, "NOT_EMOJI_PACK")


class Token(unittest.TestCase):
    def test_malformed_token_is_refused_and_errors_never_carry_it(self):
        with self.assertRaises(emoji.EmojiError) as cm:
            emoji._Bot("not-a-token")
        self.assertEqual(cm.exception.code, "TOKEN_INVALID")
        bot = emoji._Bot(TOKEN)
        self.assertNotIn(TOKEN, repr(bot))
        err = urllib.error.URLError(f"cannot reach https://api.telegram.org/bot{TOKEN}/getStickerSet")
        with mock.patch.object(emoji._OPENER, "open", side_effect=err), self.assertRaises(emoji.EmojiError) as cm:
            bot.call("getStickerSet", {"name": "x"})
        self.assertEqual(cm.exception.code, "TELEGRAM_UNREACHABLE")
        self.assertNotIn(TOKEN, cm.exception.message)
        with self.assertRaises(emoji.EmojiError):
            bot.call("sendMessage", {})  # read-only methods only
        with self.assertRaises(emoji.EmojiError):
            bot.download("../../etc/passwd")


class Library(ProjectCase):
    def test_offline_import_from_a_saved_response(self):
        res = emoji.import_pack(self.root, sticker_set=fixture())
        self.assertEqual((res["pack"], res["count"], res["source"], res["previews"]), ("demo_line_icons", 47, "file", 0))
        lib = self.read(emoji.LIBRARY)
        self.assertEqual(lib["format"], emoji.FORMAT)
        first = lib["packs"]["demo_line_icons"]["emoji"][0]
        self.assertEqual(first, {"id": "0100000000000001", "fallback": "🏠", "format": "static", "adaptive": True})
        self.assertEqual(lib["packs"]["demo_line_icons"]["link"], "https://t.me/addemoji/demo_line_icons")

    def test_live_import_saves_pictures_in_the_local_cache_only(self):
        bot = FakeBot(live_set())
        res = emoji.import_pack(self.root, link="https://t.me/addemoji/demo_line_icons", bot=bot)
        self.assertEqual(bot.calls[0], ("getStickerSet", {"name": "demo_line_icons"}))
        self.assertEqual((res["previews"], res["previewsFailed"]), (46, 1))
        self.assertIn({"file_id": "T2"}, [p for m, p in bot.calls if m == "getFile"])  # TGS -> its thumbnail
        files = emoji.previews(self.root)
        self.assertEqual(files["0100000000000001"], "0100000000000001.webp")
        self.assertNotIn("0100000000000003", files)
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".bot-ui", "emoji", "0100000000000001.webp")))
        lib = self.read(emoji.LIBRARY)
        self.assertEqual(lib["packs"]["demo_line_icons"]["emoji"][1]["format"], "animated")
        self.assertEqual(open_snapshot(self.root).files.get(emoji.LIBRARY), None, "the library is not a screen source")

    def test_without_the_resolver_a_token_is_needed(self):
        env = {"TELEGRAM_TEST_BOT_TOKEN": "", "BOT_TOKEN": "", "BOT_UI_EMOJI_RESOLVER": "off"}
        with mock.patch.dict(os.environ, env), self.assertRaises(emoji.EmojiError) as cm:
            emoji.import_pack(self.root, link="demo_line_icons")
        self.assertEqual(cm.exception.code, "TOKEN_NEEDED")

    def test_import_through_the_resolver_needs_no_token(self):
        st = live_set()
        doc = {"ok": True, "name": st["name"], "title": st["title"],
               "emoji": [{"id": s["custom_emoji_id"], "fallback": s["emoji"], "format": "static", "adaptive": False,
                          "preview": f"/api/emoji-pack/{st['name']}/{s['custom_emoji_id']}"} for s in st["stickers"]]}
        doc["emoji"][0]["preview"] = "https://evil.example/x.webp"  # not the resolver's own path: skipped
        asked: list[str] = []

        def urlopen(req, timeout=None):
            url = req.full_url
            asked.append(url)
            body, ctype = (json.dumps(doc).encode(), "application/json") if url.endswith("/demo_line_icons") else (WEBP, "image/webp")
            resp = mock.MagicMock(status=200)
            resp.headers = {"Content-Type": ctype}
            resp.read = lambda n=-1: body
            resp.__enter__ = lambda s: s
            resp.__exit__ = lambda *a: False
            return resp

        env = {"TELEGRAM_TEST_BOT_TOKEN": "", "BOT_TOKEN": "", "BOT_UI_EMOJI_RESOLVER": "https://bot-ui.example/api/emoji-pack"}
        with mock.patch.dict(os.environ, env), mock.patch.object(emoji._OPENER, "open", side_effect=urlopen):
            res = emoji.import_pack(self.root, link="https://t.me/addemoji/demo_line_icons")
        self.assertEqual((res["source"], res["count"], res["previews"], res["previewsFailed"]), ("resolver", 47, 46, 1))
        self.assertEqual(asked[0], "https://bot-ui.example/api/emoji-pack/demo_line_icons")
        self.assertTrue(all(u.startswith("https://bot-ui.example/api/emoji-pack/") for u in asked))
        self.assertNotIn("evil", " ".join(asked))
        self.assertEqual(len(emoji.previews(self.root)), 46)

    def test_resolver_errors_and_urls(self):
        for bad in ("http://bot-ui.example/api", "file:///etc", "https://x.example/a b"):
            with mock.patch.dict(os.environ, {"BOT_UI_EMOJI_RESOLVER": bad}), self.assertRaises(emoji.EmojiError):
                emoji.resolver_url()
        with mock.patch.dict(os.environ, {"BOT_UI_EMOJI_RESOLVER": "http://localhost:3020/api/emoji-pack/"}):
            self.assertEqual(emoji.resolver_url(), "http://localhost:3020/api/emoji-pack")
        err = urllib.error.HTTPError("u", 404, "nf", {"Content-Type": "application/json"}, None)
        err.read = lambda n=-1: b'{"ok":false,"error":{"code":"PACK_NOT_FOUND","message":"no such pack"}}'
        with mock.patch.object(emoji._OPENER, "open", side_effect=err), self.assertRaises(emoji.EmojiError) as cm:
            emoji._Resolver("https://bot-ui.example/api/emoji-pack").pack("nope")
        self.assertEqual(cm.exception.code, "PACK_NOT_FOUND")
        self.assertIsNone(emoji._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example/"))

    def test_an_empty_resolver_answer_changes_nothing(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        before = self.raw(emoji.LIBRARY)
        empty = mock.Mock(host="bot-ui.example")
        empty.pack.return_value = {"ok": True, "name": "demo_line_icons", "title": "x", "emoji": None}
        with self.assertRaises(emoji.EmojiError) as cm:
            emoji.import_pack(self.root, link="demo_line_icons", resolver=empty)
        self.assertEqual(cm.exception.code, "RESOLVER_ERROR")
        self.assertEqual(self.raw(emoji.LIBRARY), before)

    def test_a_hand_broken_library_still_loads(self):
        os.makedirs(os.path.join(self.root, "emoji"), exist_ok=True)
        self.write_raw(emoji.LIBRARY, json.dumps({"format": emoji.FORMAT, "packs": {"ok_pack": {"emoji": [
            {"id": "123", "fallback": 7}, {"id": "abc"}, "x"]}, "bad name!": {}}, "icons": {"home": {"id": 5}, "cart": {"id": "123", "fallback": None}}}).encode())
        lib = emoji.load_library(self.root)
        self.assertEqual(lib["packs"]["ok_pack"]["emoji"], [{"id": "123", "fallback": ""}])
        self.assertEqual(list(lib["packs"]), ["ok_pack"])
        self.assertEqual(lib["icons"], {"cart": {"id": "123", "fallback": ""}})
        emoji.brief(open_snapshot(self.root), lib)  # no crash on what is left

    def test_env_token_is_trimmed(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_TEST_BOT_TOKEN": TOKEN + "\n"}):
            self.assertEqual(emoji.token_from_env(), (TOKEN, "TELEGRAM_TEST_BOT_TOKEN"))
        with self.assertRaises(emoji.EmojiError):
            emoji._Bot(TOKEN + "\n")

    def test_icon_map_one_meaning_per_emoji_and_audit_shape(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        emoji.set_icon(self.root, "home", "0100000000000001", note="main menu")
        with self.assertRaises(emoji.EmojiError) as cm:
            emoji.set_icon(self.root, "house", "0100000000000001")
        self.assertEqual(cm.exception.code, "ICON_DUPLICATE")
        for slot, eid, code in (("Home!", "0100000000000001", "SLOT_INVALID"), ("x", "abc", "EMOJI_INVALID"), ("x", "999", "EMOJI_UNKNOWN")):
            with self.assertRaises(emoji.EmojiError) as cm:
                emoji.set_icon(self.root, slot, eid)
            self.assertEqual(cm.exception.code, code)
        emoji.set_icon(self.root, "own", "999", fallback="⭐")  # an id from elsewhere, with its fallback
        icons = self.read(emoji.LIBRARY)["icons"]
        self.assertEqual(icons["home"], {"id": "0100000000000001", "set": "demo_line_icons", "fallback": "🏠",
                                         "animated": False, "adaptive": True, "note": "main menu"})
        emoji.set_icon(self.root, "own", None)
        self.assertNotIn("own", self.read(emoji.LIBRARY)["icons"])
        # a refreshed pack keeps the slots
        emoji.import_pack(self.root, sticker_set=fixture())
        self.assertIn("home", self.read(emoji.LIBRARY)["icons"])
        res = emoji.remove_pack(self.root, "demo_line_icons")
        self.assertEqual(res["iconsKept"], ["home"])

    def test_validation_against_the_library(self):
        doc = self.read("screens/entry.start.json")
        doc["message"]["text"]["en"] = ('<tg-emoji emoji-id="0100000000000001">🏠</tg-emoji> <b>Demo shop</b> '
                                        '<tg-emoji emoji-id="0100000000000002">🔙</tg-emoji> <tg-emoji emoji-id="777">⭐</tg-emoji>')
        doc["actions"]["order"]["icon"] = {"customEmojiId": "888"}
        self.write_raw("screens/entry.start.json", json.dumps(doc, ensure_ascii=False).encode())
        codes = lambda: [(d.code, d.pointer) for d in validate(open_snapshot(self.root))]  # noqa: E731
        self.assertFalse([c for c in codes() if c[0] in ("CUSTOM_EMOJI_UNKNOWN", "CUSTOM_EMOJI_FALLBACK_MISMATCH")],
                         "no library, no library checks")
        self.assertIn(("CUSTOM_EMOJI_DOUBLE_ICON", "/actions/order/label/en"), codes())  # icon + "🛒 Place an order"
        emoji.import_pack(self.root, sticker_set=fixture())
        found = codes()
        self.assertIn(("CUSTOM_EMOJI_UNKNOWN", "/message/text/en"), found)
        self.assertIn(("CUSTOM_EMOJI_UNKNOWN", "/actions/order/icon"), found)
        self.assertIn(("CUSTOM_EMOJI_FALLBACK_MISMATCH", "/message/text/en"), found)  # 🔙 vs the pack's ⬅️
        self.assertEqual(sum(1 for c in found if c[0] == "CUSTOM_EMOJI_FALLBACK_MISMATCH"), 1)

    def test_brief_lists_icons_placements_candidates_and_rules(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        snap = open_snapshot(self.root)
        sugg = {s["slot"]: s["id"] for s in emoji.suggest_icons(snap, emoji.load_library(self.root))}
        self.assertEqual(sugg.get("cart"), "0100000000000024")  # 🛒 in the start screen's button
        emoji.set_icon(self.root, "cart", sugg["cart"])
        doc = self.read("screens/entry.start.json")
        doc["actions"]["status"]["icon"] = {"customEmojiId": "0100000000000025"}
        self.write_raw("screens/entry.start.json", json.dumps(doc, ensure_ascii=False).encode())
        b = emoji.brief(open_snapshot(self.root))
        self.assertEqual([i["slot"] for i in b["icons"]], ["cart"])
        self.assertIn({"screenId": "entry.start", "pointer": "/actions/order/label/en", "emoji": "🛒", "slot": "cart",
                       "id": "0100000000000024"}, b["candidates"])
        self.assertIn("/actions/status/icon", [p["pointer"] for p in b["placed"]])
        self.assertEqual(b["route"], "none")
        md = emoji.brief_markdown(b)
        self.assertIn("| cart | 0100000000000024 | 🛒 |", md)
        self.assertIn("never invent", md)

    def test_artifact_inlines_pictures_of_icons_and_used_emoji(self):
        emoji.import_pack(self.root, link="demo_line_icons", bot=FakeBot(live_set()))
        emoji.set_icon(self.root, "home", "0100000000000001")
        block = snapshot_document(open_snapshot(self.root))["emoji"]
        self.assertEqual(set(block["previews"]), {"0100000000000001"})
        self.assertEqual(block["previews"]["0100000000000001"], "data:image/webp;base64," + base64.b64encode(WEBP).decode())
        self.assertNotIn("tokenEnv", {k for k, v in block.items() if v})

    def test_public_demo_can_inline_every_pack_picture_within_a_budget(self):
        emoji.import_pack(self.root, link="demo_line_icons", bot=FakeBot(live_set()))
        all_ids = set(emoji.previews(self.root))
        block = snapshot_document(open_snapshot(self.root), emoji_previews="all")["emoji"]
        self.assertEqual(set(block["previews"]), all_ids)
        one = len(next(iter(block["previews"].values()))) - len("data:image/webp;base64,")
        small = snapshot_document(open_snapshot(self.root), emoji_previews="all", emoji_budget=one * 3)["emoji"]
        self.assertEqual(len(small["previews"]), 3, "the budget stops inlining, nothing breaks")


HOME, BACK, CART, BOX, CART_STATIC = "0100000000000001", "0100000000000002", "0100000000000024", "0100000000000025", "0100000000000098"


def pack_with(animated=(), video=(), twins=()):
    """The fixture pack with some emoji animated or video, and static emoji with the same fallback as `twins`' keys."""
    st = fixture()["result"]
    for sticker in st["stickers"]:
        sticker["is_animated"] = sticker["custom_emoji_id"] in animated
        sticker["is_video"] = sticker["custom_emoji_id"] in video
    for source, new in dict(twins).items():
        base = next(x for x in st["stickers"] if x["custom_emoji_id"] == source)
        st["stickers"].append({**base, "custom_emoji_id": new, "is_animated": False, "is_video": False})
    return st


class ButtonsTakeStaticEmoji(ProjectCase):
    """A button never carries an animated or video custom emoji; in text static is the default."""

    def edit_start(self, change):
        doc = self.read("screens/entry.start.json")
        change(doc)
        self.write_raw("screens/entry.start.json", json.dumps(doc, ensure_ascii=False).encode())

    def found(self):
        return [(d.code, d.severity, d.pointer, d.message) for d in validate(open_snapshot(self.root))]

    def test_validate_errors_on_a_moving_button_icon_and_warns_in_text(self):
        def change(doc):
            doc["message"]["text"]["en"] = (f'<tg-emoji emoji-id="{BACK}">⬅️</tg-emoji> <tg-emoji emoji-id="{HOME}">🏠</tg-emoji> '
                                            "<b>Demo shop</b>")
            doc["actions"]["order"]["icon"] = {"customEmojiId": CART}
            doc["actions"]["status"]["icon"] = {"customEmojiId": BOX}

        self.edit_start(change)
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(BACK, CART), video=(BOX,), twins={CART: CART_STATIC}))
        found = self.found()
        errors = {(p, m) for c, sev, p, m in found if c == "BUTTON_EMOJI_ANIMATED" and sev == "error"}
        self.assertEqual({p for p, _ in errors}, {"/actions/order/icon", "/actions/status/icon"})
        by_pointer = dict(errors)
        self.assertIn(CART_STATIC, by_pointer["/actions/order/icon"], "names the static emoji with the same meaning")
        self.assertIn("video", by_pointer["/actions/status/icon"])
        self.assertEqual([(c, sev, p) for c, sev, p, _ in found if c == "CUSTOM_EMOJI_ANIMATED"],
                         [("CUSTOM_EMOJI_ANIMATED", "warning", "/message/text/en")], "the static 🏠 is fine")

    def test_a_static_icon_and_a_project_without_a_library_are_clean(self):
        flags = lambda: [c for c, *_ in self.found() if c in ("BUTTON_EMOJI_ANIMATED", "CUSTOM_EMOJI_ANIMATED")]  # noqa: E731
        self.edit_start(lambda d: d["actions"]["order"].update(icon={"customEmojiId": HOME}))
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,)))
        self.assertFalse(flags())
        self.edit_start(lambda d: d["actions"]["order"].update(icon={"customEmojiId": CART}))
        self.assertTrue(flags())
        os.remove(os.path.join(self.root, *emoji.LIBRARY.split("/")))
        self.assertFalse(flags(), "no library, no format to check")

    def test_a_custom_emoji_inside_a_rich_button_is_a_button_use(self):
        def change(doc):
            doc["message"]["format"] = "rich.html"
            doc["message"]["text"]["en"] = (f'<p><tg-emoji emoji-id="{BACK}">⬅️</tg-emoji> Demo shop</p>'
                                            f'<tg-button action="status"><tg-emoji emoji-id="{BOX}">📦</tg-emoji> Status</tg-button>'
                                            f'<tg-button action="order"><tg-emoji emoji-id="{HOME}">🏠</tg-emoji> Order</tg-button>')
            doc["keyboard"] = {"type": "none"}

        self.edit_start(change)
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(BACK, BOX)))
        found = self.found()
        self.assertEqual([(c, sev, p) for c, sev, p, _ in found if c == "BUTTON_EMOJI_ANIMATED"],
                         [("BUTTON_EMOJI_ANIMATED", "error", "/message/text/en")], "only the 📦 inside the status button")
        self.assertEqual([c for c, _, p, _ in found if c == "CUSTOM_EMOJI_ANIMATED"], ["CUSTOM_EMOJI_ANIMATED"], "the paragraph's ⬅️")
        placed = {(u["id"], u["where"]) for u in emoji.usage(open_snapshot(self.root))}
        self.assertEqual(placed, {(BACK, "text"), (BOX, "button"), (HOME, "button")})

    def test_suggestions_prefer_the_static_emoji_of_a_meaning(self):
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,), twins={CART: CART_STATIC}))
        sugg = {s["slot"]: s for s in emoji.suggest_icons(open_snapshot(self.root), emoji.load_library(self.root))}
        self.assertEqual((sugg["cart"]["id"], sugg["cart"]["animated"]), (CART_STATIC, False))
        emoji.remove_pack(self.root, "demo_line_icons")
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,)))
        sugg = {s["slot"]: s for s in emoji.suggest_icons(open_snapshot(self.root), emoji.load_library(self.root))}
        self.assertEqual((sugg["cart"]["id"], sugg["cart"]["animated"]), (CART, True), "only an animated one exists: flagged, not hidden")

    def test_candidates_never_put_a_moving_emoji_on_a_button(self):
        def change(doc):
            doc["message"]["text"]["en"] += " 🛒"
            doc["actions"]["order"]["label"]["en"] = "🛒 Place an order"

        self.edit_start(change)
        where = lambda: {c["pointer"]: c["id"] for c in emoji.candidates(open_snapshot(self.root), emoji.load_library(self.root))  # noqa: E731
                         if c["slot"] == "cart" and c["screenId"] == "entry.start" and c["pointer"].endswith("/en")}
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,), twins={CART: CART_STATIC}))
        emoji.set_icon(self.root, "cart", CART)
        self.assertEqual(where(), {"/message/text/en": CART_STATIC, "/actions/order/label/en": CART_STATIC})
        emoji.remove_pack(self.root, "demo_line_icons")
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,)))
        emoji.set_icon(self.root, "cart", CART)
        self.assertEqual(where(), {"/message/text/en": CART}, "text keeps it (a flagged exception), the button gets nothing")

    def test_adopting_a_button_icon_takes_its_static_twin_or_nothing(self):
        self.edit_start(lambda d: d["actions"]["order"].update(icon={"customEmojiId": CART}))
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,)))
        self.assertEqual(emoji.adopt_icons(self.root, open_snapshot(self.root)), [], "no static 🛒: not an icon of the map")
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(CART,), twins={CART: CART_STATIC}))
        adopted = emoji.adopt_icons(self.root, open_snapshot(self.root))
        self.assertEqual([(a["slot"], a["id"]) for a in adopted], [("cart", CART_STATIC)])

    def test_the_brief_states_the_hard_rule(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        rules = " ".join(emoji.brief(open_snapshot(self.root))["rules"])
        self.assertIn("STATIC custom emoji only", rules)
        self.assertIn("BUTTON_EMOJI_ANIMATED", rules)
        self.assertIn("CUSTOM_EMOJI_ANIMATED", rules)


class IconMeaning(ProjectCase):
    """A button's icon says what its label says (ICON_MEANING_MISMATCH, the review sheet)."""

    def set_icons(self, **icons):
        doc = self.read("screens/entry.start.json")
        for aid, eid in icons.items():
            doc["actions"][aid]["icon"] = {"customEmojiId": eid}
            for loc, text in doc["actions"][aid]["label"].items():
                doc["actions"][aid]["label"][loc] = text.lstrip("🛒📦 ")  # the icon replaces the label emoji
        self.write_raw("screens/entry.start.json", json.dumps(doc, ensure_ascii=False).encode())

    def mismatches(self):
        return [(d.pointer, d.message) for d in validate(open_snapshot(self.root)) if d.code == "ICON_MEANING_MISMATCH"]

    def test_label_words_in_three_languages(self):
        vocab = {v["slot"]: v for v in emoji.vocabulary()}
        self.assertIn("order", emoji.label_slots("Мої замовлення", vocab))
        self.assertIn("order", emoji.label_slots("Оформить заказ", vocab))
        self.assertIn("settings", emoji.label_slots("Настройки", vocab))
        self.assertIn("catalog", emoji.label_slots("Категорії", vocab))
        self.assertEqual(emoji.label_slots("4821", vocab), set())
        self.assertIsNone(emoji.meaning_mismatch(["Order status"], ["product", "order"], vocab), "📦 may mean an order")
        self.assertEqual(emoji.meaning_mismatch(["Settings"], ["home"], vocab), ["settings"])
        self.assertIsNone(emoji.meaning_mismatch(["Whatever"], ["home"], vocab), "a label with no known meaning")

    def test_validate_warns_on_an_icon_that_means_something_else(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        self.set_icons(order=HOME, status=BOX)  # 🏠 on "Place an order", 📦 on "Order status"
        found = self.mismatches()
        self.assertEqual([p for p, _ in found], ["/actions/order/icon"])
        self.assertIn("order", found[0][1])
        self.set_icons(order=CART)  # 🛒 means cart, the label says order
        self.assertEqual([p for p, _ in self.mismatches()], ["/actions/order/icon"])
        self.set_icons(order="0100000000000026")  # 🧾 receipt / order
        self.assertEqual(self.mismatches(), [])

    def test_an_icon_mapped_to_a_slot_is_judged_by_that_slot(self):
        emoji.import_pack(self.root, sticker_set=fixture())
        emoji.set_icon(self.root, "settings", "0100000000000013")
        self.set_icons(status="0100000000000013")  # the settings icon on "Order status"
        self.assertEqual([p for p, _ in self.mismatches()], ["/actions/status/icon"])
        brief = emoji.brief(open_snapshot(self.root))
        self.assertEqual([m["pointer"] for m in brief["meaningMismatch"]], ["/actions/status/icon"])
        self.assertIn("Icons that mean something else", emoji.brief_markdown(brief))

    def test_a_rich_button_is_judged_by_its_own_words(self):
        doc = self.read("screens/entry.start.json")
        doc["message"]["format"] = "rich.html"
        doc["message"]["text"]["en"] = (f'<p>Shop</p><tg-button action="status"><tg-emoji emoji-id="{HOME}">🏠</tg-emoji> '
                                        'Settings</tg-button><tg-button action="order">Order</tg-button>')
        doc["keyboard"] = {"type": "none"}
        self.write_raw("screens/entry.start.json", json.dumps(doc, ensure_ascii=False).encode())
        emoji.import_pack(self.root, sticker_set=fixture())
        self.assertEqual([p for p, _ in self.mismatches()], ["/message/text/en"])

    def test_review_sheet_shows_every_button_icon_with_its_verdict(self):
        emoji.import_pack(self.root, sticker_set=pack_with(animated=(BOX,)))
        self.set_icons(order=HOME, status=BOX)
        html = emoji.review_sheet(open_snapshot(self.root))
        self.assertEqual(html.count('<tr class="bad">'), 2)
        self.assertIn("a button takes a static custom emoji only", html)
        self.assertIn("the label says order", html)
        out = os.path.join(self._tmp, "review.html")
        from bot_ui.cli import main
        self.assertEqual(main(["emoji", "review", "--project", self.root, "--out", out, "--json"]), 1)
        with open(out, encoding="utf-8") as fh:
            self.assertIn("Button icon review", fh.read())

class Server(ProjectCase):
    def setUp(self):
        super().setUp()
        ready, self.holder = threading.Event(), {}
        self.thread = threading.Thread(target=serve, args=(self.root,), daemon=True,
                                       kwargs={"port": 0, "ready": ready, "holder": self.holder, "quiet": True})
        self.thread.start()
        ready.wait(10)
        self.port = self.holder["studio"].port

    def tearDown(self):
        self.holder["server"].shutdown()
        self.thread.join(5)
        super().tearDown()

    def req(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Host": f"127.0.0.1:{self.port}", "Origin": f"http://127.0.0.1:{self.port}",
                   "X-Bot-UI-Token": self.holder["studio"].token}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        return r.status, raw, dict(r.getheaders())

    def test_library_api_and_preview_files(self):
        status, raw, _ = self.req("POST", "/api/emoji", {})
        doc = json.loads(raw)
        self.assertEqual((status, doc["library"]["packs"], len(doc["vocabulary"]) > 100), (200, {}, True))
        status, raw, _ = self.req("POST", "/api/emoji/import", {"stickerSet": fixture()})
        doc = json.loads(raw)
        self.assertEqual((status, doc["count"], len(doc["library"]["packs"]["demo_line_icons"]["emoji"])), (200, 47, 47))
        self.assertTrue(any(s["slot"] == "cart" for s in doc["suggestions"]))
        status, raw, _ = self.req("POST", "/api/emoji/icon", {"slot": "cart", "id": "0100000000000024"})
        self.assertEqual((status, json.loads(raw)["library"]["icons"]["cart"]["fallback"]), (200, "🛒"))
        status, raw, _ = self.req("POST", "/api/emoji/icon", {"slot": "cart2", "id": "0100000000000024"})
        self.assertEqual((status, json.loads(raw)["error"]["code"]), (422, "ICON_DUPLICATE"))
        status, raw, _ = self.req("POST", "/api/emoji/import", {"link": "x y"})
        self.assertEqual((status, json.loads(raw)["error"]["code"]), (422, "PACK_LINK"))
        status, raw, _ = self.req("POST", "/api/emoji/brief", {})
        self.assertIn("| cart |", json.loads(raw)["markdown"])
        cache = os.path.join(self.root, ".bot-ui", "emoji")
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, "0100000000000024.webp"), "wb") as fh:
            fh.write(WEBP)
        status, raw, headers = self.req("GET", "/emoji-preview/0100000000000024.webp")
        self.assertEqual((status, raw, headers["Content-Type"]), (200, WEBP, "image/webp"))
        for bad in ("/emoji-preview/..%2Fproject.json", "/emoji-preview/1.svg", "/emoji-preview/42.webp"):
            self.assertEqual(self.req("GET", bad)[0], 404, bad)
        status, raw, _ = self.req("POST", "/api/emoji", {})
        self.assertEqual(json.loads(raw)["previews"], {"0100000000000024": "0100000000000024.webp"})

    def test_a_read_only_project_refuses_library_writes(self):
        doc = self.read("project.json")
        doc["schemaVersion"] = 999
        self.write_raw("project.json", json.dumps(doc).encode())
        for path, body in (("/api/emoji/import", {"stickerSet": fixture()}), ("/api/emoji/icon", {"slot": "home", "id": "1", "fallback": "🏠"}),
                           ("/api/emoji/remove-pack", {"pack": "x"})):
            status, raw, _ = self.req("POST", path, body)
            self.assertEqual((status, json.loads(raw)["error"]["code"]), (409, "READ_ONLY"), path)
        self.assertFalse(os.path.exists(os.path.join(self.root, "emoji")))


if __name__ == "__main__":
    unittest.main()
