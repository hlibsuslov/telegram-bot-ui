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

## Ineligible bots fail **silently** — verify, don't assume

> **Verified against the live Bot API on 2026-08-05**, on a bot that qualified
> for neither route — no Fragment username, and the owner's Telegram Premium
> was not active. That is the *expected* ineligible case; what is not obvious,
> and what this section exists for, is how it fails.
>
> A caution about diagnosing this: Premium-only *profile* fields on the owner's
> account (`emoji_status_custom_emoji_id`, `background_custom_emoji_id`) are
> **not** proof of an active subscription — they survive expiry. Inferring
> eligibility from them is how this test session initially misread its own
> results. Only the round-trip below settles it.

When a bot may not use custom emoji, Telegram **does not return an error**. It
accepts the request with `ok: true` and **strips the custom emoji entities**,
leaving the alternative characters behind. The send looks perfectly successful;
the reader just sees plain emoji. This was reproduced identically through all
three input paths:

| How the emoji were sent | What came back |
|---|---|
| `parse_mode=HTML` with `<tg-emoji emoji-id="…">😀</tg-emoji>` | `entities: []` |
| Explicit `MessageEntity` (`custom_emoji`, correct UTF-16 offset) | `entities: []` |
| `sendRichMessage` with `RichTextCustomEmoji` in a table cell and a paragraph | cell returned as the plain string `"😀"` |

Consequences for how you build this:

- **A `try/except` around the send proves nothing.** There is no exception to
  catch, so a fallback ladder keyed on errors never fires and the bot ships a
  silently degraded message.
- **The only reliable check is to read the message back.** Every send method
  returns the resulting `Message`; inspect it and compare with what you sent:

  ```python
  sent = await bot.send_message(chat_id, text, parse_mode="HTML")
  used_custom_emoji = any(e.type == "custom_emoji" for e in (sent.entities or []))
  # Rich messages: walk sent.rich_message.blocks for RichTextCustomEmoji instead.
  if not used_custom_emoji:
      ...  # degrade explicitly, tell the user why, and log it
  ```

- **`icon_custom_emoji_id` cannot be used to probe eligibility.** Telegram
  echoes `reply_markup` back verbatim — the field is present in the returned
  `Message` whether or not the icon will render. Only the *entity* round-trip
  is evidence.
- **Cache the verdict with a TTL and re-probe.** Eligibility changes when the
  owner's Premium lapses or renews, so a permanent "off" flag goes stale.
- **Do not infer eligibility from anything but the round-trip** — not from the
  owner's profile fields, not from a successful send, not from an echoed button
  field. Confirm it on the bot you are actually shipping, and state the result.

### Content rule the server enforces silently, too

Per the MTProto documentation, a custom emoji entity **must wrap exactly one
regular emoji — the one in the sticker's own `alt`** (the `emoji` field in the
Bot API), *"otherwise the server will ignore it"*. Same failure mode: no error,
just a missing entity. Always take the alternative text from
`getCustomEmojiStickers`/`getStickerSet` rather than picking a similar-looking
character, and count its length in UTF-16 code units.

### When the bot is not eligible, show a picture instead

The Unicode fallback is often not good enough: in a real 80-emoji pack measured
here, the 80 distinct custom emoji had only **52 distinct fallback characters**,
so five different emoji all displayed as `☺️` and no reader could tell which ID
was which.

`sendSticker` is not the way out — a custom-emoji sticker is rejected with
`Bad Request: can't send emoji stickers in messages`. What does work: a custom
emoji is a sticker, so its file downloads and re-uploads as an ordinary image.

1. `getCustomEmojiStickers` / `getStickerSet` → `Sticker`.
2. Take `sticker.thumbnail.file_id` when present (animated `.tgs` and video
   `.webm` emoji are not still images), else `sticker.file_id`.
3. `getFile` + download, then send as a photo — optionally composited into one
   numbered sheet whose numbers match a `#` column in your table.

### Other routes worth knowing

- **A supergroup's own emoji set.** `ChatFullInfo.custom_emoji_sticker_set_name`
  — per the Bot API, custom emoji from a group's assigned set *"can be used by
  all users and bots in the group"*. Inside that one group, that one pack works
  without Fragment or Premium.
- **Polls.** `sendPoll`'s `question_entities` and each option's `text_entities`
  accept **only** custom emoji entities — a rare surface where nothing else is
  allowed.
- **Reactions.** `setMessageReaction` documents bots as non-premium users: one
  reaction per message, and a custom emoji reaction only if it is already on the
  message or explicitly allowed by chat admins.

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
- If the field is set but the bot is not eligible, **do not expect an error**:
  Telegram accepts the request and the icon simply never renders, and the field
  is echoed back in the returned `Message` either way. Establish eligibility
  from a text-entity round-trip (above) and drop the icon when it fails
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
- [ ] Eligibility **proven by a round-trip**, not assumed: a sent message was
      read back and the custom emoji entity was still there.
- [ ] The silent-strip path is handled — no reliance on an exception that
      Telegram never raises.
- [ ] Behaviour when the bot loses eligibility is defined and logged, and the
      verdict is cached with a TTL rather than latched forever.
