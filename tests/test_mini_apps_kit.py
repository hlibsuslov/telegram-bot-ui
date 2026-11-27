"""Mini App kit, styles, lint and preview stand: offline, stdlib unittest."""
import contextlib
import io
import json
import os
import re
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import _paths
import miniapp_lint as lint
import miniapp_style as style
import preview_miniapp as preview

KIT = os.path.join(_paths.EXAMPLES, "mini-apps")
BAD = os.path.join(_paths.TESTS, "fixtures", "miniapp_lint", "bad")
REF = os.path.join(_paths.ROOT, "references", "mini-apps")


def lint_dir(path):
    files, root = lint.collect([path])
    return lint.lint_files(files, root)


class Lint(unittest.TestCase):
    def test_every_rule_fires_on_the_bad_app(self):
        found = {f.rule for f in lint_dir(BAD).findings}
        self.assertEqual(found, set(lint.RULES), f"missing: {sorted(set(lint.RULES) - found)}")

    def test_errors_are_the_security_and_native_rules(self):
        rep = lint_dir(BAD)
        self.assertEqual({f.rule for f in rep.errors}, {"MA01", "MA02", "MA03", "MA04", "MA25", "MA29", "MA33"})

    def test_kit_and_examples_are_clean(self):
        rep = lint_dir(KIT)
        self.assertEqual([f.text() for f in rep.findings], [])

    def test_lines_point_at_the_finding(self):
        rep = lint_dir(BAD)
        alert = next(f for f in rep.findings if f.rule == "MA03")
        with open(os.path.join(BAD, "index.html"), encoding="utf-8") as fh:
            self.assertIn("alert(", fh.read().splitlines()[alert.line - 1])

    def test_allowed_colours(self):
        css = ":root{--tma-fb-bg:#fff} a{color:var(--x,#123456)} b{color:light-dark(#000,#fff)} i{color:rgb(0 0 0 / .12)}"
        stray = [c for c in lint.COLOR.findall(lint._strip_allowed_colors(css)) if not lint._neutral(c)]
        self.assertEqual(stray, [])
        self.assertEqual(lint.COLOR.findall(lint._strip_allowed_colors("b{color:#ff0000}")), ["#ff0000"])

    def test_declared_confirm_is_not_a_dialog(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.ts")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("function confirm(m: string) { return tg.showConfirm(m); }\nconst ok = tma.confirm('x');\n")
            self.assertEqual([f.rule for f in lint.lint_files([p], d).findings if f.rule == "MA03"], [])

    def test_cli_json_and_strict(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lint.main([BAD, "--json"])
        self.assertEqual(code, 1)
        data = json.loads(buf.getvalue())
        self.assertTrue(data["errors"] and data["warnings"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lint.main([KIT, "--strict"]), 0)

    def test_anti_slop_documents_every_rule(self):
        with open(os.path.join(REF, "anti-slop.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("## Linter rules", text)
        for rule, (_, name) in lint.RULES.items():
            self.assertIn(f"| {rule} {name} |", text, rule)


class Styles(unittest.TestCase):
    data = style.load()

    def test_presets_match_the_kit(self):
        self.assertEqual(style.check_presets(self.data), [])
        self.assertEqual(set(self.data["presets"]), {"native", "fintech", "soft", "dense"})

    def test_every_preset_documents_intent_and_rules(self):
        for name, p in self.data["presets"].items():
            for key in ("title", "intent", "use_for", "components", "do", "dont"):
                self.assertTrue(p[key], f"{name}.{key}")

    def test_profile_scales_and_clamps(self):
        tokens, errors, warnings = style.resolve({"base": "soft", "radius": "round", "density": "roomy"}, self.data)
        self.assertEqual(errors, [])
        self.assertEqual(tokens["--tma-r-group"], "32px")  # 30 * 1.25 = 37.5 -> clamped
        self.assertTrue(any("clamped" in w for w in warnings))
        tokens, errors, _ = style.resolve({"base": "dense", "density": "compact"}, self.data)
        self.assertEqual(errors, [])
        self.assertEqual(tokens["--tma-row"], "44px")  # never below the touch target

    def test_brand_contrast_and_bad_input(self):
        _, errors, _ = style.resolve({"brand": {"light": "#ffd60a", "dark": "#ffd60a", "on": "#ffffff"}}, self.data)
        self.assertTrue(any("contrast" in e for e in errors))
        _, errors, _ = style.resolve({"base": "neon", "colors": {}}, self.data)
        self.assertTrue(any("unknown key" in e for e in errors) and any("not a preset" in e for e in errors))
        _, errors, _ = style.resolve({"figure": "1px;} body{display:none"}, self.data)
        self.assertTrue(errors)

    def test_css_output(self):
        css = style.css({"base": "fintech", "glass": False,
                         "brand": {"light": "#1f5fe0", "dark": "#2a63d4", "on": "#ffffff"}}, self.data)
        self.assertIn("--tma-avatar: 44px;", css)
        self.assertIn("--tma-brand: #1f5fe0;", css)
        self.assertIn('[data-tma-scheme="dark"] { --tma-brand: #2a63d4; --tma-on-brand: #ffffff; }', css)
        self.assertIn("backdrop-filter: none", css)
        self.assertEqual(re.findall(r"--[\w-]+:", style.css({"base": "native"}, self.data)), [])

    def test_design_system_explains_every_preset(self):
        with open(os.path.join(REF, "design-system.md"), encoding="utf-8") as fh:
            text = fh.read()
        for name in self.data["presets"]:
            self.assertIn(f"`{name}`", text)


class PreviewStand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = preview.make_handler(KIT, os.path.join("vanilla", "index.html"), "Coffee")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")

    def test_stand_and_mock(self):
        status, ctype, html = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("MOCK", html)
        self.assertIn('"app": "/app/vanilla/index.html"', html)
        _, ctype, js = self.get("/__tma__/mock.js")
        self.assertTrue(ctype.startswith("text/javascript"))
        self.assertIn('"WebApp.requestFullscreen": "8.0"', js)
        self.assertIn("WebAppMethodUnsupported", js)
        self.assertIn("cfg.invoice", js)  # the stand can return paid / cancelled / failed / pending

    def test_stand_page_and_its_assets(self):
        _, _, html = self.get("/")
        for ref in ('href="/__tma__/stand.css"', 'src="/__tma__/stand.js"', 'id="stand-config"'):
            self.assertIn(ref, html)
        config = json.loads(re.search(r'<script id="stand-config" type="application/json">(.*?)</script>', html, re.S)[1])
        self.assertEqual(config["title"], "Coffee")
        self.assertEqual(config["versions"][-1], "10.1")
        status, ctype, css = self.get("/__tma__/stand.css")
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/css"))
        self.assertIn(".workspace", css)
        _, ctype, js = self.get("/__tma__/stand.js")
        self.assertTrue(ctype.startswith("text/javascript"))
        for piece in ("themeChanged sent", "deactivated sent", "backButtonClicked", "closing confirmation asks first",
                      "ready() not called", "history.replaceState"):
            self.assertIn(piece, js)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/__tma__/stand.py")
        self.assertEqual(ctx.exception.code, 404)

    def test_mock_reports_what_the_panels_show(self):
        _, _, js = self.get("/__tma__/mock.js")
        for piece in ("post('net', { id: id, phase: 'start'", "phase: 'end'", "post('flags', { closingConfirmation: true })",
                      "post('storage'", "post('audit'", "post('ready', { ms: ms })", "log('error', 'unhandled rejection'",
                      "cfg.storage && cfg.storage[name]", "if ('invoice' in m.data) cfg.invoice = m.data.invoice;"):
            self.assertIn(piece, js)

    def test_app_html_gets_the_mock_instead_of_telegram_script(self):
        _, _, html = self.get("/app/vanilla/index.html")
        self.assertIn(preview.MOCK_TAG, html)
        self.assertNotIn("telegram.org/js/telegram-web-app.js", html)
        _, ctype, css = self.get("/app/_kit/tma.css")
        self.assertTrue(ctype.startswith("text/css"))

    def test_paths_cannot_escape_the_root(self):
        for bad in ("/app/../../SKILL.md", "/app/..%2F..%2FSKILL.md", "/app/%2e%2e/%2e%2e/SKILL.md"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.get(bad)
            self.assertEqual(ctx.exception.code, 404)
        self.assertIsNone(preview.safe_path(KIT, "../../SKILL.md"))
        self.assertIsNotNone(preview.safe_path(KIT, "vanilla/index.html"))

    def test_static_checks(self):
        with open(os.path.join(KIT, "vanilla", "index.html"), encoding="utf-8") as fh:
            self.assertEqual(preview.check_entry(fh.read()), [])
        with open(os.path.join(BAD, "index.html"), encoding="utf-8") as fh:
            problems = preview.check_entry(fh.read())
        self.assertTrue(any("before telegram-web-app.js" in p for p in problems))
        self.assertTrue(any("viewport" in p for p in problems))

    def test_themes_cover_both_platforms_and_schemes_with_every_key(self):
        keys = {r["key"] for r in _paths.load("data", "mini-apps", "theme-params.json")["params"]}
        self.assertEqual(set(preview.THEMES), {"ios-light", "ios-dark", "android-light", "android-dark"})
        for name, theme in preview.THEMES.items():
            self.assertEqual(set(theme), keys, name)


class KitFiles(unittest.TestCase):
    def test_kit_css_uses_only_theme_roles_for_colour(self):
        with open(os.path.join(KIT, "_kit", "tma.css"), encoding="utf-8") as fh:
            css = lint.COMMENT_CSS.sub("", fh.read())
        stray = [c for c in lint.COLOR.findall(lint._strip_allowed_colors(css)) if not lint._neutral(c)]
        self.assertEqual(stray, [])
        for var in ("--tg-theme-section-separator-color", "--tg-theme-bottom-bar-bg-color", "--tg-safe-area-inset-top",
                    "--tg-content-safe-area-inset-top", "--tg-viewport-stable-height", "prefers-reduced-motion",
                    "prefers-reduced-transparency", 'data-tma-perf="low"'):
            self.assertIn(var, css)

    def test_kit_roles_match_theme_params(self):
        with open(os.path.join(KIT, "_kit", "tma.css"), encoding="utf-8") as fh:
            css = fh.read()
        for row in _paths.load("data", "mini-apps", "theme-params.json")["params"]:
            if row["key"] == "header_bg_color":
                continue  # read-only hint: the app sets the header with setHeaderColor
            self.assertIn(row["css_var"], css, row["key"])
            self.assertIn(row["kit_var"] + ":", css, row["kit_var"])


class Catalogue(unittest.TestCase):
    """data/mini-apps/components.json, icons.json, the kit and the gallery stay in sync."""
    cat = _paths.load("data", "mini-apps", "components.json")
    icons = _paths.load("data", "mini-apps", "icons.json")

    @staticmethod
    def read(*parts):
        with open(os.path.join(KIT, *parts), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def tokens(selector):
        """Class names and attribute selectors a kit entry names (`.tma-cell.is-button`, `th[aria-sort]`)."""
        return re.findall(r"\.([a-z][\w-]*)", selector) + re.findall(r"\[([^\]=]+)", selector)

    def test_every_entry_is_complete(self):
        groups = set(self.cat["groups"])
        self.assertGreaterEqual(len(self.cat["components"]), 90)
        for key, c in self.cat["components"].items():
            self.assertIn(c["group"], groups, key)
            self.assertIn(c["status"], {"kit", "native", "pattern", "avoid"}, key)
            self.assertTrue(c["sources"], key)
            if c["status"] == "kit":
                self.assertTrue(c["kit"], key)
            if c["status"] == "native":
                self.assertTrue(c["native"], key)
            if c["status"] == "avoid":
                self.assertTrue(c["note"], f"{key}: an avoided element names its replacement")
        self.assertIn("Not read and not represented", self.cat["$comment"])  # unread kits are never claimed

    def test_kit_entries_exist_in_css_and_gallery(self):
        css = self.read("_kit", "tma.css")
        gallery = (self.read("gallery", "index.html") + self.read("gallery", "app.ts")
                   + self.read("catalog", "index.html") + self.read("catalog", "app.ts"))
        for key, c in self.cat["components"].items():
            if c["status"] != "kit":
                continue
            for token in self.tokens(c["kit"]):
                with self.subTest(component=key, token=token):
                    if token.startswith("tma-") or token.startswith("is-"):
                        self.assertTrue(token in css, "missing in tma.css")
                    self.assertTrue(token in gallery, "not shown in the gallery or catalogue example")

    def test_every_type_role_has_a_utility(self):
        css = self.read("_kit", "tma.css")
        for role in self.cat["typography"]["roles"]:
            self.assertIn(f".tma-text-{role} ", css, role)
        for level in range(1, 7):
            self.assertIn(f".tma-prose h{level} ", css)
            self.assertIn(f"<h{level}>", self.read("gallery", "index.html"))

    def test_icons_match_the_sprite_and_examples_use_known_ids(self):
        sprite = self.read("_kit", "icons.svg")
        ids = re.findall(r'<symbol id="i-([a-z-]+)"', sprite)
        self.assertEqual(sorted(ids), sorted(self.icons["icons"]))
        self.assertGreaterEqual(len(ids), 80)
        for name, row in self.icons["icons"].items():
            self.assertTrue(row["sf_symbol"] and row["material"] and row["use"], name)
        used = set(re.findall(r"icons\.svg#i-([a-z-]+)", self.read("gallery", "index.html")))
        self.assertTrue(used <= set(ids), sorted(used - set(ids)))

    def test_gallery_is_clean_and_built_like_the_others(self):
        rep = lint_dir(os.path.join(KIT, "gallery"))
        self.assertEqual([f.text() for f in rep.findings], [])
        self.assertIn("gallery/app.ts", self.read("build.mjs"))


if __name__ == "__main__":
    unittest.main()
