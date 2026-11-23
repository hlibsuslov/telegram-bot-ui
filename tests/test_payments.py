"""tgkit.payments (Stars rail) on FakeTransport: idempotent delivery, pre-checkout
gates, multi-use invoices, admin refunds, subscriptions, reconciliation."""
import unittest

import _paths
import tg_api_lookup as lookup
import validate_payload as vp
from tgkit.payments import (NANO, ReconReport, Product, RefundPolicy, SqliteStore, StarsPayments, check_rail,
                            parse_payload, sign_payload)
from tgkit.transport import FakeTransport, TelegramErrorResponse

V = vp.Validator(lookup.Api().cat)
SECRET = b"test-only-secret-0123456789"
ADMIN, OLENA, PETRO, GROUP = 900, 111111111, 222222222, -1001234567890
T0 = 1_763_200_000


def catalog(**over):
    base = {
        "credits50": Product("credits50", "digital", {"en": "50 AI credits", "uk": "50 кредитів"},
                             {"en": "Credits for longer answers.", "uk": "Кредити для довших відповідей."}, 250),
        "pro": Product("pro", "subscription", {"en": "Pro plan"}, {"en": "Unlimited answers. Renews every 30 days."}, 300),
        "guide": Product("guide", "digital", {"en": "PDF guide"}, {"en": "A 40-page guide."}, 100, stock=5),
    }
    base.update(over)
    return base


class Bot:
    """One payments runtime with a controllable clock."""

    def __init__(self, products=None, **kw):
        self.clock = [T0]
        self.t = FakeTransport()
        self.t.script("createInvoiceLink", *[f"https://t.me/$link{i}" for i in range(20)])
        self.store = SqliteStore()
        self.pay = StarsPayments(self.t, self.store, products or catalog(), secret=SECRET, admins={ADMIN},
                                 admin_chat_id=ADMIN, now=lambda: self.clock[0], **kw)
        self.uid = 1

    def update(self, **body):
        self.uid += 1
        return {"update_id": 500000 + self.uid, **body}

    def pre_checkout(self, user, payload, amount, lang="en"):
        u = self.update(pre_checkout_query={
            "id": f"pcq{self.uid}", "from": {"id": user, "is_bot": False, "first_name": "U", "language_code": lang},
            "currency": "XTR", "total_amount": amount, "invoice_payload": payload})
        self.pay.handle(u)
        return u

    def paid(self, user, payload, amount, charge, chat=None, **extra):
        u = self.update(message={
            "message_id": self.uid, "date": self.clock[0],
            "chat": {"id": chat or user, "type": "private" if not chat else "supergroup"},
            "from": {"id": user, "is_bot": False, "first_name": "U"},
            "successful_payment": {"currency": "XTR", "total_amount": amount, "invoice_payload": payload,
                                   "telegram_payment_charge_id": charge, "provider_payment_charge_id": charge,
                                   **extra}})
        self.pay.handle(u)
        return u

    def answers(self):
        return self.t.params_of("answerPreCheckoutQuery")

    def texts(self, chat):
        return [p["text"] for p in self.t.params_of("sendMessage") if p["chat_id"] == chat]

    def buy(self, user, product="credits50", charge="stx1"):
        order = self.pay.invoice(user, user, product)
        self.pre_checkout(user, order.payload, order.amount)
        self.paid(user, order.payload, order.amount, charge)
        return order

    def tap(self, user, data):
        u = self.update(callback_query={"id": f"cq{self.uid}", "from": {"id": user, "is_bot": False, "first_name": "A"},
                                        "chat_instance": "1", "data": data,
                                        "message": {"message_id": 5, "date": 0, "chat": {"id": ADMIN, "type": "private"}}})
        self.pay.handle(u)


class WireShape(unittest.TestCase):
    def test_every_call_matches_the_bot_api_snapshot(self):
        b = Bot()
        b.buy(OLENA)
        b.pay.subscription_link(OLENA, "pro")
        b.pay.offer(GROUP, "credits50")
        b.pay.request_refund("stx1", by=ADMIN, reason="duplicate purchase")
        b.tap(ADMIN, "rf:ok:1")
        b.t.script("getStarTransactions", {"transactions": []})
        b.pay.reconcile(since=T0 - 10, until=T0 + 10)
        for method, params in b.t.calls:
            with self.subTest(method=method):
                rep = V.check_request(method, params)
                self.assertTrue(rep.ok, rep.errors)

    def test_payload_is_signed_and_short(self):
        p = sign_payload(SECRET, "ord", "a" * 12)
        self.assertLessEqual(len(p.encode()), 128)
        self.assertEqual(parse_payload(SECRET, p), ("ord", "a" * 12))
        self.assertIsNone(parse_payload(b"another-secret-0123456789", p))
        self.assertIsNone(parse_payload(SECRET, p[:-1] + ("0" if p[-1] != "0" else "1")))
        with self.assertRaises(ValueError):
            sign_payload(SECRET, "ord", "x" * 120)

    def test_stars_invoice_has_one_price_and_pay_first(self):
        b = Bot()
        b.pay.invoice(OLENA, OLENA, "credits50", "uk")
        inv = b.t.params_of("sendInvoice")[0]
        self.assertEqual(inv["currency"], "XTR")
        self.assertEqual(len(inv["prices"]), 1)
        self.assertTrue(inv["reply_markup"]["inline_keyboard"][0][0]["pay"])
        self.assertNotIn("start_parameter", inv)
        self.assertEqual(inv["title"], "50 кредитів")


class RailPolicy(unittest.TestCase):
    def test_digital_for_gram_or_card_is_refused_with_stars_path(self):
        for rail in ("GRAM", "TON", "USD"):
            for kind in ("digital", "subscription", "paid_media"):
                v = check_rail(kind, rail)
                self.assertFalse(v.ok, (kind, rail))
                self.assertIn("Stars", v.warning)
                self.assertEqual(v.suggest, "XTR")

    def test_owner_may_accept_the_risk_but_the_warning_stays(self):
        v = check_rail("digital", "GRAM", owner_accepts_risk=True)
        self.assertTrue(v.ok)
        self.assertTrue(v.warning)
        self.assertFalse(check_rail("subscription", "GRAM", owner_accepts_risk=True).ok)   # XTR-only in the API

    def test_physical_and_donations_may_use_gram(self):
        for kind in ("physical", "donation"):
            self.assertTrue(check_rail(kind, "GRAM").ok)
            self.assertEqual(check_rail(kind, "GRAM").warning, "")

    def test_money_is_integers(self):
        with self.assertRaises(ValueError):
            Product("x", "digital", {"en": "X"}, {"en": "X"}, 2.5)
        with self.assertRaises(ValueError):
            Product("x", "subscription", {"en": "X"}, {"en": "X"}, 10_001)


class PreCheckout(unittest.TestCase):
    def test_ok_answer_is_the_only_call_and_comes_first(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        before = len(b.t.calls)
        b.pre_checkout(OLENA, order.payload, 250)
        self.assertEqual(b.t.methods()[before:], ["answerPreCheckoutQuery"])
        self.assertTrue(b.answers()[0]["ok"])
        self.assertEqual(b.store.get_order(order.id).status, "pre_checkout")

    def test_forged_payload_is_declined(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        forged = order.payload[:-4] + "beef"
        b.pre_checkout(OLENA, forged, 250)
        b.pre_checkout(OLENA, sign_payload(b"attacker-secret-0123456789", "ord", order.id), 250)
        b.pre_checkout(OLENA, "ord:" + order.id, 250)
        self.assertEqual([a["ok"] for a in b.answers()], [False, False, False])
        self.assertIn("no longer valid", b.answers()[0]["error_message"])
        self.assertEqual(b.store.get_order(order.id).status, "invoiced")

    def test_someone_elses_order_is_declined_and_left_alone(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.pre_checkout(PETRO, order.payload, 250, lang="ru")      # a forwarded personal invoice
        a = b.answers()[0]
        self.assertFalse(a["ok"])
        self.assertIn("другому человеку", a["error_message"])
        self.assertEqual(b.store.get_order(order.id).status, "invoiced")
        b.pre_checkout(OLENA, order.payload, 250)
        self.assertTrue(b.answers()[1]["ok"])

    def test_tampered_amount_is_declined(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.pre_checkout(OLENA, order.payload, 1)
        self.assertFalse(b.answers()[0]["ok"])

    def test_changed_price_declines_then_sends_a_new_invoice(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.pay.catalog["credits50"] = Product("credits50", "digital", {"en": "50 AI credits"}, {"en": "Credits."}, 300)
        before = len(b.t.calls)
        b.pre_checkout(OLENA, order.payload, 250)
        self.assertEqual(b.t.methods()[before:], ["answerPreCheckoutQuery", "sendInvoice"])   # answer first
        a = b.answers()[0]
        self.assertFalse(a["ok"])
        self.assertIn("⭐300", a["error_message"])
        self.assertEqual(b.t.params_of("sendInvoice")[-1]["prices"][0]["amount"], 300)
        self.assertEqual(b.store.get_order(order.id).status, "declined")

    def test_expired_order_is_declined(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.clock[0] += 3601
        b.pre_checkout(OLENA, order.payload, 250)
        self.assertFalse(b.answers()[0]["ok"])
        self.assertIn("expired", b.answers()[0]["error_message"])
        self.assertEqual(b.store.get_order(order.id).status, "expired")

    def test_store_failure_still_answers(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.store.get_order = lambda _id: (_ for _ in ()).throw(RuntimeError("db down"))
        b.pre_checkout(OLENA, order.payload, 250)
        self.assertFalse(b.answers()[0]["ok"])
        self.assertIn("no Stars were charged", b.answers()[0]["error_message"])

    def test_stock_reservation_and_sold_out(self):
        b = Bot(products=catalog(guide=Product("guide", "digital", {"en": "PDF guide"}, {"en": "Guide."}, 100, stock=1)))
        first = b.pay.invoice(OLENA, OLENA, "guide")
        second = b.pay.invoice(PETRO, PETRO, "guide")
        b.pre_checkout(OLENA, first.payload, 100)
        b.pre_checkout(PETRO, second.payload, 100)
        self.assertEqual([a["ok"] for a in b.answers()], [True, False])
        self.assertIn("sold out", b.answers()[1]["error_message"])


class Delivery(unittest.TestCase):
    def test_double_delivery_of_the_update_delivers_once(self):
        b = Bot()
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.pre_checkout(OLENA, order.payload, 250)
        u = b.paid(OLENA, order.payload, 250, "stxAbC")
        b.pay.handle(u)                                            # same update_id again
        b.paid(OLENA, order.payload, 250, "stxAbC")                # same charge, new update_id
        self.assertEqual(len(b.texts(OLENA)), 1)
        self.assertIn("Paid ⭐250", b.texts(OLENA)[0])
        self.assertEqual(b.store.get_order(order.id).status, "delivered")
        self.assertTrue(b.pay.has_access(OLENA, "credits50"))
        self.assertEqual(b.store.balance("bot:stars"), 250 * NANO)
        self.assertEqual(b.store.db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0], 1)

    def test_on_deliver_hook_runs_once(self):
        calls = []
        b = Bot(on_deliver=lambda o, p, pay: calls.append(pay.charge_id))
        order = b.buy(OLENA, charge="stxH")
        b.paid(OLENA, order.payload, 250, "stxH")
        self.assertEqual(calls, ["stxH"])

    def test_crash_before_delivered_is_resumed_on_redelivery(self):
        b = Bot()
        boom = [True]

        def hook(*_):
            if boom[0]:
                boom[0] = False
                raise RuntimeError("worker died")
        b.pay.on_deliver = hook
        order = b.pay.invoice(OLENA, OLENA, "credits50")
        b.pre_checkout(OLENA, order.payload, 250)
        with self.assertRaises(RuntimeError):
            b.paid(OLENA, order.payload, 250, "stxR")
        self.assertEqual(b.store.get_order(order.id).status, "paid")
        b.paid(OLENA, order.payload, 250, "stxR")
        self.assertEqual(b.store.get_order(order.id).status, "delivered")
        self.assertEqual(len(b.texts(OLENA)), 1)

    def test_payment_without_order_is_not_delivered(self):
        b = Bot()
        b.paid(OLENA, "ord:ffffffffffff.0000000000000000", 250, "stxX")
        self.assertFalse(b.pay.has_access(OLENA, "credits50"))
        self.assertEqual(b.texts(OLENA), [])
        self.assertIn("matches no open order", b.texts(ADMIN)[0])
        self.assertIsNotNone(b.store.get_payment("stxX"))         # the money is still recorded

    def test_multi_use_invoice_in_a_group_is_one_order_per_payment(self):
        b = Bot()
        offer = b.pay.offer(GROUP, "credits50")
        for user, charge in ((OLENA, "stxG1"), (PETRO, "stxG2")):
            b.pre_checkout(user, offer.payload, 250)
            b.paid(user, offer.payload, 250, charge, chat=GROUP)
        b.paid(PETRO, offer.payload, 250, "stxG2", chat=GROUP)    # re-delivered
        orders = b.store.db.execute("SELECT user_id, status FROM orders WHERE offer_id = ? ORDER BY user_id",
                                    (offer.id,)).fetchall()
        self.assertEqual([tuple(r) for r in orders], [(OLENA, "delivered"), (PETRO, "delivered")])
        self.assertTrue(b.pay.has_access(OLENA, "credits50") and b.pay.has_access(PETRO, "credits50"))
        self.assertEqual(len(b.texts(PETRO)), 1)
        self.assertEqual(b.texts(GROUP), [])                      # receipts go to the payer, not the group


class Refunds(unittest.TestCase):
    def test_admin_refund_with_confirmation_and_repeat(self):
        b = Bot()
        order = b.buy(OLENA, charge="stxRf")
        refund = b.pay.request_refund("stxRf", by=ADMIN, reason="charged twice")
        self.assertEqual(refund.status, "requested")
        card = b.t.params_of("sendMessage")[-1]
        self.assertIn("whole-payment only", card["text"])
        self.assertEqual(card["reply_markup"]["inline_keyboard"][0][0]["callback_data"], f"rf:ok:{refund.id}")
        self.assertNotIn("refundStarPayment", b.t.methods())     # nothing happens before the confirmation

        b.tap(PETRO, f"rf:ok:{refund.id}")                        # not an admin
        self.assertNotIn("refundStarPayment", b.t.methods())
        self.assertTrue(b.t.params_of("answerCallbackQuery")[-1]["show_alert"])

        b.tap(ADMIN, f"rf:ok:{refund.id}")
        b.tap(ADMIN, f"rf:ok:{refund.id}")                        # double tap
        self.assertEqual(b.t.params_of("refundStarPayment"),
                         [{"user_id": OLENA, "telegram_payment_charge_id": "stxRf"}])
        self.assertEqual(b.store.get_order(order.id).status, "refunded")
        self.assertFalse(b.pay.has_access(OLENA, "credits50"))

        b.pay.handle(b.update(message={"message_id": 9, "date": T0, "chat": {"id": OLENA, "type": "private"},
                                       "refunded_payment": {"currency": "XTR", "total_amount": 250,
                                                            "invoice_payload": order.payload,
                                                            "telegram_payment_charge_id": "stxRf"}}))
        refund_msgs = [x for x in b.texts(OLENA) if "returned" in x]
        self.assertEqual(len(refund_msgs), 1)                     # told once
        self.assertIsNone(b.pay.request_refund("stxRf", by=ADMIN, reason="again"))
        self.assertEqual(len(b.t.params_of("refundStarPayment")), 1)
        self.assertEqual(b.store.balance("bot:stars"), 0)

    def test_only_admin_or_payer_may_ask(self):
        b = Bot()
        b.buy(OLENA, charge="stxP")
        with self.assertRaises(PermissionError):
            b.pay.request_refund("stxP", by=PETRO, reason="x")

    def test_cancel_keeps_the_payment(self):
        b = Bot()
        order = b.buy(OLENA, charge="stxC")
        refund = b.pay.request_refund("stxC", by=ADMIN, reason="x")
        b.tap(ADMIN, f"rf:no:{refund.id}")
        self.assertEqual(b.store.get_order(order.id).status, "delivered")
        self.assertTrue(b.pay.has_access(OLENA, "credits50"))
        self.assertIsNotNone(b.pay.request_refund("stxC", by=ADMIN, reason="asked again"))

    def test_refusal_returns_order_to_delivered(self):
        b = Bot()
        order = b.buy(OLENA, charge="stxF")
        b.t.script("refundStarPayment", TelegramErrorResponse(400, "Bad Request: CHARGE_ALREADY_REFUNDED"))
        refund = b.pay.request_refund("stxF", by=ADMIN, reason="x")
        b.tap(ADMIN, f"rf:ok:{refund.id}")
        self.assertEqual(b.store.get_order(order.id).status, "delivered")
        self.assertEqual(b.store.get_refund(refund.id).status, "failed")
        self.assertIn("code 400", b.t.params_of("editMessageText")[-1]["text"])

    def test_auto_rule_is_off_by_default_and_works_when_on(self):
        b = Bot()
        b.buy(OLENA, charge="stxA")
        b.pay.request_refund("stxA", by=OLENA, reason="changed my mind")
        self.assertNotIn("refundStarPayment", b.t.methods())     # goes to the admin queue

        b2 = Bot(refund_policy=RefundPolicy(auto_within_s=3600, is_used=lambda p: False))
        order = b2.buy(OLENA, charge="stxA2")
        r = b2.pay.request_refund("stxA2", by=OLENA, reason="changed my mind")
        self.assertEqual(r.status, "done")
        self.assertEqual(r.approved_by, 0)
        self.assertEqual(b2.store.get_order(order.id).status, "refunded")


class Subscriptions(unittest.TestCase):
    def subscribe(self, b):
        b.pay.subscription_link(OLENA, "pro")
        order_id = b.store.db.execute("SELECT id FROM orders WHERE product_id = 'pro'").fetchone()[0]
        order = b.store.get_order(order_id)
        b.pre_checkout(OLENA, order.payload, 300)
        b.paid(OLENA, order.payload, 300, "stxS1", is_recurring=True, is_first_recurring=True,
               subscription_expiration_date=T0 + 2_592_000)
        return order

    def test_link_is_a_30_day_stars_subscription(self):
        b = Bot()
        b.pay.subscription_link(OLENA, "pro")
        p = b.t.params_of("createInvoiceLink")[0]
        self.assertEqual((p["subscription_period"], p["currency"]), (2_592_000, "XTR"))

    def test_access_by_expires_at_and_renewal(self):
        b = Bot()
        order = self.subscribe(b)
        self.assertTrue(b.pay.has_access(OLENA, "pro"))
        b.pay.handle(b.update(subscription={"user": {"id": OLENA, "is_bot": False, "first_name": "O"},
                                            "invoice_payload": order.payload, "state": "canceled"}))
        self.assertTrue(b.pay.has_access(OLENA, "pro"))           # cancelled: paid period still runs
        b.clock[0] = T0 + 2_592_001
        self.assertFalse(b.pay.has_access(OLENA, "pro"))
        b.paid(OLENA, order.payload, 300, "stxS2", is_recurring=True,
               subscription_expiration_date=T0 + 2 * 2_592_000)
        b.paid(OLENA, order.payload, 300, "stxS2", is_recurring=True,
               subscription_expiration_date=T0 + 2 * 2_592_000)  # re-delivered renewal
        self.assertTrue(b.pay.has_access(OLENA, "pro"))
        self.assertEqual(sum("renewed" in x for x in b.texts(OLENA)), 1)
        self.assertEqual(b.store.subscription_for_order(order.id).expires_at, T0 + 2 * 2_592_000)

    def test_failed_renewal_sends_one_message(self):
        b = Bot()
        order = self.subscribe(b)
        failed = {"user": {"id": OLENA, "is_bot": False, "first_name": "O", "language_code": "ru"},
                  "invoice_payload": order.payload, "state": "failed"}
        for _ in range(3):
            b.pay.handle(b.update(subscription=failed))
        notes = [p for p in b.t.params_of("sendMessage") if "не прошла" in p["text"]]
        self.assertEqual(len(notes), 1)
        self.assertIn("2025-12-15", notes[0]["text"])            # the date access stops
        button = notes[0]["reply_markup"]["inline_keyboard"][0][0]
        self.assertTrue(button["url"].startswith("https://t.me/$"))
        self.assertIn("Продлить", button["text"])
        self.assertTrue(b.pay.has_access(OLENA, "pro"))           # until expires_at

    def test_update_for_another_user_is_ignored(self):
        b = Bot()
        order = self.subscribe(b)
        b.pay.handle(b.update(subscription={"user": {"id": PETRO, "is_bot": False, "first_name": "P"},
                                            "invoice_payload": order.payload, "state": "failed"}))
        self.assertEqual(b.store.subscription_for_order(order.id).state, "active")


def tx(id_, amount, date, nano=0, **partner):
    t = {"id": id_, "amount": amount, "date": date}
    if nano:
        t["nanostar_amount"] = nano
    t.update(partner)
    return t


def user_in(uid=OLENA):
    return {"source": {"type": "user", "transaction_type": "invoice_payment",
                       "user": {"id": uid, "is_bot": False, "first_name": "U"}}}


def user_out(uid=OLENA):
    return {"receiver": {"type": "user", "transaction_type": "invoice_payment",
                         "user": {"id": uid, "is_bot": False, "first_name": "U"}}}


class Reconciliation(unittest.TestCase):
    def test_chargeback_missing_and_paging(self):
        b = Bot()
        b.buy(OLENA, charge="stxK1")
        b.buy(PETRO, charge="stxK2")
        b.buy(OLENA, "guide", charge="stxK3")                     # never shows up in Telegram
        statement = [
            tx("old", 5, T0 - 100, **user_in()),                  # before the period
            tx("stxK1", 250, T0 + 1, **user_in()),
            tx("stxK2", 250, T0 + 2, **user_in(PETRO)),
            tx("stxZZ", 40, T0 + 3, nano=500_000_000, **user_in()),   # paid here, unknown to us
            tx("wd1", 1000, T0 + 4, receiver={"type": "fragment"}),
            tx("stxK1", 250, T0 + 5, **user_out()),               # outgoing, never refunded by us
            tx("late", 7, T0 + 99_999, **user_in()),              # after the period
        ]
        pages = [{"transactions": statement[i:i + 2]} for i in range(0, len(statement), 2)]
        b.t.script("getStarTransactions", *pages)
        r = b.pay.reconcile(since=T0, until=T0 + 1000, page_size=2)
        self.assertEqual([p["offset"] for p in b.t.params_of("getStarTransactions")], [0, 2, 4, 6])
        self.assertEqual(r.matched, 2)
        self.assertEqual(r.missing_here, ["stxZZ"])
        self.assertEqual(r.missing_there, ["stxK3"])
        self.assertEqual(r.chargebacks, ["stxK1"])
        self.assertEqual(r.other, ["wd1"])
        self.assertEqual(r.diff_nano, 40 * NANO + 500_000_000 - 100 * NANO)
        self.assertEqual(r.next_offset, 6)
        self.assertFalse(r.clean)
        order = b.store.get_order(b.store.get_payment("stxK1").order_id)
        self.assertEqual(order.status, "chargeback")
        self.assertFalse(b.pay.has_access(OLENA, "credits50"))
        self.assertIn("1 chargeback", b.texts(ADMIN)[-1])
        run = b.store.db.execute("SELECT matched, missing_here, missing_there, chargebacks FROM reconciliation_runs").fetchone()
        self.assertEqual(tuple(run), (2, 1, 1, 1))

    def test_lost_refund_answer_is_settled_by_the_statement(self):
        b = Bot()
        order = b.buy(OLENA, charge="stxU")
        b.t.script("refundStarPayment", "TIMEOUT")
        refund = b.pay.request_refund("stxU", by=ADMIN, reason="x")
        b.tap(ADMIN, f"rf:ok:{refund.id}")
        self.assertEqual(b.store.get_refund(refund.id).status, "unknown")
        self.assertEqual(b.store.get_order(order.id).status, "refund_requested")
        b.t.script("getStarTransactions", {"transactions": [tx("stxU", 250, T0, **user_in()),
                                                            tx("stxU", 250, T0 + 1, **user_out())]})
        r = b.pay.reconcile(since=T0, until=T0 + 10)
        self.assertEqual((r.refunds_settled, r.chargebacks), (1, []))
        self.assertTrue(r.clean)
        self.assertEqual(b.store.get_order(order.id).status, "refunded")
        self.assertEqual(len(b.t.params_of("refundStarPayment")), 1)   # never retried blindly

    def test_clean_day(self):
        b = Bot()
        b.buy(OLENA, charge="stxOK")
        b.t.script("getStarTransactions", {"transactions": [tx("stxOK", 250, T0, **user_in())]})
        r = b.pay.reconcile(since=T0, until=T0 + 10)
        self.assertIsInstance(r, ReconReport)
        self.assertTrue(r.clean)
        self.assertEqual(b.texts(ADMIN), [])


if __name__ == "__main__":
    unittest.main()
