"""Widget tooling: the build tool (kit inlining, languages, pruning, safe minify, size accounting,
forbidden APIs, payload shape), the strict lint, the validator CLI and the preview page."""
import json
import os
import subprocess
import sys
import unittest
import zlib

import _paths
import build_widget as bw
import preview_widget
import widget_lint

SCRIPTS = os.path.join(_paths.ROOT, "scripts")
KIT = '<style>/*@kit tokens.css*/</style><div class="k"><p class="mt">x</p><div class="st" id="st"></div></div>'


def page(script: str = "", extra: str = "") -> str:
    return KIT + extra + "<!--@kit runtime.js--><!--@kit i18n.js--><script>" + script + "</script>"


class Minify(unittest.TestCase):
    def test_js_literals_survive_byte_for_byte(self):
        src = ('var a = "x  //  y", b = \'/* no */\', c = `t ${1 + 2}  `;\n'
               'var re = /a\\/b [ ]+/g; // comment\nvar d = a / 2 / 3;\n/* block */ return');
        out = bw.minify_js(src)
        for lit in ('"x  //  y"', "'/* no */'", "`t ${1 + 2}  `", "/a\\/b [ ]+/g", "a / 2 / 3"):
            self.assertIn(lit, out)
        self.assertNotIn("comment", out)
        self.assertNotIn("block", out)

    def test_js_keeps_line_breaks_where_asi_matters(self):
        out = bw.minify_js("var a = 1\nvar b = a\n++b\nreturn\nx")
        self.assertIn("var b=a\n++b", out)
        self.assertIn("return\nx", out)

    def test_css_strings_and_descendant_selectors_survive(self):
        out = bw.minify_css('/* c */ .a :first-child { content: "a ;  b" ; margin : 0 }')
        self.assertIn('.a :first-child', out)
        self.assertIn('"a ;  b"', out)
        self.assertNotIn("/*", out)

    def test_minified_widget_still_compresses_like_the_server(self):
        res = bw.build_text(page(), caption="c")
        self.assertEqual(res.compressed_bytes, len(zlib.compress(res.html.encode("utf-8"), 9)))
        self.assertEqual(res.raw_bytes, len(res.html.encode("utf-8")))


class KitAndLanguages(unittest.TestCase):
    def test_kit_is_inlined_and_unused_kit_css_pruned(self):
        res = bw.build_text(page(), caption="c")
        self.assertTrue(res.ok, res.errors)
        self.assertIn("var K=", res.html)
        self.assertIn(".mt{", res.html)                 # used
        self.assertNotIn(".br>i", res.html)             # unused kit rule dropped
        self.assertNotIn("--k-warn", res.html)          # unused kit token dropped
        self.assertNotIn("@kit", res.html)

    def test_one_language_per_build(self):
        ru = bw.build_text(page(), caption="c", langs=("ru",))
        en = bw.build_text(page(), caption="c", langs=("en",))
        self.assertIn("Отправляю", ru.html)
        self.assertNotIn("Sending", ru.html)
        self.assertNotIn("Отправляю", en.html)
        with self.assertRaises(bw.BuildError):
            bw.select_languages("/*@lang en*/x/*@end*/", ("de",))

    def test_unknown_partial_is_an_error(self):
        self.assertFalse(bw.build_text("<!--@kit nope.js-->").ok)


class Gates(unittest.TestCase):
    def test_runtime_gaps_fail_the_build(self):
        for bad in ('<script>fetch("/x")</script>', "<input>", '<div style="height:100vh"></div>',
                    '<script src="https://cdn.example/x.js"></script>', '<img src="https://x/y.png">',
                    '<img src="data:image/svg+xml;base64,AA">', "<style>p{font-family:Helvetica}</style>"):
            with self.subTest(bad=bad):
                self.assertFalse(bw.build_text(bad, caption="c").ok)

    def test_strict_lint_rejects_raw_colours_but_allows_theme_paths(self):
        raw = bw.build_text('<style>body{margin:0;padding:0}p{color:#ff0000}</style><p>x</p>', caption="c", strict=True)
        self.assertTrue(any("raw-color" in e for e in raw.errors))
        ok = widget_lint.lint('<style>p{color:var(--tg-theme-text-color,#000);border-color:light-dark(#111,#eee);'
                              'background:rgba(128,128,128,.2)}</style>', caption="c")
        self.assertFalse([w for w in ok.warnings if "raw-color" in w])

    def test_lint_finds_double_band_and_missing_outcomes(self):
        rep = widget_lint.lint('<style>body{margin:0}.c{padding-bottom:env(safe-area-inset-bottom)}</style>'
                               '<script>var W=window.TelegramWidget;W.request("x")</script>', caption="c")
        text = " ".join(rep.warnings)
        self.assertIn("double-band", text)
        self.assertIn("request-errors", text)

    def test_budget_warning_above_3800(self):
        self.assertTrue(any("budget" in w for w in widget_lint.lint("<p>x</p>", caption="c", compressed=3900).warnings))


class Payloads(unittest.TestCase):
    def test_send_widget_payload(self):
        p = bw.payload("<p>x</p>", chat_id=1, caption="c", chat_data={"a": 1, "r": 0}, allow_queries=True,
                       shared=True, reply_markup={"inline_keyboard": [[{"text": "t", "callback_data": "d"}]]})
        self.assertEqual(p["method"], "sendWidget")
        self.assertEqual(p["params"]["chat_data"], '{"a":1,"r":0}')
        self.assertTrue(p["params"]["is_shared"] and p["params"]["allow_queries"])

    def test_send_shared_widget_payload_carries_no_code(self):
        p = bw.payload("<p>x</p>", chat_id=1, caption="c", widget_id="777", public_data={"x": 1}, chat_data={"u": 1})
        self.assertEqual(p["method"], "sendSharedWidget")
        self.assertNotIn("html", p["params"])
        self.assertNotIn("public_data", p["params"])     # belongs to the shared widget
        self.assertEqual(p["params"]["chat_data"], '{"u":1}')

    def test_state_over_1024_bytes_is_refused(self):
        with self.assertRaises(bw.BuildError):
            bw.payload("<p>x</p>", chat_id=1, caption="c", chat_data={"t": "я" * 600})

    def test_cli_writes_payload_from_demo(self):
        out = os.path.join(_paths.ROOT, "tests", "_tmp_payload.json")
        try:
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_widget.py"),
                                os.path.join(bw.SRC_DIR, "quiz.html"), "--strict", "--lang", "uk",
                                "--demo", os.path.join(bw.DEMO_DIR, "quiz.json"), "--payload", out],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout)
            with open(out, encoding="utf-8") as fh:
                req = json.load(fh)
            self.assertEqual(req["method"], "sendWidget")
            self.assertTrue(req["params"]["caption"] and req["params"]["reply_markup"])
        finally:
            if os.path.exists(out):
                os.remove(out)


class Gallery(unittest.TestCase):
    def test_every_source_builds_strict_in_every_language_within_budget(self):
        for name in bw.gallery_sources():
            with open(os.path.join(bw.SRC_DIR, name), encoding="utf-8") as fh:
                src = fh.read()
            demo = bw.load_demo(os.path.join(bw.DEMO_DIR, name[:-5] + ".json"))
            for lang in bw.source_languages(src):
                with self.subTest(widget=name, lang=lang):
                    res = bw.build_text(src, caption=demo["caption"], strict=True, langs=(lang,))
                    self.assertEqual(res.errors, [])
                    self.assertLessEqual(res.compressed_bytes, widget_lint.BUDGET)
                    self.assertIn(lang, ("en", "ru", "uk"))

    def test_built_files_match_sources(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_widget.py"), "--all", "--check"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_gallery_is_at_least_fourteen_widgets_with_demos(self):
        names = [n[:-5] for n in bw.gallery_sources()]
        self.assertGreaterEqual(len(names), 14)
        for n in names:
            self.assertTrue(os.path.exists(os.path.join(bw.DEMO_DIR, n + ".json")), n)
            self.assertTrue(os.path.exists(os.path.join(bw.OUT_DIR, n + ".html")), n)

    def test_validator_strict_cli_accepts_the_built_gallery(self):
        files = [os.path.join(bw.OUT_DIR, n) for n in bw.gallery_sources()]
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_widget.py"), *files,
                            "--caption", "c", "--strict", "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(r.stdout.strip().splitlines()), len(files))


class Preview(unittest.TestCase):
    def test_preview_page_is_labelled_a_mock_and_embeds_every_language(self):
        entry = preview_widget.gallery_entry(os.path.join(bw.OUT_DIR, "metrics-dashboard.html"), None)
        html = preview_widget.page([entry])
        self.assertIn("MOCK runtime", html)
        self.assertEqual(sorted(entry["html"]), ["en", "ru", "uk"])
        self.assertIn("sync", entry["answers"]["default"])       # precomputed by the real handler
        self.assertNotIn("</script><script>", html.split("var G =")[1][:50])


if __name__ == "__main__":
    unittest.main()
