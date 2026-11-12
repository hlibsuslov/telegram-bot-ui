"""Icon-system and copy audits (design rules of this skill) and the IconSystem helper."""
import json
import os
import unittest

import _paths
import audit_copy
import audit_icons
from tgkit.icons import IconSystem

CASE = ("examples", "case-studies", "btc-tracker")


class Icons(unittest.TestCase):
    def test_case_study_mixed_families_are_reported(self):
        errors, warnings = audit_icons.audit(_paths.load(*CASE, "icon-map.json"))
        self.assertEqual(errors, [])
        text = " ".join(warnings)
        self.assertIn("icon families on one bot", text)
        self.assertIn("animated and", text)
        self.assertIn("one symbol per meaning", text)

    def test_one_family_map_is_clean(self):
        doc = {"icons": {"a": {"id": "5258389041006518073", "set": "tgmacicons", "family": "iOS", "fallback": "💼"},
                         "b": {"id": "5776233299424843260", "set": "tgiosicons", "family": "iOS", "fallback": "🌐"}}}
        self.assertEqual(audit_icons.audit(doc), ([], []))

    def test_shared_id_and_bad_id_are_errors(self):
        doc = {"icons": {"delete": {"id": "5870875489362513438", "fallback": "🗑"},
                         "close": {"id": "5870875489362513438", "fallback": "✖️"},
                         "x": {"id": "CAACAgIA", "fallback": ""}}}
        errors, _ = audit_icons.audit(doc)
        self.assertTrue(any("different meanings" in e for e in errors))
        self.assertTrue(any("not a custom_emoji_id" in e for e in errors))

    def test_builder_uses_one_set_and_reports_gaps(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bim", os.path.join(_paths.EXAMPLES, "python", "icons", "build_icon_map.py"))
        bim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bim)
        st = _paths.load("examples", "python", "icons", "fixtures", "tgmacicons.partial.json")["result"]
        icon_map, missing = bim.build(st, _paths.load("examples", "python", "icons", "slots.json"))
        self.assertEqual({i["set"] for i in icon_map["icons"].values()}, {"tgmacicons"})
        self.assertIn("back", missing)
        self.assertEqual(audit_icons.audit(icon_map)[0], [])

    def test_icon_system_degrades_together(self):
        icons = {"settings": {"id": "5258096772776991776", "fallback": "⚙️"}}
        on, off, bare = IconSystem(icons), IconSystem(icons, enabled=False), IconSystem(icons, enabled=False, unicode_fallback=False)
        self.assertEqual(on.button("Settings", "settings", callback_data="s"),
                         {"text": "Settings", "callback_data": "s", "icon_custom_emoji_id": "5258096772776991776"})
        self.assertIn('emoji-id="5258096772776991776"', on.title("settings", "Settings"))
        self.assertEqual(off.button("Settings", "settings", callback_data="s")["text"], "⚙️ Settings")
        self.assertEqual(bare.button("Settings", "settings", callback_data="s")["text"], "Settings")
        self.assertEqual(on.title("settings", "<x>"), '<b><tg-emoji emoji-id="5258096772776991776">⚙️</tg-emoji> &lt;x&gt;</b>')


class Copy(unittest.TestCase):
    def test_case_study_catalog_is_consistent(self):
        self.assertEqual(audit_copy.audit(_paths.load(*CASE, "catalog.sample.json")), ([], []))

    def test_defects_are_caught(self):
        cat = {"en": {"btn_add": "➕ Add wallet", "msg": "<b>Hi {name}</b>", "x": "<b>open", "long": "1️⃣ a\n2️⃣ b\n3️⃣ c\n✅ d 🔥 🎉"},
               "uk": {"btn_add": "➕ Додати гаманець до списку відстежуваних адрес", "msg": "<b>Привіт {user}</b>", "x": "<b>ok</b>"}}
        errors, warnings = audit_copy.audit(cat)
        self.assertTrue(any("placeholders differ" in e for e in errors))
        self.assertTrue(any("unclosed <b>" in e for e in errors))
        self.assertTrue(any("button label" in w for w in warnings))
        self.assertTrue(any("missing in 'uk'" in w for w in warnings))
        self.assertTrue(any("emoji over" in w for w in warnings))

    def test_case_study_widgets_valid(self):
        from tgkit.widgets import check_widget
        for name in ("tx-confirmations.html", "price-ticker.html"):
            self.assertEqual(check_widget(_paths.read("examples", "widgets", name), caption="c").warnings, [])


if __name__ == "__main__":
    unittest.main()
