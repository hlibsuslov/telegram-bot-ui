"""Buttons inside a Rich Message are the exception (references/rich-message-buttons.md): the placement checks,
the skill's own examples and the references agree."""
import glob
import json
import os
import re
import unittest

import _paths
import validate_rich as vr
from bot_ui import rich

DOC = os.path.join(_paths.ROOT, "references", "rich-message-buttons.md")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def codes(buttons, rows=()):
    return [c for c, _ in rich.placement(buttons, list(rows))]


class Placement(unittest.TestCase):
    def test_each_misuse_has_its_code(self):
        self.assertEqual(codes([{"kind": "callback_data", "style": "", "label": "← List"}]), ["RICH_BUTTON_NAVIGATION"])
        self.assertEqual(codes([{"kind": "callback_data", "style": "", "label": "Open", "nav": True}]), ["RICH_BUTTON_NAVIGATION"])
        self.assertEqual(codes([{"kind": "callback_data", "style": "success", "label": "Approve"}]), ["RICH_BUTTON_MAIN_ACTION"])
        self.assertEqual(codes([{"kind": "url", "style": "", "label": "Runbook"}]), ["RICH_BUTTON_OUTSIDE"])
        self.assertEqual(codes([{"kind": "web_app", "style": "", "label": "Open app"}]), ["RICH_BUTTON_OUTSIDE"])
        five = [{"kind": "callback_data", "style": "", "label": f"V{i}"} for i in range(5)]
        self.assertEqual(codes(five, [5]), ["RICH_BUTTON_DENSITY"])

    def test_the_allowed_patterns_pass(self):
        toggles = [{"kind": "callback_data", "style": "link", "label": "Done"} for _ in range(12)]  # per-line links
        self.assertEqual(codes(toggles), [])
        switch = [{"kind": "", "style": "", "label": "Production"}, {"kind": "callback_data", "style": "", "label": "Staging"}]
        self.assertEqual(codes(switch, [2]), [])
        self.assertEqual(codes([{"kind": "copy_text", "style": "", "label": "Copy"}]), [])
        self.assertEqual(codes([{"kind": "callback_data", "style": "link", "label": "Done"} for _ in range(21)]),
                         ["RICH_BUTTON_DENSITY"])

    def test_raw_html_and_blocks_are_both_checked(self):
        html = ('<p>Total. <tg-button type="url" url="https://x.example">Runbook</tg-button></p>'
                '<tg-button-row><tg-button type="callback_data" data="a" style="primary">Pay</tg-button></tg-button-row>')
        self.assertEqual(sorted(w.split(":")[0] for w in vr.placement_warnings({"html": html})),
                         ["RICH_BUTTON_MAIN_ACTION", "RICH_BUTTON_OUTSIDE"])
        blocks = [{"type": "buttons", "buttons": [{"text": "← Back", "callback_data": "b"}]}]
        self.assertEqual([w.split(":")[0] for w in vr.placement_warnings({"blocks": blocks})], ["RICH_BUTTON_NAVIGATION"])


class Examples(unittest.TestCase):
    def test_no_example_payload_misplaces_a_document_button(self):
        def messages(o):
            if isinstance(o, dict):
                if isinstance(o.get("rich_message"), dict):
                    yield o["rich_message"]
                for v in o.values():
                    yield from messages(v)
            elif isinstance(o, list):
                for v in o:
                    yield from messages(v)
        found = {}
        for f in glob.glob(os.path.join(_paths.ROOT, "examples", "payloads", "*.json")):
            with open(f, encoding="utf-8") as fh:
                for m in messages(json.load(fh)):
                    for w in vr.placement_warnings(m):
                        found.setdefault(os.path.basename(f), set()).add(w.split(":")[0])
        self.assertEqual(found, {})

    def test_recipe_02_shows_the_right_split(self):
        with open(os.path.join(_paths.ROOT, "examples", "payloads", "r02-interactive-document.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        first = next(s for s in doc["steps"] if s.get("method") == "sendRichMessage")
        params = first["params"]
        self.assertEqual(params["reply_markup"]["inline_keyboard"][0][0]["style"], "success")  # Approve: keyboard
        text = json.dumps(params["rich_message"], ensure_ascii=False)
        self.assertIn('"style": "link"', text)  # Done links after the steps
        self.assertNotRegex(text, r'"style": "(primary|success|danger)"')


class References(unittest.TestCase):
    def test_the_policy_page_and_its_codes(self):
        doc = read(DOC)
        for n in range(1, 11):
            self.assertRegex(doc, rf"\n## {n}\. ")
        src = read(_paths.ROOT, "scripts", "bot_ui", "rich.py")
        for code in set(re.findall(r"`(RICH_BUTTON_[A-Z_]+)`", doc)) - {"RICH_BUTTON_ON_KEYBOARD"}:
            self.assertIn(code, src, code)

    def test_the_old_rich_first_advice_is_gone(self):
        for rel in ("buttons-and-styles.md", "format-selection.md", "floor.md"):
            text = read(_paths.ROOT, "references", rel)
            self.assertNotIn("Rich first", text, rel)
            self.assertNotIn("RICH_BUTTONS_UNUSED", text, rel)
            self.assertIn("rich-message-buttons.md", text, rel)
        self.assertNotIn("RICH_BUTTONS_UNUSED", read(_paths.ROOT, "scripts", "bot_ui", "validate.py"))


if __name__ == "__main__":
    unittest.main()
