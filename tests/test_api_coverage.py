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
            "data/bot-api/agent-notes/things.json": {"domain": "things", "notes": {
                "sendThingDraft": {"purpose": "x", "related": ["WidgetPart", "getStuff"]}}},
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
        self.assertEqual([n for n in CATALOG["methods"] if rows[n]["N"]], ["sendThingDraft"])
        self.assertEqual([n for n in CATALOG["types"] if rows[n]["C"]], ["WidgetPart"])

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
            "method.note": ["getStuff", "makeSet", "sendThing"],
            "type.card": ["RichBlockNote", "Widget"],
            "webapp.guided": ["CloudStorage.getItems", "events.popupClosed"],
        })
        text = api_coverage.report(result)
        self.assertIn("| Available methods | 3 | 1 | 1 | 2 | 1 | 1 | 1 | 0 |", text)
        self.assertIn("| **Total** | **4** | **1** | **1** | **2** | **1** | **1** | **2** | **0** |", text)
        self.assertIn("Methods named nowhere (2): makeSet, sendThing", text)
        self.assertIn("| **Total** | **3** | **2** | **1** | **0** | **1** | **1** |", text)
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

    def test_a_new_measure_enters_the_floor_without_override(self):
        self.run_cli("--update-floor")
        with open(self.floor, encoding="utf-8") as fh:
            older = json.load(fh)
        del older["gaps"]["type.card"]  # a floor written before this measure existed
        with open(self.floor, "w", encoding="utf-8") as fh:
            json.dump(older, fh)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("the floor has no type.card yet", out)
        self.assertNotIn("missing", out)
        self.assertEqual(self.run_cli("--update-floor")[0], 0)
        self.assertEqual(self.run_cli("--check")[0], 0)

    def test_symbol_removed_from_the_catalog_is_reported_as_gone(self):
        self.run_cli("--update-floor")
        catalog = json.loads(json.dumps(CATALOG))
        del catalog["methods"]["makeSet"]
        _write(self.skill, "data/bot-api/catalog.json", catalog)
        code, out = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("no longer in the catalog method.K (1): makeSet", out)
        self.assertNotIn("now covered", out)

    def test_floor_path_without_a_folder(self):
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.skill)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = api_coverage.main(["--update-floor", "--skill", self.skill, "--floor", "floor.json"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(self.skill, "floor.json")))


class UnionMembers(FakeSkill):
    def test_members_of_a_carded_union_are_in_a_card(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["types"].update({
            "Shape": {"section": "Available types", "subtypes": ["ShapeRound"]},
            "ShapeRound": {"section": "Available types", "subtypes": ["ShapeRoundSmall"]},
            "ShapeRoundSmall": {"section": "Available types"},
            "Loner": {"section": "Available types", "subtypes": ["Orphan"]},
            "Orphan": {"section": "Available types"},
        })
        _write(self.skill, "data/bot-api/catalog.json", catalog)
        _write(self.skill, "data/bot-api/agent-notes/things.json", {"domain": "things", "notes": {
            "sendThingDraft": {"purpose": "x", "related": ["Shape"]}}})
        rows = self.rows()
        self.assertEqual([n for n in ("Shape", "ShapeRound", "ShapeRoundSmall", "Loner", "Orphan") if rows[n]["C"]],
                         ["Shape", "ShapeRound", "ShapeRoundSmall"])


class Scope(FakeSkill):
    def test_nested_recipe_and_payload_folders_do_not_count(self):
        _write(self.skill, "recipes/archive/old.md", "makeSet WidgetPart")
        _write(self.skill, "examples/payloads/archive/old.json", {"steps": [{"method": "makeSet"}]})
        rows = self.rows()
        self.assertFalse(rows["makeSet"]["R"] or rows["makeSet"]["P"])
        self.assertFalse(rows["WidgetPart"]["R"])


def _git(cwd, *args):
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.autocrlf=false",
                    *args], cwd=cwd, check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class InGitCheckout(FakeSkill):
    def setUp(self):
        super().setUp()
        _git(self.skill, "init", "-q")

    def test_only_tracked_files_count(self):
        _git(self.skill, "add", "-A")
        _git(self.skill, "rm", "-q", "--cached", "examples/python/bot.py")
        self.assertFalse(self.rows()["getStuff"]["P"])
        _git(self.skill, "add", "examples/python/bot.py")
        self.assertTrue(self.rows()["getStuff"]["P"])

    def commit_base(self):
        _git(self.skill, "add", "-A")  # tracked first: untracked files do not count
        self.run_cli("--update-floor")
        _git(self.skill, "add", "-A")
        _git(self.skill, "commit", "-q", "-m", "base")

    def test_floor_lowered_in_the_same_change_fails_against_the_base(self):
        self.commit_base()
        _write(self.skill, "recipes/01-thing.md", "Call it, then render it.")
        self.assertEqual(self.run_cli("--update-floor", "--allow-new-gaps")[0], 0)
        self.assertEqual(self.run_cli("--check")[0], 0)
        code, out = self.run_cli("--check", "--against", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("lowered type.named (1): RichBlockNote", out)

    def test_symbols_new_since_the_base_may_enter_the_floor(self):
        self.commit_base()
        catalog = json.loads(json.dumps(CATALOG))
        catalog["methods"]["newThing"] = {"section": "Available methods"}
        _write(self.skill, "data/bot-api/catalog.json", catalog)
        self.assertEqual(self.run_cli("--update-floor", "--allow-new-gaps")[0], 0)
        code, out = self.run_cli("--check", "--against", "HEAD")
        self.assertEqual(code, 0, out)
        self.assertIn("not lowered against HEAD", out)

    def test_no_floor_at_the_base_is_not_an_error(self):
        _git(self.skill, "add", "-A")
        _git(self.skill, "commit", "-q", "-m", "before the floor")
        self.run_cli("--update-floor")
        code, out = self.run_cli("--check", "--against", "HEAD")
        self.assertEqual(code, 0, out)
        self.assertIn("no floor at HEAD", out)


if __name__ == "__main__":
    unittest.main()
