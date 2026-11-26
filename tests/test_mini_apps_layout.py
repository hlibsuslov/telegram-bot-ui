"""Layout rules (data/mini-apps/layouts.json, scripts/miniapp_layout.py, references/mini-apps/layout-rules.md)
and the catalogue example that applies them. Offline, stdlib unittest."""
import contextlib
import io
import json
import os
import re
import unittest

import _paths
import miniapp_layout as ml
import miniapp_lint as lint

DATA = ml.load()
KIT = os.path.join(_paths.EXAMPLES, "mini-apps")
REF = os.path.join(_paths.ROOT, "references", "mini-apps")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class RulesData(unittest.TestCase):
    def test_rules_are_numbered_and_complete(self):
        self.assertEqual(sorted(DATA["rules"]), [f"L{i:02d}" for i in range(1, 27)])  # L26: the paywall
        for rid, r in DATA["rules"].items():
            self.assertIn(r["severity"], {"error", "warn"}, rid)
            self.assertTrue(r["title"] and r["fix"], rid)

    def test_entities_are_complete(self):
        need = {"title", "ratio", "fit", "list_variant", "columns", "card", "meta", "card_action", "primary", "detail"}
        self.assertGreaterEqual(len(DATA["entities"]), 15)
        for name, e in DATA["entities"].items():
            self.assertTrue(need <= set(e), f"{name}: {sorted(need - set(e))}")
            self.assertIn(e["list_variant"], DATA["variants"], name)
        for name in ("book", "trainer", "workout", "product", "plan", "class", "event", "listing", "menu-item"):
            self.assertIn(name, DATA["entities"])

    def test_key_ratios(self):
        ratios = {k: ml.ratio_of(e["ratio"]) for k, e in DATA["entities"].items()}
        self.assertEqual(ratios["book"], "2:3")
        self.assertEqual(ratios["trainer"], "4:5")
        self.assertEqual(ratios["workout"], "16:9")
        self.assertEqual(ratios["product"], "1:1")
        self.assertEqual(ratios["event"], "3:2")
        self.assertEqual(ratios["listing"], "4:3")
        self.assertTrue(DATA["entities"]["book"]["fit"].startswith("contain"))

    def test_reference_explains_every_rule_and_entity(self):
        text = read(REF, "layout-rules.md")
        for rid in DATA["rules"]:
            self.assertTrue(f"| {rid} | {DATA['rules'][rid]['title']} |" in text, rid)
        for name, e in DATA["entities"].items():
            self.assertTrue(e["title"].split()[0].lower() in text.lower(), name)


class Review(unittest.TestCase):
    BAD = {"screen": "catalog", "entity": "book", "width": 390, "layout": {"variant": "tile", "columns": 3},
           "card": {"image": {"ratio": "1:1", "fit": "cover", "position": "top"}, "slots": ["image", "price", "title", "author"],
                    "title_lines": 3, "tags": 2, "ribbon": True, "actions": ["favourite", "add", "share"], "rating": "stars",
                    "price": {"style": "pill"}, "text_on_image": True, "description_lines": 3},
           "primary_action": "in-card", "carousels": 2, "filters": {"count": 7, "placement": "top"}, "search": "bottom",
           "unavailable": "hidden"}

    def rules(self, spec):
        return {f["rule"] for f in ml.review(spec, DATA)}

    def test_bad_catalogue_hits_the_expected_rules(self):
        self.assertEqual(self.rules(self.BAD), {"L02", "L03", "L05", "L06", "L07", "L08", "L09", "L10", "L13", "L14",
                                                "L17", "L18", "L19", "L20"})

    def test_examples_are_clean(self):
        for name, spec in ml.EXAMPLES.items():
            self.assertEqual(ml.review(spec, DATA), [], name)

    def test_primary_action_and_booking(self):
        self.assertIn("L01", self.rules({"screen": "detail", "entity": "product", "primary_action": "fixed-button"}))
        found = self.rules({"screen": "booking", "entity": "trainer", "primary_action": "main-button",
                            "booking": {"days": "calendar", "slots_columns": 6, "unavailable": "hidden", "summary": False,
                                        "main_button_names_slot": False}})
        self.assertEqual(found, {"L16"})
        self.assertEqual(len([f for f in ml.review({"booking": {"unavailable": "hidden", "summary": False}}, DATA)]), 2)

    def test_listing_price_may_lead_and_detail_order(self):
        listing = {"entity": "listing", "card": {"slots": ["image", "price", "title"]}, "layout": {"variant": "media-card"}}
        self.assertEqual(self.rules(listing), set())
        detail = {"screen": "detail", "entity": "product", "sections": ["title", "reviews", "description"]}
        self.assertEqual(self.rules(detail), {"L11"})

    def test_plans_forms_wide_screens(self):
        self.assertEqual(self.rules({"screen": "plans", "entity": "plan", "width": 390,
                                     "plans": {"layout": "side-by-side", "count": 5, "recommended": 2}}), {"L25"})
        self.assertEqual(self.rules({"screen": "form", "form": {"columns": 2, "labels": "placeholder"}}), {"L15"})
        self.assertIn("L24", self.rules({"entity": "product", "width": 768, "layout": {"variant": "tile", "columns": 3}}))

    def test_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(ml.main(["show", "trainer"]), 0)
        self.assertIn("Book {day} {time}", buf.getvalue())
        for name in DATA["entities"]:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ml.main(["show", name]), 0, name)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ml.main(["show", "spaceship"]), 1)


class CatalogExample(unittest.TestCase):
    def test_lint_clean_and_built(self):
        files, root = lint.collect([os.path.join(KIT, "catalog")])
        self.assertEqual([f.text() for f in lint.lint_files(files, root).findings], [])
        self.assertIn("catalog/app.ts", read(KIT, "build.mjs"))

    def test_applies_the_rules(self):
        src = read(KIT, "catalog", "app.ts")
        self.assertIn("'2 / 3'", src)            # book covers
        self.assertIn("'is-contain'", src)       # covers are not cropped (L03)
        self.assertIn("'4 / 5'", src)            # trainer portrait
        self.assertIn("'16 / 9'", src)           # workouts
        self.assertIn("tma-slots", src)          # booking grid (L16)
        self.assertIn("Sold out", src)           # unavailable stays visible (L08)
        self.assertNotIn("innerHTML", src)       # data goes through textContent
        for i in range(1, 7):
            self.assertTrue(os.path.isfile(os.path.join(KIT, "catalog", "media", f"cover-{i}.svg")))

    def test_new_kit_classes_are_in_the_catalogue(self):
        cat = _paths.load("data", "mini-apps", "components.json")["components"]
        css = read(KIT, "_kit", "tma.css")
        for key in ("grid", "tile", "price", "row-thumb", "favourite", "day-strip", "slot-grid", "plan-card", "check-list"):
            self.assertIn(cat[key]["kit"].lstrip("."), css, key)


if __name__ == "__main__":
    unittest.main()
