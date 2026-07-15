# Localization and RTL

Formatting must survive translation and mixed text direction. Localized strings
are **untrusted input** for the target format — escape them at the boundary.

## What to check in localized templates

- Templates that mix markup with **interpolated variables** — a translator may
  move or break the markup around a placeholder. Prefer placeholders that don't
  sit inside fragile markup; validate rendered output per locale.
- **Cyrillic** and other Latin-adjacent scripts — usually fine, but still escape.
- **Arabic / Persian / Hebrew** (RTL) — direction, punctuation mirroring,
  and placement of LTR runs (numbers, URLs, usernames, code) inside RTL text.
- **Mixed RTL/LTR** — the hardest case; see below.
- Numbers, URLs, `@usernames`, emoji, inline code, formulas, tables, lists,
  quotes — all render inside a direction context and can look reversed or
  mis-grouped.

## RTL guidance

- Do **not** decide direction solely from the UI language. The **message
  content** may be a different direction (e.g. an English quote inside an Arabic
  message, or vice versa).
- Use the `is_rtl` signal where the Bot API/objects expose it (verify for your
  version) to mark direction explicitly rather than guessing.
- Keep **LTR islands** (numbers, URLs, code, usernames) intact within RTL text;
  they should not be visually reordered. Where needed and supported, use
  directional isolation so an LTR span doesn't flip surrounding RTL punctuation.
- For **tables** and **lists** in RTL, confirm column/marker order renders as
  intended per locale.

## Escaping and localization together

- Escape each localized string for the **specific target format** (HTML vs.
  MarkdownV2 vs. Rich HTML vs. Rich Markdown) — not once, generically.
- Never let a translated string introduce unescaped control characters that
  reinterpret as structure (a stray `_`, `*`, `|`, `#`, `<`).
- For structured localized content, prefer **explicit blocks** so translated text
  is treated as data, not markup.

## Testing localization

Cover at minimum: Latin, Cyrillic, Arabic/Persian/Hebrew, mixed-direction,
emoji, and combining characters — for each format the project uses. Verify that
placeholders, entities/offsets, and split boundaries stay correct per locale.
See `testing-playbook.md`.
