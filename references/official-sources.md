# Official sources and verification log

> **Last verification: 2026-07-15.** Verified against **Bot API 10.2 (released
> 2026-07-14)**. Before doing version-dependent work, re-check the changelog for a
> newer version and update this file (with permission).

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
| Telegram Bot API | https://core.telegram.org/bots/api | Object/method specs, formatting options | 2026-07-15 |
| Bot API changelog | https://core.telegram.org/bots/api-changelog | Version history, what changed when | 2026-07-15 |
| Telegram Bot Features | https://core.telegram.org/bots/features | Feature overview | 2026-07-15 |
| Bot API formatting options | https://core.telegram.org/bots/api#formatting-options | HTML / MarkdownV2 / entity escaping rules | 2026-07-15 |
| Styled text with entities | https://core.telegram.org/api/entities | Entity types, nesting rules | 2026-07-15 |
| Rich Messages section | https://core.telegram.org/bots/api#rich-messages | Rich objects/methods | 2026-07-15 |
| Rich message formatting options | https://core.telegram.org/bots/api#rich-message-formatting-options | Rich Markdown / Rich HTML / block syntax spec (linked from official blog) | 2026-07-15 |
| Official blog: Rich Text for Bots | https://telegram.org/blog/watch-apps-and-more#obscenely-rich-text-formatting-for-bots | Feature announcement, 32,768-char limit | 2026-07-15 |

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

## Sections to re-review on each Telegram release

- Bot API changelog (new versions, renamed/removed fields).
- Rich Messages objects/methods (new blocks, new fields, constraints).
- Formatting options (tag/attribute set, MarkdownV2 escape set).
- Limits (character, block, nesting, media, table).
- Streaming/draft semantics (`draft_id`, rate limits).
- `is_rtl` / direction handling.
