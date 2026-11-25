"""emoji_packs.py library: search the telegram-bot-ui emoji library and pick one pack family (offline answers)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths

SCRIPT = os.path.join(_paths.ROOT, "scripts", "emoji_packs.py")


def hit(pack, eid, fallback, fmt="static", adaptive=False):
    return {"pack": pack, "id": eid, "fallback": fallback, "format": fmt, "adaptive": adaptive}


def entry(eid, fallback, fmt="static", adaptive=False):
    return {"id": eid, "fallback": fallback, "format": fmt, "adaptive": adaptive}


SAVED = {
    "search": {
        "🏠": {"emoji": [hit("glyphs", "11", "🏠"), hit("cartoon", "21", "🏠", "animated")]},
        "⬅️": {"emoji": [hit("glyphs", "12", "⬅️"), hit("cartoon", "22", "⬅", "animated")]},
        "⚙️": {"emoji": [hit("glyphs", "13", "⚙"), hit("cartoon", "23", "⚙️", "animated"), hit("noise", "31", "5️⃣")]},
        "settings": {"emoji": [hit("glyphs", "13", "⚙")], "packs": [{"name": "glyphs", "score": 9, "hits": 1}]},
    },
    "packs": {
        "glyphs": {"title": "Glyphs", "emoji": [entry("11", "🏠", adaptive=True), entry("12", "⬅️", adaptive=True), entry("13", "⚙️", adaptive=True)]},
        "cartoon": {"title": "Cartoon", "emoji": [entry("21", "🏠", "animated"), entry("23", "⚙", "animated")]},
    },
}


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding="utf-8", timeout=60)


class Pick(unittest.TestCase):
    def setUp(self):
        fd, self.saved = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(SAVED, fh, ensure_ascii=False)
        self.out = self.saved + ".out.json"

    def tearDown(self):
        for p in (self.saved, self.out):
            if os.path.exists(p):
                os.remove(p)

    def test_one_family_with_full_coverage_wins_and_the_map_has_real_ids_only_from_it(self):
        r = run("library", "pick", "--needs", "home,back,settings,nonsense", "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["map"]["family"], "glyphs")
        self.assertEqual({k: v["id"] for k, v in doc["map"]["icons"].items()}, {"home": "11", "back": "12", "settings": "13"})
        self.assertEqual({v["set"] for v in doc["map"]["icons"].values()}, {"glyphs"})
        self.assertEqual(doc["unknown_slots"], ["nonsense"])
        cartoon = next(x for x in doc["ranking"] if x["name"] == "cartoon")
        self.assertEqual(cartoon["missing"], ["back"])
        self.assertNotIn("noise", [x["name"] for x in doc["ranking"]], "a hit whose fallback is not the slot's emoji must not vote")

    def test_search_lists_hits_with_ids(self):
        r = run("library", "search", "settings", "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.out, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["emoji"][0]["id"], "13")

    def test_nothing_matches_exits_1(self):
        r = run("library", "pick", "--needs", "search", "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
