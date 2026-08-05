# SDK compatibility

The project's SDK — not your memory — decides which UI and formatting features
are reachable. Establish the SDK, its version, and the Bot API version it
implements before designing anything (`project-adaptation.md`).

## Determine actual capability

For the feature you need (e.g. `style`, `icon_custom_emoji_id`,
`sendRichMessageDraft`, `InputRichMessageMedia`), confirm it exists in **this**
SDK version by checking, in order:

1. The SDK's release notes / changelog for the Bot API version.
2. The installed types/methods (imports, symbols, generated bindings).
3. The SDK source.
4. The SDK issue tracker (known gaps, planned support).

Do not assume parity between the latest Bot API and the SDK — SDKs lag.

## Common SDKs (illustrative — verify versions, don't hardcode assumptions)

Python: `aiogram`, `python-telegram-bot`, `pyTelegramBotAPI`.
JS/TS: `grammY`, `Telegraf`, `node-telegram-bot-api`, GramIO.
Others: `Telegram.Bot` (C#), `TelegramBots` (Java), `go-telegram/bot` (Go),
plus raw HTTP clients in any language.

Support for the button fields added in Bot API 9.4 (`style`,
`icon_custom_emoji_id`) and for Rich Messages (10.1/10.2) varies by SDK and
version — check each, every time. Do not infer support from the SDK's release
date.

## Checking for the 9.4 button fields (run one, don't assume)

Adapt paths to the project; these are detection recipes, not version claims.

| Stack | Check |
|---|---|
| aiogram (Python) | `python -c "from aiogram.types import InlineKeyboardButton as B; print('style' in B.model_fields, 'icon_custom_emoji_id' in B.model_fields)"` |
| python-telegram-bot | `python -c "import inspect, telegram; p=inspect.signature(telegram.InlineKeyboardButton.__init__).parameters; print('style' in p, 'icon_custom_emoji_id' in p)"` |
| pyTelegramBotAPI | `python -c "import inspect, telebot; print(inspect.signature(telebot.types.InlineKeyboardButton.__init__))"` |
| grammY / Telegraf (TS) | `grep -rn "icon_custom_emoji_id" node_modules/@grammyjs/types node_modules/typegram` |
| node-telegram-bot-api | Untyped JSON objects usually pass through — verify a real send, not the types |
| Telegram.Bot (C#) | Look for `Style` / `IconCustomEmojiId` on `InlineKeyboardButton`; check the release notes for Bot API 9.4 |
| Go / Java / other | Search the generated types for `icon_custom_emoji_id`; check the changelog for 9.4 |
| Raw HTTP | Always available — you control the JSON |

Three possible outcomes, three different responses:

1. **Field present** → use it normally.
2. **Field absent, SDK is permissive** (untyped dicts/objects reach the wire
   unchanged) → you may pass it through, but **prove it** with a real send and a
   captured request payload before claiming it works.
3. **Field absent, SDK is strict** (pydantic/dataclass/typed builders drop or
   reject unknown fields) → the field never reaches Telegram. Silent dropping is
   the dangerous case: the code looks right and nothing is colored.

## Escalation when the SDK lacks a needed feature

1. **Check for a newer stable SDK version** that adds it.
2. **Review breaking changes** between current and target versions.
3. **Assess a safe upgrade** (compat with the rest of the project, tests).
4. If upgrading isn't safe/possible, build an **isolated, typed Bot API
   adapter** for just the missing method(s):
   - typed request/response models for that endpoint;
   - one place, clearly named as a temporary shim;
   - reuse the project's existing HTTP/transport layer.
5. **Never place raw HTTP calls in business logic** — keep them behind the
   adapter.
6. **Plan removal:** note the adapter is temporary and to be deleted once the SDK
   supports the feature natively.

## Raw payload pattern for keyboards

`reply_markup` is a JSON-serialized object in the Bot API, so a raw path needs no
new types — only correct serialization:

```python
markup = {"inline_keyboard": [[
    {"text": "Confirm", "callback_data": "order:confirm", "style": "success"},
    {"text": "← Back", "callback_data": "order:menu"},
]]}
await bot_api_raw("sendMessage", {              # the project's existing transport
    "chat_id": chat_id,
    "text": text,
    "parse_mode": "HTML",
    "reply_markup": json.dumps(markup),
})
```

Constraints for this path:

- Build the markup in **one** helper so the rest of the code stays SDK-native.
- Validate it before sending (`scripts/validate_keyboard.py` encodes the rules:
  one action field per inline button, `style` value set, `callback_data` ≤64
  bytes).
- Keep the same `callback_data` scheme the SDK-native path uses, so handlers are
  untouched.
- Mark it as temporary with the removal condition ("delete once <SDK> ≥ <version
  implementing Bot API 9.4> is in the lockfile").

**Never** claim a field shipped when the SDK dropped it. If neither an upgrade
nor a raw path is acceptable, ship without the field and report it as deferred.

## Don'ts

- Don't upgrade an SDK without analyzing breaking changes.
- Don't scatter raw `POST`/`fetch` Bot API calls across the codebase.
- Don't claim a feature works because the Bot API has it — verify the SDK path
  and **test** it (`testing-playbook.md`).
- Don't assume a strict SDK forwards unknown keys; assume it drops them until
  you've seen the outgoing payload.
- Don't gate a whole redesign on one unsupported presentation field — ship the
  structural improvements and report the gap.
