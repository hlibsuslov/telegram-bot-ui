"""user-data.md and data/user-data.json name only real Bot API and Mini App fields, and keep the rules."""
import json
import os
import re
import unittest

import _paths

REF = os.path.join(_paths.ROOT, "references")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


BOT = json.loads(read(_paths.ROOT, "data", "bot-api", "catalog.json"))
WEB = json.loads(read(_paths.ROOT, "data", "mini-apps", "webapp-catalog.json"))


def bot_entries():
    out = {}
    for section in ("types", "methods"):
        for item in BOT.get(section, []) if isinstance(BOT.get(section), list) else (BOT.get(section) or {}).values():
            out[item["name"]] = {f["name"] for f in (item.get("fields") or item.get("parameters") or [])}
    return out


BOT_NAMES = bot_entries()
WEB_KEYS = set(WEB["members"]) | set(WEB.get("objects", {}))
WEB_FIELDS = {}
for key, m in WEB["members"].items():
    WEB_FIELDS.setdefault(m["owner"], set()).add(m["name"])


def exists(name):
    owner, _, member = name.partition(".")
    if owner == "WebApp":
        return member in WEB_FIELDS.get("WebApp", set())
    if owner in ("WebAppUser", "WebAppInitData", "WebAppChat"):
        return member in WEB_FIELDS.get(owner, set())
    if owner not in BOT_NAMES:
        return False
    return not member or member in BOT_NAMES[owner]


class Data(unittest.TestCase):
    data = json.loads(read(_paths.ROOT, "data", "user-data.json"))

    def test_catalog_shape_is_understood(self):
        self.assertIn("ChatFullInfo", BOT_NAMES)
        self.assertIn("birthdate", BOT_NAMES["ChatFullInfo"])
        self.assertIn("requestContact", WEB_FIELDS["WebApp"])

    def test_every_named_field_exists(self):
        for tier in ("automatic", "api", "on_request"):
            for item in self.data["tiers"][tier]["items"]:
                self.assertTrue(exists(item["name"]), f"{tier}: {item['name']}")
                self.assertIn(item["sensitivity"], self.data["sensitivity"])

    def test_identifying_data_is_high_and_only_on_request(self):
        high = {i["name"] for t in ("automatic", "api") for i in self.data["tiers"][t]["items"] if i["sensitivity"] == "high"}
        self.assertEqual(high, set(), "nothing high-sensitivity arrives without the user's action")
        on_req = {i["name"]: i["sensitivity"] for i in self.data["tiers"]["on_request"]["items"]}
        for name in ("Contact.phone_number", "KeyboardButton.request_location", "PassportData", "OrderInfo.email"):
            self.assertEqual(on_req[name], "high", name)


class Reference(unittest.TestCase):
    doc = read(REF, "user-data.md")

    def test_sections(self):
        for n in range(0, 8):
            self.assertRegex(self.doc, rf"\n## {n}\. ")

    def test_backticked_api_names_exist(self):
        names = set(re.findall(r"`((?:get|send|request)[A-Z]\w+)(?:\([^`]*\))?`", self.doc))
        self.assertGreaterEqual(len(names), 8)
        for n in names:
            self.assertTrue(n in BOT_NAMES or n in WEB_FIELDS.get("WebApp", set()), n)
        for t in ("ChatFullInfo", "Contact", "KeyboardButtonRequestUsers", "KeyboardButtonRequestChat", "OrderInfo", "PassportData", "Location"):
            self.assertIn(t, BOT_NAMES)

    def test_keeps_the_rules(self):
        flat = " ".join(self.doc.split())
        for rule in ("privacy policy", "Only what the service needs", "No third parties", "No datasets",
                     "Encrypt user data at rest", "30 days", "contact.user_id == message.from.id", "/deletedata"):
            self.assertIn(rule, flat, rule)

    def test_links_resolve(self):
        for link in re.findall(r"\]\(([^)#:]+\.md)", self.doc):
            self.assertTrue(os.path.exists(os.path.join(REF, link)), link)

    def test_routed(self):
        self.assertIn("references/user-data.md", read(_paths.ROOT, "SKILL.md"))


if __name__ == "__main__":
    unittest.main()
