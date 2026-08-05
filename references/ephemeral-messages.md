# Ephemeral messages and commands (Bot API 10.2)

> **Last verified against official docs: 2026-08-05** (Bot API 10.2, 14 Jul 2026).
> Section: *Ephemeral Messages and Commands*.

A genuinely new **UI surface**, not just an API addition: a bot and one member of
a group can now talk **privately on a public timeline**. Other members see
nothing. This solves the oldest UX problem in group bots — every reply spamming
everyone, or forcing the user into DMs and losing context.

## What it is

- **Ephemeral commands (user → bot).** Set `is_ephemeral: true` on a `BotCommand`.
  The user's invocation is delivered to the target bot but stays **invisible to
  every other member**, users and bots alike.
- **Ephemeral messages (bot → user).** Send with `receiver_user_id`; only that
  user sees it.
- They may **disappear on their own** after a while, or when the app restarts.

## The delivery contract — read this before designing around it

**Delivery is explicitly not guaranteed** (especially if the user is offline).
The docs say so for both sending and editing. This shapes the whole design:

- **Never** put anything load-bearing *only* in an ephemeral message —
  no confirmations of money moving, no one-time codes, no "your booking is
  confirmed".
- Treat it as a **convenience layer** over a durable path, not a replacement.
- Message edits are likewise not guaranteed to reach the user.

## When you may send one

Any bot, within **15 seconds** of an eligible incoming action, providing one of:

- the **`callback_query_id`** from a received callback query, or
- **`reply_parameters.ephemeral_message_id`** from an incoming ephemeral message.

The message goes to the **exact client app** that triggered the action.

**Exception:** if the bot is a **chat administrator**, it can send an ephemeral
message to any non-bot member at any time, with neither id. Then it may be
delivered across several of the user's active clients — still not guaranteed.

## API surface

| Piece | Note |
|---|---|
| `BotCommand.is_ephemeral` | declares an ephemeral command |
| `receiver_user_id` + `callback_query_id` params | added to `sendMessage`, `sendPhoto`, `sendAnimation`, `sendAudio`, `sendDocument`, `sendLivePhoto`, `sendSticker`, `sendVideo`, `sendVideoNote`, `sendVoice`, `sendContact`, `sendLocation`, `sendVenue` |
| `Message.receiver_user` | who the ephemeral message was for |
| `Message.ephemeral_message_id` | id used to edit/delete/reply |
| `ReplyParameters.ephemeral_message_id` | reply to an ephemeral message (`message_id` becomes optional when present) |
| `editEphemeralMessageText` / `Media` / `Caption` / `ReplyMarkup` | edit; take `chat_id` + `receiver_user_id` + `ephemeral_message_id` |
| `deleteEphemeralMessage` | remove it |

Note the send list is the **plain** send methods — `sendRichMessage` is **not**
among them. An ephemeral reply is a regular message: `parse_mode`/`entities`,
4096 chars, `reply_markup` = inline keyboard only on the edit methods.

## UX patterns this unlocks

- **Private results from a public command.** `/balance` in a group answers only
  the asker instead of broadcasting or refusing.
- **Per-user error feedback.** "You've already voted" goes to the one person, not
  the channel.
- **Admin-only affordances.** Moderation controls surfaced to admins in-place,
  invisible to members.
- **Disambiguation prompts.** "Which of your 3 accounts?" without a public menu.
- **Silent validation.** "That date is in the past" while the user retries, with
  no visible thrash.

## Design rules

- **Say it's private.** Users assume a group message is public. If a reply is
  ephemeral, a small marker ("only you can see this") prevents confusion — the
  client may not make it obvious.
- **Respect the 15-second window.** If the work takes longer, acknowledge inside
  the window and deliver the result on a durable path. Don't architect a slow
  pipeline behind an ephemeral reply.
- **Have a fallback for non-delivery.** Since delivery isn't guaranteed, the user
  must be able to re-request the information. Make the command idempotent.
- **Don't use it to hide destructive confirmations.** A "Delete everything?"
  confirmation that may silently never arrive is a hazard — keep destructive
  flows on guaranteed paths.
- **Ephemeral ≠ secure.** It is a visibility convenience, not a privacy control
  and not encryption. Never use it for secrets, tokens, or credentials.
- **Check the SDK.** Bot API 10.2 is recent; many SDKs won't expose
  `receiver_user_id` or the `editEphemeralMessage*` family yet
  (`sdk-compatibility.md`).

## Related 10.2 change worth knowing

Mini App methods are now **blocked from origins other than the Mini App's own
domain** (auto-enabled 20 Jul 2026; opt-out via @BotFather). If a project's Mini
App loads third-party frames or cross-origin scripts that call Telegram methods,
that breaks — flag it during an audit.
