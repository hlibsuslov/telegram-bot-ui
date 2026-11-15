"""Bot API catalog: parser against saved official HTML, layout guard, snapshot
integrity, diffing. Offline: reads tests/fixtures/api/ and data/bot-api/ only."""
import copy
import os
import tempfile
import unittest

import _paths
import sync_bot_api as sync

FIX = os.path.join(_paths.TESTS, "fixtures", "api")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


API = fixture("bot_api_excerpt.html")
CHANGELOG = fixture("changelog_excerpt.html")


class ParserOnExcerpt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = sync.parse_api(API)
        cls.m, cls.t = cls.parsed["methods"], cls.parsed["types"]

    def test_counts(self):
        self.assertEqual(sorted(self.m), ["answerInlineQuery", "getMe", "getUpdates", "sendInvoice",
                                          "sendMessage", "setMessageReaction"])
        self.assertEqual(len(self.t), 17)

    def test_prose_headers_are_not_symbols(self):
        for bad in ("Formatting options", "Sending files", "November 9, 2026"):
            self.assertNotIn(bad, self.m)
            self.assertNotIn(bad, self.t)

    def test_method_required_flags_and_types(self):
        params = {p["name"]: p for p in self.m["sendMessage"]["parameters"]}
        self.assertTrue(params["text"]["required"])
        self.assertFalse(params["reply_markup"]["required"])
        self.assertEqual(params["chat_id"]["types"], [{"name": "Integer", "array": 0}, {"name": "String", "array": 0}])
        self.assertTrue(params["chat_id"]["conditional"])  # "required unless ... ephemeral reply"
        self.assertEqual(len(self.m["sendInvoice"]["parameters"]) > 15, True)
        prices = next(p for p in self.m["sendInvoice"]["parameters"] if p["name"] == "prices")
        self.assertEqual(prices["types"], [{"name": "LabeledPrice", "array": 1}])

    def test_type_optional_prefix_becomes_flag(self):
        fields = {f["name"]: f for f in self.t["User"]["fields"]}
        self.assertTrue(fields["id"]["required"])
        self.assertFalse(fields["username"]["required"])
        self.assertFalse(fields["username"]["description"].startswith("Optional"))

    def test_nested_arrays(self):
        f = self.t["InlineKeyboardMarkup"]["fields"][0]
        self.assertEqual(f["types"], [{"name": "InlineKeyboardButton", "array": 2}])

    def test_unions_and_discriminators(self):
        self.assertEqual(self.t["ReactionType"]["subtypes"],
                         ["ReactionTypeEmoji", "ReactionTypeCustomEmoji", "ReactionTypePaid"])
        self.assertEqual(self.t["MaybeInaccessibleMessage"]["subtypes"], ["Message", "InaccessibleMessage"])
        emoji_type = next(f for f in self.t["ReactionTypeEmoji"]["fields"] if f["name"] == "type")
        self.assertEqual(emoji_type["const"], "emoji")

    def test_return_types_from_prose(self):
        self.assertEqual(self.m["getUpdates"]["returns"], "Array of Update")
        self.assertEqual(self.m["getMe"]["returns"], "User")
        self.assertEqual(self.m["sendMessage"]["returns"], "Message")
        self.assertEqual(self.m["answerInlineQuery"]["returns"], "True")

    def test_sections_and_urls(self):
        self.assertEqual(self.m["getUpdates"]["section"], "Getting updates")
        self.assertEqual(self.m["answerInlineQuery"]["section"], "Inline mode")
        self.assertEqual(self.m["sendInvoice"]["url"], "https://core.telegram.org/bots/api#sendinvoice")

    def test_emoji_images_kept_as_text(self):
        emoji = next(f for f in self.t["ReactionTypeEmoji"]["fields"] if f["name"] == "emoji")
        self.assertIn("👍", emoji["description"])


class Changelog(unittest.TestCase):
    def test_releases_versions_groups_symbols(self):
        rel = sync.parse_changelog(CHANGELOG)
        self.assertEqual([(r["version"], r["date"]) for r in rel], [("10.4", "2026-11-09"), ("10.3", "2026-08-24")])
        groups = {g["title"]: g for g in rel[0]["groups"]}
        self.assertIn("Widgets", groups)
        first = groups["Widgets"]["items"][0]
        self.assertEqual(first["symbols"], ["Widget", "Message", "ExternalReplyInfo"])
        self.assertTrue(any("getUniqueGift" in it["symbols"] for it in groups["Gifts"]["items"]))

    def test_version_read_from_api_page(self):
        built = sync.build_catalog(API, CHANGELOG, "2026-11-15", min_methods=5, min_types=10)
        meta = built["catalog"]["meta"]
        self.assertEqual((meta["bot_api_version"], meta["release_date"]), ("10.4", "2026-11-09"))
        self.assertEqual(meta["counts"]["methods"], 6)


class LayoutGuard(unittest.TestCase):
    def test_excerpt_is_rejected_by_real_thresholds(self):
        with self.assertRaises(sync.LayoutError) as cm:
            sync.build_catalog(API, CHANGELOG, "2026-11-15")
        self.assertIn("methods parsed", str(cm.exception))

    def test_renamed_table_header_is_a_layout_error(self):
        broken = API.replace("<th>Parameter</th>", "<th>Argument</th>", 1)
        with self.assertRaises(sync.LayoutError):
            sync.parse_api(broken)

    def test_unknown_required_value_is_a_layout_error(self):
        broken = API.replace("<td>Yes</td>", "<td>Mandatory</td>", 1)
        with self.assertRaises(sync.LayoutError):
            sync.parse_api(broken)

    def test_missing_version_is_a_layout_error(self):
        broken = API.replace("<strong>Bot API 10.4</strong>", "<strong>Release</strong>")
        with self.assertRaises(sync.LayoutError):
            sync.build_catalog(broken, None, "2026-11-15", min_methods=5, min_types=10)

    def test_cli_writes_nothing_on_layout_error(self):
        with tempfile.TemporaryDirectory() as out:
            api = os.path.join(out, "api.html")
            with open(api, "w", encoding="utf-8") as fh:
                fh.write(API)
            code = sync.main(["--api-html", api, "--out", out])
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(os.path.join(out, "catalog.json")))

    def test_shrink_guard(self):
        cat = sync.load_catalog()
        smaller = copy.deepcopy(cat)
        for name in list(smaller["methods"])[:40]:
            del smaller["methods"][name]
        with self.assertRaises(sync.LayoutError):
            sync.check_shrink(cat, smaller)


class Diff(unittest.TestCase):
    def test_added_removed_changed(self):
        old = sync.load_catalog()
        new = copy.deepcopy(old)
        new["meta"]["bot_api_version"] = "10.5"
        new["methods"]["sendHologram"] = {**copy.deepcopy(new["methods"]["getMe"]), "name": "sendHologram"}
        del new["types"]["CallbackGame"]
        new["methods"]["sendMessage"]["parameters"].append(
            {"name": "hologram", "type": "Boolean", "types": [{"name": "Boolean", "array": 0}],
             "required": False, "description": "x"})
        p = next(p for p in new["methods"]["sendMessage"]["parameters"] if p["name"] == "text")
        p["required"] = False
        d = sync.diff_catalogs(old, new)
        self.assertEqual(d["added"]["methods"], ["sendHologram"])
        self.assertEqual(d["removed"]["types"], ["CallbackGame"])
        ch = d["changed"]["methods"]["sendMessage"]
        self.assertEqual(ch["added_parameters"], ["hologram"])
        self.assertEqual(ch["modified_parameters"]["text"]["required"], [True, False])
        self.assertIn("10.4 -> 10.5", sync.summarize_diff(d))

    def test_identical_snapshots_have_no_changes(self):
        cat = sync.load_catalog()
        d = sync.diff_catalogs(cat, copy.deepcopy(cat))
        self.assertFalse(any(d["added"].values()) or any(d["removed"].values()) or any(d["changed"].values()))


class SnapshotIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = sync.load_catalog()

    def test_meta(self):
        meta = self.cat["meta"]
        self.assertRegex(meta["bot_api_version"], r"^\d+\.\d+$")
        self.assertRegex(meta["release_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(meta["fetched_at"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(meta["counts"]["methods"], len(self.cat["methods"]))
        self.assertEqual(meta["counts"]["types"], len(self.cat["types"]))

    def test_every_referenced_type_exists(self):
        missing = sync.referenced_types(self.cat) - set(self.cat["types"])
        self.assertEqual(missing, set())

    def test_every_method_has_description_and_return_hint(self):
        for name, m in self.cat["methods"].items():
            self.assertTrue(m["description"], name)
            self.assertTrue(m["returns"], f"{name}: no return type extracted")
            self.assertTrue(name[0].islower())

    def test_union_members_with_discriminators_are_unique(self):
        """Only InlineQueryResult reuses a `type` (cached vs URL results, told apart by
        *_file_id vs *_url); validate_payload decides those structurally."""
        shared = set()
        for name, t in self.cat["types"].items():
            consts = []
            for s in t["subtypes"]:
                sub = self.cat["types"][s]
                c = next((f["const"] for f in sub["fields"] if f["name"] in ("type", "source", "status")
                          and f.get("const")), None)
                if c:
                    consts.append(c)
            if len(consts) != len(set(consts)):
                shared.add(name)
        self.assertEqual(shared, {"InlineQueryResult"})

    def test_known_10_4_symbols_present(self):
        for s in ("sendWidget", "answerWidgetQuery", "getUniqueGift", "deleteBusinessAccountGift",
                  "getChatShareThemeBackdrops"):
            self.assertIn(s, self.cat["methods"])
        for s in ("Widget", "WidgetQuery", "TonWalletCard", "PaidMessagesWaived", "AreaPosition"):
            self.assertIn(s, self.cat["types"])

    def test_changelog_snapshot_matches_catalog_version(self):
        cl = sync.load_changelog()
        self.assertEqual(cl["meta"]["newest_version"], self.cat["meta"]["bot_api_version"])
        versions = [r["version"] for r in cl["releases"] if r["version"]]
        for v in ("9.0", "9.6", "10.0", "10.4"):
            self.assertIn(v, versions)

    def test_changelog_symbols_resolve(self):
        """Symbols the newest two releases link to exist in the catalog (renames excepted)."""
        cl = sync.load_changelog()
        known = set(self.cat["methods"]) | set(self.cat["types"])
        renamed = {"StoryAreaPosition"}
        for rel in cl["releases"][:2]:
            for g in rel["groups"]:
                for it in g["items"]:
                    for s in it["symbols"]:
                        if s not in renamed:
                            self.assertIn(s, known, f"{rel['version']}: {s}")


if __name__ == "__main__":
    unittest.main()
