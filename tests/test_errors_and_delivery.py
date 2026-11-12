"""Check 6 and 8: 429 never loops tightly; an unknown send outcome is not
blindly repeated; old SDK subscriptions don't drop new updates silently."""
import unittest

import _paths  # noqa: F401
from tgkit.errors import OutcomeUnknown, RetryPolicy, TelegramError, call_with_policy, classify
from tgkit.generation import Generation, execute
from tgkit.router import Router, check_subscription
from tgkit.transport import FakeTransport, TelegramErrorResponse


class RateLimitsAndUncertainty(unittest.TestCase):
    def test_429_waits_retry_after_and_is_bounded(self):
        t = FakeTransport().script("sendMessage", *[TelegramErrorResponse(429, "Too Many Requests: retry after 7", 7)] * 5)
        slept = []
        with self.assertRaises(TelegramError):
            call_with_policy(t, "sendMessage", {"chat_id": 1, "text": "x"}, policy=RetryPolicy(max_attempts=3),
                             sleep=slept.append)
        self.assertEqual(len(t.calls), 3)
        self.assertEqual(slept, [7.0, 7.0])

    def test_429_without_retry_after_still_backs_off(self):
        t = FakeTransport().script("editMessageText", TelegramErrorResponse(429, "Too Many Requests"), True)
        slept = []
        call_with_policy(t, "editMessageText", {}, sleep=slept.append)
        self.assertTrue(slept and slept[0] >= 1.0)

    def test_unknown_outcome_of_send_is_not_repeated(self):
        t = FakeTransport().script("sendMessage", "TIMEOUT", {"message_id": 5})
        with self.assertRaises(OutcomeUnknown):
            call_with_policy(t, "sendMessage", {"chat_id": 1, "text": "order placed"}, sleep=lambda s: None)
        self.assertEqual(len(t.calls), 1, "no automatic second send - it could duplicate")

    def test_unknown_outcome_of_edit_is_retried_and_not_modified_is_success(self):
        t = FakeTransport().script("editMessageText", "TIMEOUT",
                                   TelegramErrorResponse(400, "Bad Request: message is not modified"))
        self.assertTrue(call_with_policy(t, "editMessageText", {}, sleep=lambda s: None))
        self.assertEqual(len(t.calls), 2)

    def test_validation_and_permission_are_not_retried(self):
        for err in (TelegramErrorResponse(400, "Bad Request: can't parse entities"),
                    TelegramErrorResponse(403, "Forbidden: bot was blocked by the user")):
            t = FakeTransport().script("sendMessage", err, True)
            with self.assertRaises(TelegramError):
                call_with_policy(t, "sendMessage", {}, sleep=lambda s: None)
            self.assertEqual(len(t.calls), 1)

    def test_classification(self):
        self.assertEqual(classify(400, "Bad Request: chat not found"), "validation")
        self.assertEqual(classify(404, "Not Found"), "unsupported")
        self.assertEqual(classify(400, "Bad Request: not enough rights to send widgets"), "permission")
        self.assertEqual(classify(400, "Bad Request: query is too old and response timeout expired"), "query_too_old")

    def test_final_ai_answer_policy_on_unknown_outcome(self):
        t = FakeTransport().script("sendRichMessage", "TIMEOUT")
        g = Generation(op_id="o", chat_id=1, draft_id=3)
        g.start(0.0)
        eff = g.on_done(1.0)
        with self.assertRaises(OutcomeUnknown):
            execute(eff, t, g, now=1.0)              # default: surface, let the caller reconcile
        t2 = FakeTransport().script("sendRichMessage", "TIMEOUT")
        execute(eff, t2, g, now=1.0, on_unknown="retry_once")
        self.assertEqual(t2.methods(), ["sendRichMessage", "sendRichMessage"], "explicit, bounded, logged")

    def test_rich_validation_falls_back_once_to_plain_same_address(self):
        t = FakeTransport().script("sendRichMessage", TelegramErrorResponse(400, "Bad Request: RICH_MESSAGE_INVALID"))
        g = Generation(op_id="o", chat_id=1, draft_id=3, message_thread_id=4)
        g.start(0.0)
        execute(g.on_chunk("Answer.", 0.5) + g.on_done(1.0), t, g, now=1.0)
        plain = t.params_of("sendMessage")
        self.assertEqual(len(plain), 1)
        self.assertEqual((plain[0]["chat_id"], plain[0]["message_thread_id"]), (1, 4))


class UpdateDelivery(unittest.TestCase):
    def test_sticky_and_partial_subscriptions_are_reported(self):
        handled = ["callback_query", "message", "shared_widget_query", "stopped_message_generation", "widget_query"]
        self.assertTrue(check_subscription(None, handled)[0].startswith("<allowed_updates not passed"))
        self.assertEqual(check_subscription(["message", "callback_query"], handled),
                         ["shared_widget_query", "stopped_message_generation", "widget_query"])
        self.assertEqual(check_subscription([], handled), [])

    def test_unknown_update_type_is_recorded_not_silently_dropped(self):
        events = []
        r = Router(log=events.append)
        r.on("message")(lambda m: "ok")
        r.dispatch(_paths.load("examples", "fixtures", "widget_query_ship.json"))
        self.assertEqual(r.unhandled, ["widget_query"])
        self.assertEqual(events[0]["type"], "widget_query")


if __name__ == "__main__":
    unittest.main()
