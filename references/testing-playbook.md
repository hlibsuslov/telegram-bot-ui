# Testing playbook

> Use the **project's existing test infrastructure**. Do not add a new test
> framework unless the project has none and one is required. Do not send real
> messages or use a real bot token in tests — assert on the **payload** your code
> would send (rendered string, entities, blocks, split parts).

## What to assert

- Rendered output string for the chosen `parse_mode`, or the `entities[]` array,
  or the `InputRichMessage` (`markdown`/`html`/`blocks`) structure.
- Split parts: count, boundaries, offsets, preserved keyboards/reply/topic.
- Fallback path selection per failure class.

## Regular formatting

plain text · HTML · MarkdownV2 · entities · arbitrary user input · special
characters · links · emoji · code · spoilers · block quotes · long messages.

## Rich Markdown

headings · emphasis · lists · task lists · tables · quotes · code blocks ·
formulas · details · references · media.

## Rich HTML

supported tags · unsupported tags (stripped/escaped) · nesting · escaping ·
malformed input · unsafe attributes · URL validation · media references.

## Blocks

paragraph · heading · list · table · quotation · details · mathematical
expression · media · invalid nesting · over-limit (blocks/depth/columns/media).

## Streaming

start · multiple updates · completion · cancellation · timeout · 429 backoff ·
final-send failure. Assert throttling and stable `draft_id` reuse.

## Localization

Latin · Cyrillic · Arabic/Persian/Hebrew · mixed direction · emoji · combining
characters. Assert placeholders, offsets, and split boundaries per locale.

## Regression cases (must-have)

- `can't parse entities`.
- wrong entity offset (UTF-16/surrogate off-by-one).
- unclosed tag.
- broken link split across parts.
- code block split mid-fence.
- double escaping.
- lost keyboard on split/edit.
- HTML shown as literal text (wrong/absent parse_mode).
- corrupted localized template.
- over-limit payload.
- `message is not modified` on edit.

## Verification checklist before "done"

- [ ] Tests cover each format the change touches.
- [ ] Regression cases above are represented where relevant.
- [ ] No real bot token, no real network sends in tests.
- [ ] Project lint / typecheck / test / smoke commands run and pass.
- [ ] Evidence (command output) captured for the final report.
