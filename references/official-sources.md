# Official sources and verification log

> **Last verification: 2026-08-05.** Verified against **Bot API 10.2 (released
> 2026-07-14)**, the newest version listed in the official changelog on that
> date. Before doing version-dependent work, re-check the changelog for a newer
> version and update this file (with permission).

## How to keep this current

When Telegram ships a newer Bot API version, or today is past the date above and
the task is version-sensitive:
1. Read the **Bot API changelog** first and diff against this skill's references.
2. Apply current facts to the project.
3. With permission, update the references and this log — **do not delete historic
   facts** needed for older-SDK compatibility; mark them as version-specific.

## Primary sources (source of truth)

| Source | URL | Purpose | Last checked |
|---|---|---|---|
| Telegram Bot API | https://core.telegram.org/bots/api | Object/method specs, formatting options | 2026-08-05 |
| Bot API changelog | https://core.telegram.org/bots/api-changelog | Version history, what changed when | 2026-08-05 |
| `InlineKeyboardButton` | https://core.telegram.org/bots/api#inlinekeyboardbutton | Button fields, one-action rule, `style`, icon | 2026-08-05 |
| `KeyboardButton` | https://core.telegram.org/bots/api#keyboardbutton | Reply-button fields, `style`, icon | 2026-08-05 |
| Bot API 9.4 changelog entry | https://core.telegram.org/bots/api-changelog#february-9-2026 | Colored buttons, button icons, Premium custom emoji | 2026-08-05 |
| Bot API 6.2 changelog entry | https://core.telegram.org/bots/api-changelog#august-12-2022 | Custom emoji foundation | 2026-08-05 |
| `getCustomEmojiStickers` | https://core.telegram.org/bots/api#getcustomemojistickers | Resolving custom emoji IDs (≤200/call) | 2026-08-05 |
| `getStickerSet` / `Sticker` | https://core.telegram.org/bots/api#getstickerset | Source of `custom_emoji_id` + Unicode fallback | 2026-08-05 |
| Bots FAQ | https://core.telegram.org/bots/faq | Rate limits (per chat / group / broadcast) | 2026-08-05 |
| Telegram Mini Apps | https://core.telegram.org/bots/webapps | `BottomButton` progress, `WebApp.ready()` | 2026-08-05 |
| Telegram Bot Features | https://core.telegram.org/bots/features | Feature overview | 2026-07-15 |
| Bot API formatting options | https://core.telegram.org/bots/api#formatting-options | HTML / MarkdownV2 / entity escaping rules | 2026-07-15 |
| Styled text with entities | https://core.telegram.org/api/entities | Entity types, nesting rules | 2026-07-15 |
| Rich Messages section | https://core.telegram.org/bots/api#rich-messages | Rich objects/methods | 2026-07-15 |
| Rich message formatting options | https://core.telegram.org/bots/api#rich-message-formatting-options | Rich Markdown / Rich HTML / block syntax spec (linked from official blog) | 2026-07-15 |
| Official blog: Rich Text for Bots | https://telegram.org/blog/watch-apps-and-more#obscenely-rich-text-formatting-for-bots | Feature announcement, 32,768-char limit | 2026-07-15 |

## Facts verified on 2026-08-05 (UI surface)

Read directly from the pages listed above on 2026-08-05.

**Bot API 9.4 — February 9, 2026** (changelog, verbatim):

- *"Added the field `icon_custom_emoji_id` to the classes KeyboardButton and
  InlineKeyboardButton, allowing bots to show a custom emoji on buttons if they
  are able to use custom emoji in the message."*
- *"Added the field `style` to the classes KeyboardButton and
  InlineKeyboardButton, allowing bots to change the color of buttons."*
- *"Allowed bots to use custom emoji in messages directly sent by the bot to
  private, group and supergroup chats if the owner of the bot has a Telegram
  Premium subscription."*
- Same release, non-UI-critical but related: topics in private chats
  (`createForumTopic`, `User.allows_users_to_create_topics`),
  `setMyProfilePhoto` / `removeMyProfilePhoto`.

**Field definitions** (object pages, verbatim):

- `style` — *"Optional. Style of the button. Must be one of 'danger' (red),
  'success' (green) or 'primary' (blue). If omitted, then an app-specific style
  is used."* No HEX/RGB/CSS value exists.
- `icon_custom_emoji_id` — *"Unique identifier of the custom emoji shown before
  the text of the button. Can only be used by bots that purchased additional
  usernames on Fragment or in the messages directly sent by the bot to private,
  group and supergroup chats if the owner of the bot has a Telegram Premium
  subscription."*
- `InlineKeyboardButton` — *"Exactly one of the fields other than text,
  icon_custom_emoji_id, and style must be used to specify the type of the
  button."*
- `KeyboardButton` — *"At most one of the fields other than text,
  icon_custom_emoji_id, and style must be used to specify the type of the
  button."*

**Bot API 6.2 — August 12, 2022** (changelog): added `MessageEntity` type
`custom_emoji`, `MessageEntity.custom_emoji_id`, `getCustomEmojiStickers`, and
`Sticker.type` + `Sticker.custom_emoji_id`.

**Limits and constraints re-read on 2026-08-05:**

- `callback_data`: *"Data to be sent in a callback query to the bot when the
  button is pressed, 1-64 bytes"*.
- `CopyTextButton.text`: 1–256 characters.
- `answerCallbackQuery.text`: 0–200 characters; `show_alert`, `cache_time`.
- `ReplyKeyboardMarkup.input_field_placeholder` and
  `ForceReply.input_field_placeholder`: 1–64 characters.
- `BotCommand`: `command` 1–32 chars (lowercase letters, digits, underscores),
  `description` 1–256; `setMyCommands` accepts at most 100 commands, plus
  `scope` and `language_code`.
- `getCustomEmojiStickers`: at most 200 ids per call.
- `sendChatAction`: *"The status is set for 5 seconds or less"*; channel chats
  unsupported; actions `typing`, `upload_photo`, `record_video`, `upload_video`,
  `record_voice`, `upload_voice`, `upload_document`, `choose_sticker`,
  `find_location`, `record_video_note`, `upload_video_note`.
- `sendMessageDraft`: private chats only; `draft_id` non-zero and *"Changes to
  drafts with the same identifier are animated"*; `text` 0–4096 chars, *"Pass an
  empty text to show a 'Thinking…' placeholder"*; the draft *"acts as a temporary
  30-second preview - once the output is finalized, you must call sendMessage
  with the complete message to persist it"*.
- `InputRichBlockThinking` / `RichBlockThinking`: *"corresponding to the custom
  HTML tag `<tg-thinking>`. The block may be used only in sendRichMessageDraft"*;
  docs recommend the custom emoji pack at https://t.me/addemoji/AIActions.
- `LinkPreviewOptions`: `is_disabled`, `url`, `prefer_small_media`,
  `prefer_large_media`, `show_above_text`.
- `User`: `first_name` is required; `last_name`, `username`, `language_code`,
  `is_premium` are optional.
- Bots FAQ rate limits: *"In a single chat, avoid sending more than one message
  per second"*; *"In a group, bots are not be able to send more than 20 messages
  per minute"*; ~30 messages/second for bulk broadcasts unless paid broadcasts
  are enabled.
- Mini Apps: `WebApp.ready()` hides the loading placeholder;
  `BottomButton.showProgress(leaveActive)` / `hideProgress()` (the class was
  renamed from `MainButton` in Bot API 7.10); `BottomButton.iconCustomEmojiId`
  is Bot API 9.5+.

**Version context confirmed on 2026-08-05:** the changelog's newest entry is
**Bot API 10.2 (2026-07-14)**; 9.4 (2026-02-09) is followed by 9.5
(2026-03-01), 9.6 (2026-04-03), 10.0 (2026-05-08), 10.1 (2026-06-11), 10.2.

## Facts verified on 2026-07-15

Confirmed against official changelog / blog:

- Rich Messages were introduced in **Bot API 10.1 (2026-06-11)**:
  `RichMessage`, `RichText` (+23 `RichText*`), `RichBlock` (+`RichBlock*`),
  `InputRichMessage`, `InputRichMessageContent`, `sendRichMessage`,
  `sendRichMessageDraft`, `editMessageText` `rich_message` param,
  `Message.rich_message`.
- **Bot API 10.2 (2026-07-14)** added `InputRichMessageMedia` + `media` field and
  `blocks` field on `InputRichMessage`, the `InputRichBlock*` input block classes
  (incl. `InputRichBlockListItem`, `InputRichBlockThinking`), and
  `InputMediaVoiceNote`.
- Rich messages support up to **32,768 UTF-8 characters**, with content beyond
  ~8,000 collapsed behind "Show More" (official blog).
- Bot API 10.0 (2026-05-08) had **no** Rich Messages features.
- The official blog section "Obscenely Rich Text Formatting for Bots" calls the
  feature **"rich text formatting"** and **never uses the term "RTF"**. Features
  it lists: formatting and tables, nested blockquotes, headings and anchors,
  collapsible sections and footnotes, math/formulas, superscript/subscript,
  checklists, and inline media/carousels/collages. It points developers to the
  Rich message formatting options page (anchor above).
- Regular formatting (unchanged, re-confirmed): HTML and MarkdownV2 both support
  bold, italic, underline, strikethrough, spoiler, links, user mentions, custom
  emoji (`tg-emoji` / `![](tg://emoji?id=)`), inline code, code blocks with
  language, blockquote, and expandable blockquote. Blockquote/expandable cannot
  be nested; `code`/`pre` cannot contain other entities.
- `link_preview_options` fields: `is_disabled`, `url`, `prefer_small_media`,
  `show_above_text`.

## Facts NOT confirmed on official pages (treat as secondary — verify)

Reported by third-party coverage, not confirmed on core.telegram.org during this
verification. Re-check before relying on them:

- 500 blocks per rich message.
- Nesting depth limit of 16.
- 50 media attachments per rich message.
- 20 columns per table.

## Stable historical facts (pre-2026, unchanged)

- Regular message text limit 4096 chars; caption 1024 chars.
- MessageEntity `offset`/`length` are in **UTF-16 code units**.
- Media group max 10 items.
- Regular formatting: `parse_mode` = `HTML` or `MarkdownV2`, or `entities[]`.

## Design guidance that is NOT an API constraint

These are this skill's design heuristics, verified nowhere in the docs because
Telegram does not specify them. Never present them to a user as API limits:

- buttons per row (1–2 for sentence labels, up to 3 short, more only for tokens)
  — the Bot API documents no per-row maximum; the constraint is rendering width;
- "≤8 rows before you should paginate";
- "≤2 styled buttons per keyboard, ≤1 `primary` per screen";
- streaming throttle thresholds (800–1500 ms, 30–80 characters);
- edit-based streaming side effects (flicker, scroll jumps, duplicate messages
  on error paths, stale timestamps) — widely reported engineering experience,
  not documented behaviour.

## Sections to re-review on each Telegram release

- Bot API changelog (new versions, renamed/removed fields).
- Button classes (`KeyboardButton`, `InlineKeyboardButton`): new presentation
  fields, new action types, changes to the one-action rule.
- `style` allowed values and `icon_custom_emoji_id` eligibility wording.
- Draft/streaming semantics (`sendMessageDraft`, `sendRichMessageDraft`,
  `draft_id`, thinking block).
- Rich Messages objects/methods (new blocks, new fields, constraints).
- Formatting options (tag/attribute set, MarkdownV2 escape set).
- Limits (character, block, nesting, media, table).
- Streaming/draft semantics (`draft_id`, rate limits).
- `is_rtl` / direction handling.
