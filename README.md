# telegram-bot-ui

**A portable, SDK-agnostic Agent Skill for designing and improving the user
interface of Telegram bots** — texts, buttons, keyboards, navigation, colors,
custom emoji, streaming feedback, and message rendering.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/format-Agent%20Skills-8A2BE2.svg)](https://github.com/anthropics/skills)
[![Verified: Bot API 10.2](https://img.shields.io/badge/Telegram%20Bot%20API-10.2%20verified-26A5E4.svg)](https://core.telegram.org/bots/api-changelog)

A Telegram bot has no CSS and no layout engine. Its entire interface is
**message text, formatting, keyboards, chat-level chrome (commands, menu button,
deep links), and the transitions between states** — plus what the user sees
*while the bot is working*. This skill teaches an AI coding agent to treat all
of that as one design surface: audit the project first, fix words before
structure and structure before color, and change presentation without touching
business logic.

> This repository **is** the skill. It doesn't modify any bot — you install it,
> and your agent uses it when a Telegram UI task comes up.
>
> *Formerly `telegram-rich-messages`.* All of the message-formatting capability
> is still here — it is now one layer of a larger UI skill.

## Purpose

Make a bot's interface clear, consistent, and safe to change:

- decide what a screen says and how it says it;
- label, group, order, color, and lay out buttons;
- design navigation between screens and states;
- keep every screen consistent with the rest of the bot;
- keep localization intact;
- render message bodies with the richest format that actually helps;
- give honest feedback while the bot works —

across any language and any Telegram SDK, **without breaking existing handlers,
`callback_data`, deep links, or translations**.

## When to use it

- "Improve the bot's UX/UI", "redesign this menu", "this keyboard is overloaded",
  "users don't understand this screen", "add a back button".
- Button labels, ordering, grouping, colors, custom emoji icons; inline vs reply
  keyboards; pagination; confirmations.
- Rewriting bot messages, titles, captions, prompts, errors, and empty states.
- Commands list, menu button, `/start` and deep links, first-run experience.
- Consistency work: one action named three different ways, back buttons that
  exist on some screens only, state that doesn't update after a tap.
- Streaming AI answers, progress bars, "typing" statuses, button loaders — "the
  bot feels frozen while it thinks".
- Personalization (greeting by name, locale hints) and link surfaces (URL
  buttons, link previews, deep links, mentions).
- Message rendering: HTML / MarkdownV2 / entities / Rich Messages / tables,
  `can't parse entities`, broken or oversized messages, RTL.

## When NOT to use it

Bot logic that never reaches the interface: webhook infrastructure, payment
*processing*, authorization, databases and migrations, group administration and
moderation logic, scraping, analytics pipelines. Mini App *internals* are
ordinary web front-end work — only the Telegram-side surface (the button or menu
that opens it, `BottomButton`, `WebApp.ready()`) is in scope. Not for Microsoft
`.rtf` files.

## Supported UI tasks

| Area | What the skill covers |
|---|---|
| **Message texts** | Rewriting with facts, placeholders, and i18n keys preserved; tone; length; front-loading; one job per screen |
| **Titles & captions** | Screen titles, caption limits, media captions |
| **Button text** | Verb+object labels, uniqueness, truncation in the longest locale, emoji budget |
| **Button structure** | Exactly one action field, `callback_data` schemes, copy-text/URL/Web App/switch-inline buttons |
| **Inline keyboards** | Layout, grouping, pagination, editing in place, stale-message handling, callback answers |
| **Reply keyboards** | Persistence, placeholders, `request_*` buttons, `ForceReply`, keyboard removal, label-routing traps |
| **Action order & grouping** | Probability-then-risk ordering, homogeneous rows, isolated destructive actions |
| **Visual hierarchy** | One focal action per screen, emphasis budget, formatting as emphasis not decoration |
| **Button colors** | `style`: `primary` / `success` / `danger`, assigned by meaning |
| **Custom emoji** | `icon_custom_emoji_id` on buttons, custom emoji in text, obtaining real IDs, fallbacks |
| **Navigation** | Screen/state maps, back/home, wizards, commands, menu button, deep links, topics, ephemeral messages |
| **Dynamic feedback** | `sendMessageDraft`, `sendRichMessageDraft` + `<tg-thinking>`, progress bars, `sendChatAction`, button loaders, throttling |
| **Personalization & links** | Safe display names, optional user fields, URL buttons vs text links, link previews, deep-link hygiene |
| **Consistency** | Action vocabulary, navigation slots, emoji vocabulary, state variants, cross-surface agreement |
| **Localization** | Localized labels and command descriptions, longest-translation layout, RTL |
| **Rendering** | Tables, Rich Messages, HTML/MarkdownV2/entities, splitting, media, channels, escaping |

## Rules for improving texts

1. Identify what the text must accomplish, and for whom.
2. **Keep every fact** — prices, deadlines, legal wording, IDs, links.
3. **Keep the placeholders** — same names, same count, no reordering.
4. **Edit the i18n catalog, not the call site**; update every locale or flag the
   ones that need translation.
5. First line states the point; **one job per screen**.
6. Structured data becomes a **table**, not a monospace grid.
7. Formatting is emphasis, not decoration — bold the one thing that matters.
8. No raw internals (stack traces, SQL, HTTP codes) in user-facing text.
9. Errors = what happened + what to do next. Empty states = what would be here +
   how to fill it. Confirmations = object + consequence + reversibility.
10. Re-check escaping for the parse mode and re-check length limits after every
    edit.

## Rules for designing buttons

1. **Exactly one action field** per inline button (`url`, `callback_data`,
   `web_app`, `login_url`, `switch_inline_query*`, `copy_text`, `callback_game`,
   `pay`). `text`, `style`, and `icon_custom_emoji_id` don't count.
2. `callback_data` is **1–64 bytes** — namespaced (`screen:action:id`), ASCII,
   ids not labels.
3. **Never change existing `callback_data` for a visual redesign** — messages
   already in users' chats still send the old payload.
4. Labels are **verb + object**, unique within a keyboard, and the same word for
   the same action everywhere in the bot.
5. Order by likelihood, then risk. **Destructive actions last and isolated.**
6. 1–2 buttons per row for sentence-length labels, up to 3 for short ones; more
   only for tokens. Verify against the **longest translation**.
7. Navigation row last, identical on every screen.
8. **Words before pixels** — fix the label before adding color or an emoji.
9. Every tap gets feedback; every callback query gets answered.
10. The keyboard must be fully usable with **no color and no emoji**.

## `style` — colored buttons (Bot API 9.4)

Official wording: *"Optional. Style of the button. Must be one of 'danger'
(red), 'success' (green) or 'primary' (blue). If omitted, then an app-specific
style is used."* There is **no** HEX, RGB, or CSS color in the Bot API.

| `style` | Color | Use when the action… | Examples |
|---|---|---|---|
| `primary` | blue | moves the user forward — the single most likely next step | Continue · Start · Open · Next |
| `success` | green | commits, confirms, or completes positively | Save · Confirm · Publish · Submit · Pay |
| `danger` | red | destroys, resets, or is hard to undo | Delete · Reset · Unsubscribe · Leave · Cancel plan |
| *(omit)* | app default | is secondary, neutral, or navigational | Back · Home · Settings · Help |

Budget: **at most one `primary` per screen**, `danger` only for real destruction
(always behind a confirmation), roughly **≤2 styled buttons per keyboard**, and
**never** style a list of equal options — coloring everything removes the
hierarchy color was meant to create.

## `icon_custom_emoji_id` — custom emoji on buttons (Bot API 9.4)

```json
{
  "text": "Finish the test",
  "icon_custom_emoji_id": "5368324170671202286",
  "style": "success",
  "callback_data": "finish_test"
}
```

The custom emoji renders **before** the button text. The value is the ID of one
specific custom emoji — **not** a `file_id`, not a pack name, not a link, not a
Unicode character. It cannot be guessed or derived.

**Where to get a real ID:**

- `MessageEntity.custom_emoji_id` from a message that contains the emoji;
- `Sticker.custom_emoji_id` from `getStickerSet`;
- `getCustomEmojiStickers` (≤200 ids per call) to verify ids you already have.

The skill **never invents an ID**: it plumbs the field through from config, asks
the user for the value, and shows them how to capture it.

### Premium and Fragment limits

Official wording for the field: *"Can only be used by bots that purchased
additional usernames on Fragment or in the messages directly sent by the bot to
private, group and supergroup chats if the owner of the bot has a Telegram
Premium subscription."*

So a bot qualifies via **either**:

1. **Fragment** — the bot purchased additional usernames there; or
2. **Owner Premium** (added in Bot API 9.4) — the bot's *owner* has Telegram
   Premium **and** the message is sent directly by the bot to a **private,
   group, or supergroup** chat.

Consequences the skill states out loud: channels aren't covered by route 2; the
capability depends on the **owner's** subscription staying active, not the
viewer's; and if neither route applies, use Unicode emoji instead. Custom emoji
in *message text* follow the same eligibility and have existed since **Bot API
6.2** (2022-08-12), where they always require a valid Unicode fallback
character.

## Examples

### Before → after: text only, no logic touched

```diff
- ERROR: request failed with code 500. Something went wrong.
- Please try again later or contact the administrator if the problem persists.
+ ⚠️ Couldn't load your orders.
+ This is on our side — try again in a minute.
```

`reply_markup`, handler, parse mode, and i18n key unchanged.

### Before → after: emphasis and safety

```json
{"inline_keyboard": [[
  {"text": "OK", "callback_data": "ok"},
  {"text": "Delete", "callback_data": "del"},
  {"text": "Back", "callback_data": "back"}
]]}
```

```json
{"inline_keyboard": [
  [{"text": "Save changes", "callback_data": "ok", "style": "success"}],
  [{"text": "Delete draft", "callback_data": "del", "style": "danger"}],
  [{"text": "← Back", "callback_data": "back"}]
]}
```

Same payloads, clearer intent: one commit action, destruction separated and
confirmed, navigation predictable.

### Inline keyboard with an icon and a color

```json
{"inline_keyboard": [
  [{"text": "Finish the test", "icon_custom_emoji_id": "5368324170671202286",
    "style": "success", "callback_data": "finish_test"}],
  [{"text": "Continue later", "icon_custom_emoji_id": "5368324170671202111",
    "callback_data": "pause_test"}],
  [{"text": "← Back to topics", "callback_data": "topics"}]
]}
```

### Reply keyboard

```json
{
  "keyboard": [
    [{"text": "🧾 My orders"}, {"text": "🛒 Catalog"}],
    [{"text": "📞 Share phone", "request_contact": true, "style": "primary"}],
    [{"text": "⚙️ Settings"}]
  ],
  "resize_keyboard": true,
  "is_persistent": true,
  "input_field_placeholder": "Type a city or tap a button"
}
```

Reply-keyboard buttons send their **label as a message** — so handlers must
route through stable i18n keys, never hardcoded display text.

Seven fully worked scenarios (text-only edit · rebuilding an overloaded keyboard
· adding the three styles · icon + color together · unknown `custom_emoji_id` ·
SDK without 9.4 support · when *not* to add color) live in
[`references/examples-before-after.md`](references/examples-before-after.md).

## Backward compatibility

- **Preserve** `callback_data`, URLs, deep links, payload schemes, and handler
  routing. Visual redesign ≠ handler rewrite. If a payload must change, update
  every consumer in the same change and say so.
- **Old clients** ignore unknown fields: a button with `style` /
  `icon_custom_emoji_id` renders as a normal button with the same label and
  action. Design for that baseline, then enhance.
- **Never rely on color or emoji alone** — the label carries the meaning.
- **Verify SDK support** before using new fields. Detection recipes per SDK are
  in [`references/sdk-compatibility.md`](references/sdk-compatibility.md);
  a strict, typed SDK may silently drop unknown fields, which looks like working
  code that never colors anything.
- If the SDK lags: upgrade it, or send the markup as a raw Bot API payload
  behind a single adapter — never claim a field shipped when it didn't.
- **Localization is part of compatibility**: keep catalog keys, update every
  locale, and keep layout tolerant of the longest translation.
- **Degrade a button by dropping `style`/icon, never by removing the button.**

## Checklist for an AI agent before finishing

- [ ] Audited the project and produced a **screen/state map** before editing.
- [ ] Fixed **words → structure → navigation → rendering → color**, in order.
- [ ] Every inline button has **exactly one** action field; `callback_data` ≤64
      bytes and **unchanged**.
- [ ] `style` only `primary`/`success`/`danger`, assigned by meaning; ≤1
      `primary`; `danger` behind a confirmation.
- [ ] No invented `custom_emoji_id`; eligibility route (Fragment / owner
      Premium / neither) established and reported.
- [ ] Labels understandable with **no color and no emoji**.
- [ ] Every tap acknowledged; long operations show honest, throttled progress;
      streamed drafts finalized with a real message even on failure.
- [ ] Localization keys intact; longest-translation layout verified.
- [ ] SDK support verified, or a documented raw-payload/fallback path used.
- [ ] Keyboards validated (`scripts/validate_keyboard.py`), project checks green.
- [ ] Report says what changed, what was deliberately left alone, and what still
      needs the bot owner (emoji IDs, Premium status, copy decisions).

## Repository layout

```
telegram-bot-ui/
├── SKILL.md                     # compact operational guide (loaded on activation)
├── README.md · LICENSE
├── references/                  # progressive-disclosure detail (read on demand)
│   ├── microcopy-and-labels.md          # texts, titles, captions, labels, emoji
│   ├── buttons-and-styles.md            # style colors, emphasis, layout
│   ├── inline-keyboards.md              # callbacks, pagination, editing
│   ├── reply-keyboards.md               # persistence, request_*, ForceReply
│   ├── navigation-and-flows.md          # screens, states, commands, deep links
│   ├── custom-emoji.md                  # icon_custom_emoji_id, IDs, eligibility
│   ├── dynamic-feedback-and-streaming.md# drafts, thinking, progress, loaders
│   ├── personalization-and-links.md     # user data, links, previews
│   ├── consistency-and-review.md        # cross-screen consistency + checklist
│   ├── ui-changelog.md                  # UI-relevant Bot API history & gates
│   ├── examples-before-after.md         # seven worked scenarios
│   ├── tables.md                        # structured data as real tables
│   ├── telegram-capabilities.md         # Rich Messages + capability matrix
│   ├── regular-formatting.md            # HTML/MarkdownV2/entities
│   ├── channels-and-broadcasting.md
│   ├── format-selection.md
│   ├── project-adaptation.md
│   ├── security-and-escaping.md
│   ├── limits-and-splitting.md
│   ├── rich-media.md
│   ├── streaming-and-editing.md
│   ├── localization-and-rtl.md
│   ├── errors-and-fallbacks.md
│   ├── sdk-compatibility.md
│   ├── testing-playbook.md
│   └── official-sources.md              # sources + last-verified dates
├── scripts/                     # stdlib-only validators (no token, no network)
│   ├── validate_skill.py
│   ├── validate_references.py
│   └── validate_keyboard.py
├── evals/
│   └── activation-evals.md      # positive/negative trigger scenarios
└── agents/
    └── openai.yaml              # optional Codex-specific metadata
```

## Install

**Claude Code — user level (all projects):**

```bash
git clone https://github.com/hlibsuslov/telegram-bot-ui.git \
  ~/.claude/skills/telegram-bot-ui
```

**Claude Code — repository level (one project):** clone into
`<repo>/.claude/skills/telegram-bot-ui`.

**Codex (OpenAI):** clone into `~/.agents/skills/telegram-bot-ui` (user) or
`<repo>/.agents/skills/telegram-bot-ui` (project).

On Windows the Claude Code user path is
`%USERPROFILE%\.claude\skills\telegram-bot-ui`.

The skill directory name must match the `name` in `SKILL.md`
(`telegram-bot-ui`). The repository was renamed from `telegram-rich-messages`
on 2026-08-05; GitHub redirects the old URL, so existing clones keep working —
run `git remote set-url origin https://github.com/hlibsuslov/telegram-bot-ui.git`
to update one.

## Use

- **Automatically:** the `description` in `SKILL.md` lets the host select the
  skill when a request matches — e.g. *"improve this bot's menu"*, *"make the
  confirm button stand out"*, *"add colored buttons"*, *"rewrite this bot's
  error message"*, *"the keyboard is a mess"*, *"stream the AI answer"*, *"fix
  Telegram can't parse entities"*.
- **Explicitly:** ask for it by name — *"use the telegram-bot-ui skill to audit
  our bot's screens"* (Codex: `$telegram-bot-ui`).

## Validate

```bash
python scripts/validate_skill.py                  # front matter, sections, secrets
python scripts/validate_references.py             # links, orphans, empty files, secrets
python scripts/validate_keyboard.py keyboard.json # keyboard payload rules
```

All three are standard-library only, read local files only, and never use a bot
token or the network. On Windows use `py -3` in place of `python`. Then walk
[`evals/activation-evals.md`](evals/activation-evals.md) to confirm trigger
behaviour.

## How it works

1. Read project instructions; detect language, framework, **SDK, and versions**.
2. Determine the supported **Bot API version** — this decides whether `style` and
   `icon_custom_emoji_id` are reachable at all.
3. Build a **screen/state map**: every screen, keyboard, `callback_data`, and
   transition.
4. Identify **real** UX defects; fix words → structure → navigation → rendering
   → color.
5. Implement in the project's own style, preserve payloads and localization, add
   a fallback and tests, run its checks.

Source-of-truth order: current **official Telegram docs** → Bot API changelog →
installed SDK docs → SDK source → SDK issues → third-party articles (context
only). The skill re-verifies official docs for version-dependent work and is
**not frozen** at any Bot API version.

## Official documentation

- [Bot API](https://core.telegram.org/bots/api) ·
  [changelog](https://core.telegram.org/bots/api-changelog) ·
  [Bot Features](https://core.telegram.org/bots/features) ·
  [Bots FAQ](https://core.telegram.org/bots/faq)
- [`InlineKeyboardButton`](https://core.telegram.org/bots/api#inlinekeyboardbutton) ·
  [`KeyboardButton`](https://core.telegram.org/bots/api#keyboardbutton) ·
  [`ReplyKeyboardMarkup`](https://core.telegram.org/bots/api#replykeyboardmarkup) ·
  [`ForceReply`](https://core.telegram.org/bots/api#forcereply)
- [Bot API 9.4 — 9 Feb 2026](https://core.telegram.org/bots/api-changelog#february-9-2026)
  (`style`, `icon_custom_emoji_id`) ·
  [Bot API 6.2 — 12 Aug 2022](https://core.telegram.org/bots/api-changelog#august-12-2022)
  (custom emoji foundation)
- [`getCustomEmojiStickers`](https://core.telegram.org/bots/api#getcustomemojistickers) ·
  [`getStickerSet`](https://core.telegram.org/bots/api#getstickerset) ·
  [`Sticker`](https://core.telegram.org/bots/api#sticker) ·
  [`MessageEntity`](https://core.telegram.org/bots/api#messageentity)
- [`answerCallbackQuery`](https://core.telegram.org/bots/api#answercallbackquery) ·
  [`sendChatAction`](https://core.telegram.org/bots/api#sendchataction) ·
  [`editMessageReplyMarkup`](https://core.telegram.org/bots/api#editmessagereplymarkup) ·
  [`setMyCommands`](https://core.telegram.org/bots/api#setmycommands) ·
  [`setChatMenuButton`](https://core.telegram.org/bots/api#setchatmenubutton)
- [`sendMessageDraft`](https://core.telegram.org/bots/api#sendmessagedraft) ·
  [`sendRichMessageDraft`](https://core.telegram.org/bots/api#sendrichmessagedraft) ·
  [`InputRichBlockThinking`](https://core.telegram.org/bots/api#inputrichblockthinking) ·
  [`LinkPreviewOptions`](https://core.telegram.org/bots/api#linkpreviewoptions)
- [Formatting options](https://core.telegram.org/bots/api#formatting-options) ·
  [Mini Apps](https://core.telegram.org/bots/webapps)

## Keeping it current

Telegram's UI surface evolves. Before version-dependent work, re-check the
[Bot API changelog](https://core.telegram.org/bots/api-changelog), update
[`references/ui-changelog.md`](references/ui-changelog.md) with any entry that
changes the interface, and record the new date in
[`references/official-sources.md`](references/official-sources.md). Content here
was verified against **Bot API 10.2 (released 2026-07-14)** on **2026-08-05**.

## Contributing

Issues and PRs welcome. Please: keep `SKILL.md` compact (detail belongs in
`references/`), cite official Telegram docs for any capability claim, mark
unverified numbers as such, run all three validators, and keep the skill
project-agnostic (no assumptions about a specific SDK or repo).

## License

[MIT](LICENSE).

## Disclaimer

Community project; not affiliated with or endorsed by Telegram. Verify current
behaviour against the official Bot API before relying on any capability.
