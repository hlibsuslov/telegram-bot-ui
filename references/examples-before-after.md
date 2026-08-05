# Worked scenarios (before → after)

Seven situations that cover most real UI requests. Code is illustrative — adapt
to the project's actual SDK and style; never paste a framework the project
doesn't use.

---

## 1. Improve only the text — change no logic

**Request:** "Rewrite this message, it's unclear."

**Before**

```python
await message.answer(
    "ERROR: request failed with code 500. Something went wrong. "
    "Please try again later or contact the administrator if the problem persists.",
    reply_markup=kb,
)
```

**After**

```python
await message.answer(
    "⚠️ Couldn't load your orders.\n"
    "This is on our side — try again in a minute.",
    reply_markup=kb,          # untouched
)
```

**What was allowed to change:** wording only.
**What was preserved:** `reply_markup`, handler, parse mode, i18n key.
**If the project has i18n**, the edit belongs in the catalog entry
(`orders.load_failed`), in every locale — not inline at the call site.

**Report line:** *"Text only. No keyboard, callback, or handler changes."*

---

## 2. Rebuild an overloaded inline keyboard

**Request:** "This menu is a mess."

**Before** — 9 buttons in one column, no hierarchy, destructive action mixed in:

```json
{"inline_keyboard": [
  [{"text": "Profile", "callback_data": "profile"}],
  [{"text": "My orders", "callback_data": "orders"}],
  [{"text": "Order history", "callback_data": "orders_old"}],
  [{"text": "Settings", "callback_data": "settings"}],
  [{"text": "Language", "callback_data": "lang"}],
  [{"text": "Notifications", "callback_data": "notify"}],
  [{"text": "Support", "callback_data": "help"}],
  [{"text": "Delete account", "callback_data": "acc_del"}],
  [{"text": "New order", "callback_data": "order_new"}]
]}
```

**After** — grouped by topic, primary action first, settings collapsed one level
down, destruction moved off the main screen:

```json
{"inline_keyboard": [
  [{"text": "New order", "callback_data": "order_new", "style": "primary"}],
  [{"text": "My orders", "callback_data": "orders"},
   {"text": "History", "callback_data": "orders_old"}],
  [{"text": "Profile", "callback_data": "profile"},
   {"text": "Settings", "callback_data": "settings"}],
  [{"text": "Support", "callback_data": "help"}]
]}
```

"Language" and "Notifications" now live inside `settings`; "Delete account"
lives inside `profile` behind a confirmation.

**Preserved:** every `callback_data` string. The `settings` screen must now
render the two moved buttons with their original payloads (`lang`, `notify`), so
old messages keep working.

**Report line:** *"Regrouped 9 → 4 rows, moved 2 items under Settings and
`acc_del` behind a confirmation. All callback payloads unchanged; the Settings
screen now hosts `lang`/`notify` verbatim."*

---

## 3. Add `primary`, `success`, and `danger`

**Request:** "Make the important buttons stand out."

**Before**

```json
{"inline_keyboard": [
  [{"text": "Save", "callback_data": "draft:save"}],
  [{"text": "Publish", "callback_data": "draft:publish"}],
  [{"text": "Delete draft", "callback_data": "draft:delete"}],
  [{"text": "Back", "callback_data": "menu"}]
]}
```

**After**

```json
{"inline_keyboard": [
  [{"text": "Publish", "callback_data": "draft:publish", "style": "success"}],
  [{"text": "Save as draft", "callback_data": "draft:save"}],
  [{"text": "Delete draft", "callback_data": "draft:delete", "style": "danger"}],
  [{"text": "← Back", "callback_data": "menu"}]
]}
```

Reasoning to state in the report:

- `Publish` commits the flow → `success`, and it moves to the top as the
  expected action.
- `Save as draft` is a legitimate alternative, not the main path → unstyled.
- `Delete draft` is irreversible → `danger`, kept last, and it routes to a
  confirmation screen where the confirming button is `danger` and the escape is
  unstyled.
- `Back` stays unstyled.
- No `primary` here: on a screen whose job is to commit, `success` *is* the main
  action. Adding `primary` too would create two focal points.

---

## 4. Custom emoji and color together

**Request:** "Put our branded icons on the quiz buttons."

**Preconditions to check first** (`custom-emoji.md`): the bot either purchased
additional usernames on Fragment, or its owner has Telegram Premium and the
message goes directly to a private/group/supergroup chat. Bot API ≥ 9.4 in the
installed SDK.

```json
{"inline_keyboard": [
  [{"text": "Finish the test",
    "icon_custom_emoji_id": "5368324170671202286",
    "style": "success",
    "callback_data": "finish_test"}],
  [{"text": "Continue later",
    "icon_custom_emoji_id": "5368324170671202111",
    "callback_data": "pause_test"}],
  [{"text": "← Back to topics", "callback_data": "topics"}]
]}
```

Rules applied: the icons cover a coherent group (the two test actions) rather
than one lonely button; the navigation row stays plain; both labels are complete
sentences without their icons; the IDs came from `getCustomEmojiStickers` and
live in config, not inline; no Unicode emoji were mixed into the same keyboard.

---

## 5. The `custom_emoji_id` is unknown

**Request:** "Add a custom emoji to the Confirm button."

**Do not** put a plausible-looking number in the code. Do this instead:

1. Implement the button with the field plumbed through from config, unset by
   default, so the UI works today:

```python
def confirm_button(icon_id: str | None = None) -> dict:
    btn = {"text": "Confirm order", "callback_data": "order:confirm", "style": "success"}
    if icon_id:
        btn["icon_custom_emoji_id"] = icon_id
    return btn
```

2. Ask the user for the ID **and** show them how to get one:

> I need the actual `custom_emoji_id` — it can't be guessed. Any of these works:
> **(a)** send the emoji to the bot once and read `custom_emoji_id` from the
> `custom_emoji` entity in that message; **(b)** call `getStickerSet` for the
> pack and read `custom_emoji_id` off the sticker; **(c)** if you already have
> candidate IDs, confirm them with `getCustomEmojiStickers` (≤200 per call).
> Also: is the bot eligible — Fragment usernames, or owner Premium with the
> message going to a private/group/supergroup chat?

3. Ship the rest of the redesign; don't block it on the ID.

---

## 6. The SDK doesn't support Bot API 9.4 yet

**Symptom:** the installed SDK's `InlineKeyboardButton` has no `style` /
`icon_custom_emoji_id`; a strict, typed SDK raises on unknown kwargs, or the
field is silently dropped before it reaches Telegram.

**Step 1 — verify, don't guess** (`sdk-compatibility.md`):

```bash
python -c "from aiogram.types import InlineKeyboardButton as B; print('style' in B.model_fields)"
grep -rn "icon_custom_emoji_id" node_modules/@grammyjs/types node_modules/typegram 2>/dev/null
```

**Step 2 — present both options with their cost:**

- **Upgrade the SDK** to a version implementing Bot API ≥ 9.4. Review its
  breaking changes first; this is the clean path when the project can absorb it.
- **Raw payload for these calls only** — keep it behind one adapter, never in
  business logic:

```python
markup = {"inline_keyboard": [[
    {"text": "Confirm", "callback_data": "ok", "style": "success"},
]]}
await bot_api_raw("sendMessage", {          # existing project transport
    "chat_id": chat_id,
    "text": text,
    "reply_markup": json.dumps(markup),      # JSON-serialized
})
```

**Step 3 — degrade honestly.** If neither is acceptable right now, ship the
keyboard without `style`, note it as a deferred item, and **say so** — never
claim colors were added when the field never left the process.

**Report line:** *"aiogram 3.x here has no `style`; shipped the restructured
keyboard without color and added `bot_api_raw` as an opt-in path. Colors turn on
after the SDK upgrade tracked in <issue>."*

---

## 7. When color and emoji should NOT be added

**Request:** "Make the catalog colorful."

**Refuse with a reason and offer the real fix.**

```json
{"inline_keyboard": [
  [{"text": "Running shoes", "callback_data": "cat:1"}],
  [{"text": "Trail shoes", "callback_data": "cat:2"}],
  [{"text": "Sandals", "callback_data": "cat:3"}],
  [{"text": "‹ Prev", "callback_data": "cat:p:1"},
   {"text": "2/7", "callback_data": "noop"},
   {"text": "Next ›", "callback_data": "cat:p:3"}],
  [{"text": "← Back to menu", "callback_data": "menu"}]
]}
```

Why nothing is styled: these are **equal options**. `style` is semantic — if all
of them are `primary`, none of them is. The three values also can't express a
brand palette (no HEX/RGB/CSS exists in the Bot API).

The same applies to emoji: a per-category emoji here would add noise, not
information, and a custom emoji would additionally require Fragment/Premium
eligibility for zero UX gain.

**What actually improves this screen:** clearer category names, pagination that
tells you where you are, a search entry point
(`switch_inline_query_current_chat`), and a fixed navigation row.

**Report line:** *"Left the option list unstyled deliberately — `style` is
semantic (primary/success/danger only) and coloring equal options removes
hierarchy. Added pagination context and search instead."*
