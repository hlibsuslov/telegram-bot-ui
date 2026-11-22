"""Bot API 10.5 bot settings: setMySettings planning and validation, BotFullInfo,
callback_query_mode addressing, active usernames, botinvite links."""
import unittest

import _paths  # noqa: F401
from tgkit import settings
from tgkit.transport import FakeTransport

from sync_bot_api import load_catalog  # skills/telegram-bot-ui/scripts

ME = _paths.load("examples", "fixtures", "get_me_bot_full_info.json")["result"]


class Settings(unittest.TestCase):
    def test_every_setting_is_a_set_my_settings_parameter(self):
        params = {p["name"] for p in load_catalog()["methods"]["setMySettings"]["parameters"]}
        self.assertEqual(set(settings.SETTINGS), params)

    def test_readable_settings_exist_in_bot_full_info(self):
        fields = {f["name"] for f in load_catalog()["types"]["BotFullInfo"]["fields"]}
        self.assertLessEqual(set(settings.READABLE.values()), fields)
        for key in settings.WRITE_ONLY:
            self.assertNotIn(key, fields)

    def test_plan_sends_only_differences(self):
        self.assertEqual(settings.plan(ME, {"supports_inline_queries": True, "can_join_groups": True}), {})
        self.assertEqual(settings.plan(ME, {"has_topic_sidebar": True}), {"has_topic_sidebar": True})
        self.assertEqual(settings.plan(ME, {"inline_query_placeholder": ""}), {})      # omitted = default
        self.assertEqual(settings.plan(ME, {"callback_query_mode": "default"}), {"callback_query_mode": "default"})

    def test_apply_refuses_invalid_values_before_any_call(self):
        t = FakeTransport()
        with self.assertRaises(ValueError):
            settings.apply(t, {"inline_feedback_share_denominator": 5})
        self.assertEqual(t.calls, [])

    def test_validate(self):
        self.assertEqual(settings.validate({"has_topics_enabled": True, "inline_feedback_share_denominator": 0}), ([], []))
        errors, _ = settings.validate({"has_topics_enabled": "yes", "unknown": True, "inline_query_placeholder": None})
        self.assertEqual(len(errors), 3)
        _, warnings = settings.validate({"needs_inline_query_location": True, "can_communicate_with_bots": True})
        self.assertEqual(len(warnings), 2)

    def test_callback_target_in_every_mode(self):
        inline = _paths.load("examples", "fixtures", "callback_bot_message_inline_mode.json")["callback_query"]
        self.assertEqual(settings.callback_target(inline), {"inline_message_id": "BAAAAKx2nwABOWNSENT"})
        classic = {"id": "1", "message": {"message_id": 5, "date": 0, "chat": {"id": 42, "type": "private"}}}
        self.assertEqual(settings.callback_target(classic), {"chat_id": 42, "message_id": 5})
        with self.assertRaises(ValueError):
            settings.callback_target({"id": "2"})

    def test_commands_for_any_active_username(self):
        self.assertTrue(settings.addressed_to_me("/start@ORDERS_AI", ME))
        self.assertFalse(settings.addressed_to_me("/start@someone_bot", ME))
        self.assertFalse(settings.addressed_to_me("hello @orders_ai", ME))
        self.assertEqual(settings.usernames({"username": "solo_bot"}), ["solo_bot"])

    def test_invites(self):
        self.assertEqual(settings.invite_link(ME), "https://t.me/botinvite/orders_demo_bot")
        msg = _paths.load("examples", "fixtures", "message_write_access_invited.json")["message"]
        self.assertEqual(settings.inviter_of(msg)["id"], 111111111)
        self.assertIsNone(settings.inviter_of({"write_access_allowed": {"from_request": True}}))


if __name__ == "__main__":
    unittest.main()
