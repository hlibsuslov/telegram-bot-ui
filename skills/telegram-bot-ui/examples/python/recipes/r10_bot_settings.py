"""R10 - Configure the bot from code (Bot API 10.5).

The bot's switches live in the repository instead of BotFather taps: on start
it reads getMe (BotFullInfo), sends ONE setMySettings with only what differs,
turns on topics with a sidebar, picks a callback mode and handles callbacks that
arrive with inline_message_id. The owner invites testers with the botinvite
link; an invited user is greeted with the owner's name. Group commands are
accepted for every active username of the bot.

Run:  py -3 examples/python/recipes/r10_bot_settings.py
"""
from __future__ import annotations

import _common as c
from tgkit import settings
from tgkit.transport import FakeTransport

OWNER = 111111111

# The bot's settings as code (review them like any other config change).
DESIRED = {
    "inline_query_placeholder": "Search orders…",
    "has_topics_enabled": True,
    "allows_users_to_create_topics": True,
    "has_topic_sidebar": True,
    "inline_feedback_share_denominator": 10,
    "callback_query_mode": "auto",
}


def get_me() -> dict:
    return c.fixture("get_me_bot_full_info.json")["result"]


def sync_settings(t: FakeTransport) -> dict:
    t.script("getMe", get_me())
    return settings.apply(t, DESIRED)


def resync_readable(t: FakeTransport, after: dict) -> dict:
    # Second start: getMe already reflects the readable settings -> no call for them.
    me = {**get_me(), **{k: v for k, v in after.items() if k in settings.READABLE}}
    t.script("getMe", me)
    return settings.apply(t, {k: v for k, v in DESIRED.items() if k in settings.READABLE})


def owner_invite(t: FakeTransport, me: dict, from_id: int) -> bool:
    """/invite: the link goes to the owner only (it invites up to 10 users per press)."""
    if from_id != OWNER:
        t.call("sendMessage", {"chat_id": from_id, "text": "Only the bot's owner can invite people."})
        return False
    t.call("sendMessage", {"chat_id": OWNER,
                           "text": f"Invite up to {settings.INVITE_LIMIT} people at once. They get a chat with the bot; "
                                   "you see who joined here.",
                           "reply_markup": {"inline_keyboard": [[{"text": "Invite people", "url": settings.invite_link(me)}]]}})
    return True


def greet_invited(t: FakeTransport, message: dict) -> dict | None:
    inviter = settings.inviter_of(message)
    if inviter is None:
        return None
    user = message["from"]
    t.call("sendMessage", {"chat_id": message["chat"]["id"],
                           "text": f"{inviter['first_name']} invited you to try Orders. Pick where to start:",
                           "reply_markup": {"inline_keyboard": [[{"text": "Track an order", "callback_data": "set:1:track"},
                                                                 {"text": "How it works", "callback_data": "set:1:help"}]]}})
    t.call("sendMessage", {"chat_id": OWNER, "text": f"{user['first_name']} accepted your invite."})
    return inviter


def on_callback(t: FakeTransport, cq: dict, state: dict) -> dict:
    """Works in every callback_query_mode: no chat is assumed, state is keyed by the presser."""
    t.call("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Topics on"})
    state[cq["from"]["id"]] = {"topics": True}
    target = settings.callback_target(cq)
    t.call("editMessageText", {**target, "text": "Topics are on. Each order gets its own topic in the sidebar.",
                               "reply_markup": {"inline_keyboard": [[{"text": "Turn off", "callback_data": "set:1:topics:off"}]]}})
    return target


def run(transport: FakeTransport | None = None):
    t = transport or FakeTransport()
    sent = sync_settings(t)
    again = resync_readable(t, sent)
    me = get_me()
    refused = not owner_invite(t, me, from_id=444444444)
    owner_invite(t, me, from_id=OWNER)
    inviter = greet_invited(t, c.fixture("message_write_access_invited.json")["message"])
    state: dict = {}
    target = on_callback(t, c.fixture("callback_bot_message_inline_mode.json")["callback_query"], state)
    return t, sent, again, refused, inviter, target, state


def main() -> None:
    t, sent, again, refused, inviter, target, state = run()
    c.dump(t, "Bot settings from code")
    c.check(set(sent) == {"inline_query_placeholder", "has_topics_enabled", "allows_users_to_create_topics",
                          "has_topic_sidebar", "inline_feedback_share_denominator", "callback_query_mode"},
            "one setMySettings with only the settings that differ (getMe already had the rest)")
    c.check(again == {} and t.methods().count("setMySettings") == 1, "second start: readable settings unchanged -> no call")
    errors, _ = settings.validate({"inline_feedback_share_denominator": 50, "callback_query_mode": "always"})
    c.check(len(errors) == 2, "denominator outside 1/10/100/1000 and an unknown callback mode are refused before sending")
    _, warnings = settings.validate({"can_read_all_group_messages": True, "callback_query_mode": "inline"})
    c.check(len(warnings) == 2, "privacy off and inline callback mode come with a warning for the human")
    c.check(refused, "the invite link is never shown to anyone but the owner")
    link = t.params_of("sendMessage")[1]["reply_markup"]["inline_keyboard"][0][0]["url"]
    c.check(link == "https://t.me/botinvite/orders_demo_bot", "botinvite link built from the bot's username")
    c.check(inviter and inviter["id"] == OWNER, "invited user recognised by write_access_allowed.inviter")
    c.check(target == {"inline_message_id": "BAAAAKx2nwABOWNSENT"} and 444444444 in state,
            "callback without message: edited by inline_message_id, state keyed by the presser")
    me = get_me()
    c.check(settings.addressed_to_me("/orders@orders_ai 42", me) and settings.addressed_to_me("/orders", me)
            and not settings.addressed_to_me("/orders@other_bot", me), "group commands accepted for every active username")


if __name__ == "__main__":
    main()
