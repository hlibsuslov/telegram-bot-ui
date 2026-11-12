"""Check 5: a personal fallback never becomes public; two members never see
each other's data; ownership is re-checked on the server."""
import random
import unittest

import _paths
from tgkit.ephemeral import AudienceViolation, PersonalPanels, ephemeral_params, guard_audience
from tgkit.transport import FakeTransport, TelegramErrorResponse

DATA = {111111111: "SECRET-A", 222222222: "SECRET-B"}
render = lambda uid: f"Balance: {DATA.get(uid, 'none')}"   # noqa: E731


def public_sends(t):
    return [p for m, p in t.calls if m.startswith("send") and "ephemeral_message_parameters" not in p]


class Audience(unittest.TestCase):
    def cq(self, name):
        return _paths.load("examples", "fixtures", name)["callback_query"]

    def test_every_failure_class_keeps_audience(self):
        failures = [TelegramErrorResponse(400, "Bad Request: wrong parameters"),
                    TelegramErrorResponse(403, "Forbidden: not enough rights"),
                    TelegramErrorResponse(429, "Too Many Requests: retry after 9", 9),
                    TelegramErrorResponse(500, "Internal Server Error"), "TIMEOUT"]
        for failure in failures:
            for text in (render, lambda uid: "x" * 300 + str(DATA[uid])):
                t = FakeTransport().script("sendMessage", failure)
                p = PersonalPanels(t, bot_username="demo_bot")
                p.show(self.cq("callback_card_user_a.json"), text)
                self.assertEqual(public_sends(t), [], f"{failure}: public send")
                self.assertNotIn("SECRET-B", str(t.calls))

    def test_two_members_isolated_under_random_interleaving(self):
        rng = random.Random(7)
        for _ in range(50):
            t = FakeTransport()
            p = PersonalPanels(t, bot_username="demo_bot")
            events = ["a", "b", "a_btn", "b_btn"] * 3
            rng.shuffle(events)
            for e in events:
                if e == "a":
                    p.show(self.cq("callback_card_user_a.json"), render)
                elif e == "b":
                    p.show(self.cq("callback_card_user_b.json"), render, api="10.3")
                elif e == "a_btn":
                    p.on_panel_button(self.cq("callback_panel_owner.json"), render)
                else:
                    p.on_panel_button(self.cq("callback_panel_crafted.json"), render)   # B on A's panel
            for m, params in t.calls:
                eph = params.get("ephemeral_message_parameters") or {}
                text = params.get("text", "")
                if "SECRET-A" in text:
                    self.assertIn(eph.get("callback_query_id"), ("4382000000000000001", None))
                    if m.startswith("edit"):
                        self.assertEqual(params["receiver_user_id"], 111111111)
                if "SECRET-B" in text:
                    self.assertTrue(eph.get("receiver_user_id") == 222222222 or params.get("receiver_user_id") == 222222222)
            self.assertEqual(public_sends(t), [])

    def test_guard(self):
        with self.assertRaises(AudienceViolation):
            guard_audience("sendMessage", {"chat_id": -100, "text": "x"}, personal=True, owner_id=1)
        with self.assertRaises(AudienceViolation):
            guard_audience("sendMessage", {"ephemeral_message_parameters": {"receiver_user_id": 2}}, personal=True, owner_id=1)
        guard_audience("sendMessage", {"chat_id": 1, "text": "x"}, personal=True, owner_id=1)   # own private chat

    def test_replace_from_ephemeral_rejected(self):
        with self.assertRaises(ValueError):
            ephemeral_params(self.cq("callback_panel_owner.json"), replace_original=True)

    def test_10_3_form_needs_chat(self):
        with self.assertRaises(ValueError):
            ephemeral_params(self.cq("callback_inline_message.json"), api="10.3")


if __name__ == "__main__":
    unittest.main()
