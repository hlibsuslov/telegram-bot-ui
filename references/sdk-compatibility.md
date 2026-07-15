# SDK compatibility

The project's SDK — not your memory — decides which formatting features are
reachable. Establish the SDK, its version, and the Bot API version it implements
before designing anything (`project-adaptation.md`).

## Determine actual capability

For the feature you need (e.g. `sendRichMessageDraft`, `InputRichMessageMedia`),
confirm it exists in **this** SDK version by checking, in order:

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

Support for Rich Messages (10.1/10.2) varies by SDK and version — check each.

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

## Don'ts

- Don't upgrade an SDK without analyzing breaking changes.
- Don't scatter raw `POST`/`fetch` Bot API calls across the codebase.
- Don't claim a feature works because the Bot API has it — verify the SDK path
  and **test** it (`testing-playbook.md`).
