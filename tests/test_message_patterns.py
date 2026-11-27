"""Notification patterns (references/message-patterns.md): catalog, renderer, finder and the anatomy check."""
import contextlib
import io
import json
import os
import re
import unittest

import _paths
import message_patterns as mp
import tgui
import validate_keyboard as vk
import validate_payload as vp
from tgkit import notify

REFERENCE = os.path.join(_paths.ROOT, "references", "message-patterns.md")
SOUNDS = {"ping", "silent", "ping_if_action", "ping_on_open"}
BUTTONS = {"required", "optional", "none"}
BEFORE = ("⚡️⚡️ ВНИМАНИЕ!!! ⚡️⚡️\n━━━━━━━━━━━━━━━\nУважаемый пользователь, курс Bitcoin упал ниже вашего уровня "
          "65000$. Текущая цена 64870.12$ (изменение -3.4%).\nВремя: 2026-11-27T14:05:00Z\n━━━━━━━━━━━━━━━\n"
          "С уважением, команда CryptoBot 🚀")


def codes(text, parse_mode="HTML", pattern=None, params=None):
    return {f["code"] for f in mp.check_text(text, parse_mode=parse_mode, entities=None, where="t",
                                               pattern=pattern, params=params)}


class Catalog(unittest.TestCase):
    def setUp(self):
        self.cat = mp.load_catalog()
        self.validator = vp.Validator(vp.load_catalog(vp.DATA_DIR))

    def test_every_pattern_is_complete(self):
        ids = [p["id"] for p in self.cat["patterns"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 18)
        for p in self.cat["patterns"]:
            with self.subTest(p=p["id"]):
                self.assertEqual(set(p["names"]), {"en", "ru", "uk"})
                self.assertEqual(set(p["find"]), {"en", "ru", "uk"})
                self.assertTrue(all(p["find"][lang] for lang in ("en", "ru", "uk")))
                self.assertIn(p["sound"], SOUNDS)
                self.assertIn(p["buttons"], BUTTONS)
                self.assertTrue(set(p["blocks"]) <= set(notify.BLOCKS), p["blocks"])
                lo, hi = p["header"]["words"]
                self.assertTrue(1 <= lo <= hi <= 6)
                self.assertEqual(set(p["examples"]), {"en", "ru"})

    def test_every_example_renders_and_passes_its_own_pattern(self):
        for p in self.cat["patterns"]:
            for lang, ex in p["examples"].items():
                with self.subTest(p=p["id"], lang=lang):
                    pay = notify.payload(ex, chat_id=1, sound="silent" if p["sound"] == "silent" else "ping")
                    self.assertEqual(mp.check_doc(pay, p), [])
                    rep = self.validator.check_request(pay["method"], pay["params"])
                    self.assertEqual(rep.errors, [])
                    if "reply_markup" in pay["params"]:
                        kb = vk.validate(pay["params"]["reply_markup"])
                        self.assertEqual((kb.errors, kb.warnings), ([], []))
                    used = {b["type"] for b in ex["blocks"]}
                    self.assertTrue(used <= set(p["blocks"]) | {"code", "sentence"}, (used, p["blocks"]))

    def test_the_reference_documents_every_pattern(self):
        with open(REFERENCE, encoding="utf-8") as fh:
            ref = fh.read()
        for p in self.cat["patterns"]:
            self.assertIn(f"### `{p['id']}`", ref)


class Renderer(unittest.TestCase):
    def test_grammar_and_escaping(self):
        html = notify.message("Order <1042> shipped", icon="📦", subject="To A & B",
                              blocks=[notify.facts([("Total", "<b>$5</b>"), ("Note", "x", False)])], footer="as of 14:05")
        self.assertEqual(html, "<b>📦 Order &lt;1042&gt; shipped</b>\nTo A &amp; B\n\n"
                               "Total: <b>&lt;b&gt;$5&lt;/b&gt;</b>\nNote: x\n\n<i>as of 14:05</i>")

    def test_blocks(self):
        self.assertEqual(notify.timeline([("Paid", "10:02"), ("On the way", ""), ("Delivered",)], 1),
                         "✓ Paid · 10:02\n<b>● On the way</b>\n○ Delivered")
        self.assertIn("expandable", notify.quote("a\nb\nc\nd"))
        self.assertNotIn("expandable", notify.quote("short"))
        self.assertEqual(notify.bullets(["a"], more="and 4 more"), "• a\nand 4 more")
        self.assertEqual(notify.tg_time(1700000000, "14:05"), '<tg-time unix="1700000000" format="wDT">14:05</tg-time>')
        self.assertTrue(notify.grid(["A", "B"], [["x", "1"]]).startswith("<pre>"))
        with self.assertRaises(ValueError):
            notify.render({"title": "x", "blocks": [{"type": "nope"}]})

    def test_payload_sound_photo_and_limit(self):
        silent = notify.payload({"title": "Sales this week", "blocks": []}, sound="silent")
        self.assertTrue(silent["params"]["disable_notification"])
        photo = notify.payload({"title": "Back in stock", "photo": "<file_id>", "blocks": []})
        self.assertEqual(photo["method"], "sendPhoto")
        with self.assertRaises(ValueError):
            notify.payload({"title": "x", "photo": "<id>", "blocks": [{"type": "sentence", "text": "y" * 1100}]})


class Finder(unittest.TestCase):
    def top(self, text):
        hits = mp.find(text)
        return hits[0][1]["id"] if hits else None

    def test_finds_in_three_languages(self):
        self.assertEqual(self.top("Approval needed: payout to North Ltd, approve or decline"), "action-required")
        self.assertEqual(self.top("Вход с нового устройства iPhone, если это были не вы"), "security")
        self.assertEqual(self.top("Нагадування: запис завтра о 10:00"), "reminder")
        self.assertEqual(self.top("Отчёт: выручка и продажи за неделю"), "report-kpi")
        self.assertIsNone(self.top("zzz"))


class Check(unittest.TestCase):
    def test_the_before_message_trips_the_rules(self):
        found = codes(BEFORE, parse_mode=None)
        for code in ("HEADER_NOT_BOLD", "HEADER_PUNCTUATION", "HEADER_ICONS", "DECOR_RULE", "SHOUTING",
                     "GREETING", "SIGN_OFF", "ISO_TIME", "EMOJI_PER_LINE"):
            self.assertIn(code, found)

    def test_a_clean_message(self):
        ok = "<b>📉 BTC ниже 65 000 $</b>\nВаш уровень: 65 000 $\n\nСейчас: <b>64 870 $</b> ▼ 3,4% за час\n\n<i>данные на 17:05</i>"
        self.assertEqual(codes(ok), set())

    def test_layout_rules(self):
        self.assertIn("NO_GAP", codes("<b>📦 Order shipped</b>\nDHL\nTracking: 1\nArrives: tomorrow"))
        self.assertIn("SEPARATOR_MIX", codes("<b>Report</b>\n\nA: 1\nB: 2\nC — 3\nD — 4"))
        self.assertIn("BODY_LONG", codes("<b>Report</b>\n\n" + "\n".join(f"Row {i}: {i}" for i in range(12))))
        self.assertIn("HEADER_LONG", codes("<b>We are happy to tell you that your order has shipped</b>\n\nDHL"))
        table = "<b>📊 Orders</b>\n\n<pre>A  B\n────\nx  1</pre>"
        self.assertNotIn("DECOR_RULE", codes(table))  # a rule inside <pre> belongs to the table

    def test_footer_is_italic(self):
        body = "<b>📊 Продажи за 26 ноября</b>\n\nВыручка: <b>84 200 ₽</b>\nЗаказы: <b>63</b>\n\n"
        self.assertIn("FOOTER_NOT_ITALIC", codes(body + "данные на 17:05"))
        self.assertIn("FOOTER_NOT_ITALIC", codes(body + '<tg-time unix="1795784000" format="t">17:05</tg-time>'))
        self.assertNotIn("FOOTER_NOT_ITALIC", codes(body + "<i>данные на 17:05</i>"))
        # a fact or a sentence that only mentions a time is body, not a footer
        self.assertNotIn("FOOTER_NOT_ITALIC", codes(body + "Срок: до 18:00"))
        self.assertNotIn("FOOTER_NOT_ITALIC", codes("<b>📦 Заказ готов</b>\n\nЗаберите до 18:00"))
        plain = "📊 Sales today\n\nRevenue: 84 200\n\nas of 17:05"
        u16 = lambda t: len(t.encode("utf-16-le")) // 2  # noqa: E731 (entity offsets are UTF-16 units)
        start = u16(plain) - u16("as of 17:05")
        italic = [{"type": "bold", "offset": 0, "length": 15}, {"type": "italic", "offset": start, "length": 11}]
        found = {f["code"] for f in mp.check_text(plain, parse_mode=None, entities=italic, where="t")}
        self.assertNotIn("FOOTER_NOT_ITALIC", found)
        found = {f["code"] for f in mp.check_text(plain, parse_mode=None, entities=italic[:1], where="t")}
        self.assertIn("FOOTER_NOT_ITALIC", found)

    def test_custom_emoji_header_counts_one_icon(self):
        text = '<tg-emoji emoji-id="5368324170671202286">📦</tg-emoji> <b>Order #1042 shipped</b>\nDHL\n\nArrives: tomorrow'
        self.assertEqual(codes(text), set())

    def test_pattern_rules(self):
        pats = mp.patterns()
        text = "<b>⚠️ Approval needed</b>\nPayout\n\nAmount: <b>€5</b>"
        found = codes(text, pattern=pats["action-required"], params={"disable_notification": True})
        self.assertIn("PATTERN_SOUND", found)
        self.assertIn("PATTERN_NO_ACTION", found)
        report = "<b>📊 Sales</b>\n\nRevenue: <b>€5</b>"
        self.assertIn("PATTERN_SOUND", codes(report, pattern=pats["report-kpi"], params={}))
        self.assertIn("PATTERN_HEADER_WORDS", codes("<b>📊 Sales</b>\n\nA: 1", pattern=pats["report-kpi"],
                                                    params={"disable_notification": True}))

    def test_cli_and_tgui_route(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mp.main(["show", "receipt", "--lang", "ru", "--json"]), 0)
        self.assertEqual(json.loads(out.getvalue())["payload"]["method"], "sendMessage")
        self.assertEqual(tgui.PASS["patterns"], ["message_patterns.py"])
        self.assertTrue(re.search(r"patterns\s+list\|find\|show\|render\|check", tgui.__doc__))


if __name__ == "__main__":
    unittest.main()
