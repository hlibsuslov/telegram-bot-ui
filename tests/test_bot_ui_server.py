"""bot-ui Studio server: loopback only, Host/Origin/token checks, one write path."""
from __future__ import annotations

import http.client
import json
import threading
import unittest

from _bot_ui import ProjectCase
from bot_ui.project import open_snapshot
from bot_ui.server import serve


class Server(ProjectCase):
    def setUp(self):
        super().setUp()
        ready, self.holder = threading.Event(), {}
        self.thread = threading.Thread(target=serve, args=(self.root,), daemon=True,
                                       kwargs={"port": 0, "ready": ready, "holder": self.holder, "quiet": True})
        self.thread.start()
        ready.wait(10)
        self.port = self.holder["studio"].port
        self.token = self.holder["studio"].token

    def tearDown(self):
        self.holder["server"].shutdown()
        self.thread.join(5)
        super().tearDown()

    def req(self, method, path, body=None, *, host=None, origin="ok", token="ok", ctype="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if origin == "ok":
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        elif origin is not None:
            headers["Origin"] = origin
        if token == "ok":
            headers["X-Bot-UI-Token"] = self.token
        elif token is not None:
            headers["X-Bot-UI-Token"] = token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = ctype
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = raw.decode("utf-8", "replace")
        return r.status, doc, dict(r.getheaders())

    def test_foreign_host_origin_token_and_content_type_are_refused(self):
        self.assertEqual(self.req("GET", "/", host="evil.example:80")[0], 421)
        self.assertEqual(self.req("POST", "/api/project", {}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.req("POST", "/api/project", {}, origin="null")[0], 403)  # sandboxed preview frame
        self.assertEqual(self.req("POST", "/api/project", {}, origin=None)[0], 403)
        self.assertEqual(self.req("POST", "/api/project", {}, token="guess")[0], 403)
        self.assertEqual(self.req("POST", "/api/project", {}, ctype="text/plain")[0], 415)
        self.assertEqual(self.req("GET", "/api/project")[0], 405)
        self.assertEqual(self.req("GET", "/../../project.json")[0], 404)

    def test_project_document_has_no_tokens_and_validate_does_not_write(self):
        status, doc, _ = self.req("POST", "/api/project", {})
        self.assertEqual(status, 200)
        self.assertIn("checkout.payment.confirm", doc["screens"])
        self.assertNotIn(self.token, json.dumps(doc))
        rev = doc["revision"]
        draft = dict(doc["screens"]["orders.status"])
        draft["actions"] = dict(draft["actions"], route=dict(draft["actions"]["route"], rule=dict(
            draft["actions"]["route"]["rule"], match="")))
        status, val, _ = self.req("POST", "/api/validate", {"screens": {"orders.status": draft}})
        self.assertIn("TARGET_EMPTY", [d["code"] for d in val["diagnostics"]])
        self.assertEqual(open_snapshot(self.root).revision, rev)

    def test_save_then_conflict_keeps_the_newer_version(self):
        rev = self.req("POST", "/api/revision", {})[1]["revision"]
        patch = {"format": "bot-ui-patch/v1", "projectId": "demo-shop", "baseRevision": rev, "changes": [
            {"screenId": "checkout.payment.confirm", "ops": [
                {"op": "set", "path": "/message/text/ru", "value": "<b>Подтвердите #{order.no}</b> {order.total} {order.note}"}]}]}
        status, res, _ = self.req("POST", "/api/save", {"patch": patch})
        self.assertEqual(status, 200, res)
        self.assertEqual(res["changedFiles"], ["screens/checkout.payment.confirm.json"])
        patch["changes"][0]["ops"][0]["value"] = "old base"
        status, res, _ = self.req("POST", "/api/save", {"patch": patch})
        self.assertEqual(status, 409)
        self.assertEqual(res["error"]["code"], "REVISION_CONFLICT")
        self.assertEqual(res["patch"]["changes"][0]["ops"][0]["value"], "old base", "the draft comes back")

    def test_git_status_lists_saved_but_uncommitted_screens(self):
        import subprocess
        status, doc, _ = self.req("POST", "/api/git-status", {})
        self.assertEqual((status, doc["git"]), (200, False))
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(git + ["init", "-q"], cwd=self._tmp, check=True)
        subprocess.run(git + ["add", "-A"], cwd=self._tmp, check=True)
        subprocess.run(git + ["commit", "-qm", "init"], cwd=self._tmp, check=True)
        rev = self.req("POST", "/api/revision", {})[1]["revision"]
        self.req("POST", "/api/save", {"patch": {"format": "bot-ui-patch/v1", "baseRevision": rev, "changes": [
            {"screenId": "orders.pickup", "ops": [{"op": "set", "path": "/title", "value": "Pickup!"}]}]}})
        status, doc, _ = self.req("POST", "/api/git-status", {})
        self.assertTrue(doc["git"])
        self.assertEqual(doc["projectPath"], "мой бот/bot-ui")
        self.assertEqual([(f["status"], f.get("screenId")) for f in doc["files"]], [("M", "orders.pickup")])
        self.assertIn('+  "title": "Pickup!"', doc["diff"])

    def test_preview_frame_has_no_network(self):
        status, body, headers = self.req("GET", "/preview-frame.html")
        self.assertEqual(status, 200)
        csp = headers["Content-Security-Policy"]
        self.assertIn("connect-src 'none'", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("e.source !== parent", body)

    def test_widget_draft_build_and_stale_export(self):
        status, b, _ = self.req("POST", "/api/widget/build", {"widget": "order-status", "lang": "ru",
                                                             "values": {"order.no": "1"}})
        self.assertEqual(status, 200)
        self.assertTrue(b["ok"], b["errors"])
        status, draft, _ = self.req("POST", "/api/widget/build", {"widget": "order-status", "lang": "ru",
                                                                 "files": {"style.css": "/*@kit tokens.css*/\n.x{}\n"}})
        self.assertTrue(draft["draft"])
        self.assertNotEqual(draft["sourceHash"], b["sourceHash"])
        status, _, _ = self.req("POST", "/api/widget/build", {"widget": "order-status", "files": {"../x.css": ""}})
        self.assertEqual(status, 422)
        status, ex, _ = self.req("POST", "/api/widget/export", {"widget": "order-status", "lang": "ru",
                                                               "values": {"order.no": "1"}, "sourceHash": draft["sourceHash"]})
        self.assertEqual(status, 409)
        self.assertEqual(ex["error"]["code"], "STALE_BUILD")
        status, ex, _ = self.req("POST", "/api/widget/export", {"widget": "order-status", "lang": "ru",
                                                               "values": {"order.no": "1"}, "sourceHash": b["sourceHash"]})
        self.assertEqual(status, 200)
        self.assertEqual(ex["payload"]["method"], "sendWidget")


if __name__ == "__main__":
    unittest.main()
