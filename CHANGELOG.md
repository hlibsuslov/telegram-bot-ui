# Changelog

Versions follow [Semantic Versioning](https://semver.org/). The version lives in
`adapters/routing.json` (generated into `.claude-plugin/plugin.json`) and in the
`metadata.version` of `skills/telegram-bot-ui/SKILL.md`; `scripts/validate_skill.py` fails if they differ.
Each release is tagged `v<version>`.

## Unreleased

- Skill route for a whole interface kept as files by stable screen ID:
  `references/bot-ui-projects.md` (new UI from a description, connecting one route of an existing
  bot with its `callback_data` kept, change by ID with a revision check and conflict handling,
  local Studio or an exported snapshot and `apply-patch`, widget author/build/attach and what
  changes in already-sent messages, groups and personal data, the path without the Studio).
  Linked from `SKILL.md` and the `ui` capability of the adapters. The optional `studio/` folder
  is not part of the skill install or the directory edition.
- Evals: activation P40-P41, behavioural BUI1-BUI6.

## 2.3.0 - 2026-11-22

Bot API 10.5 (released 2026-11-22).

- Catalog synced to 10.5: 194 methods, 426 types (`setMySettings`, `BotFullInfo`; `getMe` returns
  `BotFullInfo`; getMe-only flags removed from `User`; `WriteAccessAllowed.inviter`).
- **Breaking for 10.3/10.4 payloads:** expandable quotes in Rich Messages hold `blocks` instead of
  `text`. `tgkit.rich.expandable_quote` emits blocks (a plain `text` becomes one paragraph, or pass
  `blocks=`); R02, R09, R26, R31, the publishing renderer and the TypeScript R02 twin migrated;
  R02 now folds a real list inside the quote.
- Bot settings from code: `references/bot-settings.md` and `tgkit/settings.py` (`validate`, `plan`,
  `apply` = getMe + one `setMySettings` with only the differences, `callback_target` for every
  `callback_query_mode`, `addressed_to_me` over `active_usernames`, `invite_link`, `inviter_of`);
  recipe 10 (`recipes/10-bot-settings.md`, `r10_bot_settings.py`, payload, three fixtures) and
  `tests/test_bot_settings.py`.
- Coverage registry: 11 rows for 10.5 (63 in all, none uncovered); the generated table is now
  `references/bot-api-coverage.md` (was `bot-api-10.3-10.4.md`).
- References: inline mode, topics, onboarding (invited users skip `/start`), deep links
  (`t.me/botinvite`), business accounts, navigation, capabilities, changelog and catalog tables,
  official sources; `sdk-compatibility.md` records that no SDK declares 10.5 yet (tdlib's Bot API
  server does) and what breaks meanwhile. SKILL.md: callbacks without `message`.
- Payload headers and evals: every captured payload re-validated against the 10.5 catalog;
  activation evals P37-P39.
- Widget docs: field report from a production game bot (`widget-patterns.md` §16) — one shared
  widget per app with per-user state in answers, versioning by HTML hash with every old
  `widget_id` routed, hidden information on the server, fractions sent as strings, answer
  trimming to 1024 bytes, move numbers, lost answers, DOM over canvas, animation only in motion,
  clock lag in real-time games, kill switch and a pre-deploy fuzz gate.
- `tgkit.widgets.handle_widget_query` retries a dropped `answerWidgetQuery` (twice, < 1 s) and
  answers `bad_request` to wallet query types instead of playing them as an action (TS twin too).

## 2.2.1 - 2026-11-15

- `PRIVACY.md`, linked from the plugin manifests together with a support URL.
- Directory edition: `scripts/build_directory_edition.py` builds a documentation-only copy of the
  plugin (skill, references, recipes, JSON Bot API catalog, Claude subagents; no scripts or runnable
  examples) and `.github/workflows/directory-edition.yml` publishes it to the `claude-directory`
  branch for the Claude plugin directory.

## 2.2.0 - 2026-11-15

- Widget kit: `K.ask` no longer locks the widget when `request()` throws `TypeError`
  synchronously (empty or > 64-byte data); regression test runs the kit in Node.
- Widget checks: canvas pixel access, patterns, shadows and compositing; SVG `clipPath`, `mask`,
  `pattern`, `marker`, `foreignObject`, SMIL and `<image>`; logical properties, multi-column,
  `display: contents/flow-root`, `background-clip: text`, `writing-mode`. Strict lint warns on
  `request` from `pointerdown`, state written with `innerHTML`, and canvas arcs past 2π.
  `media-carousel` used `margin-inline-end` (out of profile 1) and now uses physical margins.
- Widget docs: bot-side lifecycle for long jobs, editor with autostart, image shrink loop,
  canvas cut-outs, UI strings in `public_data`, the two-crash rule; raw exception text and
  loguru `diagnose` as bot-token leaks in `errors-and-fallbacks.md`.
- Widget checks also flag removed form elements (`datalist`, `output`, …), `meta`, `ruby`,
  `math`, legacy presentational tags and attributes, editing/focus attributes, `popover` and
  `data:` AVIF/BMP/ICO images; the `disabled-pseudo` warning is gone (profile 1 maps
  `:disabled` to `[disabled]` on `<button>`).
- SDK status: aiogram 3.32.0 and node-telegram-bot-api 2.4.0 ship the widget methods;
  Telegram's widget-sandbox listed as an official source.

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
