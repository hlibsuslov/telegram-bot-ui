# Streaming and editing (rich content mechanics)

Covers streaming AI replies with `sendRichMessageDraft` and editing rich content
with `editMessageText` + `rich_message`.

> Requires Bot API 10.1+ (`sendRichMessageDraft`, `editMessageText rich_message`).
> Verify the project's version and SDK support first (`sdk-compatibility.md`).

**For the UX decision** — which feedback mechanism a given operation deserves
(`answerCallbackQuery` · `sendChatAction` · `sendMessageDraft` ·
`sendRichMessageDraft` · throttled edits · Mini App progress), the throttling
thresholds, the `<tg-thinking>` block, and the fallback ladder — read
`dynamic-feedback-and-streaming.md` first. This file is the rich-content
implementation detail underneath it.

## Streaming with `sendRichMessageDraft`

Purpose: show a rich message that fills in as an AI model generates it (heading
first, then paragraphs, then a list/table), then commit a final persistent
message.

Requirements and discipline:

- Use a **stable, non-zero `draft_id`** for the lifetime of one stream. Reuse the
  same `draft_id` to **update** the existing draft; do not allocate a new one per
  chunk.
- **Throttle updates.** Do not send a draft per token. Coalesce into meaningful
  increments (e.g. per block, per N characters, or every ~1s) to respect rate
  limits.
- Respect **rate limits** and **file-upload limits**; media in a draft still
  counts against media/upload constraints.
- **Finalize** the stream by sending a real persistent Rich Message
  (`sendRichMessage`) — the draft is a live preview, not the final record. Follow
  the project's convention for whether the draft becomes the message or is
  replaced.
- Handle **cancellation** (user stops generation), **timeout**, **network
  failures**, and Telegram **400 / 429** during streaming (back off on 429; stop
  cleanly on cancel/timeout).
- Provide a **fallback** when the SDK/API lacks draft streaming: send a normal
  message and edit it at a throttled rate, or send once at completion. Choose per
  project; make the fallback explicit.

### Streaming loop sketch (pseudocode, SDK-neutral)

```
draft_id = stable_nonzero_id(conversation)
buffer = ""
last_sent_at = 0
for chunk in ai_stream:
    buffer += chunk
    if should_flush(buffer, now, last_sent_at):   # throttle: per block / N chars / ~1s
        rich = build_rich_message(buffer)          # safe builder, not raw AI HTML
        try:
            sendRichMessageDraft(chat, draft_id=draft_id, rich_message=rich)
            last_sent_at = now
        except RateLimited as e:  backoff(e.retry_after)
        except Cancelled:         break
        except Timeout | Network: retry_or_abort()
final = build_rich_message(buffer)
sendRichMessage(chat, rich_message=final)          # persistent final message
```

`should_flush` and `build_rich_message` are project-specific; keep the builder on
the safe path (`security-and-escaping.md`).

## Editing with `editMessageText` + `rich_message`

- Pass `rich_message` to replace a message's rich content.
- **Preserve reply markup** unless you intend to change it; re-supply the keyboard
  if the SDK requires it, or the buttons may be dropped.
- Handle **`message is not modified`** — skip the edit when content is unchanged
  (compare before sending) to avoid the 400.
- Handle **not-editable** cases (too old, wrong type, deleted) → fall back to a
  **new message** explicitly.
- Preserve **topics** / **direct-message topics** (`message_thread_id`) and
  **business connections** when present in the project.

## Common failure cases

- Editing a streamed draft repeatedly can **destroy formatting** if you rebuild
  from partial/unsafe input — always rebuild through the safe builder and diff
  before editing.
- Losing the keyboard on edit — re-attach markup.
- `429` storms from unthrottled updates — coalesce and back off.
- Finalization failure — retry the final send with backoff; if it ultimately
  fails, surface an error, don't leave only a transient draft. See
  `errors-and-fallbacks.md`.
