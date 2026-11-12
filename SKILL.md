---
name: telegram-bot-ui
description: >-
  Design, build and audit Telegram bot UIs and the Bot API features
  behind them: texts, inline/reply keyboards, colored and disabled buttons,
  premium icons from one consistent set, force_reply forms, navigation, streaming AI replies with Stop
  (sendRichMessageDraft, can_stop, stopped_message_generation), ephemeral
  personal replies in groups, Rich Messages (tables, quotes, documents,
  embedded buttons), HTML widgets (sendWidget, widget_query, shared widgets,
  TON wallet), topics, formatting (HTML, MarkdownV2, entities), localization,
  plus the server side they need (allowed_updates, callback state,
  cancellation, retries, SDK gaps) and 10.3/10.4 gift, community, theme,
  managed-bot and verification updates. Use for "improve this bot's menu",
  "add a Stop button", "private answer in a group", "send a widget", "the bot
  feels frozen", "can't parse entities", "use the latest Bot API".
  Do NOT use for webhook/DevOps setup, databases, payment processing or auth
  unrelated to these features, or Microsoft .rtf files.
---

# Telegram Bot UI

Portable, SDK-agnostic skill for the full life cycle of a **Telegram bot's user
interface**: audit → screen/state map → text, buttons and navigation design →
implementation → migration → testing → documentation.

A regular Telegram message has no CSS and no layout engine. Its interface is made
of **message text, formatting, keyboards, the chat-level chrome (commands, menu
button, deep links), and the transitions between states** — this skill treats
them as one design surface. Exceptions with their own layout: **HTML widgets**
(Bot API 10.4, a sandboxed HTML/CSS/JS document inside one message —
`references/widgets.md`) and Mini Apps (a hosted web page). Neither is a
general-purpose web page inside a chat.

## Purpose

Help an agent make a bot's interface **clear, consistent, and safe to change**:
choose what a screen says and how it says it; label, group, order, color, and
lay out buttons; design navigation between screens and states; keep every
screen consistent with the rest of the bot; keep localization intact; and
render message bodies with the richest format that fits — across any language
and any Telegram SDK, **without breaking existing handlers or business logic**.

## When to use

- **Interface work:** menus, keyboards, labels, grouping, emphasis (`style`,
  custom emoji), navigation, back/pagination, confirmations, empty/error states,
  commands, menu button, deep links, first-run, consistency, localization/RTL.
- **Feedback:** "the bot feels frozen", streaming AI answers, Stop, progress.
- **Personal views in shared chats** (ephemeral), **forms** (`force_reply`,
  disabled buttons), **live cards** (widgets), **wallet** pay/sign from a widget.
- **Message rendering:** HTML / MarkdownV2 / entities, Rich Messages, tables,
  splitting, `can't parse entities`.
- **Bot API 10.3/10.4 adoption**, including the server-side handling of new
  updates and the specialized modules.

## When NOT to use

Bot work no user ever sees and that no 10.3/10.4 feature depends on: webhook /
hosting / CI setup, databases and migrations, payment *processing* (Stars or
fiat ledgers), auth, scraping, analytics pipelines, group moderation policy,
Mini App front-end internals. Microsoft `.rtf` files.

**In scope even though it is server-side:** routing and subscribing to new
updates (`widget_query`, `shared_widget_query`, `stopped_message_generation`,
`allowed_updates`), callback/widget state and authorization, cancellation,
retries and unknown outcomes, SDK adapters for missing methods, TON wallet
request/verification boundaries, and the specialized 10.3/10.4 modules
(`references/specialized-updates.md`).

## Terminology — do not confuse these

- **Inline keyboard ≠ reply keyboard.** `InlineKeyboardMarkup` is attached to a
  specific message and sends `callback_query` / opens URLs. `ReplyKeyboardMarkup`
  replaces the user's letter keyboard and **sends text as a normal message**.
  Different button classes, different UX.
- **`style` is not a color value.** It is one of exactly `primary`, `success`,
  `danger`. Telegram has no HEX/RGB/CSS button colors.
- **`icon_custom_emoji_id` is not a `file_id`,** not an emoji-pack name, not a
  link, and not a Unicode emoji. It is the ID of one specific custom emoji.
- **Telegram Rich Text is NOT Microsoft RTF.** Never call Rich Messages "RTF".
- **Rich Markdown ≠ MarkdownV2.** MarkdownV2 is a `parse_mode` for *regular*
  messages with strict escaping. Rich Markdown is the document syntax for
  *Rich Messages*.
- **Rich HTML ≠ arbitrary browser HTML.** Only Telegram's supported tag set.
- **Editing a keyboard ≠ resending a screen.** `editMessageReplyMarkup` and
  `editMessageText` update in place; sending a new message stacks screens.

## Source-of-truth policy

Trust in this order:
1. Current **official Telegram documentation** (Bot API, Bot Features,
   formatting pages, official blog).
2. Official **Bot API changelog**.
3. Docs of the **SDK actually installed** in the project.
4. **SDK source code**.
5. **SDK issue tracker**.
6. Third-party articles — supplementary context only.

**Re-verify official docs before acting** when: the task touches new APIs; today
is later than the "last verified" date in `references/official-sources.md`; the
project's Bot API version is unknown; SDK docs contradict the Bot API; you meet
an unfamiliar type/field; or the user asks for "the latest capabilities".
This skill is verified against **Bot API 10.4 (2026-11-09) on 2026-11-12** and is
not frozen there — if Telegram shipped a newer version, use it and update
`recipes/registry.json`. Version gates: `references/ui-changelog.md`; every
10.3/10.4 item: `references/bot-api-10.3-10.4.md`.

## Core workflow (audit before you redesign)

1. Read the project's instructions (`AGENTS.md` / `CLAUDE.md` / README / docs).
2. Detect language, framework, **Telegram SDK, and exact versions**.
3. Determine the **Bot API version** the SDK actually supports — this decides
   whether `style` and `icon_custom_emoji_id` are reachable at all.
4. Build a **screen/state map**: every message the user can see, every keyboard,
   every `callback_data`, every command, every transition
   (`references/navigation-and-flows.md`).
5. Classify each screen: entry / menu / form step / confirmation / result /
   error / empty / notification.
6. Identify the **real UX defects** (don't invent work): ambiguous labels,
   overloaded keyboards, dead ends with no way back, inconsistent naming,
   destructive actions one tap away, unlocalized strings, unreadable bodies.
7. Design the fix: text first, then structure, then layout, then color/emoji —
   **in that order**. Color is the last layer, never the fix for a bad label.
8. Check SDK support for every field you plan to use
   (`references/sdk-compatibility.md`).
9. Implement in the project's existing style and utilities (don't duplicate its
   keyboard builders).
10. **Preserve** `callback_data`, URLs, deep links, handler routing, and
    localization keys unless the user explicitly asked to change them.
11. Add a **fallback** path and keep old clients usable
    (`references/errors-and-fallbacks.md`).
12. Add **tests** with the project's existing test infrastructure
    (`references/testing-playbook.md`).
13. Run the project's lint / typecheck / tests / applicable smoke checks.
14. Report: screen map, what changed and why, what was deliberately left alone,
    limits, and verification evidence.

Do **not** write implementation code before steps 1–6 are complete.

## Mode: how much process the task needs

* **Small local change** (a label, one button, one message): fix it, validate the
  payload, test — no full audit, no unrelated redesign.
* **Feature or screen** (a form, a Stop button, a personal panel, a widget): steps
  1–6 for the affected screens, then build from the matching recipe.
* **Migration / new bot / "latest Bot API"**: full workflow plus the initiative rule below.

## Bot API 10.3 / 10.4 — use them on purpose

**Initiative rule.** When building or seriously reworking a bot, check which
10.3/10.4 capabilities improve the requested scenarios and implement the fitting
ones within the agreed scope — don't wait for the user to name a method. Typical
wins: Stop on long AI answers, disabled buttons + `force_reply` in forms,
ephemeral personal views in groups, compact tables / embedded buttons / expandable
quotes in documents, a widget for a live card in a private chat. Don't add them to
a one-line fix, and don't turn every message into a widget.

Find the recipe by task, symbol, version or context: `recipes/README.md`
(index), `recipes/manifest.json` (machine-readable), `recipes/registry.json`
(all 52 changelog rows). Code: `examples/python/tgkit/`, `examples/ts/tgkit.ts`;
SDK adapters: `examples/python/sdk_aiogram/`, `examples/ts/sdk-grammy/`.

Invariants that change decisions:
- **Audience.** Personal content never falls back to a public message; one member
  never sees another's data (`references/ephemeral-and-personal.md`).
- **One logical finalization** per operation: Stop, completion, error and timeout
  are different endings; late chunks and repeated Stops are no-ops
  (`references/streaming-and-editing.md`). Not a network exactly-once promise.
- **Disabled ≠ authorized.** `disabled: {}` is the button's only action; the
  server still checks state and rights on every callback/widget query.
- **Widgets:** production = private chats only (groups, inline, forwards: test
  server); code immutable; state only via edits; answer every query once in 15 s;
  no secrets in code or `public_data`; always a caption and a text/button path.
- **Wallet:** `sent_transaction` is a notice, not proof of payment.
- **Update delivery:** new update types must be in `allowed_updates` (sticky) and
  routed by the SDK — verified gaps in aiogram 3.31 / grammY 1.46
  (`references/sdk-compatibility.md`).
- **Unknown outcome:** a timed-out send may have been delivered; never repeat
  orders/payments blindly; honour `retry_after`.
- **Context decides fields:** forum `message_thread_id` ≠ channel-DM
  `direct_messages_topic_id`; drafts only in private chats
  (`references/topics-and-contexts.md`).

## The five UI layers (design in this order)

| # | Layer | Question it answers | Reference |
|---|---|---|---|
| 1 | **Words** | Does the user understand what this is and what happens next? | `references/microcopy-and-labels.md` |
| 2 | **Structure** | Which actions exist, how are they grouped and ordered? | `references/inline-keyboards.md`, `references/reply-keyboards.md` |
| 3 | **Navigation** | How do I get here, back, and out? Which state am I in? | `references/navigation-and-flows.md` |
| 4 | **Body rendering** | Is the content readable — table, list, headings, plain? | `references/format-selection.md`, `references/tables.md` |
| 5 | **Emphasis** | What is *the* action here? What is dangerous? | `references/buttons-and-styles.md`, `references/custom-emoji.md` |

A screen that fails layer 1 cannot be rescued by layers 4–5. Never start with
color.

## Button essentials (full rules in `references/buttons-and-styles.md`)

- **Inline buttons: exactly one action field** besides `text`, `icon_custom_emoji_id`,
  `style` (`url`, `callback_data`, `web_app`, `login_url`, `switch_inline_query*`,
  `copy_text`, `callback_game`, `pay`, `disabled`); reply buttons at most one;
  rich-message buttons are a third model (`style` may be `link`, no icon field).
- **`style` (9.4)** is only `primary` (the one forward action), `success` (commit),
  `danger` (destructive, behind a confirmation); omit it for everything else.
- **`icon_custom_emoji_id` (9.4)** needs Fragment usernames or an owner with Premium
  (messages sent directly to private/group/supergroup chats). **Never invent an id** —
  resolve it (`references/custom-emoji.md`); keep one family (`references/visual-language.md`).
- **`disabled: {}` (10.3)** shows an unavailable action; it is the only action field and
  never replaces the server check. **`force_reply` on keyboards (10.3)** = buttons + reply
  field; on inline keyboards it can't change in an edit.
- Color and icon decorate a working button: the label must make sense without both.

## Message body: the fit the reader needs

| Need | Use |
|---|---|
| Data compared across columns | **Table** (compact on phones) — `references/tables.md` |
| 2–5 facts read once | short lines / list — not a table |
| Live card that changes in place (private chat) | **Widget** — `references/widgets.md` |
| Structured doc: report, AI answer, comparison, checklist | **Rich Markdown** |
| Server-templated content, precise tag control | **Rich HTML** |
| Typed generation from data / CMS / AST | **`InputRichBlock` blocks** |
| A screen with a keyboard: short prompt + options | **Regular HTML**, short |
| Exact offset control, no `parse_mode` | **`MessageEntity`** |
| Genuinely no styling needed | **Plain text** |

Rule: tabular data becomes a real table, never a monospace grid; a short set of
facts stays short; a menu screen is a prompt plus buttons. Surface and format
decision table (message / rich document / keyboard / rich buttons / ephemeral /
widget / Mini App): `references/format-selection.md`.

## Feedback while the bot is working

Waiting with no signal is the most common UX failure in bots. Choose by the
shape of the operation (full rules:
`references/dynamic-feedback-and-streaming.md`):

| Situation | Mechanism |
|---|---|
| Inline button tapped | `answerCallbackQuery` **first**, then do the work |
| 2–5 s operation | `sendChatAction` (`typing`, `upload_photo`, …) — 5 s max |
| AI text being generated (private chat) | `sendMessageDraft` + `can_stop` — same `draft_id`, finalize with `sendMessage` |
| AI answer with structure | `sendRichMessageDraft` + `<tg-thinking>` → `sendRichMessage` |
| Real, nameable stages | `editMessageText`, throttled |
| Progress not measurable | Named stages — **never a fake percentage** |
| Interactive process | Mini App (`BottomButton.showProgress()`, `WebApp.ready()`) |

Never edit per token: at most ~1 update per second, coalescing sentences and
stages, after any `retry_after`. One `draft_id` / `message_id` / `operation_id`
per operation and one logical finalization (`references/streaming-and-editing.md`).

## Which reference to read (task-routed — don't read them all)

**UI / UX**
- Button labels, message wording, tone, emoji in text →
  `references/microcopy-and-labels.md`
- `style` colors, emphasis, button layout and grouping →
  `references/buttons-and-styles.md`
- Inline keyboards, `callback_data`, pagination, editing in place →
  `references/inline-keyboards.md`
- Reply keyboards, `ForceReply`, keyboard removal, placeholders →
  `references/reply-keyboards.md`
- Screens, states, back/home, commands, menu button, deep links →
  `references/navigation-and-flows.md`
- Custom emoji on buttons and in text, obtaining IDs, eligibility →
  `references/custom-emoji.md`
- One visual language: picking premium icons from one family, emoji discipline,
  screen anatomy → `references/visual-language.md`
- Which features fit which bot type (monitoring, AI, shop, group utility,
  support, docs, wallet, games) → `references/bot-archetypes.md`
- Worked audit + 10.4 upgrade of a real bot → `references/case-study-btc-tracker.md`
- Which feedback mechanism (chat action, draft, edits, loaders) →
  `references/dynamic-feedback-and-streaming.md`
- Draft state machine, Stop, throttling, races →
  `references/streaming-and-editing.md`
- Personal / ephemeral answers in groups → `references/ephemeral-and-personal.md`
- HTML widgets (send, state, queries, shared, limits) → `references/widgets.md`
- Wallet pay / sign / TON cards and transfers → `references/wallet-and-ton.md`
- Topics, channel DMs, business, inline: which fields → `references/topics-and-contexts.md`
- Gifts, communities, share themes, managed bots, verification, renames →
  `references/specialized-updates.md`
- Every 10.3/10.4 item with example and check → `references/bot-api-10.3-10.4.md`
- Personalizing with user data, links, previews, deep links →
  `references/personalization-and-links.md`
- Cross-screen consistency + the pre-finish checklist →
  `references/consistency-and-review.md`
- UI-relevant Bot API history and version gates → `references/ui-changelog.md`
- Worked before/after scenarios → `references/examples-before-after.md`

**Content rendering**
- Tables → `references/tables.md`
- Rich Messages / blocks / capability matrix →
  `references/telegram-capabilities.md`
- HTML / MarkdownV2 / entities / captions / previews →
  `references/regular-formatting.md`
- Choosing a format → `references/format-selection.md`
- Media → `references/rich-media.md`
- Limits & splitting → `references/limits-and-splitting.md`
- Channels, notifications, broadcasts →
  `references/channels-and-broadcasting.md`

**Engineering**
- Investigating an unknown project → `references/project-adaptation.md`
- Escaping / injection / user or AI content →
  `references/security-and-escaping.md`
- Localization, RTL, button-label length →
  `references/localization-and-rtl.md`
- Errors, fallbacks, old clients → `references/errors-and-fallbacks.md`
- SDK gaps / raw Bot API payloads → `references/sdk-compatibility.md`
- Testing → `references/testing-playbook.md`
- Sources & last-verified dates → `references/official-sources.md`

Local validators (offline, no token): `scripts/validate_keyboard.py` (inline /
reply / rich buttons, `disabled`, `force_reply`, `--context`, `--previous`),
`scripts/validate_rich.py` (Rich Message Limits, drafts, media refs),
`scripts/validate_widget.py` (zlib-9 size, state bytes, production/test, runtime
gaps), `scripts/audit_icons.py` (one icon family, static, no shared ids),
`scripts/audit_copy.py` (i18n placeholders, symbols, label length, HTML),
`scripts/validate_skill.py`, `scripts/validate_references.py`. Run all:
`python scripts/run_checks.py`. Evals: `evals/activation-evals.md`,
`evals/behavioral-evals.md`.

## Non-negotiable rules

- **Preserve behaviour.** Keep existing `callback_data`, URLs, deep links,
  payloads, and handler routing. A visual redesign must not rewrite handlers.
  If a `callback_data` change is unavoidable, say so and update every
  handler/route in the same change.
- **Words before pixels.** Fix the label before adding a color or an emoji.
- **No decorative color.** Assign `style` by the *meaning* of the action. Do not
  color every button; an all-colored keyboard has no hierarchy.
- **`style` accepts only** `primary`, `success`, `danger`. No HEX/RGB/CSS.
- **Never invent a `custom_emoji_id`.** Fetch it or ask for it. Never guess.
- **Never rely on color or emoji alone.** The interface must stay usable in
  plain text, in a client that ignores the new fields, and for a user who cannot
  distinguish the colors.
- **Verify SDK support** for `style` / `icon_custom_emoji_id` before using them;
  if absent, offer an SDK upgrade *or* a raw Bot API payload path
  (`references/sdk-compatibility.md`) — never silently drop the field.
- **Keep localization intact.** New strings go through the existing i18n
  mechanism with the project's key conventions; never hardcode a translated
  label over a catalog. Layout must survive the longest translation.
- **One icon family per bot:** don't mix Unicode emoji and custom emoji, or custom
  emoji from different packs/styles (iOS vs Android vs Unigram, static vs
  animated), on the same screens; titles and buttons use the same id
  (`references/visual-language.md`, `scripts/audit_icons.py`).
- **Every tap gets feedback**, and every long operation gets an honest progress
  signal — no invented percentages, no per-token edits, no stalled spinners.
  Finalize a streamed draft with a real message, including on failure.
- **Treat user data as optional and untrusted:** `last_name`, `username`,
  `language_code`, `photo_url` may be absent; names must be escaped or passed as
  entities; Mini App personalization uses validated `initData`.
- Investigate the project **before** changing it; don't duplicate its keyboard
  builders or scatter magic limits.
- **One escaping function per format** — never a single universal escaper; never
  pass arbitrary or AI-generated HTML straight to Telegram.
- Pull **current limits from official docs**; don't hardcode remembered numbers.
- Fallbacks must be explicit and logged — no silent degradation, no infinite
  retries, no logging bot tokens or full personal text.
- Don't claim a screen works until it has been **tested**, and name the level of
  evidence: static check, offline contract test, real Bot API, real clients.
  JSON or a browser preview never proves Android/iOS/Desktop/Web rendering.

## Definition of done

Screen/state map produced · real UX defects identified (not invented) · text
fixed before structure, structure before color · every inline button carries
exactly one action field · `style` assigned by meaning, ≤1 `primary` per screen,
`danger` only where destruction is real and confirmed · custom emoji IDs
verified, never invented · labels readable with no color and no emoji · every
tap acknowledged and every long operation given honest, throttled progress ·
streamed drafts finalized with a real message · personalization degrades safely
when optional user fields are missing · existing
`callback_data`/URLs/deep links/handlers preserved · localization keys intact
and layout tolerant of long translations · SDK support verified or a documented
fallback path used · body rendered with the richest fit (tables for structured
data) · safe escaping · audience-preserving fallback + tests added · new update types
subscribed and routed · Stop/cancel/timeout endings distinct · widgets: production
context, caption, size by zlib-9, server-side state · project checks green · limits
sourced from official docs · "last verified" date recorded. Report per step 14
and run `references/consistency-and-review.md`.
