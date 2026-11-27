"""accessibility-and-language.md, the kit's locale and RTL pieces, the examples and lint MA38-MA39 agree."""
import glob
import os
import re
import tempfile
import unittest

import _paths
import miniapp_lint as lint

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
EX = os.path.join(_paths.ROOT, "examples", "mini-apps")
KIT = os.path.join(EX, "_kit")


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
    doc = read(REF, "accessibility-and-language.md")

    def test_sections(self):
        for n in range(0, 12):
            self.assertRegex(self.doc, rf"\n## {n}\. ")

    def test_cross_references_point_at_real_sections(self):
        for ref, num in re.findall(r"([a-z-]+) §(\d+)", self.doc):
            path = os.path.join(REF, ref + ".md")
            if os.path.exists(path):
                self.assertRegex(read(path), rf"\n## {num}\. ", f"{ref} §{num}")

    def test_lint_rules_named_exist(self):
        src = read(_paths.ROOT, "scripts", "miniapp_lint.py")
        for rule in set(re.findall(r"\bMA\d\d\b", self.doc)):
            self.assertIn(f'"{rule}"', src, rule)

    def test_kit_classes_named_exist(self):
        css = read(KIT, "tma.css")
        for cls in set(re.findall(r"`\.(tma-[a-z_-]+)", self.doc)):
            self.assertIn("." + cls, css, cls)

    def test_routed(self):
        for f in ("README.md", "orchestration.md", "rework.md"):
            self.assertIn("accessibility-and-language.md", read(REF, f), f)
        self.assertIn("references/mini-apps/accessibility-and-language.md", _paths.routing_text())


class Kit(unittest.TestCase):
    def test_locale_exported_and_rtl_rules(self):
        ts = read(KIT, "tma.ts")
        self.assertRegex(ts, r"function locale\(")
        self.assertRegex(ts, r"return \{[^}]*\blocale\b", "locale in the returned object")
        css = read(KIT, "tma.css")
        self.assertIn('[dir="rtl"] .tma-cell__chevron', css)
        self.assertIn(".tma-sr-only", css)
        self.assertNotRegex(css, r"\.tma-switch::after\s*\{[^}]*\bleft:", "the knob uses inset-inline-start")

    def test_stars_amounts_are_spoken(self):
        """Every Stars glyph in the examples sits next to hidden words, so screen readers hear "120 Stars"."""
        for path in glob.glob(os.path.join(EX, "*", "index.html")) + glob.glob(os.path.join(EX, "*", "app.ts")):
            text = read(path)
            glyphs = len(re.findall(r"tma-star['\"]", text))
            if glyphs:
                self.assertGreaterEqual(text.count("tma-sr-only"), glyphs if path.endswith(".html") else 1, path)

    def test_stand_has_rtl_languages(self):
        page = read(_paths.ROOT, "scripts", "preview_stand", "stand.html")
        for lang in ("ar", "he", "fa"):
            self.assertRegex(page, rf'<option value="{lang}">{lang} · \w+, right to left</option>')
        self.assertIn("language_code: lang", read(_paths.ROOT, "scripts", "preview_stand", "stand.js"))


class Lint(unittest.TestCase):
    HEAD = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"></head><body>'

    def test_ma38_icon_only_controls(self):
        self.assertIn("MA38", lint_text("a.html", self.HEAD + '<button><svg><use href="#i-x"/></svg></button></body></html>'))
        for ok in ('<button aria-label="Close"><svg aria-hidden="true"></svg></button>',
                   '<button><svg aria-hidden="true"></svg><span class="tma-sr-only">Close</span></button>',
                   '<button><svg></svg> Close</button>',
                   '<a href="/"><img src="logo.svg" alt="Home"></a>'):
            self.assertNotIn("MA38", lint_text("a.html", self.HEAD + ok + "</body></html>"), ok)

    def test_ma39_physical_sides(self):
        self.assertIn("MA39", lint_text("a.css", ".x { margin-left: 8px; }\n"))
        self.assertIn("MA39", lint_text("a.css", ".x { text-align: right; }\n"))
        for ok in (".x { margin-inline-start: 8px; text-align: start; }\n", ".x { scroll-margin-left: 4px; }\n", ".x { left: 50%; }\n"):
            self.assertNotIn("MA39", lint_text("a.css", ok), ok)

    def test_examples_clean(self):
        for app in ("gallery", "catalog", "portfolio", "vanilla", "rework", "react"):
            files = [p for p in glob.glob(os.path.join(EX, app, "**", "*"), recursive=True)
                     if os.path.splitext(p)[1] in (".html", ".css", ".ts", ".tsx") and "dist" not in p and "node_modules" not in p]
            rules = {f.rule for f in lint.lint_files(files, EX).findings}
            self.assertFalse(rules & {"MA38", "MA39"}, app)


if __name__ == "__main__":
    unittest.main()
