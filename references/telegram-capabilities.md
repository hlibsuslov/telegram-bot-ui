# Telegram message capabilities

> **Last verified against official docs: 2026-08-05** (Bot API 10.2, 14 Jul 2026 —
> still the newest entry in the changelog on that date). Object field names and
> limits below were read directly from core.telegram.org. See
> `official-sources.md`.

This is a compact map, not a copy of the docs. When the task depends on an exact
field, open the official page for that object/method and confirm.

## Two mechanisms, kept separate

| | Regular Messages | Rich Messages |
|---|---|---|
| Sent with | `sendMessage`, `sendPhoto`, … + `parse_mode`/`entities` | `sendRichMessage`, `sendRichMessageDraft` |
| Styling | `parse_mode` = `HTML` / `MarkdownV2`, or `entities[]` | `markdown` **or** `html` **or** `blocks` (exactly one) |
| Model | flat text + inline entities | document tree of typed blocks |
| Text limit | 4096 chars (caption 1024) | up to 32,768 UTF-8 chars |
| Best for | notifications, prompts, short replies | reports, AI answers, docs, tables, math |

Rich Messages are an **addition**, not a replacement. Do not migrate short/regular
messages just because Rich exists.

## Bot API version history (relevant to formatting)

- **10.0 — 2026-05-08:** no Rich Messages (Guest Mode, chats, polls, business).
- **10.1 — 2026-06-11:** introduced Rich Messages. Added `RichMessage`,
  `RichText` + 23 `RichText*` classes, `RichBlock` + `RichBlock*` classes,
  `InputRichMessage`, `InputRichMessageContent`, `sendRichMessage`,
  `sendRichMessageDraft`, `editMessageText` `rich_message` parameter, and the
  `rich_message` field on `Message`.
- **10.2 — 2026-07-14:** added `InputRichMessageMedia` + `media` field on
  `InputRichMessage`; `blocks` field on `InputRichMessage`; the input block
  classes `InputRichBlock*` (Paragraph, SectionHeading, Preformatted, Footer,
  Divider, MathematicalExpression, Anchor, List, ListItem, BlockQuotation,
  PullQuotation, Collage, Slideshow, Table, Details, Map, Animation, Audio,
  Photo, Video, VoiceNote, Thinking); `InputMediaVoiceNote`. **Also shipped
  Ephemeral Messages** — a first-class UI surface, see
  `ephemeral-messages.md`.

**Version gate that matters:** Rich Messages arrived in **10.1**, but the
`InputRichBlock*` **input** classes and the `blocks` field arrived in **10.2**.
A project on exactly 10.1 can send `markdown`/`html` rich messages but **cannot**
use the typed `blocks` path.

Always confirm the **latest** version in the changelog before starting.

## Object model (high level)

- **`RichMessage`** — a received rich formatted message (read side); appears as
  `Message.rich_message`.
- **`RichBlock`** / **`RichText`** — the parsed block/inline tree Telegram returns.
- **`InputRichMessage`** — what a bot sends. Carries **exactly one** of:
  - `markdown` — a Rich Markdown string;
  - `html` — a Rich HTML string;
  - `blocks` — an array of explicit `InputRichBlock*` objects (**10.2+**).

  Plus these verified optional fields:
  - `media` — array of `InputRichMessageMedia`, binding media referenced from
    markdown/html via `tg://photo?id=`, `tg://video?id=`, `tg://audio?id=`;
  - `is_rtl` — Boolean, render the whole message right-to-left;
  - `skip_entity_detection` — Boolean, **suppress Telegram's automatic detection**
    of URLs, e-mails, @mentions, #hashtags, $cashtags, /commands, phone and bank
    card numbers. Set this whenever the body contains user-supplied or
    machine-generated text that must not become live links
    (`security-and-escaping.md`).

  Note the send *parameters* (`chat_id`, `reply_markup`, `reply_parameters`,
  `disable_notification`, `protect_content`, …) live on `sendRichMessage`, **not**
  inside `InputRichMessage`.
- **`InputRichMessageContent`** — an `InputMessageContent` variant for inline /
  guest / Web App query results.
- **`InputRichMessageMedia`** — declares a media item (by file_id, `tg://…?id=`
  reference, HTTP(S) URL, or upload) that markdown/html/blocks refer to.

## Send / edit methods

- **`sendRichMessage`** — send a complete rich message.
- **`sendRichMessageDraft`** — stream a partial/updating rich message (see
  `streaming-and-editing.md`). Uses a stable non-zero `draft_id`.
- **`editMessageText` + `rich_message`** — replace a message's rich content.

## Official Rich Message limits (documented, not folklore)

From the *Rich Message Formatting Options* section — quote these as real limits:

- **32,768 UTF-8 characters** total (including custom-emoji alt text and formula
  source); content past ~8,000 collapses behind "Show More".
- **500 blocks**, counting nested blocks, list items, **table rows**, quotation
  blocks and details blocks.
- **16 levels** of nested formatting/blocks.
- **50 media attachments** total.
- **20 columns** in a table.

## `InputRichBlock*` type discriminators (verified — several are non-obvious)

The `type` string is **not** the class name lowercased. Verified values:

| Class | `type` |
|---|---|
| `InputRichBlockParagraph` | `paragraph` |
| `InputRichBlockSectionHeading` | **`heading`** (+ `size` 1–6, **1 = largest**) |
| `InputRichBlockPreformatted` | **`pre`** |
| `InputRichBlockBlockQuotation` | **`blockquote`** (+ optional `credit`) |
| `InputRichBlockPullQuotation` | **`pullquote`** |
| `InputRichBlockMathematicalExpression` | `mathematical_expression` |
| `InputRichBlockVoiceNote` | `voice_note` |
| `InputRichBlockList` | `list` (holds `items`: `InputRichBlockListItem[]`) |
| `InputRichBlockTable` | `table` |
| `InputRichBlockDetails` | `details` (+ `summary`, `blocks`, `is_open`) |
| `InputRichBlockThinking` | `thinking` (**`sendRichMessageDraft` only**) |
| Others | `footer`, `divider`, `anchor`, `collage`, `slideshow`, `map`, `animation`, `audio`, `photo`, `video` |

`InputRichBlockListItem` is **not** a block with a `type` — it carries `blocks`,
plus optional `has_checkbox`, `is_checked`, `value`, and `type`
(`a`/`A`/`i`/`I`/`1`) for ordered-list labelling.

**`RichText`** is *either* a plain **String**, an **Array of `RichText`**, or one
of the 25 typed `RichText*` objects. A plain string is a valid `RichText` — use
it for ordinary text instead of building wrapper objects.

## Capability matrix (feature × format)

`RegMD` = MarkdownV2, `RegHTML` = regular HTML, `RMd` = Rich Markdown,
`RHTML` = Rich HTML, `Blk` = explicit `InputRichBlock*`. ✅ supported · ➖ n/a.

| Feature | Regular | RMd | RHTML | Blk | Notes |
|---|:--:|:--:|:--:|:--:|---|
| Bold / italic / underline / strike | ✅ | ✅ | ✅ | ✅ | inline entities in all |
| Spoiler | ✅ | ✅ | ✅ | ✅ | |
| Marked / highlight, sub/superscript | ➖ | ✅ | ✅ | ✅ | rich-only inline |
| Inline code / code block | ✅ | ✅ | ✅ | ✅ | fenced blocks get lang highlight |
| Links, `tg://` links | ✅ | ✅ | ✅ | ✅ | validate URL scheme |
| Block quote / expandable quote | ✅ | ✅ | ✅ | ✅ | |
| Pull quote | ➖ | ✅ | ✅ | ✅ | rich-only |
| Headings (H1–H6) | ➖ | ✅ | ✅ | ✅ | levels render differently |
| Lists (ordered/unordered) | ➖ | ✅ | ✅ | ✅ | `InputRichBlockList` + `ListItem` |
| Task lists `- [ ]` / `- [x]` | ➖ | ✅ | ✅ | ✅ | |
| Divider / horizontal rule | ➖ | ✅ | ✅ | ✅ | `---` in Rich Markdown |
| Tables | ➖ | ✅ | ✅ | ✅ | `InputRichBlockTable.cells` = **array of arrays** of `RichBlockTableCell`; `is_header`, `align`, `valign`, `colspan`, `rowspan`; **max 20 columns**; cells hold **inline formatting only**. See `tables.md` |
| Details (collapsible) | ➖ | ✅ | ✅ | ✅ | |
| Anchors / references / footnotes | ➖ | ✅ | ✅ | ✅ | |
| Math (LaTeX inline `\(…\)` / block `\[…\]`) | ➖ | ✅ | ✅ | ✅ | `MathematicalExpression` |
| Footer | ➖ | ✅ | ✅ | ✅ | |
| Photo / video / animation / audio / voice | caption only | ✅ | ✅ | ✅ | inline media blocks |
| Collage / slideshow | ➖ | ✅ | ✅ | ✅ | grouped media |
| Map | ➖ | ✅ | ✅ | ✅ | `InputRichBlockMap` |
| Thinking block | ➖ | ✅ | ✅ | ✅ | for AI reasoning display |
| Custom emoji | ✅ | ✅ | ✅ | ✅ | premium/custom emoji id |
| RTL awareness | limited | ✅ | ✅ | ✅ | see `localization-and-rtl.md` |
| Precise offset control | via entities | ➖ | ➖ | ✅ | blocks are typed, not parsed |

## Regular formatting quick reference

- **Regular HTML tags (whitelist):** `b`/`strong`, `i`/`em`, `u`/`ins`,
  `s`/`strike`/`del`, `span class="tg-spoiler"` (or `tg-spoiler`), `a href`,
  `code`, `pre`, `pre><code class="language-…">`, `blockquote`,
  `blockquote expandable`, `tg-emoji emoji-id`. No other tags/attributes.
- **MarkdownV2:** escape these outside entities with `\`:
  `` _ * [ ] ( ) ~ ` > # + - = | { } . ! ``. Inside `pre`/`code` escape `` ` ``
  and `\`; inside `(...)` link/emoji URLs escape `)` and `\`. See
  `security-and-escaping.md`.
- **MessageEntity:** `type` + `offset` + `length` in **UTF-16 code units**.
  Types include bold, italic, underline, strikethrough, spoiler, blockquote,
  expandable_blockquote, code, pre, text_link, text_mention, custom_emoji,
  mention, hashtag, cashtag, bot_command, url, email, phone_number.

## Rich Markdown / Rich HTML quick reference (verified)

Rich Markdown is **GFM-compatible where possible and may contain arbitrary
HTML** — it is *not* MarkdownV2 and needs no backslash-escaping of `.`/`-`/`!`.

| Feature | Rich Markdown | Rich HTML |
|---|---|---|
| Bold / italic | `**b**` `__b__` / `*i*` `_i_` | `<b>` `<strong>` / `<i>` `<em>` |
| Underline | *(no MD syntax — use HTML)* | `<u>` `<ins>` |
| Strikethrough | `~~s~~` | `<s>` `<strike>` `<del>` |
| Marked / highlight | `==marked==` | `<mark>` |
| Spoiler | `\|\|spoiler\|\|` | `<tg-spoiler>` |
| Sub / superscript | *(HTML only)* | `<sub>` / `<sup>` |
| Headings | `#` … `######` | `<h1>`…`<h6>` |
| Divider | `---` | `<hr/>` |
| Lists | `-` `*` `+`, `1.` | `<ul>` `<ol start type reversed>` `<li value type>` |
| Task list | `- [ ]` / `- [x]` | `<li><input type="checkbox" checked>` |
| Quote | `>` per line | `<blockquote>…<cite>Author</cite></blockquote>` |
| Pull quote | *(HTML only)* | `<aside>…<cite>…</cite></aside>` |
| Code | `` `x` ``, ```` ```lang ```` | `<code>`, `<pre><code class="language-…">` |
| Table | pipe table, `:--`/`:-:`/`--:` | `<table bordered striped><caption>…<tr><th>/<td>` |
| Math | `$x^2$`, `$$E=mc^2$$`, ```` ```math ```` | `<tg-math>`, `<tg-math-block>` |
| Footnote | `text[^id]` + `[^id]: definition` | `<tg-reference name="id">` + `<a href="#id">` |
| Anchor | *(HTML only)* | `<a name="ch1"></a>` + `<a href="#ch1">` |
| Collapsible | `<details open><summary>…</summary>…</details>` | same |
| Media | `![](https://…/x.jpg "Caption")` | `<img>`, `<video>`, `<audio>`, `<figure>`+`<figcaption>`+`<cite>` |
| Collage / slideshow | `<tg-collage>` / `<tg-slideshow>` | same |
| Map | `<tg-map lat="41.9" long="12.5" zoom="14"/>` | same |
| Date-time | `![22:45 tomorrow](tg://time?unix=…&format=wDT)` | `<tg-time unix="…" format="wDT">` |
| Custom emoji | `![😀](tg://emoji?id=…)` | `<tg-emoji emoji-id="…">😀</tg-emoji>` |
| Thinking (draft only) | `<tg-thinking>…</tg-thinking>` | same |
| Footer | *(HTML only)* | `<footer>` |

Verified gotchas:

- **Media only as a separate block**, never inline in a paragraph; media blocks
  accept **HTTP/HTTPS URLs only** (or `tg://photo\|video\|audio?id=` bound via
  `InputRichMessage.media`). Type is inferred from MIME type and URL.
- **Table cells accept inline formatting only** — no blocks inside a cell.
- **Markdown is not parsed inside block-level HTML tags** except `<details>`,
  `<tg-collage>` and `<tg-slideshow>`; elsewhere use HTML tags only.
- Inside inline HTML tags, nested Markdown *is* parsed
  (`<u>text with **bold**</u>` works).
- **Named HTML entities differ by mode.** Regular HTML supports only
  `&lt; &gt; &amp; &quot;`. **Rich HTML additionally** supports
  `&apos; &nbsp; &hellip; &mdash; &ndash; &lsquo; &rsquo; &ldquo; &rdquo;`.
  All numeric entities work in both.
- Formula source is **raw LaTeX**.
- Telegram shows an "Open this link?" confirmation before opening inline links.
- Auto-detection of URLs/mentions/hashtags/commands/phones/cards is **on by
  default** — disable with `skip_entity_detection`.

## Authoring conventions (styling defaults)

Apply these by default when generating rich content, so output looks intentional
and consistent. Verify exact field names against the official object for the
project's Bot API version.

### Tables

> **Tables are this skill's first-priority output. For the full build guide
> (Rich Markdown / Rich HTML / `InputRichBlockTable` code, split rules, escaping,
> and the monospace fallback), read `tables.md`.** The essentials:

- **Header row bold:** mark header cells with **`is_header: true`** (clients
  render header cells bold) — in Rich HTML use **`<th>`** for header cells and
  `<td>` for body; in Rich Markdown the first row (above the `---|---` separator)
  is the header. Don't fake a header with manual bold on plain `<td>`/cells —
  use the header semantics so it renders and exports correctly.
- **Alignment:** set cell `align` (`left`/`center`/`right`) and `valign`
  (`top`/`middle`/`bottom`); align numeric columns right, text left.
- **Spanning:** use `colspan`/`rowspan` (> 1) for merged cells; leave the covered
  position as a cell with **no `text`** (an omitted `text` renders invisible)
  rather than padding with `""`.
- **Rich HTML tables take `<tr>` directly** — `<thead>`/`<tbody>` are **not**
  supported tags. `<table>` accepts bare `bordered` / `striped` attributes and a
  `<caption>`.
- **Splitting:** never split a table mid-row; if a table must span messages,
  **repeat the header row** in each part and keep it with its body
  (`limits-and-splitting.md`). Max 20 columns, and **table rows count toward the
  500-block limit**.

### Everything else (defaults)

- **Section titles → heading blocks** (`SectionHeading` / `#…` / `<h1–h6>`), not
  a bold paragraph.
- **Code blocks → always set the language** for syntax highlighting
  (`pre><code class="language-…">` / ```` ```lang ````).
- **Links → descriptive anchor text**, not a bare URL; control the preview with
  `link_preview_options` (`regular-formatting.md`).
- **Quotes → blockquote**; make long quotes expandable.
- **Emphasis → sparing and consistent** (don't bold whole paragraphs); use
  bold for labels/headers, italic for asides.
- **Lists → real list blocks**; use task lists (`- [ ]`/`- [x]`) for actionable
  items.
- **Media → captions** (and `credit`/spoiler where relevant); place media blocks
  in reading order (`rich-media.md`).
- **RTL → mark direction by content**, keep LTR islands intact
  (`localization-and-rtl.md`).

## Do / don't

- **Do** choose blocks when you need typed generation, CMS output, or to avoid
  parser ambiguity; choose Rich Markdown/HTML for naturally-authored documents.
- **Don't** call any of this "RTF". Don't treat Rich Markdown as MarkdownV2.
- **Don't** assume the whole feature set below your project's Bot API version is
  available — verify the version first (`project-adaptation.md`,
  `sdk-compatibility.md`).
