"""Telegram's own elements in Mini Apps: the reference, catalogue, kit and lint rules MA28-MA29 agree."""
import os
import re
import tempfile
import unittest

import _paths
import miniapp_lint as lint

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
KIT = os.path.join(_paths.ROOT, "examples", "mini-apps")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def lint_text(name, text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return [f.rule for f in lint.lint_files([p], d).findings]


class Reference(unittest.TestCase):
    doc = read(REF, "telegram-elements.md")

    def test_every_element_has_a_section_and_the_index_lists_it(self):
        for n in range(1, 13):
            self.assertRegex(self.doc, rf"\n## T{n}\. ", f"T{n} section")
            self.assertRegex(self.doc, rf"\n\| T{n} \| ", f"T{n} index row")

    def test_catalogue_entries_point_at_the_reference(self):
        cat = _paths.load("data", "mini-apps", "components.json")
        tg = {k: c for k, c in cat["components"].items() if c["group"] == "telegram"}
        self.assertIn("telegram", cat["groups"])
        self.assertGreaterEqual(len(tg), 10)
        for key, c in tg.items():
            m = re.search(r"\(T(\d+)\)", c["note"])
            self.assertIsNotNone(m, key)
            self.assertIn(f"## T{m.group(1)}. ", self.doc, key)

    def test_kit_functions_named_in_the_reference_exist(self):
        ts = read(KIT, "_kit", "tg-values.ts")
        exported = set(re.findall(r"export function (\w+)", ts))
        named = set(re.findall(r"`(\w+)\(", self.doc)) & {
            "formatStars", "formatStarBalance", "starsText", "formatGrams", "gramsText", "toNanograms",
            "rarityPercent", "rarityTier", "giftVars", "giftNameColor", "limitedLeft"}
        self.assertTrue(named)
        self.assertLessEqual(named, exported)

    def test_routes_link_the_reference(self):
        self.assertIn("telegram-elements.md", read(REF, "README.md"))
        self.assertIn("telegram-elements.md", read(_paths.ROOT, "SKILL.md"))

    def test_star_colour_is_a_fallback_token_in_every_scheme(self):
        css = read(KIT, "_kit", "tma.css")
        self.assertEqual(len(re.findall(r"--tma-fb-star:", css)), 3)  # light, dark attribute, dark media query
        self.assertIn("--tma-star: var(--tma-fb-star)", css)
        self.assertIn('<symbol id="i-stars"', read(KIT, "_kit", "icons.svg"))


class LintRules(unittest.TestCase):
    def test_currency_names_users_should_not_see(self):
        page = '<!doctype html><html><head><meta name="viewport" content="x"></head><body><p>{}</p></body></html>'
        for shown in ("Balance: 12.5 TON", "Pay 250 XTR", "Top up with Toncoin"):
            self.assertIn("MA28", lint_text("a.html", page.format(shown)), shown)
        for fine in ("Grams (formerly Toncoin)", "Address on the TON blockchain", "Users never see the code XTR"):
            self.assertNotIn("MA28", lint_text("a.html", page.format(fine)), fine)
        self.assertIn("MA28", lint_text("a.ts", "const t = `Pay ${n} XTR`;\n"))
        self.assertNotIn("MA28", lint_text("a.ts", "if (inv.currency === 'XTR') show();\n"))

    def test_own_trust_marks(self):
        for bad in ('<span class="name verified-badge"></span>', '<i aria-label="Verified"></i>',
                    '<img src="x.svg" alt="" class="premium-mark">'):
            self.assertIn("MA29", lint_text("a.html", bad), bad)
        self.assertIn("MA29", lint_text("a.ts", "el.className = 'premium-badge';\n"))
        for fine in ('<p class="verified-at">Checked today</p>', '<span class="tma-gift__flag">Premium</span>'):
            self.assertNotIn("MA29", lint_text("a.html", fine), fine)
        self.assertEqual(lint.RULES["MA29"][0], "error")

    def test_own_back_button_in_markup(self):
        self.assertIn("MA19", lint_text("a.html", '<button class="btn-back" type="button">Back</button>'))

    def test_no_control_characters_in_the_linter(self):
        self.assertIsNone(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", read(_paths.ROOT, "scripts", "miniapp_lint.py")))


if __name__ == "__main__":
    unittest.main()


class StricterVisualRules(unittest.TestCase):
    """No emoji in the interface, SVG icons from the kit or Lucide, one surface level, palettes from the HIG."""

    def test_no_emoji_in_markup_or_ui_strings(self):
        page = '<!doctype html><html><head><meta name="viewport" content="x"></head><body>{}</body></html>'
        for bad in ("<p>Saved ✅</p>", "<li>🔥 Popular</li>", '<span class="tma-price">⭐ 250</span>', "<small>★ 4.8</small>"):
            self.assertIn("MA13", lint_text("a.html", page.format(bad)), bad)
        self.assertIn("MA13", lint_text("a.ts", "el.textContent = `Booked 🎉`;\n"))
        self.assertIn("MA13", lint_text("a.ts", "h('span', {}, `⭐ ${price}`);\n"))
        for fine in ("tma.mainButton({ text: `Pay ⭐ ${n}`, onClick });\n", "tg.showAlert('Pay ⭐ 120?');\n"):
            self.assertNotIn("MA13", lint_text("a.ts", fine), fine)
        self.assertNotIn("MA13", lint_text("a.html", page.format("<!-- ⭐ in a comment --><p>Saved</p>")))

    def test_every_kit_icon_has_a_lucide_name_and_libraries_are_open(self):
        icons = _paths.load("data", "mini-apps", "icons.json")
        for name, row in icons["icons"].items():
            self.assertRegex(row.get("lucide", ""), r"^[a-z0-9]+(-[a-z0-9]+)*$", name)
        libs = icons["open_libraries"]
        self.assertEqual(libs["order"][0], "lucide")
        for lib in libs["order"]:
            self.assertIn(libs[lib]["licence"], {"ISC", "MIT", "Apache-2.0"}, lib)
        self.assertTrue(any("emoji" in n for n in libs["never"]))

    def test_nested_surfaces(self):
        self.assertIn("MA35", lint_text("a.html", '<div class="tma-card"><ul class="tma-list"><li>x</li></ul></div>'))
        self.assertIn("MA35", lint_text("a.html", '<div class="stat-card"><div class="stat-card-inner">1</div></div>'))
        self.assertNotIn("MA35", lint_text("a.html", '<section class="tma-section"><ul class="tma-list"><li>x</li></ul></section>'
                                                     '<div class="tma-card"><p>text</p></div>'))

    def test_named_palettes_pass_contrast_in_both_schemes(self):
        import miniapp_style as style
        pal = _paths.load("data", "mini-apps", "palettes.json")
        self.assertIn("human-interface-guidelines/color", pal["source"])
        self.assertEqual(len(pal["system"]), 12)
        for name in pal["system"]:
            b = style.palette_brand(name)
            self.assertGreaterEqual(style.contrast(b["light"], b["on"]), 4.5, name)
            self.assertGreaterEqual(style.contrast(b["dark"], b["on_dark"]), 4.5, name)
        for product, names in pal["by_product"].items():
            if not product.startswith("$"):
                self.assertLessEqual(set(names), set(pal["system"]), product)
        css = style.css({"base": "native", "brand": "teal"}, style.load())
        self.assertIn("--tma-brand: #008198", css)
        self.assertIn('[data-tma-scheme="dark"] { --tma-brand: #00d2e0; --tma-on-brand: #000000; }', css)
        _, errors, _ = style.resolve({"brand": "neon"}, style.load())
        self.assertTrue(errors)


class StarsLook(unittest.TestCase):
    def test_pill_sparkles_stop_without_motion_and_text_contrast(self):
        import miniapp_style as style
        css = read(KIT, "_kit", "tma.css")
        self.assertIn(".tma-stars-pill", css)
        self.assertRegex(css, r"prefers-reduced-motion: reduce\) \{ \.tma-sparkles > i \{ animation: none; opacity: \.5; \}")
        self.assertIn('[data-tma-perf="low"] .tma-sparkles > i', css)
        light = re.search(r"--tma-fb-star-text: (#[0-9a-f]{6})", css).group(1)
        self.assertGreaterEqual(style.contrast(light, "#fdf0d4"), 4.5)
        self.assertIn('<symbol id="i-stars-gold"', read(KIT, "_kit", "icons.svg"))

    def test_original_star_is_fetched_only_with_consent(self):
        import contextlib
        import io
        import fetch_telegram_star as fetch
        self.assertRegex(fetch.COMMIT, r"^[0-9a-f]{40}$")
        for sha in fetch.FILES.values():
            self.assertRegex(sha, r"^[0-9a-f]{64}$")
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fetch.main(["--out", d]), 2)
            self.assertEqual(os.listdir(d), [])
        self.assertIn("GPL-3.0", read(REF, "telegram-elements.md"))
