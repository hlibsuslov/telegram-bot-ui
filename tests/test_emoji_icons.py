"""IconSystem v2: clusters, UTF-16 offsets, transforms, eligibility, degradation, kill switch."""
import unittest

import _paths  # noqa: F401
from tgkit.errors import TelegramError
from tgkit.icons import (EmojiMap, Eligibility, IconSystem, SendContext, apply_entities, apply_html, apply_keyboard,
                         apply_markdown, apply_request, apply_rich_message, batched, emoji_key, ids_from_message,
                         iter_clusters, load_vocabulary, resolve_icon_map, strip_entities, strip_html, strip_keyboard,
                         strip_markdown, strip_request, strip_rich_message, uses_custom_emoji, verify_ids)
from tgkit.text import utf16_len
from tgkit.transport import FakeTransport, TelegramErrorResponse

VOCAB = load_vocabulary()
ICONS = {"settings": {"id": "0300000000000001", "fallback": "⚙️"},
         "home": {"id": "0300000000000002", "fallback": "🏠"},
         "done": {"id": "0300000000000003", "fallback": "✅"},
         "code": {"id": "0300000000000004", "fallback": "👩‍💻"}}
EMAP = EmojiMap(ICONS, VOCAB)


class Clusters(unittest.TestCase):
    def test_zwj_and_flag_sequences_are_single_clusters(self):
        self.assertEqual([c for _, _, c in iter_clusters("x👩‍💻y🏳️‍🌈⚙️ 1️⃣🇺🇦")], ["👩‍💻", "🏳️‍🌈", "⚙️", "1️⃣", "🇺🇦"])

    def test_variation_selector_is_ignored_for_matching(self):
        self.assertEqual(emoji_key("⚙"), emoji_key("⚙️"))
        self.assertEqual(EMAP.slot_for("⚙"), "settings")
        html, rep = apply_html("⚙ and ⚙️", EMAP)
        self.assertEqual(rep["replaced"], 2)
        self.assertEqual(html.count('emoji-id="0300000000000001">⚙️<'), 2)

    def test_gear_inside_a_zwj_sequence_is_not_matched(self):
        _, rep = apply_html("🧑‍🔧", EMAP)
        self.assertEqual(rep["replaced"], 0)


class Offsets(unittest.TestCase):
    def test_entities_use_utf16_with_surrogates_and_zwj(self):
        text = "😀👩‍💻 ⚙️ 🏠"
        ents, rep = apply_entities(text, [], EMAP)
        got = [(e["offset"], e["length"], e["custom_emoji_id"]) for e in ents]
        self.assertEqual(got, [(2, 5, "0300000000000004"), (8, 2, "0300000000000001"), (11, 2, "0300000000000002")])
        units = text.encode("utf-16-le")
        for e in ents:
            frag = units[2 * e["offset"]: 2 * (e["offset"] + e["length"])].decode("utf-16-le")
            self.assertTrue(EMAP.slot_for(frag))
        self.assertEqual(rep["unmapped"], ["😀"])

    def test_composer_offsets(self):
        text, ents = IconSystem(ICONS).composer().add("Hi 😀 ").icon("settings").add("Settings", "bold").build()
        self.assertEqual(text, "Hi 😀 ⚙️ Settings")
        emoji = next(e for e in ents if e["type"] == "custom_emoji")
        bold = next(e for e in ents if e["type"] == "bold")
        self.assertEqual((emoji["offset"], emoji["length"]), (utf16_len("Hi 😀 "), 2))
        self.assertEqual(bold["offset"], utf16_len("Hi 😀 ⚙️ "))

    def test_capture_reads_utf16_slices(self):
        text = "😀 home 🏠 gear ⚙️"
        ents = [{"type": "custom_emoji", "offset": utf16_len("😀 home "), "length": 2, "custom_emoji_id": "1"},
                {"type": "custom_emoji", "offset": utf16_len("😀 home 🏠 gear "), "length": 2, "custom_emoji_id": "2"}]
        got = ids_from_message({"message": {"text": text, "entities": ents}}, VOCAB)
        self.assertEqual([(g["emoji"], g["suggested_slot"]) for g in got], [("🏠", "home"), ("⚙️", "settings")])


class Transforms(unittest.TestCase):
    def test_round_trips(self):
        html = "<b>⚙️ Settings</b> ✅ <i>🏠</i>"
        self.assertEqual(strip_html(apply_html(html, EMAP)[0]), html)
        md = r"⚙️ *Settings* ✅ done\."
        self.assertEqual(strip_markdown(apply_markdown(md, EMAP)[0]), md)
        ents, _ = apply_entities("⚙️ x ✅", [{"type": "bold", "offset": 0, "length": 2}], EMAP)
        self.assertEqual(strip_entities(ents), [{"type": "bold", "offset": 0, "length": 2}])
        rich = {"blocks": [{"type": "paragraph", "text": ["Hi ✅ ", {"type": "bold", "text": "⚙️ x"}]},
                           {"type": "table", "cells": [[{"text": "🏠 Home"}]]}]}
        self.assertEqual(strip_rich_message(apply_rich_message(rich, EMAP)[0]), rich)
        for rm in ({"html": "<h1>🏠 Home</h1>"}, {"markdown": "# 🏠 Home"}):
            self.assertEqual(strip_rich_message(apply_rich_message(rm, EMAP)[0]), rm)
        kb = {"inline_keyboard": [[{"text": "⚙️ Settings", "callback_data": "s"}]]}
        self.assertEqual(strip_keyboard(apply_keyboard(kb, EMAP)[0], EMAP), kb)

    def test_protected_regions_are_untouched(self):
        html, rep = apply_html('<code>✅</code> <a href="https://x">⚙️</a> <pre>🏠</pre>', EMAP)
        self.assertNotIn("tg-emoji", html)
        self.assertEqual(rep["protected"], 3)
        md, _ = apply_markdown("`✅` [⚙️](https://x) ```\n🏠\n```", EMAP)
        self.assertNotIn("tg://emoji", md)
        ents, _ = apply_entities("✅ ⚙️", [{"type": "code", "offset": 0, "length": 1},
                                         {"type": "text_link", "offset": 2, "length": 2, "url": "https://x"}], EMAP)
        self.assertFalse(any(e["type"] == "custom_emoji" for e in ents))
        rm, _ = apply_rich_message({"blocks": [{"type": "pre", "text": "✅"},
                                               {"type": "paragraph", "text": [{"type": "code", "text": "✅"}]}]}, EMAP)
        self.assertNotIn("custom_emoji", str(rm))

    def test_existing_custom_emoji_are_not_wrapped_twice(self):
        once = apply_html("✅", EMAP)[0]
        self.assertEqual(apply_html(once, EMAP)[0], once)
        md_once = apply_markdown("✅", EMAP)[0]
        self.assertEqual(apply_markdown(md_once, EMAP)[0], md_once)

    def test_no_double_icon(self):
        ic = IconSystem(ICONS)
        self.assertEqual(ic.button("⚙️ Settings", "settings", callback_data="s"),
                         {"text": "Settings", "callback_data": "s", "icon_custom_emoji_id": "0300000000000001"})
        kb, rep = apply_keyboard({"inline_keyboard": [[{"text": "✅ Done", "icon_custom_emoji_id": "0300000000000003",
                                                        "callback_data": "d"}]]}, EMAP)
        self.assertEqual(kb["inline_keyboard"][0][0]["text"], "Done")
        off = IconSystem(ICONS, enabled=False)
        self.assertEqual(off.button("⚙️ Settings", "settings", callback_data="s")["text"], "⚙️ Settings")

    def test_emoji_only_label_is_not_converted(self):
        kb, rep = apply_keyboard({"inline_keyboard": [["✅"]]}, EMAP)
        self.assertEqual(kb["inline_keyboard"][0][0], {"text": "✅"})
        self.assertTrue(any("emoji-only" in w for w in rep["warnings"]))

    def test_poll_options_and_legacy_markdown(self):
        p, _ = apply_request("sendPoll", {"question": "Best ✅?", "options": [{"text": "🏠 Home"}]}, EMAP)
        self.assertEqual(p["question_entities"][0]["type"], "custom_emoji")
        self.assertEqual(p["options"][0]["text_entities"][0]["custom_emoji_id"], "0300000000000002")
        p2, rep = apply_request("sendMessage", {"text": "✅", "parse_mode": "Markdown"}, EMAP)
        self.assertEqual(p2["text"], "✅")
        self.assertTrue(rep["warnings"])


class Eligibility_(unittest.TestCase):
    def test_routes(self):
        prem, frag = Eligibility(owner_premium=True), Eligibility(fragment_usernames=True)
        for t in ("private", "group", "supergroup"):
            self.assertEqual(prem.route(SendContext(t)), "owner_premium")
        self.assertIsNone(prem.route(SendContext.channel()))
        self.assertIsNone(prem.route(SendContext("private", business=True)))
        self.assertIsNone(prem.route(SendContext("private", inline=True)))
        self.assertIsNone(Eligibility().route(SendContext("private")))
        for ctx in (SendContext.channel(), SendContext("private", business=True), SendContext("group", inline=True)):
            self.assertEqual(frag.route(ctx), "fragment")


class Degradation(unittest.TestCase):
    def params(self):
        return {"chat_id": 1, "parse_mode": "HTML", "text": '<b><tg-emoji emoji-id="0300000000000002">🏠</tg-emoji> Home</b> ✅',
                "reply_markup": {"inline_keyboard": [[{"text": "Settings", "icon_custom_emoji_id": "0300000000000001",
                                                       "callback_data": "s"}, {"text": "✅ Done", "callback_data": "d"}]]}}

    def test_all_or_nothing_per_message(self):
        ic = IconSystem(ICONS, vocabulary=VOCAB, eligibility=Eligibility(owner_premium=True))
        on = ic.for_context(SendContext("private")).prepare("sendMessage", self.params())
        off = ic.for_context(SendContext.channel()).prepare("sendMessage", self.params())
        self.assertEqual(on["text"].count("tg-emoji emoji-id"), 2)
        self.assertTrue(all(b.get("icon_custom_emoji_id") for b in on["reply_markup"]["inline_keyboard"][0]))
        self.assertFalse(uses_custom_emoji(off))
        self.assertEqual(off["reply_markup"]["inline_keyboard"][0][0]["text"], "⚙️ Settings")

    def test_strict_mode_strips_mixed_messages(self):
        ic = IconSystem(ICONS, vocabulary=VOCAB, strict=True)
        p = ic.prepare("sendMessage", {"text": "✅ 🎉", "parse_mode": "HTML"})
        self.assertEqual(p["text"], "✅ 🎉")

    def test_uncovered_slot_is_label_only_while_icons_are_on(self):
        icons = {**ICONS, "help": {"fallback": "❓"}}
        on, off = IconSystem(icons), IconSystem(icons, enabled=False)
        self.assertEqual(on.button("Help", "help", callback_data="h"), {"text": "Help", "callback_data": "h"})
        self.assertEqual(on.text("help"), "")
        self.assertEqual(off.button("Help", "help", callback_data="h")["text"], "❓ Help")

    def test_rich_helpers(self):
        ic = IconSystem(ICONS)
        self.assertEqual(ic.rich("done"), {"type": "custom_emoji", "custom_emoji_id": "0300000000000003", "alternative_text": "✅"})
        self.assertEqual(ic.md2("done"), "![✅](tg://emoji?id=0300000000000003)")
        self.assertEqual(IconSystem(ICONS, enabled=False).rich_label("done", "Done"), "✅ Done")


class KillSwitch(unittest.TestCase):
    REFUSED = TelegramErrorResponse(400, "Bad Request: custom emoji not allowed (test)")

    def test_refusal_retries_once_and_does_not_loop(self):
        log = []
        ic = IconSystem(ICONS, vocabulary=VOCAB, log=log.append)
        t = FakeTransport().script("sendMessage", self.REFUSED, self.REFUSED)
        with self.assertRaises(TelegramError):
            ic.send(t, "sendMessage", {"chat_id": 1, "text": "✅ ok", "parse_mode": "HTML"})
        self.assertEqual(len(t.calls), 2)
        self.assertTrue(ic.killed)
        self.assertFalse(uses_custom_emoji(t.calls[1][1]))
        self.assertEqual(len(log), 1)
        ic.send(t, "sendMessage", {"chat_id": 1, "text": "✅ again", "parse_mode": "HTML"})
        self.assertEqual(len(t.calls), 3)
        self.assertFalse(uses_custom_emoji(t.calls[2][1]))
        self.assertEqual(len(log), 1)

    def test_views_share_the_switch_and_unrelated_errors_are_raised(self):
        ic = IconSystem(ICONS, vocabulary=VOCAB, eligibility=Eligibility(owner_premium=True))
        t = FakeTransport().script("sendMessage", self.REFUSED)
        ic.send(t, "sendMessage", {"chat_id": 1, "text": "✅"}, SendContext("private"))
        self.assertFalse(ic.for_context(SendContext("group")).active)
        ic2 = IconSystem(ICONS, vocabulary=VOCAB)
        t2 = FakeTransport().script("sendMessage", TelegramErrorResponse(400, "Bad Request: can't parse entities"))
        with self.assertRaises(TelegramError):
            ic2.send(t2, "sendMessage", {"chat_id": 1, "text": "✅"})
        self.assertEqual(len(t2.calls), 1)
        self.assertFalse(ic2.killed)

    def test_request_without_custom_emoji_is_not_retried(self):
        ic = IconSystem({}, vocabulary=VOCAB)
        t = FakeTransport().script("sendMessage", self.REFUSED)
        with self.assertRaises(TelegramError):
            ic.send(t, "sendMessage", {"chat_id": 1, "text": "plain"})
        self.assertEqual(len(t.calls), 1)


class Resolution(unittest.TestCase):
    def sets(self):
        return [_paths.load("examples", "python", "icons", "fixtures", f"{n}.json")["result"]
                for n in ("demo_line_icons", "demo_line_icons_extra")]

    def test_ids_are_never_fabricated(self):
        sets = self.sets()
        real = {s["custom_emoji_id"] for st in sets for s in st["stickers"]}
        doc, rep = resolve_icon_map(sets, VOCAB, ["home", "gift", "rocket", "medal_1", "not_a_slot"])
        self.assertTrue(all(i["id"] in real for i in doc["icons"].values()))
        self.assertEqual(sorted(doc["icons"]), ["gift", "home"])
        self.assertEqual(rep["uncovered"], ["rocket", "medal_1"])
        self.assertEqual(rep["unknown_slots"], ["not_a_slot"])
        self.assertEqual(doc["icons"]["gift"]["set"], "demo_line_icons_extra")

    def test_one_sticker_one_meaning(self):
        doc, rep = resolve_icon_map(self.sets(), VOCAB, ["done", "confirm"])
        self.assertIn("done", doc["icons"])
        self.assertNotIn("confirm", doc["icons"])
        self.assertTrue(rep["conflicts"])

    def test_fallback_is_the_stickers_own_emoji(self):
        doc, _ = resolve_icon_map(self.sets(), VOCAB, ["delete"])
        self.assertEqual(doc["icons"]["delete"]["fallback"], "🗑")

    def test_verify_batches_of_200(self):
        ids = [str(10 ** 15 + i) for i in range(450)]
        seen = []
        t = FakeTransport().script("getCustomEmojiStickers", *[
            (lambda m, p: seen.append(len(p["custom_emoji_ids"])) or [{"custom_emoji_id": i} for i in p["custom_emoji_ids"][1:]])
            for _ in range(3)])
        found, missing = verify_ids(t, ids + ids[:5])
        self.assertEqual(seen, [200, 200, 50])
        self.assertEqual(len(missing), 3)
        self.assertEqual(len(found), 447)
        self.assertEqual([len(b) for b in batched(ids)], [200, 200, 50])

    def test_strip_request_restores_fallback_labels(self):
        kb = {"reply_markup": {"keyboard": [[{"text": "Home", "icon_custom_emoji_id": "0300000000000002"}]]}}
        self.assertEqual(strip_request(kb, EMAP)["reply_markup"]["keyboard"][0][0], {"text": "🏠 Home"})


if __name__ == "__main__":
    unittest.main()
