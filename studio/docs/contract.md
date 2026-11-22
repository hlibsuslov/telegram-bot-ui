# bot-ui project contract, schemaVersion 1

One versioned source of a Telegram bot interface inside the bot's repository. The skill,
the CLI (`studio/bot-ui.py`), the local Studio, the interactive artifact and the adapters
read and write the same files through the same rules. The format version (`schemaVersion`)
is independent of the tool version, the Bot API version and any SDK version.

Executable form of this document: `studio/bot_ui/` (Python, canonical), `studio/web/src/core/`
(TypeScript port for the browser, checked by `tests/test_bot_ui_parity.py`), fixtures in
`studio/templates/checkout/` (valid project and scenarios) and `studio/fixtures/` (failures).

## Files

```text
bot-ui/
  project.json                 schemaVersion, projectId, locales, entry points, fields, handlers
  screens/<screenId>.json      one screen = one main message, keyboard, actions
  scenarios/<scenarioId>.json  ordered synthetic events for the simulator and tests
  widgets/<widgetId>/          widget.json + index.html (+ style.css, widget.js)
  widgets/_kit/                widget kit partials, vendored by `bot-ui init`
  .bot-ui/                     lock, write journal, build cache (ignored by Git and the revision)
```

The revision is `sha256:` over the sorted relative paths and bytes (CRLF read as LF) of the
source files above. Editor history, mtime, `.bot-ui/` and anything else are ignored.

## Identity

- IDs: lowercase ASCII letters, digits, `_`, `-`, with `.` between segments; at most 64
  characters; no Windows reserved names as a segment. Example: `checkout.payment.confirm`.
- A screen ID never changes with content, locale, position on the map or title. The file is
  `screens/<id>.json`; a different name, a duplicate ID or two paths that differ only in
  letter case are errors (one file on Windows).
- Actions are addressed by `(screenId, actionId)`; action IDs are one segment.
- `callback_data` = explicit `callbackData` of the action (keep the old bot's values there),
  else `<screenId>:<actionId>`, else `h:` + 32 hex of SHA-256 when that is over 64 bytes.
  The same value on several screens is fine when every button with it does the same thing
  (`CALLBACK_SHARED`, info: old bots reuse "menu"); the same value with another effect is an
  error (`CALLBACK_COLLISION`). The adapter picks the screen the pressed message shows.
- A message is addressed by `(screenId, message.id)`. Telegram message IDs, row indexes and
  titles are never identity.
- Renaming or deleting an ID is a migration. v1 has no rename; deleting a screen with
  incoming links or entry points is refused (`SCREEN_HAS_INCOMING`).

## project.json

| Field | Meaning |
| --- | --- |
| `schemaVersion` | `1`. Another value opens read-only (`SCHEMA_VERSION_UNSUPPORTED`). |
| `projectId` | Stable ID; a patch for another project is refused. |
| `defaultLocale`, `locales` | Every text has the default locale; others warn when missing. |
| `entryPoints[]` | `{id, type: command\|event\|deeplink, command\|eventKey\|payload, screen}`. A screen ID alone is not a public entry point or a permission to broadcast. |
| `contexts` | Audiences the bot runs in (`private`, `group`, ...). v1 targets `private`. |
| `fields` | `{name: {type: string\|number\|boolean\|enum, values?, source: data\|context\|state\|input, maxLength?, example?}}`. Placeholders `{name}` and rules refer to these. |
| `handlers` | `{handlerId: {outcomes: [..]}}`: code the bot registers; the UI maps outcomes. |
| `messages` | `stale`, `disabled` texts used by the engine. |
| `capabilities` | `widgets`, `richMessages` of the target environment; `customEmoji`: `fragment` (the bot bought extra usernames on Fragment), `owner_premium` (the owner has Premium: private, group, supergroup only) or `none` (default). Telegram drops custom emoji from an ineligible bot without an error, so every use warns while it is `none`. |
| `adapter` | SDK name and version for documentation; never a token. |

`source`: `data` (fixtures, server data), `context` (trusted runtime: chat type, delivery
method set by the server), `state` (set by an action's `set`), `input` (typed by the user).

## Screen

```json
{
  "id": "orders.status", "title": "...", "kind": "status", "audience": "private",
  "message": {"id": "main", "format": "regular.html", "text": {"ru": "...", "en": "..."},
              "states": {"loading": {"text": {"ru": "...", "en": "..."}}}},
  "keyboard": {"type": "inline", "rows": [["route"], ["refresh", "back"]]},
  "actions": {
    "route": {"label": {...}, "type": "navigate", "presentation": "send",
              "rule": {"when": {"field": "delivery.method", "eq": "pickup"},
                       "match": "orders.pickup", "otherwise": "orders.delivery"}},
    "refresh": {"label": {...}, "type": "answer", "text": {...}},
    "back": {"label": {...}, "type": "back", "fallback": "entry.start"}
  },
  "input": {"field": "order.note", "to": "checkout.payment.confirm"},
  "widget": {"ref": "order-status"}
}
```

- `kind`: entry, menu, form, confirmation, result, error, empty, loading, notification, status.
- `message.format`: `regular.plain` and `regular.html` are edited in the Studio;
  `regular.markdownv2` renders; `regular.entities`, `rich`, `media.photo` are kept and open
  read-only (`FORMAT_READ_ONLY`). Unknown fields anywhere are kept on write.
- `keyboard.type`: `inline` (callback buttons), `reply` (a press arrives as text equal to the
  label), `force_reply` (asks for text; `placeholder`), `remove`, `none`.
- Action types: `navigate` (`to` or `rule`), `back` (`fallback` after a restart), `url`
  (never followed by the graph or the simulator), `answer` (toast), `handler` (`handlerId`,
  `outcomes`, `pending`), `disabled` (answers that it is unavailable). Optional:
  `presentation` (`edit` | `send`), `set` (state fields), `style` (primary/success/danger),
  `callbackData`, `hidden`.
- Placeholders `{field}` are escaped for the format at render time; `{{` and `}}` are braces.
- `message.media` (optional): `{type, file, spoiler?, emoji?}`. `type`: `photo`, `video`,
  `animation`, `audio`, `voice`, `video_note`, `sticker`. `file` is exactly one of
  `{"fileId": "..."}`, `{"url": "https://..."}` or `{"field": "<declared string field>"}`; bot-ui
  never uploads local files and has no documents. The text is the caption (at most 1024)
  for photo, video, animation, audio and voice; a sticker or video note has no text
  (`MEDIA_NO_CAPTION`). `spoiler` applies to photo, video, animation. `emoji` lets previews
  show a sticker. Sends: `sendPhoto` ... `sendSticker`; edits: `editMessageMedia` for photo,
  video, animation, audio (also text -> media); media -> text, voice, video notes and stickers
  are never edited: the engine sends a new message (`fallback` `edit_kind`).
- Custom (premium) emoji: in `regular.html` text `<tg-emoji emoji-id="<digits>">😀</tg-emoji>`
  with one ordinary emoji inside as the fallback; on a button `"icon": {"customEmojiId": "<digits>"}`
  (sent as `icon_custom_emoji_id`, inline and reply keyboards). The label must read well
  without the icon. Stickers are `message.media` of type `sticker`.

## Premium emoji library (optional)

`emoji/library.json` (`format: bot-ui-emoji/v1`), written by the Studio's Emoji page and
`bot-ui emoji`, committed with the project:

- `packs.<name>`: `{title, link, importedAt, formats, source, emoji: [{id, fallback, format, adaptive}]}`
  from `getStickerSet` (`sticker_type` must be `custom_emoji`). `fallback` is the sticker's own
  emoji, `format` is `static`, `animated` (TGS) or `video` (WEBM), `adaptive` = `needs_repainting`
  (Telegram paints it in the text colour).
- `icons.<slot>`: `{id, set, fallback, animated, adaptive, note?}`, the bot's icon map. A slot is a
  meaning (`data/emoji/slots.json` of the skill, or the user's own lowercase name); one emoji has
  one meaning. The skill's `scripts/audit_icons.py` reads this file as an icon map.

Pictures live in `.bot-ui/emoji/<id>.<webp|webm|png|jpg>`, a local cache that is never committed;
without it every surface shows the fallback. Only an import by link goes online. By default it
asks the telegram-bot-ui resolver (`GET https://telegram-bot-ui-site.vercel.app/api/emoji-pack/<name>`
and the picture paths it returns), which reads the pack with the project's own bot: the user
needs no token and only the pack name is sent. `BOT_UI_EMOJI_RESOLVER` sets another resolver URL
or `off`. With a token of the user's own (the Studio form, or `TELEGRAM_TEST_BOT_TOKEN` /
`BOT_TOKEN` when the resolver is off) the Studio reads the pack itself (read-only `getStickerSet`,
`getFile`, the file download on api.telegram.org); that token is never stored. A saved
`getStickerSet` response imports offline without pictures. The library is not part of the
revision. With a library, `validate` adds `CUSTOM_EMOJI_UNKNOWN` (id not in it, info) and
`CUSTOM_EMOJI_FALLBACK_MISMATCH` (fallback differs from the pack's emoji, info); always,
`CUSTOM_EMOJI_DOUBLE_ICON` (button icon plus an emoji at the start of the label, warning).
`bot-ui emoji brief [--json]` is what an agent reads before placing custom emoji.

## Transition rule

One declarative condition per navigate action: `when.field` (a declared `context` or
`state` field), `when.eq` (a value of its type), and two existing targets `match` and
`otherwise`. No expressions are executed. Fields from `input` or a widget are not trusted
context (`RULE_FIELD_UNTRUSTED`). Checks: declared field, value type, both targets exist,
same audience (`AUDIENCE_MISMATCH`). The trace shows the field, whether it matched and the
branch, never the value. Business permissions stay on the server.

## Diagnostics

`{code, severity: error|warning|info, file, pointer, screenId?, message}`. Errors block a
write. `bot-ui validate --json` lists them all; the Studio shows them next to the field.

## Writes

Every write is a `bot-ui-patch/v1` document:

```json
{"format": "bot-ui-patch/v1", "projectId": "demo-shop", "baseRevision": "sha256:...",
 "changes": [
   {"screenId": "checkout.payment.confirm",
    "ops": [{"op": "set", "path": "/message/text/ru", "value": "...", "from": "<old value>"}]},
   {"screenId": "new.screen", "create": {...}},
   {"widgetId": "order-status", "file": "style.css", "content": "...", "fromHash": "sha256:..."}
 ]}
```

- Paths are an allowlist of JSON pointers (`store.ALLOWED_PATHS`): texts, labels, keyboard,
  actions and their targets/rules, input, widget reference. `/id` is never writable.
- Under a cross-process lock (`.bot-ui/write.lock`) the project is re-read. A different
  revision returns `REVISION_CONFLICT` with `currentRevision` and `fieldConflicts` (ops whose
  `from` no longer matches) and writes nothing. `--rebase` applies on the newer revision only
  when `fieldConflicts` is empty.
- The future snapshot is validated; any error refuses the write (`VALIDATION_FAILED`).
- Files are written to a temp file in the same folder and `os.replace`d. Several files form a
  transaction: originals go to `.bot-ui/txn/`, `.bot-ui/journal.json` lists them; a crash
  is rolled back the next time the project opens (`WRITE_RECOVERED`).
- Paths resolve inside the project root only: no absolute, UNC or drive paths, no `..`,
  no symlinks or junctions.
- An equivalent patch on the current revision writes nothing and returns an empty diff.
- Manual edits outside this protocol are allowed; they simply change the revision, so the
  next protocol write from an older revision conflicts instead of overwriting them.

## Simulation

See `studio/bot_ui/engine.py`. Session: active screen, locale, context, state, data, input,
history (Back), message instances (with accessibility), active inline message, reply keyboard,
awaited input. Events: `command`, `text`, `press` (optionally on an older `message`), `event`
(external `eventKey` with `data`), `context`, `locale`, `inaccessible`, `expect`. Effects:
`send`, `edit`, `answer`, `fallback`, `link`, `noop`. Message instances are numbered from 1;
no clocks. Policies: a press on a message that no longer shows the action is stale
(acknowledged, nothing else changes); an edit that Telegram cannot do (inaccessible message,
widget, reply/ForceReply keyboard) becomes `fallback` + `send`; a widget outside a private chat
or with widgets disabled becomes its screen's regular message.

## Adapter

An adapter maps an incoming update to an engine event (callback_data -> `(screenId, actionId)`
through the same `callback_data` rule; `/command` and text as is), runs the engine with the
bot's registered handlers, and turns effects into Bot API requests with `render.bot_request`
(sendMessage / editMessageText / answerCallbackQuery / sendWidget) through an injected
transport. Context (chat type, delivery method) comes from the trusted runtime, never from
callback data. The project is read on start and re-read when its revision changes.

## Artifact

`bot-ui export-snapshot --output studio.html` writes one self-contained HTML file: the Studio
client in artifact mode plus a `bot-ui-snapshot/v1` document (projectId, schemaVersion,
baseRevision, the screens, scenarios and the project's declared fields; no paths, tokens or
widget sources). It edits texts and rules, simulates both branches and exports a
`bot-ui-patch/v1` file. Writing to Git is always `bot-ui apply-patch --patch-file ...`, with the
same checks as a Studio save; a patch from an older revision conflicts.

## Widget data fields (optional, for people)

`widget.json` may describe the keys of `chat_data` / `public_data` so the Studio can show a
form instead of raw JSON. Unknown or undescribed keys still work and stay editable as JSON.

```json
"dataFields": {"chatData": {
  "s":  {"label": "Current step", "type": "choice", "options": [{"value": 0, "label": "Order placed"}]},
  "eta": {"label": "Expected arrival", "type": "time"},
  "r":  {"label": "Data version", "type": "number", "advanced": true, "help": "The bot sets it."}
}}
```

`type`: `text`, `number`, `choice` (`options` with typed values), `time` (unix seconds),
`boolean`. `advanced: true` hides the field in Beginner mode. Labels are for the editor only;
nothing here is sent to Telegram.
