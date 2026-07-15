# telegram-rich-messages

**A portable, SDK-agnostic Agent Skill for the full life cycle of Telegram
message formatting** — for bots, channels, and automated/semi-automated
broadcasts.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/format-Agent%20Skills-8A2BE2.svg)](https://github.com/anthropics/skills)
[![Verified: Bot API 10.2](https://img.shields.io/badge/Telegram%20Bot%20API-10.2%20verified-26A5E4.svg)](https://core.telegram.org/bots/api-changelog)

It teaches an AI coding agent (Claude Code, Codex, and other Agent Skills hosts)
to **audit a project first, then apply the minimum sufficient format** — never to
copy a fixed architecture into every codebase. Works with any language and any
Telegram library, and it is safe for legacy projects.

> This repository **is** the skill. It doesn't modify any bot — you install it,
> and your agent uses it when a Telegram formatting task comes up.

## What it covers

- **Every regular format:** plain text, Telegram **HTML**, **MarkdownV2**, and
  **MessageEntity** — all entity types, nesting rules, custom emoji, captions.
- **Rich Messages** (Bot API 10.1/10.2): **Rich Markdown**, **Rich HTML**, and
  explicit **`InputRichBlock`** blocks — headings, lists, task lists, tables,
  quotes/pull-quotes, code, math (LaTeX), details, anchors, footnotes, thinking
  blocks, and inline media (`sendRichMessage`, `InputRichMessage`).
- **Streaming AI replies** as live drafts (`sendRichMessageDraft`) and **editing**
  (`editMessageText` + `rich_message`).
- **Channels & broadcasting:** channel posts, notifications, and automatic /
  semi-automatic mailings — rate limits, personalization safety, per-recipient
  fallback, link-preview / silent / protected-content controls.
- **Safety:** context-aware escaping (one escaper per format), tag/attribute/URL
  whitelists, safe handling of user input and AI-generated content.
- **Robustness:** long-message splitting, limits, error classification, a
  fallback ladder, localization and **RTL**, SDK capability gaps, and a testing
  playbook.

Terminology it enforces: Telegram Rich Text is **not** Microsoft `.rtf`; Rich
Markdown is **not** MarkdownV2; Rich HTML is **not** arbitrary browser HTML; the
Bot API Rich Messages differ from Telegram's user-facing Rich Text Editor;
regular and rich messages are different mechanisms.

## Repository layout

```
telegram-rich-messages/
├── SKILL.md                     # compact operational guide (loaded on activation)
├── README.md · LICENSE
├── references/                  # progressive-disclosure detail (read on demand)
│   ├── regular-formatting.md        # all HTML/MarkdownV2/entity features
│   ├── telegram-capabilities.md     # Rich Messages + capability matrix
│   ├── channels-and-broadcasting.md # channels, notifications, mailings
│   ├── format-selection.md
│   ├── project-adaptation.md
│   ├── security-and-escaping.md
│   ├── limits-and-splitting.md
│   ├── rich-media.md
│   ├── streaming-and-editing.md
│   ├── localization-and-rtl.md
│   ├── errors-and-fallbacks.md
│   ├── sdk-compatibility.md
│   ├── testing-playbook.md
│   └── official-sources.md          # sources + last-verified dates
├── scripts/                     # stdlib-only validators (no token, no network)
│   ├── validate_skill.py
│   └── validate_references.py
├── evals/
│   └── activation-evals.md      # positive/negative trigger scenarios
└── agents/
    └── openai.yaml              # optional Codex-specific metadata
```

## Install

**Claude Code — user level (all projects):**

```bash
git clone https://github.com/hlibsuslov/telegram-rich-messages.git \
  ~/.claude/skills/telegram-rich-messages
```

**Claude Code — repository level (one project):** clone into
`<repo>/.claude/skills/telegram-rich-messages`.

**Codex (OpenAI):** clone into `~/.agents/skills/telegram-rich-messages` (user)
or `<repo>/.agents/skills/telegram-rich-messages` (project).

On Windows the Claude Code user path is
`%USERPROFILE%\.claude\skills\telegram-rich-messages`.

## Use

- **Automatically:** the `description` in `SKILL.md` lets the host select the
  skill when a request matches — e.g. *"fix Telegram can't parse entities"*,
  *"add Rich Messages for AI answers"*, *"format this channel broadcast safely"*.
- **Explicitly:** ask for it by name — *"use the telegram-rich-messages skill to
  audit our formatter"* (Codex: `$telegram-rich-messages`).

## Validate

```bash
python scripts/validate_skill.py        # front matter, sections, secrets
python scripts/validate_references.py    # links, orphans, empty files, secrets
```

Both are standard-library only, read local files only, and never use a bot token
or the network. Then walk `evals/activation-evals.md` to confirm trigger
behaviour.

## How it works

1. Read project instructions; detect language, framework, **SDK, and versions**.
2. Determine the supported **Bot API version**.
3. Map every place messages are generated / formatted / sent / edited.
4. Identify **real** defects; pick the **minimum** format that solves them.
5. Implement in the project's own style, add a fallback and tests, run its checks.

Source-of-truth order: current **official Telegram docs** → Bot API changelog →
installed SDK docs → SDK source → SDK issues → third-party articles (context
only). The skill re-verifies official docs for version-dependent work and is
**not frozen** at any Bot API version.

## Keeping it current

Telegram's formatting API evolves. Before version-dependent work, re-check the
[Bot API changelog](https://core.telegram.org/bots/api-changelog) and update
`references/official-sources.md`. Content here was verified against **Bot API
10.2 (released 2026-07-14)** on **2026-07-15**.

## Contributing

Issues and PRs welcome. Please: keep `SKILL.md` compact (detail belongs in
`references/`), cite official Telegram docs for any capability claim, mark
unverified numbers as such, run both validators, and keep the skill
project-agnostic (no assumptions about a specific SDK or repo).

## License

[MIT](LICENSE).

## Disclaimer

Community project; not affiliated with or endorsed by Telegram. Verify current
behaviour against the official Bot API before relying on any capability.
