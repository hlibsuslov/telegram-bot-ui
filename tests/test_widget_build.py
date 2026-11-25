"""Widget tooling: the build tool (kit inlining, languages, pruning, safe minify, size accounting,
forbidden APIs, payload shape), the strict lint, the validator CLI and the preview page."""
import http.client
import json
import os
import shutil
import subprocess
import sys
import threading
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
                    '<img src="data:image/svg+xml;base64,AA">', "<style>p{font-family:Helvetica}</style>",
                    "<script>c.getImageData(0,0,1,1)</script>", "<script>c.shadowBlur=4</script>",
                    "<script>c.globalCompositeOperation='xor'</script>", '<svg><clipPath id="a"/></svg>',
                    '<svg><animate attributeName="x"/></svg>', "<style>p{margin-inline-start:4px}</style>",
                    "<style>p{columns:2}</style>", "<style>p{display:contents}</style>",
                    "<style>p{background-clip:text}</style>", "<datalist></datalist>", "<ruby>a</ruby>",
                    "<center>x</center>", "<font>x</font>", '<div tabindex="0">x</div>',
                    "<div contenteditable>x</div>", '<table border="1"></table>', '<p align="center">x</p>',
                    "<div popover>x</div>", '<img src="data:image/avif;base64,AA">'):
            with self.subTest(bad=bad):
                self.assertFalse(bw.build_text(bad, caption="c").ok)

    def test_runtime_gaps_leave_allowed_lookalikes_alone(self):
        for good in ("<style>.g{display:grid;grid-template-columns:1fr 1fr}</style>",
                     "<style>p{margin-left:4px;border-radius:3px}</style>", '<img src="data:image/png;base64,AA">',
                     "<script>c.arc(5,5,4,0,Math.PI*2)</script>", "<strong>a</strong><footer>b</footer>",
                     '<table><tr><td colspan="2">x</td></tr></table>', "<button disabled>x</button>",
                     '<svg><stop stop-color="#000"/></svg>', "<style>button:disabled{color:var(--k-hint)}</style>"):
            with self.subTest(good=good):
                self.assertTrue(bw.build_text(good, caption="c").ok, bw.build_text(good, caption="c").errors)

    def test_lint_warns_on_tap_request_innerhtml_state_and_canvas_arc(self):
        cases = {
            "tap-request": 'el.addEventListener("pointerdown", function () { W.request("x") })',
            "innerhtml-state": "box.innerHTML = W.chatData",
            "canvas-arc": "c.rect(0,0,9,9);c.arc(4,4,3,0,7,true)",
        }
        for rule, js in cases.items():
            with self.subTest(rule=rule):
                rep = widget_lint.lint("<script>var W=window.TelegramWidget;" + js + "</script>", caption="c")
                self.assertTrue(any(rule in w for w in rep.warnings), rep.warnings)
        clean = widget_lint.lint('<script>var W=window.TelegramWidget;b.onclick=function(){W.request("x")};'
                                 "n.textContent=W.chatData;c.moveTo(7,4);c.arc(4,4,3,0,Math.PI*2)</script>",
                                 caption="c")
        for rule in cases:
            self.assertFalse([w for w in clean.warnings if rule in w])

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


KIT_ASK_THROW = r"""
const fs = require("fs"), vm = require("vm");
const calls = [];
let mode = "throw";
const W = { viewer: { id: 1 }, isPreview: false, chatType: "private",
  request(d) { calls.push(d); if (mode == "throw") throw new TypeError("data must be 1-64 bytes");
               return Promise.resolve({ result: '{"ok":true}' }); } };
const ctx = vm.createContext({ window: { TelegramWidget: W }, navigator: { language: "en" },
  document: { getElementById: () => null, documentElement: {} }, Promise, JSON, Object, String });
vm.runInContext(fs.readFileSync(process.argv[process.argv.length - 1], "utf8"), ctx);
const K = ctx.K; K.draw = () => {};
let failed = null;
K.ask("x".repeat(65), { fail: e => { failed = e; } });
setTimeout(() => {
  mode = "ok";
  const second = K.ask("ok");
  console.log(JSON.stringify({ failed: failed && failed.name, busyAfterThrow: K.busy, second, calls }));
}, 10);
"""


class KitRuntime(unittest.TestCase):
    def test_synchronous_throw_from_request_does_not_lock_the_widget(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        runtime = os.path.join(_paths.EXAMPLES, "widgets", "_kit", "runtime.js")
        r = subprocess.run([node, "-e", KIT_ASK_THROW, "--", runtime], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["failed"], "TypeError")      # the throw reached the fail handler
        self.assertEqual(out["second"], 1)                 # the next tap asks again
        self.assertEqual(out["calls"], ["x" * 65, "ok"])


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
        out = os.path.join(_paths.TESTS, "_tmp_payload.json")
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


class PreviewMessages(unittest.TestCase):
    """The preview page acts only on messages from the iframe it registered, and the mock runtime
    inside the iframe only on messages from its parent page: any other window can postMessage."""

    PARENT = 'addEventListener("message", function(e){ var m = e.data||{}, fr = frames[m.f];'
    CHILD = 'addEventListener("message", function(e){'

    @staticmethod
    def listener(html, start):
        at = html.index(start)
        return html[at:html.index("});", html.index("log(m.t", at) if "frames" in start else at) + 3]

    def run_node(self, script):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not on PATH")
        r = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return json.loads(r.stdout)

    def test_page_ignores_messages_from_other_windows(self):
        html = preview_widget.page([], serve=True)
        listener = self.listener(html, self.PARENT)
        script = (
            "var got = [], handler; function addEventListener(t, f){ handler = f; }"
            "function answer(fr, m){ got.push('req'); } function setH(){ got.push('size'); } function log(){ got.push('log'); }"
            "var own = {}, frames = {f1: {ifr: {contentWindow: own}, w: 320}};"
            + listener +
            "handler({source: {}, data: {k: 'req', f: 'f1', data: 'x'}});"
            "handler({source: null, data: {k: 'log', f: 'f1', t: 'info', m: 'x'}});"
            "var foreign = got.length;"
            "handler({source: own, data: {k: 'req', f: 'f1', data: 'x'}});"
            "console.log(JSON.stringify([foreign, got]));")
        self.assertEqual(self.run_node(script), [0, ["req"]])

    def test_mock_runtime_ignores_messages_from_other_windows(self):
        listener = self.listener(preview_widget.MOCK_JS, self.CHILD)
        script = (
            "var got = [], handler, P = {}; function addEventListener(t, f){ handler = f; }"
            "var W = {__answer: function(){ got.push('ans'); }, __push: function(){ got.push('push'); }};"
            "function fire(){ got.push('theme'); }"
            + listener +
            "handler({source: {}, data: {k: 'ans', id: 1}}); handler({source: {}, data: {k: 'push'}});"
            "var foreign = got.length; handler({source: P, data: {k: 'ans', id: 1}});"
            "console.log(JSON.stringify([foreign, got]));")
        self.assertEqual(self.run_node(script), [0, ["ans"]])


class PreviewServe(unittest.TestCase):
    """L4: `--serve` answers only its own page: loopback Host, same-origin JSON POST, bounded body."""

    @classmethod
    def setUpClass(cls):
        entry = preview_widget.gallery_entry(os.path.join(bw.OUT_DIR, "metrics-dashboard.html"), None)
        cls.srv = preview_widget.make_server([entry], 0)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def request(self, method, body=b"", host=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest(method, "/q" if method == "POST" else "/", skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{self.port}")
        for name, value in headers.items():
            conn.putheader(name.replace("_", "-"), value)
        if "Content_Length" not in headers:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body or None)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, data

    def post(self, doc, **headers):
        headers.setdefault("Origin", f"http://127.0.0.1:{self.port}")
        headers.setdefault("Content_Type", "application/json")
        return self.request("POST", json.dumps(doc).encode(), **headers)

    def ask(self):
        return {"widget": "metrics-dashboard", "data": "sync", "frame": "f0", "state": "default"}

    def test_own_page_and_query_are_answered(self):
        self.assertEqual(self.request("GET")[0], 200)
        self.assertEqual(self.request("GET", host=f"localhost:{self.port}")[0], 200)
        status, data = self.post(self.ask())
        self.assertEqual(status, 200)
        self.assertIn("result", json.loads(data))

    def test_foreign_host_is_refused(self):
        """DNS rebinding: a page on evil.example resolved to 127.0.0.1 sends its own Host."""
        self.assertEqual(self.request("GET", host=f"evil.example:{self.port}")[0], 421)
        self.assertEqual(self.post(self.ask(), host=f"evil.example:{self.port}")[0], 421)

    def test_cross_origin_post_is_refused(self):
        self.assertEqual(self.post(self.ask(), Origin="http://evil.example")[0], 403)
        self.assertEqual(self.post(self.ask(), Origin="null")[0], 403)
        no_origin = {"Content_Type": "application/json"}
        self.assertEqual(self.request("POST", json.dumps(self.ask()).encode(), **no_origin)[0], 403)

    def test_simple_text_plain_post_is_refused(self):
        """A form or `fetch(no-cors)` from another page can only send text/plain without a preflight."""
        self.assertEqual(self.post(self.ask(), Content_Type="text/plain;charset=UTF-8")[0], 415)

    def test_oversized_or_malformed_body_is_refused(self):
        too_big = preview_widget.MAX_BODY + 1
        self.assertEqual(self.request("POST", Origin=f"http://127.0.0.1:{self.port}",
                                      Content_Type="application/json", Content_Length=str(too_big))[0], 413)
        self.assertEqual(self.request("POST", b"{not json", Origin=f"http://127.0.0.1:{self.port}",
                                      Content_Type="application/json")[0], 400)
        self.assertEqual(self.post(["sync"])[0], 400)
        self.assertEqual(self.post({"widget": "metrics-dashboard"})[0], 400)

    def test_live_bots_are_capped(self):
        entry = preview_widget.gallery_entry(os.path.join(bw.OUT_DIR, "metrics-dashboard.html"), None)
        live = preview_widget._Live([entry])
        for n in range(preview_widget.MAX_LIVE_BOTS + 20):
            live.ask(dict(self.ask(), frame=f"f{n}"))
        self.assertLessEqual(len(live.bots), preview_widget.MAX_LIVE_BOTS)

    def test_page_posts_json(self):
        html = preview_widget.page([], serve=True)
        self.assertIn('headers:{"Content-Type":"application/json"}', html)


if __name__ == "__main__":
    unittest.main()
