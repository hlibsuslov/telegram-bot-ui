# Visual widget builder, builder/v1

A widget can be described by a typed configuration instead of hand-written HTML. The Studio
renders a form from the type's schema; the server generates the widget source from the
configuration and builds it with the usual pipeline (`widgets.build`: kit, lint, runtime
check, raw and zlib-9 budgets). Hand-written widgets are unchanged.

Owner of this format: the coordinator. Generator and schema: `skills/telegram-bot-ui/scripts/bot_ui/builder.py`.
Form: `studio/web/src/features/widgets/` (renders whatever the schema says).

## Storage (widget.json)

```json
{
  "id": "spring-sale", "title": "Spring sale", "entry": "index.html", "languages": ["en", "ru"],
  "builder": {
    "type": "product",               // message | product | promo | countdown | quiz
    "version": 1,
    "content": { "title": {"en": "Coffee beans", "ru": "Кофе в зёрнах"}, "price": "€14.90", ... },
    "style": {
      "preset": "card",              // telegram | card | soft | contrast | null (= custom)
      "custom": { "block": {...}, "button": {...}, "text": {...}, "image": {...}, "animation": "none" },
      "palette": "per-theme",        // per-theme | shared
      "colors": { "light": {"bg": null, "text": "#111111", ...}, "dark": {...} }
    }
  }
}
```

- While `builder` is present and `builder.ejected` is not true, the generator owns the
  widget's `index.html` (it is regenerated in memory at build time; the Studio never writes
  hand-edited code over it). Ejecting (Pro: "Edit the code") writes the generated
  `index.html`, `style.css`, `widget.js` and sets `builder.ejected: true`; from then on the
  files are the source and the form is read-only. Ejecting is explicit and reversible only
  through Git.
- `content` values that are localized are `{locale: text}` maps; the build for a language
  takes that locale, else the default locale. Empty optional text means the block is not
  rendered and costs no bytes.
- A style field the user changes while a preset is active copies the preset's values into
  `custom`, applies the change and sets `preset: null`. Choosing a preset never overwrites
  `custom`, so "Restore my design" is `preset: null`.
- `colors[theme][slot] = null` means "inherit the Telegram theme" (`--tg-theme-*`). With
  `palette: "shared"` the light slots are used for both themes; the dark slots are kept.
- Request data sent by the widget stays within 64 UTF-8 bytes; the bot's handler decides on
  the server (prices, stock, codes); widget numbers are display only.

## Schema (`POST /api/widget/builder-schema` -> this shape)

```json
{
  "version": 1,
  "types": {
    "product": {
      "title": "Product card", "summary": "...", "icon": "shopping-bag",
      "sections": [ {"id": "content", "title": "Content", "fields": [FIELD, ...]} ],
      "states": [ {"id": "default", "title": "Ready"} ],       // preview states for interactive types
      "defaults": { ...content... }
    }
  },
  "style": { "sections": [ ... ], "presets": [ {"id": "card", "title": "Card", "values": {...}} ],
             "colorSlots": { "common": [...], "product": [...], "quiz": [...] } }
}
```

FIELD: `{key, label, type, help?, default?, localized?, max?, min?, step?, multiline?,
options?: [{value, label}], when?: {key, eq | in}, item?: {fields: [FIELD]}, minItems?,
maxItems?, toggle?}` where `key` is a dot path inside `content` (or `style.custom`), `when`
hides the field unless another key matches, and `toggle` names a boolean key that shows or
hides the block while keeping its values.

Types: `text`, `number`, `toggle`, `choice`, `color`, `datetime` (unix seconds, entered in the
author's time zone, stored absolute), `list` (items with stable `id`), `action`
(`{kind: request | link | copy, ...}`: request -> `data` <= 64 B and `done` text <= 64;
link -> https URL <= 256; copy -> text <= 256, empty = the button label), `image` (name of an
SVG asset in the widget folder).

## Types, first iteration

| Type | Content | Preview states |
| --- | --- | --- |
| message | image, title (80), text (400), button label (32) + action, footnote (400) | default |
| product | image, name, description, price (24), old price (24, struck when a new one is set), quantity counter (max 1-99), badge (16, corner), button + action (`{n}` = quantity in request data and done text), footnote; each block has a show toggle | default, tapped |
| promo | title, text, code (24), reveal: immediately or on tap (closed label 24; the code comes from the bot's answer), caption under the coupon (40), coupon look, button + action | closed, revealed, copied |
| countdown | title, text, deadline (absolute), finished text (60), digits look, button + action | running, finished |
| quiz | 1-5 questions x 2-4 answers (80 / 32, stable ids), result text (160), final button + action (request data = answer ids), "play again" | question N, result |

Preview requests are answered by `builder.mock_answers(config)` (synthetic, local).
Moderation, scheduling and publishing are out of scope (separate lifecycle).

## Generated code, requests and preview states

- One source serves every language: localized texts are `/*@lang xx*/K.add(...)` blocks and the
  build keeps the one it is for, so an ejected widget keeps all its languages. Colours are
  `--c-<slot>` custom properties on the root block: a `--k-*` theme token by default,
  `light-dark(light, dark)` for chosen colours (a null side keeps the token).
- Style extras over the table above: `block.fill` (theme card colour), `button.look: native`
  (the app draws its own button; radius and height do not apply), `image.aspect` for a full-width
  picture, `animation: none | calm | lively` (the kit turns it off under reduced motion).
- Requests (all <= 64 bytes): the button's `data` (product: `{n}` = chosen quantity); promo on
  tap sends `promo` and expects `{ok, s: {c: code, r}}` (or `c` in the answer); quiz sends
  `data + ":" + answer ids joined by "."`. The answer's `s` becomes `chat_data`; `msg` overrides
  the done text.
- `chat_data` the generated widgets read (what a real bot stores): product `{n}` (confirmed
  quantity, shows the done text), promo `{c, cp?}` (revealed code, copied), countdown `{d}`
  (moves the deadline), quiz `{a: "a1.a5.a9"}` (submitted: shows the result).
- Preview state ids (`schema.types[t].states`): message `default`; product `default | tapped`;
  promo `closed | revealed | copied`; countdown `running | finished`; quiz `q1 … qN | result`
  (N = number of questions; the schema lists q1-q5). The first id is what production shows.
  `/api/widget/build {state}` bakes any other state into that build only (its `sourceHash`
  includes the state and export refuses it); export builds use the first state.

## Endpoints

- `POST /api/widget/builder-schema {}` -> the schema above (defaults in the project's locales).
- `POST /api/widget/builder-validate {config, widget?}` -> `{ok, issues: [{pointer, code, message}]}`;
  with `widget` the image names are checked against its SVG files.
- `POST /api/widget/eject {widget, expectedRevision}` -> the store's write result; 409 on a
  revision conflict, 422 when the widget is hand-written or already ejected.
- Library: `builder:message|product|promo|countdown|quiz` templates (`source: "builder"`) come
  right after `blank`; creating one writes widget.json and a placeholder index.html.
