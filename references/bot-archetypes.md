# Bot archetypes: which features fit which bot (Bot API 10.4)

> Verified 2026-11-12. Use this when designing a new bot or a major rework, together with the
> initiative rule in `SKILL.md`. "Prod" = available in production today; "test" = test server
> only. Recipes: `recipes/README.md`. Visual system: `visual-language.md`.

Pick the archetype(s), take the **core screens**, add the features marked ✓ where they serve the
user's task, and avoid the ✗ traps. Most real bots combine 2–3 archetypes.

## Monitoring / alerts (wallet tracker, uptime, orders status, price alerts)

- Core screens: main menu · watched-items list (paginated) · item detail · alert settings (per
  item, per level) · alert message · analysis/statistics.
- ✓ **Widget card per tracked event** in the private chat: one message whose state moves
  (0 → 3 confirmations, "shipped → delivered") instead of a message per step; caption kept in
  sync for the chat list. Widget edits are **silent** — send one real message for the events the
  user wants to hear (R09).
- ✓ **Shared ticker widget** for a value many users watch (price, status page): one
  `editSharedWidgetData` updates every copy; `cache_time` matched to how fast it changes.
- ✓ Compact table for lists people compare (addresses, positions); short lines for 3–5 facts.
- ✓ `copy_text` for ids/addresses, `date_time` for event times, URL button to the explorer.
- ✓ Disabled buttons for options that exist but aren't available (taken numbers, paused items).
- ✗ A widget per alert in **groups** (test server only); four separate messages per event.
- Recipe: [09 tracker bot](../recipes/09-tracker-bot.md); case study `case-study-btc-tracker.md`.

## AI assistant / copilot

- Core: chat · streamed answer · sources/quotes · follow-up actions · history/topics · settings.
- ✓ Rich drafts with real stage labels + **Stop** (`can_stop`), policy for partial answers (R01).
- ✓ Topics for parallel conversations + topic links (R08); quote-back with `quote_rich_texts` (R02).
- ✓ Expandable quotes for long sources, document blocks for generated files, compact tables.
- ✗ Reasoning in `<tg-thinking>`; per-token edits; a full answer after Stop.

## Shop / ordering / booking

- Core: catalog → item → options → cart → checkout → confirmation → order status → support.
- ✓ Form steps with **buttons + reply field** (`force_reply` on keyboards) and a disabled
  Submit (R03); disabled sold-out options with the reason in text.
- ✓ Private-chat widget for the order card that updates (R05); wallet pay for TON (R07) —
  confirm on chain; Stars invoices for in-app goods (outside 10.3/10.4).
- ✓ Idempotent submit; unknown send outcome → show server state, never charge twice.
- ✗ Using a widget for text input (no inputs) — use the chat or a Mini App.

## Team / group utility (lunch orders, standups, shared lists, games for two)

- Core: shared card in the group · personal view · settings for admins · summaries.
- ✓ **Ephemeral personal panels** over the shared card; 10.4 short form for callbacks (R04).
- ✓ Welcome newcomers privately (`can_send_welcome_messages`, community joins — mini M01/M02).
- ✓ Polls: native `sendPoll`, or a shared widget in private chats; group widgets on **test**.
- ✗ Posting anyone's personal data in the group as a "fallback".

## Support desk / CRM-like (business accounts, channel direct messages)

- Core: inbox · conversation · quick replies · statuses · handover.
- ✓ Address by context: `business_connection_id`; channel DM chats use
  `direct_messages_topic_id`, no ephemeral callback replies there (`topics-and-contexts.md`).
- ✓ `paid_messages_waived` awareness, gift notes respected (`is_private`), mini M03/M09.
- ✗ `message_thread_id` in channel DM chats; inline-switch buttons there.

## Content / documentation / knowledge base

- Core: index · article · search · related · feedback.
- ✓ Rich Messages with headings, compact tables, expandable quotes, `tg://document` attachments,
  section-level buttons (`<tg-button-row>`) and in-text buttons (R02).
- ✓ Read and answer quotes from rich messages (`TextQuote.rich_texts`).
- ✗ Tables for 2–3 facts; one giant message instead of sections and "show more".

## Wallet / crypto / payments utility

- Core: balance/card · pay · history · link wallet · settings.
- ✓ Widget wallet flow (`{wallet: true}`, `sendTransaction`, `signData`) with an order state
  machine; wallet cards (`ton_wallet_card`), transfer service messages, `ton_address` entities (R07).
- ✓ Mask `bank_card_number` entities in logs; copy buttons for addresses.
- ✗ "Paid" on `sent_transaction`; float amounts; re-asking to pay after a timeout.

## Games and live interactive bots

- Core: lobby · game board · score · rematch.
- ✓ Private-chat widget with canvas/SVG and pointer events; horizontal drags with
  `touch-action: pan-y`; state on the bot with revisions; groups/inline/forwards on **test**.
- ✗ Vertical drags, keyboard input, network calls inside the widget.

## Bot factories and verification organizations

- ✓ `request_managed_bot` with `suggested_username` (Premium suffixes become secondary usernames, M07).
- ✓ `verifyUser`/`verifyChat` descriptions with text links only (M08).

## Choosing the surface quickly

| The user must… | Use |
|---|---|
| pick one of a few options | inline keyboard |
| pick **or** type | inline keyboard + `force_reply` |
| watch a value change | widget (private) / edited message (groups) |
| read and compare | Rich Message with a (compact) table |
| see something private in a group | ephemeral reply |
| type a lot, log in, browse remote data | Mini App |
