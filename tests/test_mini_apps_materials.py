"""materials-and-trends.md, the kit's glass tokens, design-sources.json web_materials and lint MA42-MA44 agree."""
import os
import re
import tempfile
import unittest

import _paths
import miniapp_lint as lint

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
CSS = os.path.join(_paths.ROOT, "examples", "mini-apps", "_kit", "tma.css")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def lint_text(name, text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return [f.rule for f in lint.lint_files([p], d).findings]


class Glass(unittest.TestCase):
    css = read(CSS)
    data = _paths.load("data", "mini-apps", "design-sources.json")["web_materials"]

    def test_tokens_match_the_data(self):
        """Change the material in one place: the regular level's tokens and each level's overrides equal the data."""
        reg = self.data["levels"]["regular"]
        self.assertIn(f"--tma-glass-tint: {reg['tint_pct']}%;", self.css)
        self.assertIn(f"--tma-glass-blur: {reg['blur_px']}px;", self.css)
        self.assertIn(f"--tma-glass-saturate: {reg['saturate']};", self.css)
        for level in ("thin", "thick"):
            v = self.data["levels"][level]
            rule = re.search(rf"\.tma-glass\.is-{level} \{{([^}}]*)\}}", self.css)
            self.assertTrue(rule, level)
            self.assertIn(f"--tma-glass-tint: {v['tint_pct']}%", rule.group(1))
            self.assertIn(f"--tma-glass-blur: {v['blur_px']}px", rule.group(1))

    def test_one_class_reads_the_tokens(self):
        body = re.search(r"\n\.tma-glass \{([^}]*)\}", self.css).group(1)
        for token in ("--tma-glass-tint", "--tma-glass-blur", "--tma-glass-saturate", "--tma-glass-rim", "--tma-glass-lift"):
            self.assertIn(f"var({token}", body)
        self.assertNotRegex(body, r"blur\(\d", "no literal blur in the component")

    def test_every_solid_case_has_a_rule(self):
        for needle in ("prefers-reduced-transparency: reduce", "prefers-contrast: more", "@supports not ((backdrop-filter",
                       '[data-tma-perf="low"] .tma-glass', '[data-tma-glass="off"] .tma-glass', '[data-tma-style="dense"] .tma-glass'):
            self.assertIn(needle, self.css)
        self.assertEqual(len(self.data["solid_when"]), 6)

    def test_kit_reads_iOS_frost_values(self):
        frost = _paths.load("data", "mini-apps", "design-sources.json")["ios27"]["liquid_glass"]["figma_effect"]
        self.assertEqual(self.data["levels"]["thin"]["blur_px"], frost["frost_regular"])
        self.assertEqual(self.data["levels"]["regular"]["blur_px"], frost["frost_medium_large"])


class Reference(unittest.TestCase):
    doc = read(REF, "materials-and-trends.md")

    def test_sections(self):
        for n in range(0, 8):
            self.assertRegex(self.doc, rf"\n## {n}\. ")

    def test_radar_rows_have_a_decision(self):
        rows = re.findall(r"^\| ([^|]+) \| (adopt|adapt|avoid)[^|]* \|", self.doc, re.M)
        self.assertGreaterEqual(len(rows), 12)

    def test_kit_names_exist(self):
        css = read(CSS)
        for cls in set(re.findall(r"`\.(tma-[a-z-]+)", self.doc)):
            self.assertIn("." + cls, css, cls)
        for token in set(re.findall(r"(--tma-glass-[a-z-]+)", self.doc)):
            if not token.endswith("-"):
                self.assertIn(token, css, token)

    def test_routed(self):
        for f in ("README.md", "orchestration.md", "design-sources.md", "anti-slop.md"):
            self.assertIn("materials-and-trends.md", read(REF, f), f)
        self.assertIn("references/mini-apps/materials-and-trends.md", _paths.routing_text())


class Lint(unittest.TestCase):
    def test_ma42_side_stripe(self):
        self.assertIn("MA42", lint_text("a.css", ".alert-card { border-left: 3px solid var(--tma-danger); }\n"))
        self.assertNotIn("MA42", lint_text("a.css", ".alert-card { border-left: 1px solid var(--tma-separator); }\n"))
        self.assertNotIn("MA42", lint_text("a.css", "blockquote.quote { border-inline-start: 2px solid var(--tma-accent); }\n"))

    def test_ma43_hard_shadow(self):
        self.assertIn("MA43", lint_text("a.css", ".x { box-shadow: 4px 4px 0 var(--tma-text); }\n"))
        for ok in (".x { box-shadow: 0 8px 24px rgb(0 0 0 / .14); }\n", ".x { box-shadow: inset 0 1px 0 rgb(255 255 255 / .3); }\n",
                   ".x { box-shadow: 0 0 0 2px var(--tma-accent); }\n"):
            self.assertNotIn("MA43", lint_text("a.css", ok), ok)

    def test_ma44_eyebrow(self):
        self.assertIn("MA44", lint_text("a.html", '<p class="eyebrow">New</p><h1>Plans</h1>'))
        self.assertNotIn("MA44", lint_text("a.html", '<h1>Plans</h1>'))


if __name__ == "__main__":
    unittest.main()
