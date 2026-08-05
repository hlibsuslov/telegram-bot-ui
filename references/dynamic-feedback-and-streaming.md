# Dynamic feedback: streaming, progress, and loaders

A bot cannot animate arbitrary UI frame by frame. What "animation" actually
means in a Telegram chat is one of these:

- text appearing progressively (`sendMessageDraft`, `sendRichMessageDraft`);
- one message being edited in place (`editMessageText`);
- an updating progress bar inside that message;
- the client's own spinner on a tapped inline button (cleared by
  `answerCallbackQuery`);
- a chat action status ("typing", "uploading photo"…);
- an animated temporary draft;
- a GIF / video / sticker / message effect;
- real animation inside a Mini App.

Pick the mechanism from the **shape of the operation**, not from what looks
impressive.

## Decision table

| Situation | Mechanism |
|---|---|
| AI generates a plain-text answer in a private chat | `sendMessageDraft` |
| AI generates a structured answer (headings, tables, collapsibles) | `sendRichMessageDraft` → `sendRichMessage` |
| Short operation, 2–5 s | `sendChatAction` |
| User tapped an inline button | `answerCallbackQuery` **immediately**, then work |
| Operation has real, nameable stages | `editMessageText` with a stage list / progress bar |
| Progress cannot be measured | Named stages — **never** a fake percentage |
| Operation runs in a group | One status message + rare edits (or an ephemeral message) |
| Genuinely interactive process | Mini App with its own progress UI |
| SDK too old for the new methods | Raw Bot API payload, or fall back to edits |
| Client support unknown | Feature flag + plain-text fallback |

## 1. `sendMessageDraft` — native text streaming

Introduced in **Bot API 9.3** (2025-12-31), opened to **all bots in 9.5**
(2026-03-01). Official description: *"stream a partial message to a user while
the message is being generated. Note that the streamed draft is ephemeral and
acts as a temporary 30-second preview — once the output is finalized, you must
call `sendMessage` with the complete message to persist it in the user's chat."*

Parameters that matter: `chat_id` (**private chats only**), `draft_id`
(non-zero; *"Changes to drafts with the same identifier are animated"*), `text`
(**0–4096 chars**; *"Pass an empty text to show a 'Thinking…' placeholder"*),
plus `parse_mode` / `entities` and `message_thread_id`.

```json
{ "chat_id": 123456789, "draft_id": 48127, "text": "" }
```
```json
{ "chat_id": 123456789, "draft_id": 48127, "text": "Analyzing the sources…" }
```
```json
{ "chat_id": 123456789, "draft_id": 48127,
  "text": "Analyzing the sources…\n\nFirst finding: …" }
```

Then **finalize with `sendMessage`** — the draft is a preview, not a message.

**Use it for:** AI answers, report generation, translation, file analysis,
search, any long text produced incrementally.

**Don't use it for:** group flows (private chats only), operations whose result
isn't progressively-built text, anything that must persist every intermediate
state, or an SDK that doesn't support the method yet.

**Invariants:** one `draft_id` per operation, held for the whole run; finalize
exactly once; if generation fails, still send a real message saying so — never
leave the user with an expired preview and nothing else.

## 2. `sendRichMessageDraft` and the Thinking block

**Bot API 10.1** (2026-06-11) added Rich Messages and their streaming form.
For streaming specifically there is a dedicated block —
`InputRichBlockThinking` / `RichBlockThinking`, HTML tag `<tg-thinking>`:

> *"A block with a 'Thinking…' placeholder, corresponding to the custom HTML tag
> `<tg-thinking>`. The block may be used **only in `sendRichMessageDraft`**,
> therefore it can't be received in messages."*

The docs also point to `https://t.me/addemoji/AIActions` as a recommended custom
emoji set for use inside the block (subject to the usual custom-emoji
eligibility rules — `custom-emoji.md`).

```html
<tg-thinking>Looking through the official docs…</tg-thinking>
```
```html
<tg-thinking>Comparing sources…</tg-thinking>
<h2>Preliminary result</h2>
<p>Found 4 relevant updates.</p>
```

Final send via `sendRichMessage` — **without** the thinking block.

**Match the final message to the draft.** A rich draft that resolves into a
plain Markdown message is a visible regression: the content reflows, tables
collapse, and the user sees the answer "downgrade" at the last second. Decide
the final format *before* streaming, and keep the draft's structure.

**Fallback ladder** (each step must be reachable at runtime, not just in theory):

```
sendRichMessageDraft
  → sendMessageDraft
    → editMessageText (throttled)
      → sendChatAction + a single final sendMessage
```

## 3. Edit-based streaming and progress bars

The pre-9.3 approach, still correct for anything with **real stages**: send a
message, keep its `message_id`, and edit it as the operation advances.

```
Preparing report ░░░░░░░░░░
Preparing report ███░░░░░░░ 30%
Preparing report ███████░░░ 70%
Done ██████████ 100%
```

**Only show a percentage you actually know.** If the number is invented, show
named stages instead:

```
✓ Sources collected
✓ Data compared
⏳ Building the result
```

**Throttling rules** — do not edit per token. Update when at least one holds:

- 800–1500 ms have passed since the last edit;
- 30–80 new characters/tokens have accumulated;
- a sentence finished;
- a real stage boundary was crossed;
- the final result is ready.

Telegram's own FAQ states: *"In a single chat, avoid sending more than one
message per second"*, *"In a group, bots are not be able to send more than 20
messages per minute"*, and about 30 messages/second for bulk broadcasts. Those
sentences are about sending, but edits consume the same budget in practice —
throttle them and always honour `retry_after` on 429
(`errors-and-fallbacks.md`).

**Known costs of edit-based streaming** (design around them; treat as
engineering experience, not documented API behaviour): the message can flicker
on some clients, long-lived edited messages keep their original timestamp, error
paths can produce duplicate messages, intermediate tool/debug text can leak into
the chat, and scroll position can jump. Mitigations: throttle, keep exactly one
`message_id` per operation, never emit intermediate text as *new* messages, and
make finalization idempotent.

**Editing an unchanged message** raises `message is not modified` — compare
before editing.

## 4. The native button loader

Tapping an inline button shows the client's own progress indicator. It clears
only when the bot calls `answerCallbackQuery`. So: **answer first, work after.**

```ts
await answerCallbackQuery(cq.id);                       // clears the spinner
await editMessageText({ text: "Processing…" });         // shows our own state
const result = await performLongOperation();
await editMessageText({ text: render(result), reply_markup: finalKeyboard });
```

- Silent answer (no `text`) is fine and is the common case.
- `text` is **0–200 characters**; a toast, not a place for results.
- `show_alert: true` is a modal — reserve it for consequences and confirmations.
- Keep `cache_time` at 0 for anything state-dependent.
- If the work takes more than a moment, immediately edit the screen to a
  "working" state and **disable the buttons that must not be pressed twice** —
  then re-enable/replace them when finished. Server-side idempotency still
  required; the UI is not a lock.

## 5. Chat actions

`sendChatAction` sets a status for **5 seconds or less**, and clients clear it as
soon as a message arrives from the bot. Telegram: *"We only recommend using this
method when a response from the bot will take a noticeable amount of time to
arrive."* Channel chats are not supported.

Actions: `typing`, `upload_photo`, `record_video`, `upload_video`,
`record_voice`, `upload_voice`, `upload_document`, `choose_sticker`,
`find_location`, `record_video_note`, `upload_video_note`. **Pick the one that
matches what the user will actually receive** — `typing` before a photo is a
small lie the client will contradict.

Waiting ladder:

```
0–1 s     : show nothing
1–5 s     : sendChatAction("typing")
> 5 s     : re-send the action every ~4 s, or switch to a status message
long gen. : sendMessageDraft / sendRichMessageDraft
```

## 6. Mini App progress (boundary)

The Mini App's *internal* UI is ordinary web front-end work and out of this
skill's scope. Its **Telegram-side** controls are in scope:

- `Telegram.WebApp.ready()` — *"informs the Telegram app that the Mini App is
  ready to be displayed… Once this method is called, the loading placeholder is
  hidden"*. Call it as early as the essential UI is up.
- `BottomButton` (the class was renamed from `MainButton` in Bot API 7.10; the
  `Telegram.WebApp.MainButton` accessor remains): `showProgress(leaveActive)` —
  *"A method to show a loading indicator on the button… By default, the button
  is disabled while the action is in progress"* — and `hideProgress()`.
  `iconCustomEmojiId` on the button is Bot API 9.5+.

```js
Telegram.WebApp.MainButton.setText("Building the report").show().showProgress();
// … work …
Telegram.WebApp.MainButton.hideProgress();
```

Leave `leaveActive` unset for form submissions — a re-tappable submit button
during submission is a duplicate-order bug.

## 7. Operation lifecycle (apply to every long action)

1. **Classify** the operation: instant / short / long / streaming / measurable /
   unmeasurable.
2. **Acknowledge instantly** — `answerCallbackQuery`, or a chat action.
3. **Hold one identity for the whole run**: one `draft_id`, one preview
   `message_id`, one internal `operation_id`. Never let a retry create a second
   stream.
4. **Report progress honestly** — real percentages or named stages.
5. **Throttle** updates per the rules above.
6. **Finalize atomically**: persist the result → send the final message →
   close/expire the preview → clear the loader → replace the keyboard with the
   final one → make sure no destructive callback is left armed on a stale
   screen.
7. **Fail visibly**: on error, the last thing the user sees must be a real
   message explaining it plus a way forward — never a stalled spinner or an
   evaporated draft.
8. **Verify SDK support** before using drafts or rich drafts
   (`sdk-compatibility.md`); ship the fallback path if it's missing.
9. **Test on Android, iOS, Desktop, and Web** — draft and edit rendering differs
   between clients (`testing-playbook.md`).

## Checklist

- [ ] Mechanism chosen from the decision table, not by preference.
- [ ] `answerCallbackQuery` called before long work, every time.
- [ ] One `draft_id` / `message_id` / `operation_id` per operation.
- [ ] No per-token edits; throttle thresholds implemented and tuned.
- [ ] No invented percentages.
- [ ] Draft finalized with a real message; failure path also ends in a message.
- [ ] Final format matches the streamed format (rich stays rich).
- [ ] `retry_after` honoured; 429s not retried in a tight loop.
- [ ] Fallback ladder implemented and exercised in tests.
