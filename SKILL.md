---
name: telegram-rich-messages
description: >-
  Audit, design, implement, migrate, debug, and test Telegram message formatting
  for bots, channels, and automated/semi-automated broadcasts. Covers plain text,
  Telegram HTML, MarkdownV2, MessageEntity (all types, nesting, custom emoji),
  captions, link-preview/silent/protected options, and Bot API Rich Messages
  (Rich Markdown, Rich HTML, InputRichMessage, InputRichBlock, sendRichMessage,
  sendRichMessageDraft, editMessageText rich_message), plus tables, formulas,
  lists, code, inline/rich media, long-message splitting, streaming AI drafts,
  editing, channel posts, mass mailings, localization, and RTL. Use for tasks
  that render or format Telegram message/post content, "can't parse entities"
  errors, unsafe or double escaping, broken/oversized messages, broadcast
  formatting, or migrating formatter utilities to current Bot API. Do NOT use for
  bot logic unrelated to presentation (webhooks, commands, payments, auth, group
  admin, Mini Apps without text) or Microsoft .rtf files.
---

# Telegram Rich Messages

Portable, SDK-agnostic skill for the full life cycle of **Telegram message
presentation**: audit → format selection → design → implementation → fixing →
migration → testing → documentation. It teaches you to **investigate the target
project first**, then pick the *minimum* format that solves the task — never to
copy a fixed architecture into every project.

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
7. Choose the **minimum sufficient format** (see matrix below).
8. Design a solution compatible with the current SDK and Bot API version.
9. Implement it in the project's existing style and utilities (don't duplicate).
10. Add a **fallback** path (see `errors-and-fallbacks.md`).
11. Add **tests** using the project's existing test infrastructure.
12. Run the project's lint / typecheck / tests / applicable smoke checks.
13. Re-check that no unsafe legacy patterns remain.
14. Report: current message-flow map, changes, limits, and verification evidence.

Do **not** write implementation code before the audit (steps 1–6) is complete.

## Format selection (quick matrix)

Pick the simplest format that fully solves the task. Full matrix + rules:
`references/format-selection.md`.

| Need | Use |
|---|---|
| No formatting | **Plain text** |
| Compact, predictable styling; HTML is project standard | **Regular HTML** |
| Project already uses it / genuinely best | **MarkdownV2** (strict escaping) |
| Exact offset/length control, no parse_mode | **MessageEntity** |
| AI answers, articles, tables, task lists, math, docs | **Rich Markdown** |
| Server-templated complex content, precise supported-tag control | **Rich HTML** |
| Typed generation, CMS, AST, precise structure, ambiguity-free | **Explicit `InputRichBlock`** |
| Photo/video/doc/album/caption fits UX better | **Separate media methods** |

Rule: **do not auto-migrate every message to Rich Messages.** Short notifications
usually stay regular messages.

## Which reference to read (task-routed — don't read them all)

- Every regular format (HTML/MarkdownV2/entities, custom emoji, captions,
  link-preview/silent/protected controls) → `references/regular-formatting.md`
- Rich Messages / blocks / capability matrix → `references/telegram-capabilities.md`
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

## Definition of done

Audit complete and defects identified · minimum sufficient format chosen ·
implemented in project style · backward compatible (keyboards, callbacks, topics,
reply context, localizations intact) · safe context-aware escaping · fallback +
tests added · project checks green · limits sourced from official docs · no
unverified claims · "last verified" date recorded. Report per step 14.
