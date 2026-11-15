"""Emoji data files, audit_icons v2, the emoji_packs CLI, recipes 70-75 and their payloads."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import _paths
import audit_icons
import emoji_packs

FIX = ("examples", "python", "icons", "fixtures")
CLI = os.path.join(_paths.ROOT, "scripts", "emoji_packs.py")
VOCAB = _paths.load("data", "emoji", "slots.json")
PACKS = _paths.load("data", "emoji", "packs.json")


def fixture(name):
    return _paths.load(*FIX, f"{name}.json")["result"]


def write(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))


def cli(*args):
    p = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8", cwd=_paths.ROOT)
    return p.returncode, p.stdout, p.stderr


class Data(unittest.TestCase):
    def test_vocabulary(self):
        slots = VOCAB["slots"]
        self.assertGreaterEqual(len(slots), 150)
        groups = {"navigation", "actions", "status", "commerce", "finance", "media", "communication", "settings",
                  "time", "people", "analytics", "ai", "files", "warnings", "post"}
        self.assertEqual({v["group"] for v in slots.values()}, groups)
        uses = {"button", "title", "inline", "post_accent", "status"}
        for name, v in slots.items():
            with self.subTest(slot=name):
                self.assertTrue(v["unicode"] and isinstance(v["label"], str) and v["note"])
                self.assertTrue(set(v["use"]) <= uses and v["use"])
                self.assertRegex(name, r"^[a-z0-9_]+$")

    def test_packs_have_metadata_and_no_ids(self):
        names = set()
        for p in PACKS["packs"]:
            with self.subTest(pack=p["name"]):
                for key in ("name", "link", "title", "family", "style", "archetypes", "tone", "choose_when", "evidence"):
                    self.assertTrue(p.get(key), key)
                self.assertEqual(p["link"], f"https://t.me/addemoji/{p['name']}")
                names.add(p["name"])
        self.assertNotRegex(json.dumps(PACKS), r"\d{15,}")      # no custom_emoji_id in the registry
        for p in PACKS["packs"]:
            self.assertTrue(set(p["siblings"]) <= names)
        self.assertIn("redistribut", PACKS["licensing"])

    def test_fixtures_are_marked_synthetic(self):
        for n in ("demo_line_icons", "demo_line_icons_extra", "demo_solid_icons", "demo_motion_icons"):
            self.assertTrue(all(s["custom_emoji_id"].startswith("0") for s in fixture(n)["stickers"]))


class Audit(unittest.TestCase):
    def build(self, *names):
        from tgkit.icons import resolve_icon_map
        sets = [fixture(n) for n in names]
        return resolve_icon_map(sets, VOCAB["slots"], ["home", "settings", "success", "pending", "rocket"])[0]

    def test_fixture_ids_need_the_flag(self):
        doc = self.build("demo_line_icons")
        self.assertTrue(any("synthetic fixture id" in e for e in audit_icons.audit(doc)[0]))
        self.assertEqual(audit_icons.audit(doc, allow_fixture_ids=True), ([], []))

    def test_mixed_families_animation_and_adaptive(self):
        line, motion = self.build("demo_line_icons"), self.build("demo_motion_icons")
        mixed = {"icons": {**{k: v for k, v in line["icons"].items() if k in ("home", "settings")},
                           **{k: v for k, v in motion["icons"].items() if k in ("success", "rocket")}}}
        _, warnings = audit_icons.audit(mixed, allow_fixture_ids=True)
        text = " ".join(warnings)
        self.assertIn("icon families on one bot", text)
        self.assertIn("animated and", text)
        self.assertIn("adaptive", text)

    def test_payload_audit(self):
        doc = {"steps": [{"method": "sendMessage", "params": {"reply_markup": {"inline_keyboard": [[
            {"text": "⚙️ Settings", "icon_custom_emoji_id": "5258096772776991776", "callback_data": "s"},
            {"text": "🔥 Hot", "callback_data": "h"}]]}}}]}
        errors, warnings = audit_icons.audit_payload(doc)
        self.assertTrue(any("double icon" in e for e in errors))
        self.assertTrue(any("mixed keyboard" in w for w in warnings))


class Cli(unittest.TestCase):
    def test_resolve_reports_coverage(self):
        code, out, err = cli("resolve", "--sticker-set", os.path.join(*FIX, "demo_line_icons.json"),
                             "--slots", "home,back,rocket")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(json.loads(out)["icons"]), ["back", "home"])
        self.assertIn("uncovered (1): rocket", err)

    def test_suggest_ranks_by_metadata_without_sets(self):
        code, out, _ = cli("suggest", "--needs", "home,settings,done,wallets", "--archetype", "monitoring")
        ranking = json.loads(out)["ranking"]
        self.assertEqual(code, 0)
        self.assertTrue(all(r["basis"].startswith("metadata") for r in ranking))
        self.assertFalse(ranking[0]["animation"] and ranking[0]["animation"].startswith("animated"))

    def test_suggest_uses_real_coverage_when_sets_are_given(self):
        packs = [{"name": "demo_line_icons", "family": "a", "link": "x", "archetypes": [], "tone": []},
                 {"name": "demo_motion_icons", "family": "b", "link": "y", "archetypes": [], "tone": []}]
        ranked = emoji_packs.rank_packs(["home", "settings", "done"], VOCAB["slots"], packs,
                                        sets=[fixture("demo_line_icons"), fixture("demo_motion_icons")])
        self.assertEqual(ranked[0]["name"], "demo_line_icons")
        self.assertEqual(ranked[0]["coverage"], 1.0)

    def test_verify_detects_removed_emoji(self):
        with tempfile.TemporaryDirectory() as d:
            m, r = os.path.join(d, "map.json"), os.path.join(d, "resp.json")
            stickers = fixture("demo_line_icons")["stickers"]
            write(m, {"icons": {"home": {"id": stickers[0]["custom_emoji_id"], "fallback": "🏠", "set": "demo_line_icons"},
                                "back": {"id": stickers[1]["custom_emoji_id"], "fallback": "⬅️", "set": "demo_line_icons"}}})
            write(r, {"ok": True, "result": stickers[:1]})
            code, out, _ = cli("verify", "--map", m, "--response", r)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["removed_slots"], ["back"])

    def test_capture_and_apply_strip_round_trip(self):
        code, out, _ = cli("capture")
        self.assertEqual(code, 0)
        self.assertIn("custom_emoji", out)
        with tempfile.TemporaryDirectory() as d:
            m, p = os.path.join(d, "map.json"), os.path.join(d, "p.json")
            code, out, _ = cli("resolve", "--sticker-set", os.path.join(*FIX, "demo_line_icons.json"), "--slots", "settings,done")
            write(m, out)
            params = {"text": "<b>⚙️ Settings</b> ✅", "parse_mode": "HTML",
                      "reply_markup": {"inline_keyboard": [[{"text": "✅ Done", "callback_data": "d"}]]}}
            write(p, params)
            code, applied, _ = cli("apply", "--map", m, "--in", p, "--context", "private", "--owner-premium")
            self.assertEqual(code, 0)
            self.assertIn("tg-emoji", applied)
            write(p, applied)
            code, stripped, _ = cli("strip", "--map", m, "--in", p)
            self.assertEqual(json.loads(stripped), params)
            code, chan, err = cli("apply", "--map", m, "--in", p, "--context", "channel", "--owner-premium")
            self.assertNotIn("tg-emoji", chan)
            self.assertIn("not eligible", err)


class Recipes(unittest.TestCase):
    def test_recipe_docs_follow_the_ten_point_format(self):
        docs = sorted(f for f in os.listdir(os.path.join(_paths.ROOT, "recipes")) if re.match(r"7\d-.*\.md$", f))
        self.assertEqual(len(docs), 6)
        for f in docs:
            body = _paths.read("recipes", f)
            for n in range(1, 11):
                self.assertRegex(body, rf"(?m)^{n}\. \*\*", f"{f} misses point {n}")
            py = re.search(r"examples/python/recipes/(r7\d_\w+\.py)", body).group(1)
            self.assertTrue(os.path.exists(os.path.join(_paths.EXAMPLES, "python", "recipes", py)))

    def test_payloads_match_the_code(self):
        p = subprocess.run([sys.executable, os.path.join(_paths.EXAMPLES, "python", "icons", "export_emoji_payloads.py"),
                            "--check"], capture_output=True, text=True, cwd=_paths.ROOT)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_payloads_pass_the_icon_audit(self):
        for f in sorted(os.listdir(os.path.join(_paths.EXAMPLES, "payloads"))):
            if f.startswith("r7"):
                doc = _paths.load("examples", "payloads", f)
                errors, warnings = audit_icons.audit_payload(doc, post="channel" in doc["context"])
                self.assertEqual(errors, [], f)
                self.assertEqual(warnings, [], f)


if __name__ == "__main__":
    unittest.main()
