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
