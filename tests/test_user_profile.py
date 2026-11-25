"""tgkit.profile keeps the baseline record as user-profile.md describes; every Bot API field it names exists."""
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "examples", "python"))
from tgkit import profile as P  # noqa: E402

NOW = datetime(2026, 11, 24, 12, 0)
USER = {"id": 42, "first_name": "Ada", "username": "ada", "language_code": "en"}
BOT = json.load(open(os.path.join(_paths.ROOT, "data", "bot-api", "catalog.json"), encoding="utf-8"))
FIELDS = {name: {f["name"] for f in t.get("fields", [])} for name, t in BOT["types"].items()}


class Record(unittest.TestCase):
    def test_first_contact_records_acquisition_once(self):
        p = P.touch(None, USER, NOW, payload="item_42", entry="start")
        self.assertEqual((p.acquisition.kind, p.acquisition.value, p.acquisition.entry), ("item", "42", "start"))
        p = P.touch(p, USER, NOW + timedelta(days=1), payload="ad_spring")
        self.assertEqual(p.acquisition.kind, "item", "first touch is never overwritten")

    def test_payloads_are_allowlisted(self):
        self.assertEqual(P.parse_acquisition(None).kind, "organic")
        self.assertEqual(P.parse_acquisition("<script>").kind, "other")
        self.assertEqual(P.parse_acquisition("ref_ab12").value, "ab12")

    def test_profile_update_time_moves_only_on_change(self):
        p = P.touch(None, USER, NOW)
        self.assertIsNone(p.profile_updated_at)
        P.touch(p, USER, NOW + timedelta(hours=1))
        self.assertIsNone(p.profile_updated_at)
        P.touch(p, {**USER, "username": "ada_l"}, NOW + timedelta(hours=2))
        self.assertEqual(p.profile_updated_at, NOW + timedelta(hours=2))
        self.assertFalse(hasattr(p, "username_history"), "no history of usernames")

    def test_block_and_unblock(self):
        p = P.touch(None, USER, NOW)
        P.chat_member_update(p, {"new_chat_member": {"status": "kicked"}}, NOW)
        self.assertEqual(p.notifications.blocked_at, NOW)
        P.chat_member_update(p, {"new_chat_member": {"status": "member"}}, NOW)
        self.assertIsNone(p.notifications.blocked_at)

    def test_snapshot_keeps_only_interface_fields(self):
        p = P.touch(None, USER, NOW)
        P.apply_chat_full_info(p, {"active_usernames": ["ada", "ada_collectible"], "has_private_forwards": True,
                                   "has_restricted_voice_and_video_messages": True, "bio": "x",
                                   "birthdate": {"day": 1, "month": 2}, "rating": {"level": -1}}, NOW)
        self.assertFalse(P.can_send_voice(p))
        self.assertEqual(p.stars_rating_level, -1)
        self.assertFalse(hasattr(p, "bio") or hasattr(p, "birthdate"))

    def test_handle(self):
        p = P.UserProfile(user_id=1, first_name="Ada", active_usernames=["ada_c"])
        self.assertEqual(P.display_handle(p), "@ada_c")
        self.assertEqual(P.display_handle(P.UserProfile(user_id=1, first_name="Ada")), "Ada")

    def test_terms(self):
        p = P.UserProfile(user_id=1, terms_version="2026-01")
        self.assertTrue(P.needs_terms(p, "2026-11"))
        self.assertFalse(P.needs_terms(p, "2026-01"))


class Accent(unittest.TestCase):
    backdrop = {"center_color": 0x5B8C51, "edge_color": 0x2E4A2B, "symbol_color": 0x1F331D, "text_color": 0xFFFFFF}

    def test_unique_gift_theme(self):
        p = P.UserProfile(user_id=1, share_theme={"type": "unique_gift", "gift": {"backdrop": {"colors": self.backdrop}}})
        self.assertEqual(P.personal_accent(p, "light"), {"center": "#5b8c51", "edge": "#2e4a2b", "symbol": "#1f331d", "text": "#ffffff"})

    def test_emoji_theme_uses_cached_backdrops(self):
        p = P.UserProfile(user_id=1, share_theme={"type": "emoji", "emojis": [], "background_backdrop_id": 7})
        self.assertIsNone(P.personal_accent(p, "light"))
        self.assertEqual(P.personal_accent(p, "light", {7: self.backdrop})["text"], "#ffffff")

    def test_gift_colors_by_scheme_then_none(self):
        gc = {"light_theme_main_color": 0x112233, "light_theme_other_colors": [0x445566],
              "dark_theme_main_color": 0xAABBCC, "dark_theme_other_colors": [0xDDEEFF]}
        p = P.UserProfile(user_id=1, unique_gift_colors=gc)
        self.assertEqual(P.personal_accent(p, "dark")["accent"], "#aabbcc")
        self.assertEqual(P.personal_accent(p, "light")["others"], ["#445566"])
        self.assertIsNone(P.personal_accent(P.UserProfile(user_id=1), "light"))


class Api(unittest.TestCase):
    def test_fields_used_exist(self):
        for t, f in (("ChatFullInfo", "share_theme"), ("ChatFullInfo", "unique_gift_colors"), ("ChatFullInfo", "active_usernames"),
                     ("ChatFullInfo", "has_private_forwards"), ("ChatFullInfo", "has_restricted_voice_and_video_messages"),
                     ("ChatFullInfo", "rating"), ("ChatFullInfo", "community"), ("ChatShareThemeEmoji", "background_backdrop_id"),
                     ("ChatShareThemeUniqueGift", "gift"), ("UniqueGift", "backdrop"), ("UniqueGiftBackdrop", "colors"),
                     ("UniqueGiftBackdropColors", "text_color"), ("UniqueGiftColors", "dark_theme_main_color"),
                     ("ChatMemberMember", "tag"), ("ChatMemberAdministrator", "custom_title"), ("Update", "my_chat_member")):
            self.assertIn(f, FIELDS[t], f"{t}.{f}")
        self.assertIn("getChatShareThemeBackdrops", BOT["methods"])


class Reference(unittest.TestCase):
    doc = open(os.path.join(_paths.ROOT, "references", "user-profile.md"), encoding="utf-8").read()

    def test_sections_and_links(self):
        for n in range(0, 7):
            self.assertRegex(self.doc, rf"\n## {n}\. ")
        for link in re.findall(r"\]\(([^)#:]+\.md)", self.doc):
            self.assertTrue(os.path.exists(os.path.join(_paths.ROOT, "references", link)), link)

    def test_functions_named_exist(self):
        for fn in re.findall(r"`(touch|apply_chat_full_info|chat_member_update|personal_accent|display_handle|can_send_voice|needs_terms)", self.doc):
            self.assertTrue(hasattr(P, fn), fn)

    def test_routed(self):
        self.assertIn("references/user-profile.md", _paths.routing_text())


if __name__ == "__main__":
    unittest.main()
