"""TON wallet flows started from a widget (Bot API 10.4).

What Telegram gives the bot (widget_query.type):
* {"type": "data", "wallet_card": TonWalletCard?} - a request sent with
  {wallet: true}: the user's profile wallet card (address, balance, stickers).
* {"type": "sign_data", "wallet": WidgetQueryWallet, "sign_data": "<json>"} -
  TON Connect signData result, signed for the domain "bot<bot_id>".
* {"type": "sent_transaction", "wallet": WidgetQueryWallet, "msg_hash": "..."} -
  the wallet *says* it sent a message.

Boundary (no invented guarantees):
* `from` is authenticated by Telegram - who tapped is reliable.
* `sent_transaction` is a notification, NOT proof of payment. The order becomes
  "awaiting confirmation"; only an on-chain check (sender, recipient, amount,
  comment/payload, success) moves it to "paid". That check is the bot's job,
  through its own TON indexer/node - outside Telegram.
* `sign_data` must be verified by the bot: ed25519 signature with the wallet's
  public_key, domain bot<bot_id>, fresh timestamp, and the public key tied to
  the address on chain (state_init). The standard library has no ed25519, so
  the verifier is injected.
* The wallet that pays is the device's wallet; it can differ from the profile
  wallet card. Never put `from` in the transaction.
* After a TIMEOUT the payment may have gone out: never ask to pay again
  blindly - show the order's server state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class OrderState(str, Enum):
    NEW = "new"
    INVOICED = "invoiced"                 # a transaction request was handed out
    AWAITING_CONFIRMATION = "awaiting"    # wallet reported sent_transaction
    PAID = "paid"                         # verified on chain
    MISMATCH = "mismatch"                 # chain says something else
    EXPIRED = "expired"


@dataclass
class Order:
    order_id: str
    user_id: int
    amount_nano: int
    merchant_address: str
    state: OrderState = OrderState.NEW
    valid_until: int = 0
    msg_hashes: list[str] = field(default_factory=list)


class ChainVerifier(Protocol):
    def check(self, *, msg_hash: str, sender: str, recipient: str,
              amount_nano: int, order_id: str) -> str:
        """Return 'confirmed', 'pending', or 'mismatch'."""


class SignatureVerifier(Protocol):
    def verify(self, *, sign_data_json: str, public_key_hex: str, expected_domain: str) -> bool: ...


def transaction_request(order: Order, *, now: int, ttl: int = 300) -> dict[str, Any]:
    """TON Connect sendTransaction request the bot returns in answerWidgetQuery.

    Attach the order reference as a text-comment `payload` (base64 BOC) built
    with your TON library, e.g. @ton/core:
        beginCell().storeUint(0, 32).storeStringTail(order_id).endCell().toBoc()
    It is omitted here on purpose - this repo does not ship a BOC encoder.
    """
    order.valid_until = now + ttl
    order.state = OrderState.INVOICED
    return {"valid_until": order.valid_until,
            "messages": [{"address": order.merchant_address, "amount": str(order.amount_nano)}]}


def wallet_card_summary(card: dict[str, Any] | None) -> str:
    """Human summary of a TonWalletCard (balance is in the smallest units)."""
    if not card:
        return "No wallet card on the profile."
    tons = int(card["amount"]) / 1_000_000_000
    stickers = len(card.get("stickers", []))
    return f"Wallet {short_address(card['address'])}: {tons:.2f} TON, {stickers} NFT sticker(s)"


def short_address(addr: str) -> str:
    return addr if len(addr) <= 12 else f"{addr[:4]}…{addr[-4:]}"


def on_sent_transaction(order: Order, query: dict[str, Any], verifier: ChainVerifier) -> dict[str, Any]:
    """Handle {"type": "sent_transaction"}; returns the answer for the widget."""
    if query["from"]["id"] != order.user_id:
        return {"ok": False, "err": "not_your_order"}
    t = query["type"]
    if order.state == OrderState.PAID:
        return {"ok": True, "state": order.state.value}       # repeated notification
    order.msg_hashes.append(t["msg_hash"])
    order.state = OrderState.AWAITING_CONFIRMATION
    verdict = verifier.check(msg_hash=t["msg_hash"], sender=t["wallet"]["address"],
                             recipient=order.merchant_address,
                             amount_nano=order.amount_nano, order_id=order.order_id)
    if verdict == "confirmed":
        order.state = OrderState.PAID
    elif verdict == "mismatch":
        order.state = OrderState.MISMATCH
    return {"ok": True, "state": order.state.value}


def on_sign_data(query: dict[str, Any], verifier: SignatureVerifier, *, bot_id: int) -> dict[str, Any]:
    t = query["type"]
    wallet = t["wallet"]
    if not wallet.get("public_key"):
        return {"ok": False, "err": "unknown_public_key"}      # can't verify: say so
    good = verifier.verify(sign_data_json=t["sign_data"], public_key_hex=wallet["public_key"],
                           expected_domain=f"bot{bot_id}")
    return {"ok": good, "address": short_address(wallet["address"])} if good else {"ok": False, "err": "bad_signature"}


def describe_transfer(service: dict[str, Any]) -> str:
    """Message.ton_wallet_transfer service message -> a line for the user."""
    amount = int(service["amount"]) / 1_000_000_000
    direction = "Sent" if amount < 0 else "Received"
    comment = service.get("comment")
    status = "pending" if not service.get("transaction_id") else "recorded"
    tail = f" — “{comment}”" if comment else (" — encrypted comment" if "comment" not in service else "")
    return f"{direction} {abs(amount):.2f} TON {'to' if amount < 0 else 'from'} {short_address(service['peer_address'])} ({status}){tail}"
