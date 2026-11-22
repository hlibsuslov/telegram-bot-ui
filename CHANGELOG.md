# Changelog

Versions follow [Semantic Versioning](https://semver.org/). The version lives in
`adapters/routing.json` (generated into `.claude-plugin/plugin.json`) and in the
`metadata.version` of `skills/telegram-bot-ui/SKILL.md`; `scripts/validate_skill.py` fails if they differ.
Each release is tagged `v<version>`.

## 3.0.0 - 2026-11-23

The skill now covers the whole interface of a Telegram bot, not one feature of it: screens,
texts, keyboards, navigation, states, streaming replies, HTML widgets, premium emoji, posts and
agent-operated flows. This release adds bot-ui projects (the interface as files by stable screen
ID), the optional local bot-ui Studio, widget design profiles and a premium pass for polish
requests. No breaking changes for existing installs: 3.0 marks the wider scope.

### bot-ui projects and the local Studio

The optional local Studio lives in `studio/` and is not part of the skill install.

- bot-ui Studio opens one local project at a time. It maps screens and transitions, simulates
  Telegram conversations, edits messages and keyboards, and previews HTML widgets. It saves
  changes to the bot’s repository for Git review and can export a patch for offline drafts.
- The landing page includes a browser demo of Pulloa, a coffee pickup bot with 19 screens,
  four scenarios and six interactive widgets. README links cover the demo, local setup and
  the project format in English, Russian and Ukrainian.
- Skill route for a whole interface kept as files by stable screen ID:
  `references/bot-ui-projects.md` (new UI from a description, connecting one route of an existing
  bot with its `callback_data` kept, change by ID with a revision check and conflict handling,
  local Studio or an exported snapshot and `apply-patch`, widget author/build/attach and what
  changes in already-sent messages, groups and personal data, the path without the Studio).
  Linked from `SKILL.md` and the `ui` capability of the adapters. The optional `studio/` folder
  is not part of the skill install or the directory edition.
- Evals: activation P40-P41, behavioural BUI1-BUI6.
- `bot-ui` project format v1 (`studio/docs/contract.md`): screens, actions and one typed transition
  rule per button, stable IDs and `callback_data`, a revision over the sources, one locked write
  path with `expectedRevision`, field-level conflicts and journaled multi-file writes.
- CLI `py -3 studio/bot-ui.py`: `init`, `list`, `show`, `validate`, `set`, `patch`, `apply-patch`,
  `simulate`, `render`, `build`, `studio`, `export-snapshot`, `inventory` and `import` (aiogram
  routers, read-only on the bot; refuses bots without router handlers).
- Simulator engine in Python with a TypeScript port checked on the same fixtures; adapters for
  aiogram 3.31.0 and raw tgkit over one runtime (Bot API 10.5 callbacks with `inline_message_id`
  and inaccessible messages, stale buttons, widget fallback outside private chats).
- Studio on shadcnblocks `application-shell1`: a map of Telegram message previews with arrows from
  their buttons, a screen editor with a live preview, Beginner and Pro modes, en/ru/uk editing,
  a Telegram-style simulator, one Changes page (drafts, saved files, requests, a ready prompt for
  your agent), every media kind by `file_id`/URL and custom emoji.
- Widgets: a library of the skill's 23 widgets with live previews, a visual builder (message,
  product card, promo code, countdown offer, quiz) with presets and light/dark colours, named
  preview states, photo-to-SVG assets, builds through the strict widget pipeline, export of the
  HTML and the `sendWidget` payload.
- An offline one-file artifact for hosts without a local port: edit texts and rules, simulate,
  export a patch, apply it with the CLI.
- bot-ui Studio: premium emoji library. The Emoji page imports a pack from its
  `t.me/addemoji/...` link through the telegram-bot-ui resolver on the project site (no token;
  only the pack name is sent; `BOT_UI_EMOJI_RESOLVER` changes or turns it off; the user's own
  token or a saved getStickerSet response still work), shows every emoji with its picture, suggests icons for the ordinary
  emoji the screens already use, and keeps the bot's icon map (one meaning per emoji) in
  `emoji/library.json`. Text fields and button icons get an emoji picker; previews, the map and
  the simulator draw the real pictures (adaptive emoji in the text colour); the offline artifact
  inlines the pictures it needs.
- Agent handoff: `bot-ui emoji brief [--json]` (icon map, placements, replaceable emoji, unknown
  ids, rules) and a premium emoji section in the Changes prompt. `validate` adds
  `CUSTOM_EMOJI_UNKNOWN`, `CUSTOM_EMOJI_FALLBACK_MISMATCH` and `CUSTOM_EMOJI_DOUBLE_ICON`.

### Widget design profiles

- `scripts/widget_design.py`: a widget's `design.json` compiles to CSS over the kit tokens and the
  client button variables; six presets, per-theme or shared colours, a contrast check for light
  and dark; the build applies it and reports its byte cost.
- Studio: the Look step of a code widget has a Design panel (presets with light and dark
  previews, block, motion, button, texts, chips, counter, bars and picture options, contrast and
  byte cost). Visual-builder widgets keep their own Design step.

### Premium pass

Premium pass: what a person sees, checked. Ideas from 21 public Telegram skills, restated and
verified (revisions and licenses: `references/official-sources.md`, "Community skills reviewed").

- Routing: "make it premium / nicer / polished" now goes to the premium pass
  (`references/visual-language.md` §7: first line and facts → buttons → color → icons, themes,
  locales, custom emoji off, states, compatibility), not only to the emoji-pack recipes.
- `SKILL.md` mode list: a polish request reads the premium pass first and covers empty, error
  and stale states (a real agent run without it skipped them).
- `validate_keyboard.py` warns on layout and meaning: styled or ✅/❌-marked navigation (red
  Back, "❌ Close"; "Close account" is an action, not navigation), navigation above other
  actions (a confirmation's red last row is allowed), a `danger` button sharing a row with any
  other action (Back beside it is fine), labels that don't say what happens ("OK", "Yes",
  "Submit", "Да", "Надіслати"), more than 8 rows; Ukrainian destructive words ("Скинути") now
  count as destructive. Warnings only; tests in `tests/test_premium_pass.py`.
- Found by those checks in our own examples and fixed (layout and labels only, same
  `callback_data`): R35 Reject on its own row; `AgentBridge.approve(destructive=True)` (R40, MCP
  `approve`) puts the red Approve alone in the last row so a mis-tap on Reject can't run it.
- R03 (form): the submit button sits above Back/Cancel and says "Place order"
  (`FormRunner(submit_label=...)`, default "Send answers"); Python, TypeScript and payload updated.
- Shapes for stale screens (out of date + what is saved + one fresh entry) and notifications
  (event and needed action in the ≤ ~80-char preview line, one fact per line, resolved in place)
  in `microcopy-and-labels.md`; consent/peer-choice/escape style rules in `buttons-and-styles.md`;
  page size by row density, no dead pager and a multi-select pattern in `inline-keyboards.md`;
  no half-open markup in drafts (`streaming-and-editing.md`); strip test in the final review.
- Worked set on one bot, same data before and after (menu, wizard, error, empty, stale tap,
  notification): `examples-before-after.md` 17-20, `examples/premium-pass/before-after.json`.
- Evals: UI5 (ru), UI6 (en) activation and B16 behavioural for the premium request.
- `scripts/run_evals.py --execute` resolves the host CLI with `shutil.which` (Windows npm
  installs `claude.cmd`, which `CreateProcess` can't start by name).

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
