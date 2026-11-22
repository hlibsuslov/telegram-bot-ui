# Widget design tab

The widget workbench has two editors: **Design** (no code) and **Code** (the files). Design writes
`widgets/<id>/design.json`, a design profile that the skill compiles to CSS at build time
(`skills/telegram-bot-ui/scripts/widget_design.py`, rules in
`references/widget-design-system.md#14-design-profiles-designjson`). Markup, script and texts are
never touched, so the same controls restyle every kit widget: all 18 gallery samples, in every
language, with every preset, stay under Telegram's 4096-byte limit (`tests/test_widget_design.py`).

## What a hosted widget builder offers, and where we stand

A paid builder of HTML widgets for Telegram (reviewed from screenshots, 2026-11-22) has four
steps: Template, Text, Design, Placement. Its Design step, function by function:

| Their function | Ours | Status |
|---|---|---|
| Ready-made looks (4 tiles, light and dark halves) | 6 presets: Telegram, Card, Soft, Contrast, Lines, Showcase; "My design" restores what a preset replaced | done |
| Colours: own per theme or one for both; light/dark preview switch; "unset = Telegram's colour"; reset one / reset all | same, 13 slots (theirs: about 9), unset swatches show Telegram's real colour per theme | done |
| Block background + second colour (gradient), border colour | `bg`, `bg2`, `border` | done |
| Counter colours | `surface` (chips, cards, counter, tracks) | done |
| Parent block: corners, border width, padding, gap between blocks, content position | corners, border, padding, **gap to the bubble**, position | done, except gap between blocks (our samples are interactive layouts with their own spacing) |
| Motion: none / calm / lively, replay, Reduce motion respected | same; motion never uses opacity or blur (Telegram stops a widget with more than 16 such elements) | done |
| Button: filled/outline, corners, height, width, position | Telegram/filled/outline/soft/text, corners, height, width, position; restyled through Telegram's button variables, so pressed and disabled states stay | done |
| Title and texts: size and position for title, main and secondary text | same | done |
| Counter: outline/filled, corners | same, plus chip corners, selected-chip style, card corners, progress bar height and corners | done |
| Coupon: dashed / filled / ticket | needs a coupon part in the kit and a promo template | next |
| Badge: colour (label turns white or dark by itself), corners, corner position | needs a badge part in the kit | next |
| Picture: upload SVG ≤ 30 KB or PNG/JPEG/WebP ≤ 3 MB, resized to 96 px and ≤ 2 KB; SVG cleaned; width, aspect, corners, position | corners and backdrop for the picture area; upload and conversion not yet | next |
| AI illustration (paid tier) | — | later |
| Telegram limit meter ("57 %") | HTML, zlib-9 and state meters, plus "this look adds N B" | done |
| Preview in a group or a channel post with "forwarded from" | private chat preview; widgets cannot be posted in channels, only forwarded (Telegram guide) | next: a "forwarded to a channel" preview |

What we add that they do not show: contrast check in both themes (WCAG 4.5:1 text, 3:1 labels),
a warning when the background paints the whole bubble, sections only for parts the widget has,
per-option byte cost (unused options cost nothing), code view of the same profile, export of the
built HTML with a ready `sendWidget` payload, and the same profile from the command line
(`build_widget.py --design`, `preview_widget.py --design <preset>`).

## Next steps, in order

1. Kit parts `badge` and `coupon` (markup class, tokens, design options) and a promo template.
2. Picture upload: SVG sanitising and raster downscale to a `data:` image inside the budget.
3. Template and Text steps for non-developers (pick a sample, edit its strings per language).
4. "Forwarded to a channel" preview context.
