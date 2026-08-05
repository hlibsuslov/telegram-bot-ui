# Errors, fallbacks, and old clients

## Degradation ladders (adapt to the project — not a universal mandate)

Content:

```
Explicit rich blocks
  → Rich HTML or Rich Markdown
    → Regular HTML or MessageEntity
      → plain text
```

Interface:

```
styled + custom-emoji buttons
  → styled buttons (style only)
    → plain buttons (text + action only)
      → text instructions / commands
```

Feedback:

```
sendRichMessageDraft
  → sendMessageDraft
    → throttled editMessageText
      → sendChatAction + one final message
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

## UI-specific failure modes

| Symptom | Likely cause | Response |
|---|---|---|
| Buttons render but have no color | SDK dropped `style` before the request, or the client predates 9.4 | Inspect the outgoing payload; see `sdk-compatibility.md` |
| 400 on a button payload | Two action fields on one inline button, or an invalid `style` value | `style` ∈ {`primary`,`success`,`danger`}; exactly one action field |
| 400 mentioning custom emoji | Bot not eligible (no Fragment usernames, owner not Premium), or a bogus ID | Verify eligibility; verify the ID with `getCustomEmojiStickers`; drop the icon |
| `callback_data` rejected | Over **64 bytes** (bytes, not characters) | Shorten the payload; move state server-side |
| `message is not modified` | Edit with identical text *and* markup | Compare before editing; skip the no-op |
| Spinner never stops on a button | `answerCallbackQuery` not called | Answer first, then work |
| Old message's button acts on stale data | No server-side state re-validation | Re-check state on every callback; disable finished keyboards |
| Streamed draft vanished, nothing left | Draft expired without a final `sendMessage` | Always finalize — including on the error path |

## Old and inconsistent clients

`style` and `icon_custom_emoji_id` are presentation fields. A client that
doesn't know them shows a normal button with the same label and the same action
— which is exactly why the label must carry the full meaning
(`buttons-and-styles.md`). Design for that baseline first, then add the
enhancement.

Assume nothing about rendering parity across Android, iOS, Desktop, and Web —
especially for newer surfaces (rich drafts, thinking blocks, ephemeral message
edits). Where behaviour matters, put it behind a feature flag with a plain-text
fallback and verify on each platform (`testing-playbook.md`).

## `can't parse entities` — first response

Almost always a payload problem: wrong escaping for the chosen parse_mode, an
unclosed/unknown tag, a broken link, or (for entities) a wrong UTF-16 offset.
Fix the payload; don't just retry. See `security-and-escaping.md` and
`testing-playbook.md` regression cases.

## Fallback design

- Build the fallback **once, explicitly**, and test it.
- Keep the fallback path safe (same escaping discipline).
- Preserve keyboards, reply/topic context, and meaning through the fallback.
- A degraded **button** keeps its label and its action — only `style` and the
  icon may be dropped. Never fall back by removing the button.
- Decide per message class whether to **degrade** or **fail loudly**.
