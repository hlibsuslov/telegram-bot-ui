"""Every JSON request/update example in the API-area references is structurally
valid against the committed snapshot, and every symbol they cite exists."""
import json
import os
import re
import unittest

import _paths
import tg_api_lookup as lookup
import validate_payload as vp

REFS = ["api-catalog.md", "payments-and-stars.md", "payments-pipeline.md", "inline-mode.md", "business-accounts.md",
        "updates-and-delivery.md", "media-and-files.md", "chat-administration.md",
        "polls-checklists-and-reactions.md", "gifts-and-stories.md", "mini-apps-bridge.md"]
FENCE = re.compile(r"```json\n(.*?)```", re.S)
API = lookup.Api()
V = vp.Validator(API.cat)


def blocks(name):
    path = os.path.join(_paths.ROOT, "references", name)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return FENCE.findall(fh.read())


class ReferenceExamples(unittest.TestCase):
    def test_references_exist(self):
        for name in REFS:
            self.assertTrue(os.path.isfile(os.path.join(_paths.ROOT, "references", name)), name)

    def test_every_json_example_is_valid(self):
        checked = 0
        for name in REFS:
            for i, raw in enumerate(blocks(name)):
                with self.subTest(ref=name, block=i):
                    doc = json.loads(raw)
                    if "method" in doc:
                        rep = V.check_request(doc["method"], doc.get("params", {}))
                    elif "update_id" in doc:
                        rep = V.check_object("Update", doc)
                    elif "_type" in doc:
                        rep = V.check_object(doc["_type"], {k: v for k, v in doc.items() if k != "_type"})
                    else:
                        continue
                    self.assertTrue(rep.ok, rep.errors)
                    checked += 1
        self.assertGreater(checked, 40)

    def test_init_data_snippet_verifies_and_rejects(self):
        import hashlib, hmac, time, urllib.parse
        with open(os.path.join(_paths.ROOT, "references", "mini-apps-bridge.md"), encoding="utf-8") as fh:
            code = re.search(r"```python\n(.*?)```", fh.read(), re.S).group(1)
        ns = {}
        exec(code, ns)
        token = "123:TEST-ONLY"
        fields = {"auth_date": str(int(time.time())), "query_id": "q1", "user": '{"id":1}', "signature": "sig"}
        check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        data = urllib.parse.urlencode(fields)
        self.assertEqual(ns["verify_init_data"](data, token)["query_id"], "q1")
        with self.assertRaises(ValueError):
            ns["verify_init_data"](data, "123:OTHER")
        fields["auth_date"] = "1"
        with self.assertRaises(ValueError):
            ns["verify_init_data"](urllib.parse.urlencode(fields), token)

    def test_update_table_covers_every_update_field(self):
        with open(os.path.join(_paths.ROOT, "references", "updates-and-delivery.md"), encoding="utf-8") as fh:
            text = fh.read()
        for f in API.cat["types"]["Update"]["fields"]:
            if f["name"] != "update_id":
                self.assertIn(f"| `{f['name']}` |", text, f"Update.{f['name']} missing from the table")

    def test_cited_method_names_exist(self):
        """`someMethod` in backticks that looks like a Bot API method must exist."""
        known = set(API.cat["methods"])
        allowed = {"openInvoice", "sendData", "openTelegramLink", "switchInlineQuery", "requestChat",
                   "shareMessage", "openLink", "close", "ready", "expand", "requestContact",
                   "requestWriteAccess", "downloadFile", "showPopup", "readTextFromClipboard",
                   "setEmojiStatus", "requestEmojiStatusAccess", "hideKeyboard", "shareToStory",
                   "initData", "initDataUnsafe", "addToHomeScreen", "checkHomeScreenStatus"}
        verbs = ("send", "get", "set", "edit", "delete", "answer", "create", "ban", "unban", "restrict",
                 "promote", "approve", "decline", "pin", "unpin", "forward", "copy", "upload", "refund",
                 "post", "repost", "transfer", "upgrade", "convert", "read", "remove", "stop", "verify",
                 "export", "revoke", "leave", "close", "reopen", "hide", "unhide", "replace", "save", "gift",
                 "log", "add")
        pat = re.compile(r"`(" + "|".join(verbs) + r")([A-Z][A-Za-z]*)`")
        for name in REFS:
            path = os.path.join(_paths.ROOT, "references", name)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for m in pat.finditer(text):
                sym = m.group(1) + m.group(2)
                if sym not in allowed:
                    self.assertIn(sym, known, f"{name}: `{sym}` is not a Bot API method")


if __name__ == "__main__":
    unittest.main()
