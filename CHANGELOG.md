# Changelog

Versions follow [Semantic Versioning](https://semver.org/). The version lives in
`adapters/routing.json` (generated into `.claude-plugin/plugin.json`) and in the
`metadata.version` of `skills/telegram-bot-ui/SKILL.md`; `scripts/validate_skill.py` fails if they differ.
Each release is tagged `v<version>`.

## 2.1.0 - 2026-11-15

- Deep redesign path (`skills/telegram-bot-ui/references/redesign-orchestration.md`): access and mandate levels,
  project style research, brand mapped onto what Telegram allows, a new menu structure with
  a migration for old `callback_data`, commands and deep links, and a tuning loop.
- Bot style profile (`skills/telegram-bot-ui/references/bot-style-profile.md`): the knobs that tune a bot, each
  with its evidence. `scripts/style_profile.py` probes a project's style signals without
  opening secrets, scaffolds a profile and checks it against API limits and the skill's rules.
- README (en, ru, uk): plugin icon and name above the banner, release and stars badges, install
  with the GitHub CLI (`gh skill install hlibsuslov/telegram-bot-ui`); `docs/assets/social-preview.png`
  for the repository's link preview.

## 2.0.1 - 2026-11-15

- Plugin icon: `assets/icon.svg` (Codex `interface.composerIcon`) and a 512 px
  `assets/icon.png` (Claude Code plugin `icon`, Codex `interface.logo`), wired in by
  `scripts/build_adapters.py`.

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
- Packaging: the skill lives in `skills/telegram-bot-ui/` (the folder installers copy, with
  its own `LICENSE`); Claude Code plugin and marketplace, an Agent Plugins `plugin.json`, a
  Codex `.codex-plugin/plugin.json`, five subagents, Codex agents, and adapters for Cursor,
  Gemini CLI, Copilot and plain `AGENTS.md`, all generated from the skill's `SKILL.md` and
  `adapters/routing.json`.
