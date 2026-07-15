# Errors and fallbacks

## Degradation ladder (adapt to the project — not a universal mandate)

```
Explicit rich blocks
  → Rich HTML or Rich Markdown
    → Regular HTML or MessageEntity
      → plain text
```

Fall back one step at a time, only for the failure classes that warrant it. The
right ladder depends on the project: some flows should surface an error instead
of degrading (e.g. a payment receipt must not silently become plain text).

## Classify the failure before reacting

| Class | Signal | Reaction |
|---|---|---|
| Validation error (your payload) | 400 `can't parse entities`, bad offset, unclosed tag, malformed blocks, over-limit | Fix the payload; degrade a format step; do **not** retry unchanged |
| Unsupported SDK/API capability | missing type/method, older Bot API | Use a supported format or the adapter (`sdk-compatibility.md`); degrade |
| Telegram 400 (other) | e.g. `message is not modified`, invalid media | Handle specifically (skip edit / fix media); don't blind-retry |
| Telegram 403 | bot blocked / no rights | Stop for that chat; surface; do not retry in a loop |
| Telegram 429 | rate limited, `retry_after` | Back off for `retry_after`, then retry once/limited |
| Transient network | timeout, connection reset | Bounded retry with backoff |
| Telegram 5xx | server error | Bounded retry with backoff |
| Permissions | can't send type in chat/topic | Surface; adjust or skip |

## Rules

- **Differentiate** the classes above — never treat all failures the same.
- **No infinite retries.** Bound retries and honor `retry_after`.
- **No silent fallback.** Log that a fallback happened and why (without dumping
  bot token or full personal text).
- **No error suppression.** Swallowing exceptions hides real defects.
- On split sends, a failed part must not silently drop the remaining parts.
- Retrying a **validation** error unchanged is pointless — change the payload
  (fix escaping/offsets/limits) or degrade the format.

## `can't parse entities` — first response

Almost always a payload problem: wrong escaping for the chosen parse_mode, an
unclosed/unknown tag, a broken link, or (for entities) a wrong UTF-16 offset.
Fix the payload; don't just retry. See `security-and-escaping.md` and
`testing-playbook.md` regression cases.

## Fallback design

- Build the fallback **once, explicitly**, and test it.
- Keep the fallback path safe (same escaping discipline).
- Preserve keyboards, reply/topic context, and meaning through the fallback.
- Decide per message class whether to **degrade** or **fail loudly**.
