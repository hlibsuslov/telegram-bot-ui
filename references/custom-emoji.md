# Custom emoji — on buttons and in text

Two different mechanisms, one eligibility rule:

| Where | Mechanism | Since |
|---|---|---|
| **On a button** | `icon_custom_emoji_id` on `KeyboardButton` / `InlineKeyboardButton` | Bot API **9.4** (2026-02-09) |
| **In message text** | `custom_emoji` `MessageEntity`, `<tg-emoji emoji-id="…">😀</tg-emoji>` (HTML), `![😀](tg://emoji?id=…)` (MarkdownV2) | Bot API **6.2** (2022-08-12) |

## Eligibility — check this first

Official Bot API wording for `icon_custom_emoji_id` (identical on both button
classes): *"Unique identifier of the custom emoji shown before the text of the
button. Can only be used by bots that purchased additional usernames on Fragment
or in the messages directly sent by the bot to private, group and supergroup
chats if the owner of the bot has a Telegram Premium subscription."*

So a bot may use custom emoji when **either**:

1. it **purchased additional usernames on Fragment** (the long-standing 6.2-era
   route, which also covers messages the bot sends anywhere it can post); **or**
2. the **bot owner has Telegram Premium** *and* the message is sent **directly
   by the bot** to a **private, group, or supergroup** chat — the relaxation
   introduced by Bot API 9.4.

Consequences to state out loud when you propose custom emoji:

- **Channel posts are not covered by the Premium route.** Route 2 lists private,
  group, and supergroup chats only. For channels, the Fragment route applies.
- **It depends on the *bot owner's* Premium, not the viewer's.** If the owner
  lets Premium lapse, the calls that rely on route 2 start failing — design the
  fallback now, not later.
- **"Directly sent by the bot"** excludes messages sent on behalf of someone
  else (e.g. business-account sending). Verify against current docs for the
  specific send path you use.
- Before recommending this feature, **ask which route the project qualifies
  for.** If neither, use Unicode emoji and say why.

## Getting a real `custom_emoji_id` — never invent one

The value is the ID of one specific custom emoji sticker. It is **not** a
`file_id`, not a sticker-pack name, not a `t.me/addemoji/...` link, and not a
Unicode character. IDs cannot be derived, guessed, or "looked up by name". A
fabricated ID is a bug that ships silently.

Three legitimate sources:

1. **From a message that already contains the emoji** — `MessageEntity` of type
   `custom_emoji` carries `custom_emoji_id`. Have the owner send the emoji to
   the bot once and log the entity. This is the easiest path for most projects.
2. **From a sticker set** — `getStickerSet` returns `Sticker` objects; each
   custom-emoji sticker exposes `custom_emoji_id` (and `emoji`, the Unicode
   fallback character).
3. **Verifying IDs you already have** — `getCustomEmojiStickers` takes
   `custom_emoji_ids` (**at most 200 per call**) and returns the corresponding
   `Sticker` objects. Use it to confirm an ID resolves and to read its `emoji`.

**Agent protocol when the ID is unknown:** implement the UI with the field
plumbed through but left unset (or read from config), then ask the user for the
ID *and* show them the capture snippet above. Do not block the whole redesign on
it, and do not fill in a placeholder that looks real.

Store IDs in configuration/constants with a comment naming the pack and the
Unicode fallback — not scattered as magic strings.

```python
# config: emoji pack "MyBotIcons", fallback ✅
FINISH_ICON_ID = os.environ.get("TG_ICON_FINISH")  # verified via getCustomEmojiStickers
```

## Buttons

```json
{
  "text": "Finish the test",
  "icon_custom_emoji_id": "5368324170671202286",
  "style": "success",
  "callback_data": "finish_test"
}
```

The icon renders **before** the text. Presentation only — it does not count as
the button's action field (`buttons-and-styles.md`).

Rules:

- **The label must stand alone.** Unlike text entities, a button icon has no
  alternative-emoji field. If the client cannot show the icon, the user sees
  only `text` — so never encode meaning in the icon (`✏️` + empty label is a
  broken button).
- **Icon a set, not a single button.** One icon on one button in an otherwise
  bare keyboard looks like a rendering bug. Icon a whole coherent group, or
  none.
- **Don't mix** custom emoji icons with Unicode emoji pasted into `text` on the
  same keyboard — pick one convention per bot and record it.
- **Keep icons out of destructive confirmation buttons** unless the icon is
  unmistakably a warning; a friendly icon undercuts a `danger` action.
- If the field is set but the bot is not eligible, expect Telegram to reject the
  request — handle it as a validation error and fall back to a plain button
  (`errors-and-fallbacks.md`).

## In message text

HTML: `<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>`
MarkdownV2: `![👍](tg://emoji?id=5368324170671202286)`
Entities: `MessageEntity` with `type: "custom_emoji"` and `custom_emoji_id`.

Official rule: *"A valid emoji must be provided as an alternative value for the
custom emoji. The emoji will be shown instead of the custom emoji in places
where a custom emoji cannot be displayed (e.g., system notifications) or if the
message is forwarded by a non-premium user. It is recommended to use the emoji
from the `emoji` field of the custom emoji sticker."*

So: **always supply the Unicode fallback**, and take it from the sticker's own
`emoji` field (via `getStickerSet` / `getCustomEmojiStickers`) rather than
picking one that "looks close". Note that MarkdownV2 requires `)` and `\` inside
the `(...)` part to be escaped, and that `parse_mode: Markdown` (legacy) cannot
express custom emoji at all — use MarkdownV2 or HTML.

More on entity mechanics: `regular-formatting.md`.

## Unicode emoji vs custom emoji — choosing

| Situation | Choose |
|---|---|
| Bot has no Fragment usernames and owner has no Premium | Unicode |
| Message goes to a channel and there are no Fragment usernames | Unicode |
| A branded icon set that must look the same everywhere | Custom (with fallbacks) |
| Status markers in dense lists (✅/⏳/❌) | Unicode — universally rendered |
| One-off decoration | Neither; usually cut it |

Whatever you choose, keep the **budget low**: emoji are punctuation for the eye,
not paragraph markers. `microcopy-and-labels.md` has the per-screen limits.

## Checklist

- [ ] Confirmed which eligibility route the bot qualifies for (Fragment /
      owner Premium / neither) — and stated it in the report.
- [ ] Every `custom_emoji_id` came from an entity, `getStickerSet`, or
      `getCustomEmojiStickers` — none invented.
- [ ] Text usages carry a valid Unicode fallback taken from the sticker's own
      `emoji` field.
- [ ] Buttons remain understandable with the icon missing.
- [ ] IDs live in config with a comment, not inline magic strings.
- [ ] Behaviour when the bot loses eligibility is defined and logged.
