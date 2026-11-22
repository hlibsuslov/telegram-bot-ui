"""Widget design profiles (scripts/widget_design.py): validation, compilation to CSS, contrast,
the build integration and the invariant that every preset fits every gallery widget."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths
import build_widget as bw
import widget_design as wd
import widget_lint

SCRIPTS = os.path.join(_paths.ROOT, "scripts")


def src(name: str) -> str:
    with open(os.path.join(bw.SRC_DIR, name + ".html"), encoding="utf-8") as fh:
        return fh.read()


class Validate(unittest.TestCase):
    def test_presets_are_valid(self):
        for name in wd.PRESETS:
            with self.subTest(preset=name):
                self.assertEqual(wd.validate(wd.apply_preset(name)), [])

    def test_bad_values_are_named(self):
        errs = wd.validate({"button": {"style": "neon", "radius": 99}, "colors": {"light": {"text": "red", "x": "#000000"}},
                            "motion": "wild", "extra": 1})
        joined = "\n".join(errs)
        for part in ("button.style", "button.radius", "colors.light.text", "unknown slot 'x'", "motion", "'extra'"):
            self.assertIn(part, joined)

    def test_build_refuses_an_invalid_profile(self):
        res = bw.build_text(src("quiz"), langs=("en",), design={"block": {"radius": -1}})
        self.assertFalse(res.ok)
        self.assertIn("design:", res.errors[0])


class Compile(unittest.TestCase):
    def test_empty_profile_changes_nothing(self):
        plain = bw.build_text(src("quiz"), langs=("en",))
        for design in ({}, wd.apply_preset("telegram")):
            res = bw.build_text(src("quiz"), langs=("en",), design=design)
            self.assertEqual(res.html, plain.html)
        self.assertEqual(wd.compile_css({}), "")

    def test_theme_mode_uses_light_dark_with_telegram_for_the_unset_side(self):
        css = wd.compile_css({"colors": {"mode": "theme", "light": {"text": "#112233"}}})
        self.assertIn("--k-tx:light-dark(#112233,var(--tg-theme-text-color,#000))", css)

    def test_shared_mode_writes_one_colour(self):
        css = wd.compile_css({"colors": {"mode": "shared", "shared": {"button": "#d4f36b"}, "light": {"button": "#000000"}}})
        self.assertIn("--k-btn:#d4f36b", css)
        self.assertNotIn("#000000", css)

    def test_buttons_restyled_through_client_variables(self):
        css = wd.compile_css({"colors": {"mode": "shared", "shared": {"button": "#123456"}},
                              "button": {"style": "filled", "radius": 4, "height": "high"}})
        for decl in ("--tg-button-bg:var(--k-btn)", "--tg-button-radius:4px", "--tg-button-height:44px"):
            self.assertIn(decl, css)

    def test_outline_ring_only_on_primary_buttons(self):
        css = wd.compile_css({"button": {"style": "outline"}})
        self.assertIn(wd.PRIMARY + "{box-shadow:inset 0 0 0 1.5px currentColor}", css)
        self.assertNotIn(":not(.ch)", css)

    def test_rules_only_for_parts_the_widget_has(self):
        design = {"counter": {"style": "outline"}, "bar": {"height": 8}, "image": {"radius": 12}, "chips": {"radius": 4}}
        quiz = wd.compile_css(design, bw.prune_kit_css(bw.inline_kit(src("quiz"))[0]))
        card = wd.compile_css(design, bw.prune_kit_css(bw.inline_kit(src("product-card"))[0]))
        self.assertNotIn(".qt", quiz)
        self.assertNotIn(".im", quiz)
        self.assertIn(".br", quiz)
        self.assertIn(".k .qt .ch", card)
        self.assertIn(".k .im", card)

    def test_motion_never_animates_opacity_or_filters(self):
        css = wd.compile_css({"motion": "lively"})
        self.assertIn("@keyframes k-in", css)
        self.assertIn("@keyframes k-sh", css)
        self.assertNotIn("opacity", css)
        self.assertNotIn("filter", css)

    def test_profile_css_comes_before_the_widgets_own_rules(self):
        res = bw.build_text(src("rating-feedback"), langs=("en",), design={"button": {"style": "outline"}})
        self.assertTrue(res.ok, res.errors)
        self.assertLess(res.html.index("box-shadow:inset 0 0 0 1.5px currentColor"), res.html.index(".sr button"))


class Contrast(unittest.TestCase):
    def test_ratio(self):
        self.assertAlmostEqual(wd.contrast("#000000", "#ffffff"), 21.0, places=1)

    def test_low_contrast_is_reported_per_theme(self):
        w = wd.warnings({"colors": {"mode": "theme", "dark": {"hint": "#333333", "bg": "#222222"}}, "block": {"inset": 6}})
        self.assertTrue(any(x.startswith("dark theme: Secondary text") for x in w), w)
        self.assertFalse(any(x.startswith("light theme") for x in w), w)

    def test_telegram_only_pairs_are_not_the_profiles_problem(self):
        self.assertEqual(wd.warnings({"block": {"radius": 12}}), [])

    def test_full_bubble_background_is_flagged(self):
        w = wd.warnings({"colors": {"mode": "shared", "shared": {"bg": "#ffffff", "text": "#000000"}}})
        self.assertTrue(any("whole bubble" in x for x in w))

    def test_lint_accepts_the_profiles_colours_only(self):
        html = '<style>.a{color:#123456}.b{color:#654321}</style>'
        rep = widget_lint.lint(html, caption="x", allowed_colors={"#123456"})
        self.assertEqual([r for r in rep.warnings if "raw-color" in r], ["[raw-color] hard-coded colour #654321 without a theme variable"])


class Gallery(unittest.TestCase):
    def test_every_preset_fits_every_widget_in_every_language(self):
        for name in bw.gallery_sources():
            text = src(name[:-5])
            for lang in bw.source_languages(text):
                for preset in wd.PRESETS:
                    with self.subTest(widget=name, lang=lang, preset=preset):
                        res = bw.build_text(text, caption="x", strict=True, langs=(lang,), design=wd.apply_preset(preset))
                        self.assertEqual(res.errors, [])
                        self.assertLessEqual(res.compressed_bytes, 4096)

    def test_samples_keep_custom_buttons_out_of_the_primary_selector(self):
        # Rating stars are drawn by the widget: they carry a class so profiles leave them alone.
        self.assertIn('"s on" : "s"', src("rating-feedback"))
        for name in bw.gallery_sources():
            self.assertNotRegex(src(name[:-5]), r"button[^{]*\{[^}]*min-height:\s*36px",
                                "use var(--tg-button-height, 36px) so the profile's button height applies")


class Cli(unittest.TestCase):
    def test_build_with_design_file_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "design.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(wd.apply_preset("soft"), fh)
            out = os.path.join(tmp, "w.html")
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_widget.py"), os.path.join(bw.SRC_DIR, "quiz.html"),
                                "--design", path, "--strict", "--caption", "Quiz", "-o", out],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("--tg-button-radius:24px", fh.read())
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "widget_design.py"), "check", path],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
