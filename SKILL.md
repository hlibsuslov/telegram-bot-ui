---
name: telegram-rich-messages
description: >-
  FIRST PRIORITY — produce Telegram's editor-style rich formatting, above all
  TABLES, then headings, lists, quotes, code, and inline media, for bot, channel,
  and broadcast messages via Bot API Rich Messages (Rich Markdown/HTML,
  InputRichMessage, InputRichBlockTable and other blocks, sendRichMessage,
  sendRichMessageDraft, editMessageText rich_message). Then everything else:
  audit, migrate, debug, and test all other Telegram formatting — plain text,
  HTML, MarkdownV2, MessageEntity (types, nesting, custom emoji), captions,
  link-preview/silent/protected options, long-message splitting, streaming AI
  drafts, editing, channels, localization, and RTL. Use for any task that renders
  or formats Telegram message/post content — especially tables — "can't parse
  entities" errors, unsafe/double escaping, or broken/oversized messages. Do NOT
  use for bot logic unrelated to presentation (webhooks, commands, payments,
  auth, group admin, Mini Apps without text) or Microsoft .rtf files.
---

# Telegram Rich Messages

Portable, SDK-agnostic skill for the full life cycle of **Telegram message
presentation**: audit → format selection → design → implementation → fixing →
migration → testing → documentation. It teaches you to **investigate the target
project first**, then make content **as richly structured as it deserves —
tables first** — falling back to simpler formats only when structure adds
nothing.

## Top priority: tables and rich formatting

**This is the skill's headline job.** Telegram now supports true editor-style
rich messages for bots (Bot API 10.1+): the same **tables, headings, lists,
quotes, code blocks, and inline media** described in Telegram's blog *"Text
Editor, Communities & Ephemeral Messages"*. Bots, channels, and broadcasts can
all produce them via Rich Messages (`sendRichMessage` + `InputRichMessage`).

Default reach order for any task:

1. **Is the content rows/columns or label→value data?** → build a **table**
   (`references/tables.md`). This is the first thing to try.
2. **Is it a structured document** (report, AI answer, comparison, schedule)? →
   rich formatting — headings, lists, quotes, code, media.
3. **Escape hatch — is it a genuinely trivial one-liner** (a status, an "OK", a
   short prompt/notification)? → plain or regular formatting.

Tables come **first**; everything else is chosen only when a table or rich
document genuinely doesn't fit. Do not wrap a one-line confirmation in a table —
but do prefer a real table for anything with structure, instead of monospace
`pre` blocks or bulleted key/values.

## Purpose

Help safely work with everything about how Telegram message *content* looks and
is delivered — in bots, channels, and automated/semi-automated broadcasts:
choosing a format, writing safe escaping, building structured/rich content,
controlling previews/notifications, splitting long messages, streaming AI
answers, editing, posting to channels, mailing to many recipients, localizing,
handling RTL, adding fallbacks, and testing — across any language and any
Telegram SDK.

## When to use

Message/post-presentation tasks: Telegram HTML / MarkdownV2 / MessageEntity (all
entity types, nesting, custom emoji); captions; link-preview, silent, and
protected-content options; Rich Markdown, Rich HTML, Rich Messages;
`sendRichMessage`, `sendRichMessageDraft`, `InputRichMessage`, `InputRichBlock`;
tables, formulas, lists, task lists, quotes, code blocks, inline/rich media;
long messages; AI streaming drafts; channel posts; automatic/semi-automatic
broadcasts and newsletters; `can't parse entities`; wrong/double escaping; broken
or oversized formatting; localized message templates; RTL; Telegram CMS /
publishing editors; migrating old Telegram formatter utilities.

## When NOT to use

Do not activate for: general bot setup; webhook infrastructure; commands
unrelated to formatting; payments / Stars; authorization; Mini Apps with no text
content; group administration; parsing *incoming* messages unrelated to rich
content; Telegram marketing strategy; Microsoft `.rtf` files.

## Terminology — do not confuse these

- **Telegram Rich Text is NOT Microsoft RTF.** Never call Rich Messages "RTF".
  `.rtf` files are unrelated. Only use "RTF" for actual `.rtf` documents.
- **Rich Markdown ≠ MarkdownV2.** MarkdownV2 is a `parse_mode` for *regular*
  messages with strict char escaping. Rich Markdown is a document syntax for
  *Rich Messages* (headings, tables, task lists, math, details, media).
- **Rich HTML ≠ arbitrary browser HTML.** Only a specific Telegram-supported tag
  set is allowed; never pass raw/AI HTML through.
- **Bot API Rich Messages ≠ Telegram's user-facing Rich Text Editor.** Related,
  different interfaces. Don't cite the editor UI as the Bot API contract.
- **Regular Messages and Rich Messages are different mechanisms.** New Rich
  capabilities do **not** mean every existing message must be migrated.

## Source-of-truth policy

Trust in this order:
1. Current **official Telegram documentation** (Bot API, Bot Features, formatting
   pages, official blog).
2. Official **Bot API changelog**.
3. Docs of the **SDK actually installed** in the project.
4. **SDK source code**.
5. **SDK issue tracker**.
6. Third-party articles — supplementary context only.

**Re-verify official docs before acting** when: the task touches new APIs; today
is later than the "last verified" date in `references/official-sources.md`; the
project's Bot API version is unknown; SDK docs contradict the Bot API; you meet
an unfamiliar type/param; or the user asks for "the latest capabilities".
For anything version-dependent, check the **Bot API changelog first**. This skill
is **not frozen** at Bot API 10.2 — if Telegram shipped a newer version, use it.

## Core workflow (audit before you code)

1. Read the project's instructions (`AGENTS.md` / `CLAUDE.md` / README / contrib docs).
2. Detect language, framework, **Telegram SDK, and exact versions**.
3. Determine the **Bot API version** the SDK/project actually supports.
4. Find every point that **generates, formats, sends, and edits** messages.
5. Classify each message (notification / interactive / document / AI answer / media).
6. Identify the **real defects** (don't invent work).
7. Choose the format **richest-fit-first — a table for any structured data**
   (see matrix below); simpler formats only as the escape hatch.
8. Design a solution compatible with the current SDK and Bot API version.
9. Implement it in the project's existing style and utilities (don't duplicate).
10. Add a **fallback** path (see `errors-and-fallbacks.md`).
11. Add **tests** using the project's existing test infrastructure.
12. Run the project's lint / typecheck / tests / applicable smoke checks.
13. Re-check that no unsafe legacy patterns remain.
14. Report: current message-flow map, changes, limits, and verification evidence.

Do **not** write implementation code before the audit (steps 1–6) is complete.

## Format selection (quick matrix)

Try the richest fit first; drop to a simpler format only when structure adds
nothing. Full matrix + rules: `references/format-selection.md`.

| Need | Use |
|---|---|
| **Rows/columns or label→value data** | **Table** — `references/tables.md` (`InputRichBlockTable` / Rich MD pipe table / Rich HTML `<table>`) |
| Structured doc: AI answer, article, report, task list, math | **Rich Markdown** |
| Server-templated complex content, precise supported-tag control | **Rich HTML** |
| Typed generation from data / CMS / AST, ambiguity-free | **Explicit `InputRichBlock` blocks** |
| Photo/video/doc/album/caption fits UX better | **Separate media methods** |
| *Escape hatch:* trivial one-liner, HTML is project standard | **Regular HTML** |
| *Escape hatch:* project standardizes on it | **MarkdownV2** (strict escaping) |
| *Escape hatch:* exact offset/length control, no parse_mode | **MessageEntity** |
| *Escape hatch:* genuinely no styling needed | **Plain text** |

Rule: **default to a table (or rich document) for anything with structure; use
the simpler formats only as the escape hatch for genuinely trivial one-liners.**
Don't inflate a one-line confirmation into a table — but don't render structured
data as monospace or bullet soup either.

## Which reference to read (task-routed — don't read them all)

- **Tables (the flagship — read first for any structured data)** →
  `references/tables.md`
- Rich Messages / blocks / capability matrix → `references/telegram-capabilities.md`
- Every regular format (HTML/MarkdownV2/entities, custom emoji, captions,
  link-preview/silent/protected controls) → `references/regular-formatting.md`
- Channel posts, notifications, automated/semi-automated broadcasts →
  `references/channels-and-broadcasting.md`
- Choosing a format → `references/format-selection.md`
- Investigating an unknown project → `references/project-adaptation.md`
- Escaping / injection / safe user or AI content → `references/security-and-escaping.md`
- Limits & splitting long messages → `references/limits-and-splitting.md`
- Media (rich + separate methods) → `references/rich-media.md`
- Streaming drafts & editing → `references/streaming-and-editing.md`
- Localization & RTL → `references/localization-and-rtl.md`
- Telegram/API errors & fallback ladder → `references/errors-and-fallbacks.md`
- SDK gaps / raw Bot API adapter → `references/sdk-compatibility.md`
- Testing → `references/testing-playbook.md`
- Sources & last-verified dates → `references/official-sources.md`

## Non-negotiable rules

- **Tables first.** For any structured / rows-columns / label→value data, build a
  real Telegram table (`references/tables.md`) — not a monospace `pre` grid or a
  bulleted list. Simpler formats are the escape hatch for trivial one-liners, not
  the default.
- Investigate the project **before** changing it.
- **One escaping function per format** — never a single universal escaper.
- Never pass **arbitrary or AI-generated HTML** straight to Telegram; whitelist
  tags, attributes, and URL schemes.
- `InputRichMessage` carries **exactly one** of `markdown`, `html`, or `blocks`.
- Compute offsets/lengths in **UTF-16 code units** (Telegram's unit).
- Pull **current limits from official docs**; don't hardcode remembered numbers.
- Fallback must be explicit and logged — no silent degradation, no infinite
  retries, no swallowing errors, no logging bot tokens or full personal text.
- Don't duplicate formatter utilities, scatter magic limits, or upgrade an SDK
  without reviewing breaking changes.
- Don't claim a feature works until it is **tested**.
- Apply rich-content styling conventions by default: **semantic table headers**
  (`is_header` / `<th>` / markdown header row, repeated when a table splits;
  never faked with bold body cells), aligned numeric columns, language-tagged
  code blocks, heading blocks for titles, descriptive link text, captions on
  media (see `references/tables.md` and `references/telegram-capabilities.md`).

## Definition of done

Audit complete and defects identified · richest-fit format chosen (**table** for
structured data; simpler formats only as the escape hatch) · tables use semantic
headers + aligned columns · implemented in project style · backward compatible
(keyboards, callbacks, topics,
reply context, localizations intact) · safe context-aware escaping · fallback +
tests added · project checks green · limits sourced from official docs · no
unverified claims · "last verified" date recorded. Report per step 14.
