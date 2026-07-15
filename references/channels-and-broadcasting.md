# Channels, notifications, and broadcasting

Guidance for **formatting content that is posted or broadcast**, not just replied
in a chat: channel posts, group announcements, and automatic / semi-automatic
mailings (newsletters, drip campaigns, alerts). This is about presentation and
safe delivery of formatted content at scale — not marketing strategy and not the
transport/queue itself (build those only if the audit shows the need,
`project-adaptation.md`).

## Delivery surfaces

| Surface | Notes for formatting |
|---|---|
| **Channel post** | Bot must be an admin with post rights. Same formatting as chat messages (HTML/MarkdownV2/entities, or Rich). No inline `reply` keyboards except URL/login/copy-text style buttons; callback flows go through the linked discussion group. |
| **Group announcement** | Respect topic (`message_thread_id`) if it's a forum. |
| **Broadcast / mailing** | Same content rendered per recipient; the hard problems are rate limits, personalization safety, and per-recipient fallback (below). |
| **Scheduled post** | Content is composed now, shown later — validate rendering at compose time; entities/offsets must still be correct. |
| **Rich Message post** | Great for long structured channel content (reports, digests); mind the 32,768-char budget and "Show More" (`limits-and-splitting.md`). |

## Composing once, sending to many

- **Author the formatted content once**, then send/copy it to each target. Prefer
  `copyMessage`/`copyMessages` (or re-send the same prepared payload) so every
  recipient gets identical, already-validated formatting — don't re-render
  per-recipient unless you're personalizing.
- If you personalize (name, locale, numbers), treat each inserted value as
  **untrusted** and escape it for the exact format at insertion
  (`security-and-escaping.md`). A single unescaped `_`/`<`/`|` from a user's
  display name breaks the whole message.
- Keep the template's markup and the personalization variables separate; validate
  a rendered sample **per locale** (`localization-and-rtl.md`).

## Rate limits and throttling (verify current values)

Broadcasting hits Telegram limits — pull current numbers from official docs; do
not hardcode remembered ones. Typical constraints to design around:

- A sustained per-chat send rate (~1 msg/sec) and a bulk/broadcast ceiling
  (historically ~30 messages/sec across different chats).
- `429` responses carry `retry_after` — honor it (`errors-and-fallbacks.md`).

Design the sender to throttle, back off on `429`, and never tight-loop. The
formatting job stays the same; the delivery loop must be rate-aware.

## Notification controls

- `disable_notification=True` for silent posts (digests, low-priority alerts).
- `protect_content=True` to prevent forwarding/saving of sensitive posts.
- `link_preview_options` to disable or position previews — for link-heavy
  broadcasts an unwanted large preview is the most common visual defect
  (`regular-formatting.md`).
- `has_spoiler` / `show_caption_above_media` for media posts.

## Buttons in posts

- Channel/broadcast posts support **URL**, **login**, **copy-text**, and
  **Web App** buttons; **callback** buttons need a chat context (the linked
  discussion group or a private chat), not a bare channel.
- If a broadcast reuses a keyboard, ensure the markup survives any splitting and
  is attached to the correct part (`limits-and-splitting.md`).

## Editing and pinning posts

- Edit a channel post's text with `editMessageText` (+ `rich_message` for Rich),
  preserving `reply_markup` and skipping no-op edits (`message is not modified`).
  See `streaming-and-editing.md`.
- Pinned-message previews are truncated; put the key line first so the pinned
  preview still reads well.

## Per-recipient fallback for mailings

A broadcast must not abort because one recipient fails:

- `403` (blocked / kicked / no rights) → skip that recipient, record it, continue.
- `429` → back off `retry_after`, then continue.
- `400` validation on personalized content → the **template** is likely fine but
  a personalized value broke it; fix escaping, don't retry unchanged.
- Never silently drop the rest of the batch; log outcomes without dumping bot
  token or full personal text (`errors-and-fallbacks.md`).

## CMS / publishing editors

If the project has a content editor or CMS that produces Telegram posts:

- Store content in a **structured** form (blocks/AST or a controlled subset of
  markup), not raw HTML — so it can render safely to HTML, MarkdownV2, or Rich.
- Validate on save (tags/attrs/URL whitelist, limits, entity offsets) so bad
  formatting is caught before it's broadcast.
- Prefer explicit **blocks** or Rich Markdown for long structured posts; prefer
  regular HTML/entities for short announcements.

## Testing broadcasts

Cover: template render per locale; personalization with hostile display names
(chars that break each format); link-preview on/off; silent/protected flags;
split + keyboard preservation; per-recipient `403`/`429` handling. Assert on the
**payload**, never send real broadcasts from tests (`testing-playbook.md`).
