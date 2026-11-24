"""Telegram.WebApp catalog (data/mini-apps) and webapp_lookup: offline, stdlib unittest."""
import contextlib
import io
import json
import os
import unittest

import _paths
import tg_api_lookup
import webapp_lookup as wl

API = wl.WebAppApi()
FIXTURE = os.path.join(_paths.TESTS, "fixtures", "webapps", "webapps_min.html")


class CommittedCatalog(unittest.TestCase):
    def test_every_member_has_version_and_anchor(self):
        self.assertEqual(wl.check(API), [])
        for key, m in API.cat["members"].items():
            self.assertTrue(m["url"].startswith(wl.PAGE_URL + "#"), key)
            if m["version"] is None:
                self.assertTrue(m["version_source"].startswith("unversioned"), key)

    def test_size_and_snapshot_meta(self):
        meta = API.cat["meta"]
        self.assertGreaterEqual(meta["counts"]["members"], wl.MIN_MEMBERS)
        self.assertEqual(meta["bot_api_version_checked"], "10.5")
        self.assertEqual(meta["script_highest_gate"], "9.6")
        self.assertEqual(meta["newest_member_version"], "10.1")

    def test_known_versions(self):
        expected = {
            "WebApp.requestChat": "9.6", "WebApp.hideKeyboard": "9.1", "BottomButton.iconCustomEmojiId": "9.5",
            "WebApp.DeviceStorage": "9.0", "WebApp.SecureStorage": "9.0", "WebApp.safeAreaInset": "8.0",
            "WebApp.contentSafeAreaInset": "8.0", "WebApp.requestFullscreen": "8.0", "WebApp.shareMessage": "8.0",
            "WebApp.SecondaryButton": "7.10", "WebApp.setBottomBarColor": "7.10", "WebApp.shareToStory": "7.8",
            "WebApp.disableVerticalSwipes": "7.7", "WebApp.BiometricManager": "7.2", "WebApp.SettingsButton": "7.0",
            "WebApp.CloudStorage": "6.9", "WebApp.switchInlineQuery": "6.7", "WebApp.platform": "6.4",
            "WebApp.showPopup": "6.2", "WebApp.BackButton": "6.1", "WebApp.isVersionAtLeast": "6.1",
            "WebApp.close": "6.0", "WebApp.ready": "6.0", "WebApp.sendData": "6.0", "WebApp.MainButton": "6.0",
            "BottomButton.setParams": "6.0", "BottomButton.hasShineEffect": "7.10", "BottomButton.offClick": "6.1",
            "WebAppInitData.signature": "8.0", "WebAppInitData.chat_join_request_query_id": "10.1",
            "events.secondaryButtonClicked": "7.10", "events.activated": "8.0", "events.themeChanged": "6.0",
            "ThemeParams.section_separator_color": "7.6", "ThemeParams.bottom_bar_bg_color": "7.10",
        }
        for key, ver in expected.items():
            self.assertEqual(API.cat["members"][key]["version"], ver, key)

    def test_option_versions_do_not_date_the_member(self):
        self.assertEqual(API.cat["members"]["WebApp.openLink"]["option_versions"], ["6.4"])
        self.assertIn("9.5", API.cat["members"]["BottomButton.setParams"]["option_versions"])

    def test_bottom_button_has_no_style_field(self):
        names = {API.cat["members"][k]["name"] for k in API.cat["objects"]["BottomButton"]["members"]}
        self.assertNotIn("style", names)
        self.assertTrue({"color", "textColor", "position", "iconCustomEmojiId", "hasShineEffect"} <= names)

    def test_serverless_is_unversioned(self):
        m = API.cat["members"]["WebApp.Serverless"]
        self.assertIsNone(m["version"])
        self.assertEqual(m.get("badge"), "NEW")

    def test_theme_params_match_catalog(self):
        keys = {m["name"] for m in API.cat["members"].values() if m["owner"] == "ThemeParams"}
        self.assertEqual(len(keys), 15)
        rows = API.theme["params"]
        self.assertEqual({r["key"] for r in rows}, keys)
        for r in rows:
            self.assertEqual(r["css_var"], "--tg-theme-" + r["key"].replace("_", "-"))
            self.assertTrue(r["fallback"]["light"] and r["fallback"]["dark"], r["key"])
            if r["fallback_key"]:
                self.assertIn(r["fallback_key"], keys)

    def test_gates_cover_newer_members_only(self):
        gates = API.gates()
        self.assertEqual(gates["WebApp.requestFullscreen"], "8.0")
        self.assertNotIn("WebApp.ready", gates)
        self.assertNotIn("WebApp.Serverless", gates)


class Lookup(unittest.TestCase):
    def test_resolve_forms(self):
        self.assertEqual(API.resolve("WebApp.expand"), ("member", "WebApp.expand"))
        self.assertEqual(API.resolve("Telegram.WebApp.expand"), ("member", "WebApp.expand"))
        self.assertEqual(API.resolve("expand"), ("member", "WebApp.expand"))
        self.assertEqual(API.resolve("MainButton.setText"), ("member", "BottomButton.setText"))
        self.assertEqual(API.resolve("SecondaryButton.position"), ("member", "BottomButton.position"))
        self.assertEqual(API.resolve("WebApp.MainButton"), ("member", "WebApp.MainButton"))
        self.assertEqual(API.resolve("themeChanged"), ("member", "events.themeChanged"))
        self.assertEqual(API.resolve("bottombutton"), ("object", "BottomButton"))
        self.assertIsNone(API.resolve("WebApp.noSuchThing"))

    def test_since_and_search(self):
        added = {m["key"] for m in API.since("9.6")}
        self.assertEqual(added, {"WebApp.requestChat"})
        self.assertEqual(API.search("requestChat")[0]["key"], "WebApp.requestChat")

    def test_cli_show_and_bot_api_delegation(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(wl.main(["show", "WebApp.requestFullscreen"]), 0)
        self.assertIn("isVersionAtLeast('8.0')", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(tg_api_lookup.main(["--json", "show", "WebApp.shareMessage"]), 0)
        self.assertEqual(json.loads(buf.getvalue())["version"], "8.0")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(tg_api_lookup.main(["show", "WebAppInfo"]), 0)  # Bot API type still wins
        self.assertIn("section: Available types", buf.getvalue())


class Parser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.cat = wl.parse(fh.read())
        cls.m = cls.cat["members"]

    def test_mark_at_start_dates_member(self):
        self.assertEqual((self.m["WebApp.isActive"]["version"], self.m["WebApp.isActive"]["version_source"]),
                         ("8.0", "mark"))
        self.assertEqual(self.m["ThemeParams.section_separator_color"]["version"], "7.6")  # after "Optional."
        self.assertEqual(self.m["events.activated"]["version"], "8.0")

    def test_mark_later_in_text_is_an_option(self):
        self.assertEqual(self.m["WebApp.openLink"]["version"], "6.0")
        self.assertEqual(self.m["WebApp.openLink"]["option_versions"], ["6.4"])
        self.assertEqual(self.m["BottomButton.setParams"]["option_versions"], ["9.5"])

    def test_recent_changes_only_from_added_items(self):
        self.assertEqual(self.m["WebApp.version"]["version"], "6.1")
        self.assertEqual(self.m["WebApp.isVersionAtLeast"]["version_source"], "changelog")
        self.assertEqual(self.m["WebApp.close"]["version"], "6.0")  # "no longer close" is not an Added item
        self.assertEqual(self.m["events.backButtonClicked"]["version"], "6.1")

    def test_renamed_class_and_parent_versions(self):
        self.assertEqual(self.m["BottomButton.offClick"]["version"], "6.1")  # "class MainButton" alias
        self.assertEqual(self.m["BottomButton.iconCustomEmojiId"]["version"], "9.5")
        self.assertEqual(self.m["BottomButton.text"]["version"], "6.0")  # object since WebApp.MainButton
        self.assertEqual(self.m["BackButton.show"]["version"], "6.1")
        self.assertEqual(self.m["SettingsButton.show"]["version"], "7.0")
        self.assertEqual(self.cat["objects"]["SettingsButton"]["version"], "7.0")

    def test_new_badge_and_second_table(self):
        self.assertIn("WebApp.Serverless", self.m)
        self.assertEqual(self.m["WebApp.Serverless"]["badge"], "NEW")
        self.assertIsNone(self.m["Serverless.call"]["version"])
        self.assertIn("ServerlessError.status", self.m)

    def test_guard_rejects_small_page(self):
        self.assertTrue(any("only" in p for p in wl.guard(self.cat)))

    def test_diff(self):
        d = wl.diff(self.cat, {"members": {**self.m, "WebApp.newThing": {"version": "11.0"}}})
        self.assertEqual(d["added"], ["WebApp.newThing"])
        self.assertEqual(wl.diff(None, self.cat), {"initial": True})


if __name__ == "__main__":
    unittest.main()
