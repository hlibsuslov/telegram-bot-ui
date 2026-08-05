# Tables — the flagship capability

> **Read this first for any structured content.** Since Bot API 10.1 introduced
> Rich Messages, a bot can send a **real Telegram table** (the same element the
> user-facing Rich Text Editor produces). Tables are this skill's
> **first-priority** output: whenever data has rows and columns — comparisons,
> schedules, prices, scores, key/value facts, status lists — reach for a table
> before anything else.
>
> **Last verified against official docs: 2026-08-05** (Bot API 10.2, 14 Jul
> 2026). Field names below were read directly from the official
> `InputRichBlockTable` / `RichBlockTableCell` object pages and the *Rich Message
> Formatting Options* section — they are **confirmed, not guessed**.

**Don't wait to be asked.** Spotting table-shaped content and *offering* the
table is part of the job — see `content-shape-detection.md` for the detection
signals and the wording of the offer.

## When a table is the right call

Reach for a table when the content is **two or more parallel records with shared
attributes**, or **label → value pairs** you want aligned. Examples: a price
list, a match schedule, a feature comparison, quiz results, a config diff, a
leaderboard, an order summary. If the content is genuinely one flat sentence or a
single status line, use the escape hatch (plain/regular message) — see
`format-selection.md`. Everything with structure defaults to a table.

**Do not fake tables.** A monospace `pre` block with hand-aligned spaces is a
*fallback of last resort* (see the bottom of this file), never the default. Real
tables reflow correctly on every client, export cleanly, and stay aligned.

## The three ways to build a table (pick by how the data arrives)

All three are carried inside **one** `InputRichMessage` and sent with
`sendRichMessage` (or streamed with `sendRichMessageDraft`, or replaced with
`editMessageText` + `rich_message`). `InputRichMessage` holds **exactly one** of
`markdown`, `html`, or `blocks`.

| Data source | Build path | Field |
|---|---|---|
| Text the model/author writes naturally | **Rich Markdown** pipe table | `markdown` |
| Server-side template with precise tag control | **Rich HTML** `<table>` | `html` |
| Rows from a DB / API / CMS / AST — programmatic | **Explicit blocks** `InputRichBlockTable` | `blocks` |

Prefer **blocks** when the rows come from data (no string-escaping pitfalls, no
parser ambiguity). Prefer **Rich Markdown** for naturally-authored answers.

### 1. Rich Markdown (GitHub-style pipe table)

The first row is the **header**; the `---` separator row sets per-column
alignment (`:--` left, `:-:` center, `--:` right).

```python
table = (
    "| Team    | Played | Won | Points |\n"
    "|:--------|-------:|----:|-------:|\n"
    "| Alpha   |     10 |   7 |     21 |\n"
    "| Bravo   |     10 |   6 |     19 |\n"
)
# InputRichMessage.markdown = table  → sendRichMessage (exact SDK call varies)
```

- Header cells render **bold** automatically — do not also bold them by hand.
- Escape a literal `|` inside a cell as `\|`.
- **Cells accept inline formatting only** (official constraint): bold, italic,
  `code`, links, `<sup>`/`<sub>`, `<tg-spoiler>`, custom emoji, math. **No block
  content** — no lists, no nested tables, no paragraphs, no media inside a cell.
- Numbers → right-aligned columns; labels → left.

### 2. Rich HTML (`<table>` with real header cells)

```html
<table bordered striped>
  <caption>Season standings</caption>
  <tr><th>Team</th><th align="right">Played</th><th align="right">Points</th></tr>
  <tr><td>Alpha</td><td align="right">10</td><td align="right">21</td></tr>
  <tr><td>Bravo</td><td align="right">10</td><td align="right">19</td></tr>
</table>
```

- **Do not use `<thead>` / `<tbody>` / `<tfoot>`** — they are *not* in Telegram's
  supported Rich HTML tag set. Put `<tr>` directly inside `<table>`.
- `bordered` and `striped` are **bare boolean attributes** on `<table>`.
- `<caption>` supplies the table caption.
- Header cells are `<th>`; body cells `<td>`. Never fake a header with a bold
  `<td>`.
- Cell attributes: `align` (`left`/`center`/`right`), `valign`
  (`top`/`middle`/`bottom`), `colspan`, `rowspan`.
- Escape `<`, `>`, `&` in every dynamic cell value. Rich HTML supports only these
  named entities: `&lt; &gt; &amp; &quot; &apos; &nbsp; &hellip; &mdash; &ndash;
  &lsquo; &rsquo; &ldquo; &rdquo;` (plus all numeric entities). See
  `security-and-escaping.md`.

### 3. Explicit `InputRichBlockTable` blocks (programmatic — preferred for data)

Build the table as typed objects — no string escaping, no parser ambiguity. This
is the safest path when rows come from a database, API, or CMS.

**`InputRichBlockTable`** — verified fields:

| Field | Type | Notes |
|---|---|---|
| `type` | String | always `"table"` |
| `cells` | **Array of Array of `RichBlockTableCell`** | rows of cells |
| `is_bordered` | True | *Optional.* table has borders |
| `is_striped` | True | *Optional.* table is striped |
| `caption` | `RichText` | *Optional.* caption of the table |

**`RichBlockTableCell`** — verified fields (there is **no** separate
`InputRichBlockTableCell`; the input table reuses this class):

| Field | Type | Notes |
|---|---|---|
| `text` | `RichText` | *Optional.* **If omitted, the cell is invisible** — this is how you leave a hole under a `rowspan`/`colspan`. |
| `is_header` | True | *Optional.* header cell (renders bold) |
| `colspan` | Integer | *Optional.* columns spanned, if > 1 |
| `rowspan` | Integer | *Optional.* rows spanned, if > 1 |
| `align` | String | `left` / `center` / `right` |
| `valign` | String | `top` / `middle` / `bottom` |

`RichText` is **either a plain String**, an Array of `RichText`, or one of the
typed `RichText*` objects (bold, italic, code, url, custom emoji, math, …). For
ordinary cells a plain string is enough — that is the whole point of this path.

```python
def cell(text, header=False, align=None):
    c = {"text": text}
    if header:
        c["is_header"] = True
    if align:
        c["align"] = align
    return c

table_block = {
    "type": "table",
    "caption": "Season standings",
    "is_striped": True,
    "cells": [
        [cell("Team", header=True),
         cell("Played", header=True, align="right"),
         cell("Points", header=True, align="right")],
        *[
            [cell(t["name"]),
             cell(str(t["played"]), align="right"),
             cell(str(t["points"]), align="right")]
            for t in standings
        ],
    ],
}
# InputRichMessage.blocks = [table_block]  → sendRichMessage
```

- **`is_header: true`** marks header cells semantically; clients render them
  bold. Always use it instead of manual bold.
- Rows are just the outer array — there is **no row object** and no `rows` field.
- A cell's `text` is `RichText`, so it can hold a link, code, or custom emoji —
  but still **inline content only**, never blocks.

## Cross-cutting table rules (apply in all three paths)

### Header row
Every table gets a header row. Mark it semantically: `is_header: true` (blocks),
`<th>` (Rich HTML), or the first row above `---` (Rich Markdown). Never simulate a
header with bold body cells — it breaks export and screen readers.

### Alignment
Set `align` per column: **numbers/currency/dates right, text left, short flags
center**. Right-aligned numeric columns are the single biggest readability win in
a Telegram table. `valign` (`top`/`middle`/`bottom`) handles multi-line cells —
align text **top** when rows have uneven height.

### Spanning (merged cells)
Use `colspan`/`rowspan` (> 1) for merged cells — e.g. a group title across the
top. To leave the covered position empty, emit a cell with **no `text`** (an
omitted `text` renders an invisible cell) rather than a cell containing `""`.

### Column cap — 20 (officially documented)
A table may have **up to 20 columns** (official *Rich Message Limits*). If data
is wider, transpose it (attributes as rows) or split into two tables with a
shared key column. Never silently drop columns — if you cap, say so.

### Other official limits that bite tables
- **500 blocks** per rich message — and **table rows count as blocks**. A 400-row
  table will not fit alongside anything else; paginate it.
- **32,768 UTF-8 characters** per rich message (content past ~8,000 collapses
  behind "Show More").
- **16 levels** of nested formatting/blocks.

### Splitting a long table across messages
- **Never split mid-row.** Break only between rows.
- **Repeat the header row** at the top of each continuation part so every part is
  self-describing.
- Keep the header physically with its body (don't strand a header at the end of
  part 1). See `limits-and-splitting.md` for the splitter and part-numbering.

### Escaping cell content
One escaper per format (`security-and-escaping.md`):
- **Rich Markdown cell:** escape `|` → `\|`; escape Markdown-active chars in user
  text; keep to one logical line.
- **Rich HTML cell:** escape `<`, `>`, `&`; whitelist any inline tags you allow.
- **Blocks:** no escaping needed for plain-string `text` — that's the point; only
  apply the matching escaper if a cell embeds inline markdown/HTML.

## Data → table recipes

- **Key/value facts** (order summary, profile, config): two columns, left label,
  values aligned by type. Consider a `Field | Value` header.
- **List of records** (standings, prices, schedule): one column per attribute,
  one row per record, numeric columns right-aligned.
- **Comparison** (plan A vs B vs C): first column = feature, one column per
  option, ✓/✗ or values in cells. Mark the leading cell of each row
  `is_header: true` for a row-header effect.
- **Diff / before-after:** three columns — item, before, after — with changed
  cells emphasized (bold inside the cell).

## Fallback ladder when Rich Messages are unavailable

Tables are the goal, but degrade explicitly and logged — never silently
(`errors-and-fallbacks.md`):

1. **Rich table** (`sendRichMessage` + markdown/html/blocks) — the default.
2. If the project's Bot API version is **below 10.1** (or below 10.2 for
   `blocks`) or the SDK can't reach the rich methods (`sdk-compatibility.md`):
   send a **regular message** with a monospace `pre` block containing a
   space-aligned ASCII table. Compute column widths in **UTF-16 code units**;
   pad with spaces; keep it under 4096 chars and split by whole rows.
3. If even that is too wide for small screens: emit a **key/value list**
   (`Label: value` lines grouped per record) instead of a cramped grid.

Always log which rung was used and why. Do not claim "sent a table" when the
fallback shipped a monospace block — report what actually went out.

## Verify before you ship

- Confirm the project's SDK exposes `sendRichMessage` / `InputRichMessage` — and
  that it is on **Bot API 10.2+** if you use `blocks` (10.1 shipped Rich Messages
  but *not* the `InputRichBlock*` input classes). Otherwise wrap the raw Bot API
  method (`sdk-compatibility.md`).
- Re-read the official object pages if today is well past the verification date
  above (`official-sources.md`).
- Test render on **mobile and desktop** and after an **export** (see
  `testing-playbook.md`) — a table that looks fine on desktop can wrap badly on a
  narrow phone.
