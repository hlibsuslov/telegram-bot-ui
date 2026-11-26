"""Choosing from a list: the example picker (inline and Rich Message), the keyboard rules SELECTION_EMOJI,
LONG_COLUMN and DECORATED_CONTROL, and references/selection-lists.md."""
import os
import re
import unittest

import _paths
import pick_categories as pc
import validate_keyboard as vk
import validate_rich as vr

REF = os.path.join(_paths.ROOT, "references", "selection-lists.md")
MANY = [(f"c{i}", i, {"uk": f"Категорія {i}", "en": f"Category {i}"}) for i in range(25)]


def warnings(doc):
    rep = vk.validate(doc)
    return rep.errors, rep.warnings


class Picker(unittest.TestCase):
    def test_inline_screen_is_clean_on_every_page_and_state(self):
        cases = [("uk", set(), 0, None), ("uk", {"mandatory"}, 0, None), ("en", {"c1", "c9"}, 1, MANY),
                 ("en", set(), 3, MANY)]
        for lang, sel, page, options in cases:
            with self.subTest(lang=lang, sel=sorted(sel), page=page):
                screen = pc.inline_screen(lang, sel, page, **({"options": options} if options else {}))
                self.assertEqual(warnings(screen["reply_markup"]), ([], []))
                rows = screen["reply_markup"]["inline_keyboard"]
                self.assertLessEqual(len(rows), 8)
                self.assertTrue(all(len(r) <= 3 for r in rows))
                primary = [b for r in rows for b in r if b.get("style") == "primary"]
                self.assertLessEqual(len(primary), 1, "Done is the one primary action")
                labels = " ".join(b["text"] for r in rows for b in r)
                self.assertFalse(re.search("[⚪✅🔘🟢☑]", labels), "no emoji as state")

    def test_state_summary_bulk_and_done(self):
        none = pc.inline_screen("uk", set())
        self.assertIn("Оберіть хоча б одну", none["text"])
        flat = [b for r in none["reply_markup"]["inline_keyboard"] for b in r]
        self.assertIn({"text": "Готово", "disabled": {}}, flat)
        self.assertIn("Вибрати всі", [b["text"] for b in flat])
        some = pc.inline_screen("uk", {"mandatory", "service"})
        self.assertIn("Обрано 2 з 9 · 34 знаків", some["text"])
        texts = [b["text"] for r in some["reply_markup"]["inline_keyboard"] for b in r]
        self.assertIn("✓ Наказові · 11", texts)
        self.assertIn("Заборонні · 48", texts)
        self.assertIn("Очистити", texts)
        self.assertIn("Готово · 2", texts)

    def test_custom_emoji_check_carries_the_state_alone(self):
        screen = pc.inline_screen("en", {"mandatory"}, check_icon_id="5368324170671202286")
        chosen = [b for r in screen["reply_markup"]["inline_keyboard"] for b in r if b.get("icon_custom_emoji_id")]
        self.assertEqual([b["text"] for b in chosen], ["Mandatory · 11"])

    def test_long_lists_get_pages_and_search(self):
        rows = pc.inline_screen("en", set(), 0, options=MANY)["reply_markup"]["inline_keyboard"]
        flat = [b for r in rows for b in r]
        self.assertIn({"text": "1/4", "disabled": {}}, flat)
        self.assertTrue(any("switch_inline_query_current_chat" in b for b in flat))

    def test_rich_screen_uses_native_checkboxes_and_validates(self):
        for sel in (set(), {"warning", "plates"}):
            payload = pc.rich_screen("uk", sel)
            errors, warns, _ = vr.validate(payload)
            self.assertEqual((errors, warns), ([], []))
            self.assertEqual(warnings(payload["rich_message"])[0], [])
            items = payload["rich_message"]["blocks"][2]["items"]
            self.assertTrue(all(i["has_checkbox"] for i in items))
            self.assertEqual(sorted(i["blocks"][0]["text"][1]["button"]["callback_data"][6:] for i in items if i.get("is_checked")),
                             sorted(sel))

    def test_toggle_trusts_only_known_ids(self):
        self.assertEqual(pc.toggle(set(), "cat:t:mandatory"), {"mandatory"})
        self.assertEqual(pc.toggle({"mandatory"}, "cat:t:mandatory"), set())
        self.assertEqual(pc.toggle({"x"}, "cat:t:nope"), {"x"})
        self.assertEqual(len(pc.toggle(set(), "cat:all")), len(pc.CATEGORIES))
        self.assertEqual(pc.toggle({"mandatory"}, "cat:none"), set())


class KeyboardRules(unittest.TestCase):
    SCREENSHOT = {"inline_keyboard": [[{"text": t, "callback_data": f"c:{i}"}] for i, t in enumerate(
        ["⚪ Усі категорії · 282", "⚪ Delineator/marker signs · 17", "⚪ Direction (guide) signs · 49",
         "⚪ Information signs · 46", "✅ Mandatory signs · 11", "⚪ Priority (right-of-way) signs · 7",
         "⚪ Prohibitory signs · 48", "✅ Service signs · 23", "✅ Supplementary plates · 34", "⚪ Warning signs · 47"])]
        + [[{"text": "🏁 Готово", "callback_data": "done", "style": "success"}]]}

    def test_the_screenshot_keyboard_gets_all_three(self):
        _, warns = warnings(self.SCREENSHOT)
        for code in ("SELECTION_EMOJI", "LONG_COLUMN", "DECORATED_CONTROL"):
            self.assertTrue(any(code in w for w in warns), code)

    def test_quiet_cases(self):
        self.assertEqual(warnings({"inline_keyboard": [[{"text": "← Back", "callback_data": "b"}],
                                                       [{"text": "⬅️ Назад", "callback_data": "b2"}]]})[1], [])
        status = {"inline_keyboard": [[{"text": "✅ Paid", "disabled": {}}], [{"text": "Menu", "callback_data": "m"}]]}
        self.assertFalse([w for w in warnings(status)[1] if "SELECTION_EMOJI" in w], "one status label is not a list")
        six = {"inline_keyboard": [[{"text": f"Option {i}", "callback_data": f"o:{i}"}] for i in range(6)]}
        self.assertFalse([w for w in warnings(six)[1] if "LONG_COLUMN" in w])
        seven = {"inline_keyboard": [[{"text": f"Option {i}", "callback_data": f"o:{i}"}] for i in range(7)]}
        self.assertTrue([w for w in warnings(seven)[1] if "LONG_COLUMN" in w])


class Reference(unittest.TestCase):
    def test_reference_routes_and_names_the_rules(self):
        with open(REF, encoding="utf-8") as fh:
            doc = fh.read()
        for word in ("SELECTION_EMOJI", "LONG_COLUMN", "DECORATED_CONTROL", "has_checkbox", "pick_categories.py",
                     "switch_inline_query_current_chat", "business"):
            self.assertIn(word, doc)
        for other in ("inline-keyboards.md", "INDEX.md"):
            with open(os.path.join(_paths.ROOT, "references", other), encoding="utf-8") as fh:
                self.assertIn("selection-lists.md", fh.read(), other)


if __name__ == "__main__":
    unittest.main()


class ReviewFixes(unittest.TestCase):
    """Findings of the security review before the merge to main."""

    def test_option_ids_must_fit_callback_data(self):
        with self.assertRaises(ValueError):
            pc.inline_screen("en", set(), options=[("x" * 80, 1, {"en": "Long"})])
        with self.assertRaises(ValueError):
            pc.rich_screen("en", set(), options=[("a:b", 1, {"en": "Colon"})])

    def test_emoji_library_flag_takes_a_json_file_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                vk.load_moving_emoji(d)  # a folder
            p = os.path.join(d, "library.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("{}")
            with self.assertRaises(ValueError):
                vk.load_moving_emoji(p)

    def test_a_screen_whose_message_is_not_an_object_does_not_break_the_icon_scan(self):
        import sys
        sys.path.insert(0, os.path.join(_paths.ROOT, "scripts"))
        from bot_ui import emoji
        snap = type("S", (), {"screens": {"x": {"id": "x", "message": "plain text", "actions": {}}}})()
        self.assertEqual(emoji.button_icons(snap), [])
