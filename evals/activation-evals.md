# Activation eval scenarios

Use these to check that the skill triggers on the right requests and stays out of
the wrong ones. The `description` in `SKILL.md` is what drives selection — if a
positive case doesn't trigger or a negative case does, refine the description.

**Priority note:** UI requests (P1–P16) are the skill's primary job. Formatting
and rendering requests (P17–P24) remain fully in scope — they are one layer of
the same surface, not a separate skill.

## Positive — interface (should activate)

| # | Request | Why it matches | Routes to |
|---|---|---|---|
| P1 | "Improve the UX of this Telegram bot." | core purpose | `SKILL.md` workflow |
| P2 | "This menu is a mess — restructure it." | keyboard structure | `inline-keyboards.md` |
| P3 | "Make the main action stand out." | emphasis | `buttons-and-styles.md` |
| P4 | "Add colored buttons to the bot." | `style` (9.4) | `buttons-and-styles.md` |
| P5 | "Can I make a red Delete button?" | `danger` semantics | `buttons-and-styles.md` |
| P6 | "Put our custom emoji on the buttons." | `icon_custom_emoji_id` | `custom-emoji.md` |
| P7 | "Rewrite these bot messages, they're confusing." | microcopy | `microcopy-and-labels.md` |
| P8 | "The buttons say different things for the same action." | consistency | `consistency-and-review.md` |
| P9 | "Users get stuck with no way back." | navigation | `navigation-and-flows.md` |
| P10 | "Turn this reply keyboard into inline buttons." | keyboard choice | `reply-keyboards.md` |
| P11 | "Add pagination to this list of 60 items." | list UX | `inline-keyboards.md` |
| P12 | "Clean up the /commands list and the menu button." | chat chrome | `navigation-and-flows.md` |
| P13 | "The bot feels frozen while it generates the answer." | feedback | `dynamic-feedback-and-streaming.md` |
| P14 | "Stream the AI reply the way ChatGPT does." | `sendMessageDraft` | `dynamic-feedback-and-streaming.md` |
| P15 | "Greet the user by name safely." | personalization | `personalization-and-links.md` |
| P16 | "Should this link be a button or inline text?" | link surface | `personalization-and-links.md` |

## Positive — rendering (should activate)

| # | Request | Why it matches | Routes to |
|---|---|---|---|
| P17 | "Fix Telegram `can't parse entities`." | escaping/entity defect | `security-and-escaping.md` |
| P18 | "Render a table inside a Telegram message." | table | `tables.md` |
| P19 | "Send this price list as a Telegram table." | data → table | `tables.md` |
| P20 | "Migrate the bot's messages from MarkdownV2 to HTML." | format migration | `format-selection.md` |
| P21 | "Add Rich Messages for AI answers." | Rich Messages | `telegram-capabilities.md` |
| P22 | "Fix long-message splitting." | limits | `limits-and-splitting.md` |
| P23 | "Our localized templates break MarkdownV2." | i18n + escaping | `localization-and-rtl.md` |
| P24 | "Update the bot to the latest Bot API UI features." | capability migration | `ui-changelog.md` |

## Negative (should NOT activate)

| # | Request | Why it's out of scope |
|---|---|---|
| N1 | "Set up a Telegram webhook." | infrastructure |
| N2 | "Implement Telegram Stars payment processing." | payment logic |
| N3 | "Fix the bot's user database schema." | data layer |
| N4 | "Write a marketing strategy for our Telegram channel." | content strategy |
| N5 | "Open an RTF file." | Microsoft `.rtf`, unrelated |
| N6 | "Build the React components inside our Mini App." | web front-end internals |
| N7 | "Configure admin rights and anti-spam in a supergroup." | group administration |
| N8 | "Set up the bot's CI pipeline." | devops |
| N9 | "Scrape messages from a channel into a dataset." | data collection |
| N10 | "Add OAuth login to our backend." | auth infrastructure |

## Boundary notes

- N2 flips **positive** for the *checkout screen's* wording, button labels, or
  `pay`-button placement — the interface, not the payment flow.
- N6 flips **positive** for the Telegram-side surface: the button or menu button
  that opens the Mini App, `BottomButton` progress, `WebApp.ready()`.
- N7 flips **positive** if the task is about how the admin *bot's* screens look.
- N1/N3/N8/N9/N10 stay negative even when the project is a Telegram bot — the
  test is whether a user sees the result.
- "RTF" only means Microsoft `.rtf` here — never Telegram Rich Messages (N5 is a
  hard negative and a terminology trap).
- A pure "rewrite this text" request is **positive** (P7) — text is layer 1 of
  the interface.

## How to run the check

1. Read each request as the routing model would see only the `SKILL.md`
   `name` + `description`.
2. Confirm every P activates and every N does not.
3. Confirm the P cases route to the reference in the last column — a skill that
   activates but reads the wrong file still gives bad advice.
4. If misrouted, tighten trigger terms or the "Do NOT use" clause in the
   description, then re-check — don't add scope the skill can't deliver.
