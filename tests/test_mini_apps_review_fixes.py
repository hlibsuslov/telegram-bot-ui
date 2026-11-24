"""Regression tests for the P5 review findings (code review, security audit, Codex security review)."""
import http.client
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

import _paths
import miniapp_lint as lint
import miniapp_style as style
import preview_miniapp as preview

sys.path.insert(0, os.path.join(_paths.EXAMPLES, "mini-apps", "bot"))
sys.path.insert(0, os.path.join(_paths.EXAMPLES, "mini-apps", "server", "python"))
from bot_side import MiniAppBot, parse_start_param  # noqa: E402
import verify_init_data as v  # noqa: E402
from tgkit.transport import FakeTransport  # noqa: E402

KIT = os.path.join(_paths.EXAMPLES, "mini-apps")


def write(folder, rel, text):
    path = os.path.join(folder, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class LintFixes(unittest.TestCase):
    def test_project_under_an_api_folder_is_still_client_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "api", "app")
            p = write(root, "main.js", "Telegram.WebApp.ready(); alert('hi'); localStorage.x = 1;\n")
            rules = {f.rule for f in lint.lint_files([p], root).findings}
            self.assertTrue({"MA03", "MA14"} <= rules, rules)

    def test_ready_in_the_kit_does_not_satisfy_the_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = write(tmp, "_kit/tma.ts", "export function createTma(){ return { ready(){ tg.ready(); } } }\n")
            app = write(tmp, "app/app.ts", "import { createTma } from '../_kit/tma.ts'; const tma = createTma();\n")
            rules = {f.rule for f in lint.lint_files([kit, app], tmp).findings}
            self.assertIn("MA18", rules)

    def test_id_selectors_are_not_colours(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "s.css", "#add, #face { padding: 4px; } a { color: #ff0000; }\n")
            colours = [f.msg for f in lint.lint_files([p], tmp).findings if f.rule == "MA05"]
            self.assertEqual(len(colours), 1)
            self.assertIn("#ff0000", colours[0])


class PreviewFixes(unittest.TestCase):
    def test_paths_with_drives_backslashes_nul_unc_and_dotfiles_are_refused(self):
        for bad in ("C:/Windows/win.ini", "..\\..\\x", "a\x00b", "//server/share/x", ".env", "vanilla/.git/config",
                    "%2e%2e/x", "a%5c..%5c..%5cx"):
            with self.subTest(path=bad):
                self.assertIsNone(preview.safe_path(KIT, bad))
        self.assertIsNotNone(preview.safe_path(KIT, "vanilla/index.html"))

    def test_foreign_host_header_is_refused(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), preview.make_handler(KIT, os.path.join("vanilla", "index.html"), "<b>x</b>"))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            for host, code in ((f"127.0.0.1:{port}", 200), (f"localhost:{port}", 200), ("attacker.example", 403)):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/", headers={"Host": host})
                res = conn.getresponse()
                body = res.read().decode()
                self.assertEqual(res.status, code, host)
                if code == 200:
                    self.assertNotIn("<b>x</b>", body)  # the app title is escaped before it reaches the page
                conn.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_default_root_is_narrow_outside_kit_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "secret.txt", "x")
            entry = write(tmp, "app/index.html", "<html><head><meta name=viewport></head></html>")
            self.assertTrue(os.path.isfile(entry))
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()) as out:
                preview.main([os.path.dirname(entry), "--check"])
            self.assertIn(os.path.join(tmp, "app"), out.getvalue())


class BotSideFixes(unittest.TestCase):
    def test_extra_cannot_redirect_the_message(self):
        t = FakeTransport()
        b = MiniAppBot(t, bot_username="b", app_url="https://x.example.com")
        b.write_allowed.add(1)
        with self.assertRaises(ValueError):
            b.notify(1, "hi", chat_id=2)
        self.assertTrue(b.notify(1, "hi", disable_notification=True))
        self.assertEqual(t.calls[-1][1]["chat_id"], 1)

    def test_failed_answer_does_not_burn_the_query(self):
        class Failing(FakeTransport):
            def call(self, method, params):
                raise RuntimeError("network")
        b = MiniAppBot(Failing(), bot_username="b", app_url="https://x.example.com")
        with self.assertRaises(RuntimeError):
            b.answer_query_once("q1", {})
        self.assertNotIn("q1", b.answered_queries)

    def test_web_app_data_must_be_a_shallow_object(self):
        t = FakeTransport()
        b = MiniAppBot(t, bot_username="b", app_url="https://x.example.com")
        for data in ("[1,2]", "\"text\"", "[" * 3000 + "]" * 3000):
            self.assertIsNone(b.on_web_app_data({"chat": {"id": 1}, "web_app_data": {"data": data}}, lambda d: d))

    def test_trailing_newline_start_param(self):
        import re
        self.assertIsNone(parse_start_param("order-1\n", {"o": re.compile(r"^order-\d+$")}))


class VerifierFixes(unittest.TestCase):
    def test_identity_public_key_is_refused(self):
        identity = (1).to_bytes(32, "little")  # y = 1, x = 0
        self.assertFalse(v.ed25519_verify(identity, b"msg", identity + (0).to_bytes(32, "little")))

    def test_query_grammar(self):
        for raw in ("?auth_date=1&hash=" + "a" * 64, "auth_date=1&flag&hash=" + "a" * 64):
            with self.assertRaises(v.InitDataError):
                v.verify_hmac(raw, "12345:X")


class StyleFixes(unittest.TestCase):
    def test_dense_profile_carries_the_android_list_rule(self):
        css = style.css({"base": "dense"}, style.load())
        self.assertIn('[data-tma-platform="android"] .tma-list', css)


if __name__ == "__main__":
    unittest.main()
