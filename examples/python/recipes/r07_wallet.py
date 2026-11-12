"""R07 - Wallet interaction from a widget (Bot API 10.4, production in private chats).

Covers all three WidgetQueryType variants, the profile wallet card, a TON
transfer service message, ton_address entities, and the AreaPosition rename.
The chain check is injected: Telegram's notification is not proof of payment.

Run:  py -3 examples/python/recipes/r07_wallet.py
"""
from __future__ import annotations

import json

import _common as c
from tgkit import wallet
from tgkit.router import Router
from tgkit.text import utf16_offset
from tgkit.transport import FakeTransport
from tgkit.widgets import encode_state

CHAT = 111111111
BOT_ID = 999000111
MERCHANT = "UQAsampleMerchant00000000000000000000000000000005"


class FakeChain:
    """Your indexer/node adapter. Here: answers from a table."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def check(self, **kw):
        self.calls.append(kw)
        return self.verdicts.pop(0)


class FakeSigner:
    def verify(self, *, sign_data_json, public_key_hex, expected_domain):
        return json.loads(sign_data_json).get("domain") == expected_domain   # + real ed25519 check


def run(verdicts=("pending", "confirmed"), transport: FakeTransport | None = None):
    t = transport or FakeTransport()
    order = wallet.Order(order_id="42", user_id=CHAT, amount_nano=1_250_000_000, merchant_address=MERCHANT)
    chain = FakeChain(verdicts)
    msg = t.call("sendWidget", {"chat_id": CHAT, "html": c.widget_html("wallet-pay.html"),
                                "caption": "Order #42 · 1.25 TON", "allow_queries": True,
                                "chat_data": encode_state({"o": "42", "amt": "1.25 TON", "st": "new", "r": 0})})
    rev = [0]

    def push_state():
        rev[0] += 1
        t.call("editMessageWidgetData", {"chat_id": CHAT, "message_id": msg["message_id"],
                                         "chat_data": encode_state({"o": "42", "amt": "1.25 TON",
                                                                    "st": order.state.value, "r": rev[0]})})

    def answer(q, data):
        t.call("answerWidgetQuery", {"widget_query_id": q["id"], "data": json.dumps(data, separators=(",", ":"))})

    router = Router()

    @router.on("widget_query")
    def on_query(q):
        if q["from"]["id"] != order.user_id:
            return answer(q, {"ok": False, "err": "not_your_order"})
        kind = q["type"]["type"]
        if kind == "data" and q["data"] == f"pay:{order.order_id}":
            card = q["type"].get("wallet_card")           # profile card; the payer may differ
            tx = wallet.transaction_request(order, now=1762900000)
            return answer(q, {"ok": True, "tx": tx, "card": wallet.wallet_card_summary(card)})
        if kind == "sent_transaction":
            result = wallet.on_sent_transaction(order, q, chain)
            push_state()
            return answer(q, {**result, "s": {"o": "42", "amt": "1.25 TON", "st": order.state.value, "r": rev[0]}})
        if kind == "sign_data":
            return answer(q, wallet.on_sign_data(q, FakeSigner(), bot_id=BOT_ID))
        return answer(q, {"ok": False, "err": "unknown"})

    router.dispatch(c.fixture("widget_query_wallet_data.json"))
    router.dispatch(c.fixture("widget_query_sent_transaction.json"))
    # Later: your chain watcher confirms the transfer and pushes the new state.
    if order.state == wallet.OrderState.AWAITING_CONFIRMATION:
        verdict = chain.check(msg_hash=order.msg_hashes[-1], sender="", recipient=MERCHANT,
                              amount_nano=order.amount_nano, order_id=order.order_id)
        if verdict == "confirmed":
            order.state = wallet.OrderState.PAID
            push_state()
    router.dispatch(c.fixture("widget_query_sign_data.json"))
    return t, order, chain


def main() -> None:
    t, order, chain = run()
    c.dump(t, "Wallet payment")
    first = json.loads(t.params_of("answerWidgetQuery")[0]["data"])
    tx = first["tx"]
    c.check(tx["messages"][0] == {"address": MERCHANT, "amount": "1250000000"} and "from" not in tx,
            "transaction request: nanotons as a decimal string, no 'from'")
    second = json.loads(t.params_of("answerWidgetQuery")[1]["data"])
    c.check(second["state"] == "awaiting", "sent_transaction -> 'awaiting', not 'paid'")
    states = [json.loads(p["chat_data"])["st"] for p in t.params_of("editMessageWidgetData")]
    c.check(states == ["awaiting", "paid"], "paid only after the chain check")
    third = json.loads(t.params_of("answerWidgetQuery")[2]["data"])
    c.check(third["ok"] is True, "sign_data verified for domain bot<bot_id>")

    t2, order2, _ = run(verdicts=("mismatch",))
    c.check(order2.state == wallet.OrderState.MISMATCH, "a mismatching transfer is never marked paid")

    card = c.fixture("get_chat_result_wallet_theme.json")["result"]["ton_wallet_card"]
    pos = card["stickers"][0]["position"]
    c.check(set(pos) >= {"x_percentage", "y_percentage", "rotation_angle", "corner_radius_percentage"},
            "sticker position parsed as AreaPosition (renamed from StoryAreaPosition)")
    c.check(wallet.wallet_card_summary(card).startswith("Wallet UQAs…0003: 5.25 TON"), "wallet card summary")
    svc = c.fixture("message_ton_wallet_transfer.json")["message"]["ton_wallet_transfer"]
    c.check(wallet.describe_transfer(svc).startswith("Sent 1.25 TON to UQAs…0005 (pending)"),
            "negative amount = outgoing; empty transaction_id = not sent yet")
    m = c.fixture("message_entities_ton_bank.json")["message"]
    ents = {e["type"]: e for e in m["entities"]}
    start = m["text"].index(MERCHANT)
    c.check(ents["ton_address"]["offset"] == utf16_offset(m["text"], start)
            and ents["ton_address"]["length"] == len(MERCHANT),
            "ton_address entity located by UTF-16 offset")


if __name__ == "__main__":
    main()
