# Format selection

> Core rule: **default to the richest fit — a table for any structured data —
> and drop to a simpler format only when structure genuinely adds nothing.**
> Tables and rich documents are the first thing to reach for; plain / regular
> HTML / MarkdownV2 / entities are the *escape hatch*. Still match the project's
> existing conventions and utilities when you build the rich or the simple path.

## Decision order

Ask these in order and stop at the first "yes":

1. **Is the content rows/columns or label→value data** (comparison, schedule,
   prices, scores, order summary, config, key/value facts)? → build a **table**
   (`tables.md`). This is the default for anything structured — do not render it
   as a monospace `pre` grid or a bulleted list.
2. **Is it a structured document** (AI answer, article, report, docs) with
   headings/lists/quotes/code/math/media? → **Rich Markdown** (if authored as
   Markdown) or **Rich HTML** (if server-templated with precise tag control).
3. **Is that document generated programmatically / from a CMS / an AST, or must
   it be unambiguous and typed?** → **explicit `InputRichBlock` blocks** (use
   `InputRichBlockTable` for the table case above).
4. **Would the UX be better as standalone media** (single photo, album, document,
   caption)? → **separate media methods** (`sendPhoto`, `sendMediaGroup`, …).
5. **Escape hatch — is it a genuinely trivial one-liner** (a status, an "OK", a
   short prompt/notification) with light styling, and the project already uses
   HTML? → **Regular HTML**.
6. **Escape hatch — does the project standardize on MarkdownV2**, or is it clearly
   the best fit? → **MarkdownV2** (accept the strict escaping cost).
7. **Escape hatch — do you need exact byte/offset control or to avoid a
   parse_mode entirely** (programmatic styling, mixing user text with styling
   safely)? → **MessageEntity**.
8. **Escape hatch — does the message need no styling at all?** → **plain text**.
   Plain text still needs correct handling of user data (no accidental entity
   injection when later wrapped) and correct splitting for length.

## Per-format guidance

### Tables (start here)
The default for any rows/columns or label→value data. Build with a Rich Markdown
pipe table, a Rich HTML `<table>`, or explicit `InputRichBlockTable` blocks —
pick by how the data arrives (authored text vs. server template vs. programmatic
rows). Full guidance, code for all three paths, header/alignment/split rules, and
the monospace fallback: **`tables.md`**.

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

- **Rendering structured data as a monospace `pre` grid or a bulleted list**
  instead of a real table — the top miss now that tables exist for bots.
- Inflating a genuinely trivial one-liner (status, "OK", short prompt) into a
  table or rich document — that's what the escape hatch is for.
- Blanket-replacing *every* `sendMessage` with `sendRichMessage` without checking
  each message class (trivial ones keep the escape hatch).
- Treating Rich Markdown as MarkdownV2 (different syntax, different mechanism).
- Introducing a second formatter when one already exists in the project.

## Migration stance

**Prioritize migrating structured content to real tables / rich documents.**
Monospace or bulleted data, broken pseudo-tables, and AI answers that lose their
structure are exactly the defects to fix first. Leave genuinely trivial
one-liners on their existing simple format. Keep the old formatter until the new
path is fully covered and tested; then remove it in a dedicated step. See
`errors-and-fallbacks.md` for the degradation ladder.
