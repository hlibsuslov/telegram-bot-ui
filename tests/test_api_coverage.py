"""scripts/api_coverage.py: the levels it assigns on a small fake skill, and the floor it ratchets."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import _paths  # noqa: F401  (puts scripts/ on sys.path)
import api_coverage


def _write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text))


CATALOG = {
    "meta": {"bot_api_version": "9.9"},
    "methods": {
        "sendThing": {"section": "Available methods"},
        "sendThingDraft": {"section": "Available methods"},
        "getStuff": {"section": "Available methods"},
        "makeSet": {"section": "Stickers"},
    },
    "types": {
        "Widget": {"section": "Available types"},
        "WidgetPart": {"section": "Available types"},
        "RichBlockNote": {"section": "Rich messages"},
    },
}
WEBAPP = {
    "meta": {},
    "members": {
        "WebApp.ready": {"name": "ready", "kind": "method"},
        "CloudStorage.getItems": {"name": "getItems", "kind": "method"},
        "events.themeChanged": {"name": "themeChanged", "kind": "event"},
        "events.popupClosed": {"name": "popupClosed", "kind": "event"},
    },
}


class FakeSkill(unittest.TestCase):
    def setUp(self):
        self.skill = tempfile.mkdtemp(prefix="cov-")
        self.addCleanup(shutil.rmtree, self.skill, True)
        files = {
            "data/bot-api/catalog.json": CATALOG,
            "data/mini-apps/webapp-catalog.json": WEBAPP,
            # whole identifiers only: sendThingDraft must not count for sendThing
            "references/messages.md": "Use `sendThingDraft` to stream. A Widget holds parts.",
            # the generated registry and the index name everything, and do not count
            "references/bot-api-coverage.md": "sendThing getStuff makeSet WidgetPart RichBlockNote",
            "references/INDEX.md": "sendThing getStuff makeSet WidgetPart RichBlockNote",
            "references/mini-apps/webapp-api.md": "`ready()` and `CloudStorage.getItems` and popupClosed",
            "references/mini-apps/events.md": "Handle `themeChanged`.",
            "recipes/01-thing.md": "Call getStuff, then render RichBlockNote.",
            "examples/payloads/r01.json": {"steps": [{"method": "sendThingDraft"}]},
            "examples/python/bot.py": "await bot.get_stuff()\n",
            "examples/mini-apps/app/main.ts": "tg.ready();\n",
            # dependencies are not the skill's own code
            "examples/mini-apps/app/node_modules/x/index.js": "popupClosed getItems makeSet",
            "scripts/validate_payload.py": "def _rules_sendThingDraft(self): pass\n",
        }
        for rel, text in files.items():
            _write(self.skill, rel, text)
        self.floor = os.path.join(self.skill, "floor.json")

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = api_coverage.main([*args, "--skill", self.skill, "--floor", self.floor])
        return code, out.getvalue()

    def rows(self):
        return {r["name"]: r for r in api_coverage.measure(self.skill)["rows"]}


class Levels(FakeSkill):
    def test_bot_api_levels(self):
        rows = self.rows()
        levels = {n: "".join(k for k in "KRPV" if rows[n][k]) for n in CATALOG["methods"]}
        self.assertEqual(levels, {"sendThing": "", "sendThingDraft": "KPV", "getStuff": "RP", "makeSet": ""})
        self.assertTrue(rows["Widget"]["K"])
        self.assertFalse(rows["WidgetPart"]["K"] or rows["WidgetPart"]["R"] or rows["WidgetPart"]["P"])
        self.assertTrue(rows["RichBlockNote"]["R"])

    def test_webapp_levels(self):
        rows = self.rows()
        flags = {n: "".join(k for k in "AGC" if rows[n][k]) for n in WEBAPP["members"]}
        self.assertEqual(flags, {"WebApp.ready": "AC", "CloudStorage.getItems": "A",
                                 "events.themeChanged": "G", "events.popupClosed": "A"})

    def test_gaps_and_report_numbers(self):
        result = api_coverage.measure(self.skill)
        self.assertEqual(api_coverage.gaps(result["rows"]), {
            "method.K": ["getStuff", "makeSet", "sendThing"],
            "method.P": ["makeSet", "sendThing"],
            "type.named": ["WidgetPart"],
            "webapp.guided": ["CloudStorage.getItems", "events.popupClosed"],
        })
        text = api_coverage.report(result)
        self.assertIn("| Available methods | 3 | 1 | 1 | 2 | 1 | 1 | 0 |", text)
        self.assertIn("| **Total** | **4** | **1** | **1** | **2** | **1** | **2** | **0** |", text)
        self.assertIn("Methods named nowhere (2): makeSet, sendThing", text)
        self.assertIn("| **Total** | **3** | **2** | **1** | **0** | **1** |", text)
        self.assertIn("| **Total** | **4** | **3** | **1** | **1** | **2** |", text)


class Floor(FakeSkill):
    def test_check_needs_a_floor(self):
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("no floor", out)

    def test_check_passes_on_the_recorded_state(self):
        self.assertEqual(self.run_cli("--update-floor")[0], 0)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("method.K 1/4", out)

    def test_lost_coverage_fails(self):
        self.run_cli("--update-floor")
        _write(self.skill, "references/messages.md", "A Widget holds parts.")
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("missing method.K (1): sendThingDraft", out)

    def test_gained_coverage_makes_the_floor_stale_until_updated(self):
        self.run_cli("--update-floor")
        _write(self.skill, "references/mini-apps/events.md", "Handle `themeChanged` and `popupClosed`.")
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("now covered webapp.guided (1): events.popupClosed", out)
        self.assertEqual(self.run_cli("--update-floor")[0], 0)
        self.assertEqual(self.run_cli("--check")[0], 0)
        with open(self.floor, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["gaps"]["webapp.guided"], ["CloudStorage.getItems"])

    def test_update_refuses_to_lower_the_floor(self):
        self.run_cli("--update-floor")
        _write(self.skill, "recipes/01-thing.md", "Call it, then render it.")
        code, out = self.run_cli("--update-floor")
        self.assertEqual(code, 1)
        self.assertIn("new gap type.named (1): RichBlockNote", out)
        self.assertEqual(self.run_cli("--update-floor", "--allow-new-gaps")[0], 0)
        self.assertEqual(self.run_cli("--check")[0], 0)


if __name__ == "__main__":
    unittest.main()
