"""bot-ui inventory of an existing aiogram bot (read-only static analysis)."""
from __future__ import annotations

import os
import unittest

from _bot_ui import FIXTURES
from bot_ui.inventory import scan


class Inventory(unittest.TestCase):
    def setUp(self):
        self.inv = scan(os.path.join(FIXTURES, "aiogram_bot"))

    def test_entry_points_callbacks_and_kept_callback_data(self):
        self.assertEqual(sorted(e["value"] for e in self.inv["entryPoints"]), ["help", "start"])
        screens = {s["id"]: s for s in self.inv["proposedScreens"]}
        self.assertEqual(screens["imported.catalog"]["keepCallbackData"], ["menu:catalog"])
        self.assertEqual(screens["imported.start"]["texts"], ["<b>Welcome</b>\nPick a section."])
        self.assertEqual(screens["imported.item"]["confidence"], "low")
        self.assertIn({"file": "bot.py", "line": 8 + 3, "text": "Catalog", "kind": "inline", "callbackData": "menu:catalog",
                       "confidence": "high"}, self.inv["buttons"])

    def test_dynamic_places_are_reported_not_guessed(self):
        what = [d["what"] for d in self.inv["dynamic"]]
        self.assertIn("edit_text() with a computed text", what)
        self.assertTrue(any("computed text or callback_data" in w for w in what))
        self.assertEqual(self.inv["status"], "static")


if __name__ == "__main__":
    unittest.main()
