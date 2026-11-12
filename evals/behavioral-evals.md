# Behavioral evals (reproducible, NOT yet run as agent evals)

Status 2026-11-12: these tasks are prepared for an agent run (Claude Code, Codex or similar with
this skill installed). **No agentic run was performed** — the offline tests in `tests/` and
`examples/ts` check the reference implementations, not an agent's behaviour. To run: give the
agent only the "Request" and "Context" (never the method names in "Must"), let it work in a scratch
copy of a small bot (or the `examples/` harness), then grade against "Must" and "Critical failure".
Record model, date, skill commit and the grade per task.

| ID | Request (user words) | Context | Must (observable) | Critical failure |
|---|---|---|---|---|
| B01 | "Add a simple main menu: Orders, Settings, Help." | aiogram bot, plain text messages | inline keyboard, short prompt, labels with words, ≤ 1 primary; **no** rich message / widget | turns a 3-button menu into a rich document or widget |
| B02 | "Compare our three plans: price, seats, storage, support." | any SDK, Bot API 10.4 | real table (compact if > 4 cols), header cells, numbers right-aligned; text fallback | monospace grid; table for a 2-fact message |
| B03 | "Order form: size (pick or type), phone, time. People double-submit." | private chat | `force_reply` on the inline keyboard, disabled Submit until valid, Back keeps answers, idempotent submit, `force_reply` repeated on edits | `disabled` + `callback_data`; relying on the disabled button for authorization |
| B04 | "The AI answer takes 30 s and users can't stop it." | private chat, LLM streaming | rich draft with `can_stop`, subscription to the stop update, cancel upstream, distinct endings, one final, throttling | final full answer after Stop; per-token drafts; reasoning in thinking block |
| B05 | "In our group, 'My balance' must show each person only their balance." | supergroup | ephemeral reply per presser + `answerCallbackQuery`; server-side owner check; private fallback | any public message with a balance; one user's data in another's panel |
| B06 | "Show the order as an interactive card that updates." | production bot, private chat | `sendWidget` with caption + text alternative, `widget_query` subscribed and answered once, state edits with revision, size checked by zlib-9 | widget in a group for production; `fetch()` in the widget; secrets in `public_data` |
| B07 | "Our bot uses aiogram 3.31; widget taps time out." | aiogram 3.31.0 | diagnose: widget updates dropped / not in allowed_updates; isolated adapter with removal condition; contract test | "upgrade fixes it" without evidence; raw calls scattered in handlers |
| B08 | "Old messages still have a 'Pay' button that charges again." | callback bot | server-side state check, stale answer, disabled/removed button on old messages, callback contract preserved | trusting the button; changing `callback_data` without migrating handlers |
| B09 | "sendMessage timed out when confirming the order — resend?" | order bot | outcome unknown: no blind resend; reconcile by operation id; bounded retries; 429 → `retry_after` | unconditional resend; retry loop on 429 |
| B10 | "Accept TON payments for orders in the chat." | private chat | widget wallet flow, `awaiting` on `sent_transaction`, chain verification boundary, timeout → no repeat payment | marking paid on the notification |
| B11 | "Let people forward the poll and keep voting." | production | explains forwards are test-server only; ships private-chat shared widget; test-server plan | promises live forwards in production |
| B12 | "Users ask about a line in our rich FAQ; quote it back." | rich messages | read `quote.rich_texts` when `text` is empty; `quote_rich_texts` reply | loses the quote; quotes buttons |

| B13 | "Our buttons use premium icons but the bot looks messy." | icon ids from several packs | resolves sets (`getCustomEmojiStickers`), runs `audit_icons.py`, rebuilds from one family, titles use the same ids, uncovered slots label-only | invents ids; adds more packs; animated icons on buttons |
| B14 | "Upgrade our wallet-tracker bot to the latest Bot API." | aiogram 3.31, private chats, alerts per confirmation | one widget card per tx with silent edits + one audible final message, compact table for address lists, disabled taken options, adapter for `SendWidget`, text fallback | widgets in groups for production; four messages kept; tables for 4 facts |

## Combination and specialized tasks

| ID | Request | Must | Critical failure |
|---|---|---|---|
| C01 | "Team lunch bot: one card in the group, everyone's own order privately, a poll for the place." | 04 + 03 + 06 (private-chat shared widget or native poll), contexts respected | personal data public; group widget in production |
| C02 | "Support assistant in topics with citations from our policy." | 01 + 08 + 02, isolation per topic | Stop in one topic ends another |
| C03 | "Delete the shop account's old gifts." | dry-run plan, preconditions, explicit confirmation, no Stars | deletes without confirmation |
| C04 | "Welcome people who join from our community, privately." | community_chat_joined + welcome right/ephemeral | public greeting per join |

## Transfer tasks (no method names given; change language/SDK/context/availability)

| ID | Request | Variation | Must |
|---|---|---|---|
| T01 | "A quiz bot: show a live scoreboard card and let players answer by tapping." | grammY (TS), private chat | finds recipes 05/06 via the index, adapts with the grammY adapter, tests with node:test |
| T02 | "Same quiz, but in a group." | group, production | refuses group widgets for production; inline keyboard + edits fallback, test-server plan |
| T03 | "Сделай бота-ассистента на русском с кнопкой остановки ответа." | Russian UI, python-telegram-bot 22.8 | checks PTB's Bot API version (10.0 → no Stop support) → raw adapter or edit-based fallback; Russian labels; RTL-safe |
| T04 | "Personal receipts in the group after payment." | channel direct-messages chat | recognises no ephemeral callback replies there; uses `direct_messages_topic_id` and a private-chat path |

Grading: Must = all items present and running (tests or recipe run); any Critical failure = fail.
