# Tables — the flagship capability

> **Read this first for any structured content.** Since Bot API 10.1 introduced
> Rich Messages, a bot can send a **real Telegram table** (the same element the
> user-facing Rich Text Editor produces — see the official blog *"Text Editor,
> Communities & Ephemeral Messages"*). Tables are this skill's **first-priority**
> output: whenever data has rows and columns — comparisons, schedules, prices,
> scores, key/value facts, status lists — reach for a table before anything else.
>
> **Last verified against official docs: 2026-07-15** (Bot API 10.2, 14 Jul
> 2026). Exact nested field names of `InputRichBlockTable` are marked *(verify)* —
> confirm them on the official object page for the project's Bot API version
> before relying on them. See `official-sources.md`.

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
    "| Team        | Played | Won | Points |\n"
    "|:------------|-------:|----:|-------:|\n"
    "| Alpha       |     10 |   7 |     21 |\n"
    "| Bravo       |     10 |   6 |     19 |\n"
    "| Charlie     |     10 |   4 |     13 |\n"
)
bot.send_rich_message(chat_id=chat_id, markdown=table)   # exact SDK call varies
```

- Header cells render **bold** automatically — do not also bold them by hand.
- Escape a literal `|` inside a cell as `\|`; keep cell text on one line (use
  `<br>`-equivalent only if the project's Rich Markdown supports it — *verify*).
- Numbers → right-aligned columns; labels → left. See alignment note below.

### 2. Rich HTML (`<table>` with real header cells)

Use `<th>` for header cells and `<td>` for body cells — never fake a header with
bold `<td>`. Whitelist tags/attributes exactly as for regular HTML
(`security-and-escaping.md`); escape `< > &` in every dynamic cell value.

```html
<table>
  <thead>
    <tr><th>Team</th><th>Played</th><th>Won</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>Alpha</td><td align="right">10</td><td align="right">7</td><td align="right">21</td></tr>
    <tr><td>Bravo</td><td align="right">10</td><td align="right">6</td><td align="right">19</td></tr>
  </tbody>
</table>
```

Put the string in `InputRichMessage.html`. Confirm the supported table tag set
(`table`/`thead`/`tbody`/`tr`/`th`/`td` and which cell attributes) on the
official **Rich message formatting options** page before shipping.

### 3. Explicit `InputRichBlockTable` blocks (programmatic — preferred for data)

Build the table as typed objects — no string escaping, no parser ambiguity. This
is the safest path when rows come from a database, API, or CMS.

```python
# Shape is illustrative — VERIFY exact field/type names against the official
# InputRichBlockTable object for your Bot API version (see official-sources.md).
def cell(text, header=False, align="left"):
    return {"is_header": header, "align": align,
            "blocks": [{"type": "paragraph", "text": text}]}

table_block = {
    "type": "table",
    "rows": [
        {"cells": [cell("Team", header=True),
                   cell("Played", header=True, align="right"),
                   cell("Points", header=True, align="right")]},
        *[
            {"cells": [cell(t["name"]),
                       cell(str(t["played"]), align="right"),
                       cell(str(t["points"]), align="right")]}
            for t in standings
        ],
    ],
}
bot.send_rich_message(chat_id=chat_id, blocks=[table_block])
```

- **`is_header: true`** marks header cells; clients render them bold and repeat
  them when the table is scrolled/exported. This is the *semantic* header — always
  use it instead of manual bold.
- Cell content is itself a list of inline/rich blocks, so a cell can hold a link,
  code, or custom emoji — not just plain text.

## Cross-cutting table rules (apply in all three paths)

### Header row
Every table gets a header row. Mark it semantically: `is_header: true` (blocks),
`<th>` (Rich HTML), or the first row above `---` (Rich Markdown). Never simulate a
header with bold body cells — it breaks export and screen readers.

### Alignment
Set `align` per column: **numbers/currency/dates right, text left, short flags
center**. Right-aligned numeric columns are the single biggest readability win in
a Telegram table. Vertical alignment (`top`/`middle`/`bottom`) exists on cells if
the content is multi-line *(verify field name)*.

### Spanning (merged cells)
Use `colspan`/`rowspan` (cell field `> 1`) for merged cells — e.g. a group title
across the top — instead of padding with empty cells. *(Verify the exact field
names.)*

### Column cap
There is a per-table **column limit** (*secondary: ~20 columns — verify before
relying on it*). If data is wider, transpose it (attributes as rows) or split into
two tables with a shared key column. Never silently drop columns — if you cap,
say so.

### Splitting a long table across messages
A Rich Message holds up to **32,768 characters**, so most tables fit in one. If a
table is genuinely too long:

- **Never split mid-row.** Break only between rows.
- **Repeat the header row** at the top of each continuation part so every part is
  self-describing.
- Keep the header physically with its body (don't strand a header at the end of
  part 1). See `limits-and-splitting.md` for the splitter and part-numbering.

### Escaping cell content
One escaper per format (`security-and-escaping.md`):
- **Rich Markdown cell:** escape `|` → `\|`; escape any Markdown-active chars in
  user text; keep to one logical line.
- **Rich HTML cell:** escape `<`, `>`, `&`; whitelist any inline tags you allow.
- **Blocks:** no escaping needed for plain text — that's the point; only apply the
  matching escaper if a cell embeds inline markdown/HTML.

## Data → table recipes

- **Key/value facts** (order summary, profile, config): two columns, left label
  (header optional or a single "Field | Value" header), values right- or
  left-aligned by type. Consider one header row `Field | Value`.
- **List of records** (standings, prices, schedule): one column per attribute,
  one row per record, numeric columns right-aligned.
- **Comparison** (plan A vs B vs C): first column = feature (row header via a
  leading `is_header` cell per row *(verify row-header support)*), one column per
  option, ✓/✗ or values in cells.
- **Diff / before-after:** three columns — item, before, after — with changed
  cells emphasized (bold inside the cell).

## Fallback ladder when Rich Messages are unavailable

Tables are the goal, but degrade explicitly and logged — never silently
(`errors-and-fallbacks.md`):

1. **Rich table** (`sendRichMessage` + markdown/html/blocks) — the default.
2. If the project's Bot API version is **below 10.1** or the SDK can't reach the
   rich methods (`sdk-compatibility.md`): send a **regular message** with a
   monospace `pre` block containing a space-aligned ASCII table. Compute column
   widths in **UTF-16 code units**; pad with spaces; keep it under 4096 chars and
   split by whole rows if needed.
3. If even that is too wide for small screens: emit a **key/value list**
   (`Label: value` lines grouped per record) instead of a cramped grid.

Always log which rung was used and why. Do not claim "sent a table" when the
fallback shipped a monospace block — report what actually went out.

## Verify before you ship

- Open the official **`InputRichBlockTable`** / **Rich message formatting
  options** page and confirm: the type discriminator, the row/cell field names,
  `is_header`, `align`, `colspan`/`rowspan`, and the real column cap.
- Confirm the project's SDK exposes `sendRichMessage`/`InputRichMessage` (or wrap
  the raw Bot API method — `sdk-compatibility.md`).
- Test render on **mobile and desktop** and after an **export** (see
  `testing-playbook.md`) — a table that looks fine on desktop can wrap badly on a
  narrow phone.
