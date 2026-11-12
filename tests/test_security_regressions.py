"""Regressions for the Codex security review of PR #4 (2026-11-12)."""
import json
import threading
import unittest

import _paths
from tgkit import wallet
from tgkit.errors import RetryPolicy, TelegramError, call_with_policy
from tgkit.text import split_text, utf16_len
from tgkit.transport import FakeTransport, TelegramErrorResponse

MERCHANT = "UQAsampleMerchant00000000000000000000000000000005"


def order():
    return wallet.Order(order_id="42", user_id=111111111, amount_nano=1_250_000_000, merchant_address=MERCHANT)


class Chain:
    def __init__(self, verdict="pending"):
        self.verdict = verdict

    def check(self, **kw):
        return self.verdict


class Wallet(unittest.TestCase):
    def test_no_reinvoice_after_payment_and_same_request_on_replay(self):
        o = order()
        first = wallet.transaction_request(o, now=1000)
        self.assertEqual(wallet.transaction_request(o, now=1010), first, "replay within validity = same request")
        q = _paths.load("examples", "fixtures", "widget_query_sent_transaction.json")["widget_query"]
        wallet.on_sent_transaction(o, q, Chain("confirmed"))
        self.assertEqual(o.state, wallet.OrderState.PAID)
        self.assertIsNone(wallet.transaction_request(o, now=1020))
        self.assertEqual(o.state, wallet.OrderState.PAID, "a replayed pay: must not reset a paid order")

    def test_one_transfer_cannot_pay_two_orders(self):
        seen = {}
        q = _paths.load("examples", "fixtures", "widget_query_sent_transaction.json")["widget_query"]
        a, b = order(), wallet.Order(order_id="43", user_id=111111111, amount_nano=1_250_000_000, merchant_address=MERCHANT)
        wallet.transaction_request(a, now=1)
        wallet.transaction_request(b, now=1)
        wallet.on_sent_transaction(a, q, Chain(), seen)
        self.assertEqual(wallet.on_sent_transaction(b, q, Chain("confirmed"), seen)["err"], "transfer_already_used")
        self.assertNotEqual(b.state, wallet.OrderState.PAID)

    def test_sent_transaction_without_invoice_is_refused(self):
        q = _paths.load("examples", "fixtures", "widget_query_sent_transaction.json")["widget_query"]
        self.assertEqual(wallet.on_sent_transaction(order(), q, Chain("confirmed"))["err"], "no_invoice")

    def test_sign_data_needs_fresh_single_use_challenge_and_address_binding(self):
        q = _paths.load("examples", "fixtures", "widget_query_sign_data.json")["widget_query"]
        calls = []

        class Verifier:
            def verify(self, **kw):
                calls.append(kw)
                return True

        ch = wallet.SignChallenge(user_id=111111111, nonce="n-7f3a", issued_at=1000)
        self.assertEqual(wallet.on_sign_data(q, Verifier(), bot_id=1, challenge=None, now=1001)["err"], "no_challenge")
        self.assertEqual(wallet.on_sign_data(q, Verifier(), bot_id=1, challenge=ch, now=99999)["err"], "challenge_expired")
        self.assertTrue(wallet.on_sign_data(q, Verifier(), bot_id=1, challenge=ch, now=1001)["ok"])
        kw = calls[-1]
        self.assertEqual(kw["expected_address"], q["type"]["wallet"]["address"])
        self.assertEqual(kw["state_init_b64"], q["type"]["wallet"]["state_init"])
        self.assertEqual(kw["expected_payload"], ch.payload())
        self.assertEqual(wallet.on_sign_data(q, Verifier(), bot_id=1, challenge=ch, now=1002)["err"], "no_challenge")
        other = wallet.SignChallenge(user_id=222222222, nonce="x", issued_at=1000)
        self.assertEqual(wallet.on_sign_data(q, Verifier(), bot_id=1, challenge=other, now=1001)["err"], "no_challenge")


class TextSplit(unittest.TestCase):
    def test_overlong_combining_sequence_terminates(self):
        zalgo = "a" + "́" * 50 + " tail"
        result = {}

        def run():
            result["parts"] = split_text(zalgo, limit=10)

        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(2)
        self.assertFalse(th.is_alive(), "split_text looped forever")
        parts = result["parts"]
        self.assertTrue(all(p for p, _ in parts))
        self.assertTrue(all(utf16_len(p) <= 10 for p, _ in parts))
        self.assertEqual("".join(p for p, _ in parts).replace(" ", ""), zalgo.replace(" ", ""))


class LongFloodWait(unittest.TestCase):
    def test_retry_after_beyond_max_wait_is_not_retried_early(self):
        t = FakeTransport().script("sendMessage", TelegramErrorResponse(429, "Too Many Requests: retry after 120", 120), {"message_id": 1})
        slept = []
        with self.assertRaises(TelegramError) as cm:
            call_with_policy(t, "sendMessage", {}, policy=RetryPolicy(max_wait=60), sleep=slept.append)
        self.assertEqual(cm.exception.retry_after, 120)
        self.assertEqual((len(t.calls), slept), (1, []))


class WalletWidget(unittest.TestCase):
    def test_pay_stays_locked_after_timeout(self):
        html = _paths.read("examples", "widgets", "wallet-pay.html")
        self.assertIn("unsure=true", html)
        self.assertIn("!unsure", html)


if __name__ == "__main__":
    unittest.main()
