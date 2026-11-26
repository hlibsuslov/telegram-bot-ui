"""emoji_packs.py: picking a pack family by the library's faceted tags (style, colour, theme fit, topic, ...)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths

SCRIPT = os.path.join(_paths.ROOT, "scripts", "emoji_packs.py")
sys.path.insert(0, os.path.join(_paths.ROOT, "scripts"))
import emoji_packs  # noqa: E402


def hit(pack, eid, fallback):
    return {"pack": pack, "id": eid, "fallback": fallback, "format": "static", "adaptive": True}


def entry(eid, fallback):
    return {"id": eid, "fallback": fallback, "format": "static", "adaptive": True}


def pack_doc(title):
    return {"title": title, "emoji": [entry("1", "🏠"), entry("2", "⬅️"), entry("3", "⚙️")]}


def tags(**facets):
    return {f: [[v, c] for v, c in vals] for f, vals in facets.items()}


def value(en, ru):
    return {"en": en, "ru": ru}


FACETS = {
    "ok": True, "generated": "2026-11-25", "thresholds": {"emoji": 0.5, "pack": 0.3, "show": 0.55},
    "taxonomy": {"version": 1, "facets": {
        "style": {"label": {"en": "Style", "ru": "Стиль"}, "scope": ["pack", "emoji"],
                  "values": {"outline": value("outline", "контурный"), "glossy": value("glossy", "глянцевый"),
                             "3d": value("3d", "объёмный")}},
        "fit": {"label": {"en": "Theme fit", "ru": "Тема"}, "scope": ["pack", "emoji"],
                "values": {"adaptive": value("adaptive", "адаптивный"), "both": value("both", "обе"),
                           "light": value("light", "светлая"), "dark": value("dark", "тёмная")}},
        "color": {"label": {"en": "Colour", "ru": "Цвет"}, "scope": ["pack", "emoji"],
                  "values": {"blue": value("blue", "синий"), "red": value("red", "красный")}},
        "topic": {"label": {"en": "Topic", "ru": "Тема"}, "scope": ["pack", "emoji"],
                  "values": {"interface": value("interface", "интерфейс"), "characters": value("characters", "персонажи")}},
        "use": {"label": {"en": "Bot kind", "ru": "Бот"}, "scope": ["pack"],
                "values": {"shop": value("shop", "магазин"), "utility": value("utility", "утилита")}},
        "mood": {"label": {"en": "Mood", "ru": "Настроение"}, "scope": ["pack", "emoji"],
                 "values": {"calm": value("calm", "спокойный"), "playful": value("playful", "игривый")}},
        "motion": {"label": {"en": "Motion", "ru": "Движение"}, "scope": ["pack", "emoji"],
                   "values": {"static": value("static", "статичный"), "animated": value("animated", "анимированный")}},
    }},
    "packs": [
        {"name": "glyphs", "category": "Interface & icons", "count": 3, "meanings": 3, "compatible": [["lineduo", 0.9]],
         "facets": tags(style=[("outline", 0.9)], fit=[("adaptive", 1.0)], color=[("blue", 0.8)], topic=[("interface", 0.9)],
                        use=[("utility", 0.9)], mood=[("calm", 0.6)], motion=[("static", 1.0)])},
        {"name": "gloss", "category": "Interface & icons", "count": 3, "meanings": 3, "compatible": [],
         "facets": tags(style=[("glossy", 0.9)], fit=[("light", 0.8)], color=[("red", 0.8)], topic=[("interface", 0.9)],
                        use=[("shop", 0.9)], mood=[("playful", 0.7)], motion=[("static", 1.0)])},
        {"name": "lineduo", "category": "Interface & icons", "count": 3, "meanings": 3, "compatible": [["glyphs", 0.9]],
         "facets": tags(style=[("outline", 0.85)], fit=[("adaptive", 1.0)], color=[("blue", 0.7)], topic=[("interface", 0.9)],
                        use=[("shop", 0.8)], mood=[("calm", 0.5)], motion=[("static", 1.0)])},
        {"name": "toons", "category": "Memes & characters", "count": 3, "meanings": 3, "compatible": [],
         "facets": tags(style=[("3d", 0.9), ("outline", 0.2)], fit=[("light", 0.6)], topic=[("characters", 0.9)],
                        motion=[("animated", 1.0)])},
    ],
}

SAVED = {
    "search": {
        "🏠": {"emoji": [hit("glyphs", "1", "🏠"), hit("gloss", "1", "🏠"), hit("toons", "1", "🏠")]},
        "⬅️": {"emoji": [hit("glyphs", "2", "⬅️"), hit("gloss", "2", "⬅️"), hit("toons", "2", "⬅️")]},
        "⚙️": {"emoji": [hit("glyphs", "3", "⚙️"), hit("gloss", "3", "⚙️"), hit("toons", "3", "⚙️")]},
    },
    "packs": {n: pack_doc(n.title()) for n in ("glyphs", "gloss", "lineduo", "toons")},
    "facets": FACETS,
}
NEEDS = "home,back,settings"


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding="utf-8", timeout=60)


class Brief(unittest.TestCase):
    def pick(self, brief=None, require=None, saved=SAVED, **kw):
        vocab = emoji_packs.load_vocabulary(None)
        return emoji_packs.pick_family(NEEDS.split(","), vocab, emoji_packs.LibraryClient(saved), brief=brief,
                                       require=require, **kw)

    def test_the_brief_decides_between_packs_that_cover_the_slots_equally(self):
        self.assertEqual(self.pick({"style": ["outline"]})["map"]["family"], "glyphs")
        self.assertEqual(self.pick({"style": ["glossy"]})["map"]["family"], "gloss")

    def test_labels_in_either_language_are_taxonomy_ids(self):
        out = self.pick({"style": ["контурный"], "color": ["Blue"]})
        self.assertEqual(out["brief"], {"style": ["outline"], "color": ["blue"], "fit": ["both"]})
        self.assertEqual(out["map"]["family"], "glyphs")

    def test_a_pack_that_fits_the_brief_joins_the_candidates_without_a_search_vote(self):
        # lineduo is not in any search answer: only its tags bring it in (and it is a real candidate, fully covered)
        out = self.pick({"style": ["outline"], "use": ["shop"]})
        names = [r["name"] for r in out["ranking"]]
        self.assertIn("lineduo", names)
        self.assertEqual(out["map"]["family"], "lineduo")
        self.assertEqual(next(r for r in out["ranking"] if r["name"] == "lineduo")["votes"], 0)

    def test_matched_tags_are_explained_with_their_confidence(self):
        row = self.pick({"style": ["outline"], "color": ["blue"]})["ranking"][0]
        self.assertEqual(row["name"], "glyphs")
        self.assertIn(["style", "outline", 0.9], row["matched"])
        self.assertGreater(row["brief_match"], 0.7)

    def test_a_tag_below_the_packs_confidence_threshold_counts_for_nothing(self):
        # toons is tagged outline at 0.2, below the 0.3 pack threshold
        out = emoji_packs.rank_by_facets(FACETS, {"style": ["outline"]})
        self.assertEqual(next(r for r in out["packs"] if r["name"] == "toons")["score"], 0.0)

    def test_a_required_tag_is_a_hard_filter(self):
        out = self.pick({"style": ["glossy"]}, require=["fit:adaptive"])
        self.assertNotIn("gloss", [r["name"] for r in out["ranking"]])
        self.assertEqual(self.pick(None, require=["style:3d"])["map"]["family"], "toons")
        none = self.pick({"style": ["outline"]}, require=["color:red", "style:outline"])
        self.assertIsNone(none["map"])
        self.assertIn("no pack carries every required tag", none["notes"])

    def test_the_requested_theme_is_part_of_the_brief(self):
        both = self.pick({"mood": ["calm"]}, theme="both")
        dark = self.pick({"mood": ["calm"]}, theme="dark")
        self.assertEqual(both["map"]["family"], "glyphs")
        self.assertEqual(dark["brief"]["fit"], ["dark"])

    def test_unknown_facets_and_values_are_reported_not_guessed(self):
        out = self.pick({"style": ["watercolour"], "weather": ["rain"]})
        self.assertTrue(any("watercolour" in n for n in out["notes"]))
        self.assertTrue(any("weather" in n for n in out["notes"]))

    def test_an_older_library_without_tags_still_picks_by_coverage_and_says_so(self):
        saved = {k: v for k, v in SAVED.items() if k != "facets"}
        out = self.pick({"style": ["outline"]}, saved=saved)
        self.assertIsNotNone(out["map"])
        self.assertIn("the library has no tags yet: ranked by coverage only", out["notes"])
        self.assertNotIn("brief", out)

    def test_without_a_brief_the_answer_is_unchanged(self):
        out = self.pick()
        self.assertNotIn("brief", out)
        self.assertNotIn("notes", out)
        self.assertNotIn("brief_match", out["ranking"][0])


class StaticOnButtons(unittest.TestCase):
    """A button never takes an animated or video emoji: the pick gives every slot the static emoji of its meaning."""
    MIXED = {"title": "Mixed", "emoji": [
        {"id": "10", "fallback": "🏠", "format": "animated", "adaptive": False},
        {"id": "11", "fallback": "🏠", "format": "static", "adaptive": False},
        {"id": "20", "fallback": "⬅️", "format": "video", "adaptive": False},
        {"id": "21", "fallback": "◀️", "format": "static", "adaptive": False},
        {"id": "30", "fallback": "⚙️", "format": "animated", "adaptive": False}]}
    SAVED = {"search": {"🏠": {"emoji": [hit("mixed", "10", "🏠")]}, "⬅️": {"emoji": [hit("mixed", "20", "⬅️")]},
                        "⚙️": {"emoji": [hit("mixed", "30", "⚙️")]}},
             "packs": {"mixed": MIXED}}

    def pick(self, **kw):
        return emoji_packs.pick_family(["home", "back", "settings"], emoji_packs.load_vocabulary(None),
                                       emoji_packs.LibraryClient(self.SAVED), **kw)

    def test_static_is_the_default_and_wins_over_an_animated_one_of_the_same_meaning(self):
        icons = self.pick()["map"]["icons"]
        self.assertEqual(icons["home"]["id"], "11")  # the same fallback, the static entry
        self.assertEqual(icons["back"]["id"], "21")  # the slot's other emoji, static: not the video ⬅️
        self.assertEqual((icons["settings"]["id"], icons["settings"]["animated"]), ("30", True))  # no static one: still covered
        self.assertEqual(self.pick()["ranking"][0]["static_share"], 0.67)

    def test_an_explicit_motion_wins(self):
        icons = self.pick(motion="any")["map"]["icons"]
        self.assertEqual((icons["home"]["id"], icons["back"]["id"]), ("10", "20"))
        self.assertEqual(self.pick(motion="any")["ranking"][0]["static_share"], 0.0)

    def test_the_cli_picks_static_without_a_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved, out = os.path.join(tmp, "saved.json"), os.path.join(tmp, "out.json")
            with open(saved, "w", encoding="utf-8") as fh:
                json.dump(self.SAVED, fh, ensure_ascii=False)
            for flags, home in ((), "11"), (("--motion", "any"), "10"):
                r = run("library", "pick", "--needs", "home,back", *flags, "--library-json", saved, "--out", out)
                self.assertEqual(r.returncode, 0, r.stderr)
                with open(out, encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh)["map"]["icons"]["home"]["id"], home, flags)


class Profile(unittest.TestCase):
    def test_the_style_profile_becomes_a_brief(self):
        brief = emoji_packs.brief_from_profile({
            "bot": {"archetype": "shop"},
            "brand": {"traits": ["calm", "precise", "plain"], "accent": "#2F6FEB", "icon_style": "Outline"}})
        self.assertEqual(brief, {"topic": ["interface"], "style": ["outline"], "color": ["blue"],
                                 "mood": ["calm", "serious"], "use": ["shop"]})

    def test_a_profile_without_style_facts_asks_only_for_interface_icons(self):
        self.assertEqual(emoji_packs.brief_from_profile({}), {"topic": ["interface"]})

    def test_accent_colours_map_to_the_library_colour_names(self):
        for hex_, family in {"#E53935": "red", "#43A047": "green", "#FFC107": "gold", "#8E24AA": "purple",
                             "#111111": "black", "#888888": "gray", "#FFFFFF": "white", "nonsense": None}.items():
            self.assertEqual(emoji_packs.accent_family(hex_), family, hex_)


class Cli(unittest.TestCase):
    def setUp(self):
        fd, self.saved = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(SAVED, fh, ensure_ascii=False)
        self.out = self.saved + ".out.json"
        self.profile = self.saved + ".profile.json"
        with open(self.profile, "w", encoding="utf-8") as fh:
            json.dump({"bot": {"archetype": "shop"}, "brand": {"icon_style": "outline", "accent": "#2F6FEB"}}, fh)

    def tearDown(self):
        for p in (self.saved, self.out, self.profile):
            if os.path.exists(p):
                os.remove(p)

    def read(self):
        with open(self.out, encoding="utf-8") as fh:
            return json.load(fh)

    def test_facets_without_a_brief_lists_the_taxonomy(self):
        r = run("library", "facets", "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = self.read()
        self.assertEqual(doc["packs"], 4)
        self.assertIn("outline", doc["facets"]["style"]["values"])

    def test_facets_ranks_packs_for_a_profile_and_flags(self):
        r = run("library", "facets", "--profile", self.profile, "--require", "fit:adaptive", "--library-json", self.saved,
                "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = self.read()
        self.assertEqual([p["name"] for p in doc["packs"]][:2], ["lineduo", "glyphs"])
        self.assertEqual(doc["brief"]["use"], ["shop"])

    def test_pick_takes_the_profile_and_flags_override_it(self):
        r = run("library", "pick", "--needs", NEEDS, "--profile", self.profile, "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read()["map"]["family"], "lineduo")
        r = run("library", "pick", "--needs", NEEDS, "--profile", self.profile, "--style", "glossy", "--use", "shop",
                "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read()["map"]["family"], "gloss")

    def test_a_bad_requirement_is_reported_and_exits_1(self):
        r = run("library", "facets", "--require", "style:nope", "--library-json", self.saved, "--out", self.out)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nope", r.stderr)


if __name__ == "__main__":
    unittest.main()
