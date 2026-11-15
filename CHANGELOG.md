# Changelog

Versions follow [Semantic Versioning](https://semver.org/). The version lives in
`adapters/routing.json` (generated into `.claude-plugin/plugin.json`) and in the
`metadata.version` of `SKILL.md`; `scripts/validate_skill.py` fails if they differ.
Each release is tagged `v<version>`.

## 2.0.0 - 2026-11-15

First tagged release of `telegram-bot-ui`, the successor of the `telegram-rich-messages`
skill.

- Bot UI/UX skill for Bot API 10.4: screens, keyboards, colored buttons, streaming AI
  replies with Stop, private replies in groups, Rich Messages, HTML widgets, custom emoji
  packs, formatting and localization.
- Product recipes (shop, support, booking, onboarding, subscriptions, inline mode,
  business), channel publishing with approval, and agent-operated bots with a security
  core.
- Offline Bot API catalog and lookup, payload, keyboard, rich message and widget
  validators.
- Packaging: Claude Code plugin and marketplace, five subagents, Codex agents, and adapters
  for Cursor, Gemini CLI, Copilot and plain `AGENTS.md`, all generated from `SKILL.md` and
  `adapters/routing.json`.
