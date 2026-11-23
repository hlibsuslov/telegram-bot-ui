"""references/mini-apps: JSON examples valid, every Telegram.WebApp member cited exists with the stated
version, every Bot API method cited exists. Offline, stdlib unittest."""
import glob
import json
import os
import re
import unittest

import _paths
import tg_api_lookup as lookup
import validate_payload as vp
import webapp_lookup as wl

REF_DIR = os.path.join(_paths.ROOT, "references", "mini-apps")
API = lookup.Api()
V = vp.Validator(API.cat)
WEB = wl.WebAppApi()
FENCE = re.compile(r"```json\n(.*?)```", re.S)
MEMBER = re.compile(r"`(?:Telegram\.)?((?:WebApp|BottomButton|MainButton|SecondaryButton|BackButton|SettingsButton|"
                    r"HapticFeedback|CloudStorage|DeviceStorage|SecureStorage|BiometricManager|LocationManager|"
                    r"Serverless)\.[A-Za-z_]+)")
TABLE_ROW = re.compile(r"^\| `([A-Za-z]+\.[A-Za-z_]+)[^`]*` \| ([0-9.]+|new \(2026-10\)) \|", re.M)


def refs():
    return sorted(glob.glob(os.path.join(REF_DIR, "*.md")))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class MiniAppReferences(unittest.TestCase):
    def test_branch_files_exist(self):
        names = {os.path.basename(p) for p in refs()}
        self.assertTrue({"README.md", "decide.md", "launch-and-lifecycle.md", "webapp-api.md", "security.md",
                         "telegram-design-guidelines.md", "design-sources.md"} <= names)

    def test_json_examples_are_valid(self):
        checked = 0
        for path in refs():
            for i, raw in enumerate(FENCE.findall(read(path))):
                with self.subTest(ref=os.path.basename(path), block=i):
                    doc = json.loads(raw)
                    if "method" in doc:
                        rep = V.check_request(doc["method"], doc.get("params", {}))
                    elif "update_id" in doc:
                        rep = V.check_object("Update", doc)
                    else:
                        continue
                    self.assertTrue(rep.ok, rep.errors)
                    checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_cited_webapp_members_exist(self):
        for path in refs():
            for m in MEMBER.finditer(read(path)):
                with self.subTest(ref=os.path.basename(path), member=m.group(1)):
                    self.assertIsNotNone(WEB.resolve(m.group(1)), m.group(1))

    def test_api_tables_match_catalog_versions(self):
        rows = TABLE_ROW.findall(read(os.path.join(REF_DIR, "webapp-api.md")))
        self.assertGreater(len(rows), 60)
        for name, ver in rows:
            kind, key = WEB.resolve(name)
            expected = WEB.cat["members"][key]["version"] or "new (2026-10)"
            self.assertEqual(ver, expected, name)

    def test_cited_bot_api_methods_exist(self):
        client = {m["name"] for m in WEB.cat["members"].values()} | {"getUserMedia", "createTma"}  # browser API, kit factory
        verbs = ("send", "get", "set", "edit", "delete", "answer", "create", "save", "refund")
        pat = re.compile(r"`(" + "|".join(verbs) + r")([A-Z][A-Za-z]*)`")
        for path in refs():
            for m in pat.finditer(read(path)):
                sym = m.group(1) + m.group(2)
                if sym not in client:
                    self.assertTrue(sym in API.cat["methods"], f"{os.path.basename(path)}: `{sym}`")

    def test_security_page_has_both_ed25519_keys(self):
        text = read(os.path.join(REF_DIR, "security.md"))
        self.assertIn("e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d", text)
        self.assertIn("40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec", text)

    def test_bridge_points_to_the_branch(self):
        text = read(os.path.join(_paths.ROOT, "references", "mini-apps-bridge.md"))
        self.assertNotIn("out of scope", text)
        self.assertIn("mini-apps/README.md", text)


if __name__ == "__main__":
    unittest.main()
