# Format selection

> Core rule: **use the simplest format that fully solves the task.** Do not
> migrate everything to Rich Messages. Match the *project's* existing standard
> unless there is a concrete reason to change it.

## Decision order

Ask these in order and stop at the first "yes":

1. **Does the message need any styling at all?** No → **plain text**. Plain text
   still needs correct handling of user data (no accidental entity injection when
   later wrapped) and correct splitting for length.
2. **Is it a short/interactive/notification message with light styling, and the
   project already uses HTML?** → **Regular HTML**.
3. **Does the project already standardize on MarkdownV2, or is MarkdownV2 clearly
   the best fit?** → **MarkdownV2** (accept the strict escaping cost).
4. **Do you need exact byte/offset control or to avoid a parse_mode entirely
   (e.g. programmatic styling, mixing user text with styling safely)?** →
   **MessageEntity**.
5. **Is the content a naturally-authored document** (AI answer, article, report,
   docs) with headings/tables/lists/math? → **Rich Markdown** (if authored as
   Markdown) or **Rich HTML** (if server-templated with precise tag control).
6. **Is the content generated programmatically / from a CMS / an AST, or must be
   unambiguous and typed?** → **explicit `InputRichBlock` blocks**.
7. **Would the UX be better as standalone media** (single photo, album, document,
   caption)? → **separate media methods** (`sendPhoto`, `sendMediaGroup`, …).

## Per-format guidance

### Plain text
Zero markup. Cheapest and safest. Prefer for logs, one-line statuses, and any
message where styling adds nothing. Still split long text safely.

### Regular HTML
Best default for compact, predictable styling in interactive flows *if HTML is
already the project's convention*. Whitelist tags/attrs; escape `< > &` in
dynamic parts. Predictable and easy to test.

### MarkdownV2
Only when already the project standard or genuinely best. Every reserved char in
dynamic text must be escaped (`security-and-escaping.md`). Easy to break with
user input; prefer HTML or entities for user-supplied content unless MarkdownV2
is mandated.

### MessageEntity
When you need exact `offset`/`length` control, want no parse_mode, or must
safely interleave untrusted text with styling. Offsets are **UTF-16 code units** —
compute them from the final string, accounting for surrogate pairs (emoji).

### Rich Markdown
For complex, document-like content that is natural to write as Markdown: AI
replies, articles, headings, tables, task lists, formulas, structured docs. Put
it in `InputRichMessage.markdown`. Requires Bot API 10.1+/10.2+; verify support.

### Rich HTML
For complex server-templated content where you want precise control over the
supported Telegram tag set. Put it in `InputRichMessage.html`. Same tag/attr/URL
whitelisting discipline as regular HTML, plus rich-only tags.

### Explicit `InputRichBlock` blocks
For typed generation, CMS/AST output, complex documents, precise structure,
inline media ordering, and to avoid any markdown/HTML parsing ambiguity. Put the
array in `InputRichMessage.blocks`. Most verbose, most deterministic.

### Separate media methods
When the UX is fundamentally a media post — one photo, an album, a document with
a caption. Do **not** also embed the same media in a Rich Message (no
duplication without a product reason). See `rich-media.md`.

## Anti-patterns

- Auto-replacing all `sendMessage` calls with `sendRichMessage`.
- Using Rich Messages for every short notification.
- Treating Rich Markdown as MarkdownV2 (different syntax, different mechanism).
- Introducing a second formatter when one already exists in the project.
- Choosing a richer format than the content needs "to be future-proof".

## Migration stance

Migrate a message class to a richer format only when the audit shows a concrete
defect or unmet need (e.g. tables rendered as broken monospace, AI answers losing
structure). Keep the old formatter until the new path is fully covered and
tested; then remove it in a dedicated step. See `errors-and-fallbacks.md` for the
degradation ladder.
