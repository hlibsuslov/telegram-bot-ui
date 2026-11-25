# Changelog

Versions follow [Semantic Versioning](https://semver.org/). The version lives in
`adapters/routing.json` (generated into `.claude-plugin/plugin.json`) and in the
`metadata.version` of `skills/telegram-bot-ui/SKILL.md`; `scripts/validate_skill.py` fails if they differ.
Each release is tagged `v<version>`.

## 3.3.0 - 2026-11-25

**Every Bot API symbol has an agent card, the emoji library is chosen by tags, and evals have a judge.**

- **Agent cards for the whole Bot API:** a note and a checked request example for every one of the 194
  methods (messages, editing, stickers, chat-admin, chat-info, bot-settings, business, forums, platform,
  inline widgets, payments), 426 of 426 types named in a card, and 286 of 286 WebApp members with guidance
  or code. `lookup` (and the MCP lookup) returns catalog + note + example in one card; `sync` marks changed
  notes for review. A random sample of cards was checked against Telegram's own pages.
- **`api_coverage.py`** measures knowledge, reference, payload and validation per symbol with a ratcheting
  floor in `run_checks.py`; CI fails a floor lowered against the PR base.
- **Rich Messages as JSON blocks:** block and rich-text builders mirrored from the catalog, `validate_rich.py`
  checks blocks as deeply as HTML (errors with paths, never a crash), and `references` explain when to send
  blocks instead of HTML. The Studio marks block screens as not supported.
- **Payments:** a read-only ledger audit over the Star statement (`tgkit`), the shipping path in the pipeline,
  and a pre-checkout recipe that checks payload, payer, currency and shipping option against the stored
  order before the amount.
- **Mini Apps:** typed, version-gated events, a state snapshot and batch storage in the kit; the official
  base64 `Authorization` form of init data is accepted.
- **Emoji library by tags:** the library client reads every answer and the offline export
  (`--library-file emoji-library.ndjson.gz`) through a vendored contract; `pick --profile` compares the
  brand accent with pack colours and says in one line why each pack was chosen. The MCP pick tools return
  each pack's description. In the Studio, the Emoji page filters every pack by style, colour, theme fit and
  motion and ranks packs for the slots the project's screens use; the single-file snapshot carries the same
  catalog and works offline.
- **Recipe R76:** the bot builds its own custom emoji pack and uses it.
- **Evals:** 78 activation cases for the Bot API domains, routing counted through the first playbook,
  timeouts kept apart from misses; a behavioural runner with a versioned, tool-less LLM judge, per-role
  scores and a release gate. The judge agrees with 10 hand-labelled answers 50 of 50 times.
- **Hardening:** the installer refuses linked project folders, junctions and reparse points before any copy;
  `preview_widget --serve` checks Host, Origin, JSON and body size; the preview page and mock runtime act
  only on messages from their own frame; the Telegram bridge enforces each tool's input schema; MCP null
  optional arguments get their defaults.

### Compatibility

- The library client requires the `taxonomy` and `generated` fields that the website adds in this release.
  Against an older website, online picking answers `CONTRACT_MISMATCH`; the offline export keeps working.
  Deploy the website first.
- `bot-ui/` projects need no change.

## 3.2.0 - 2026-11-25

**A router instead of one long entry, one CLI, and the bot remembered between sessions.**

- **SKILL.md is a 9.5 KB router** (was 25.4 KB, description 846 characters, was 1024 of 1024): Start steps,
  a table of twelve commands generated from `commands/index.json`, scope, invariants and the next-step rule.
  The safety rules now sit in the first third, inside what Claude Code keeps after compaction (the first
  5000 tokens of a skill); before, `Non-negotiable rules` and `Definition of done` were cut.
- **Twelve commands with playbooks** (`commands/<verb>.md`, each under 4 KB): `start`, `audit`, `improve`,
  `fix`, `build`, `post`, `widget`, `mini-app`, `emoji`, `agent-bot`, `map`, `lookup`. A playbook names the
  reference sections to read, the steps, the checks, a path without scripts (directory edition) and its done
  criterion. The user never has to know a verb; with no request, `start` suggests the next steps.
  `references/floor.md` holds what every edit obeys; `references/INDEX.md` lists every reference with its
  summary and commands (generated).
- **`scripts/tgui.py`**, one entry point: every tool as a subcommand, plus `context` (saved facts, findings,
  Studio requests and signals in under 2 KB), `next`, `doctor` (other installed copies with another version,
  version mismatch, catalog age, context and map health), `findings`, `requests`, `check changed` (the right
  validator for every changed Telegram file) and `hook` (an opt-in Claude Code post-edit check that never
  blocks).
- **Project memory in `bot-ui/context/`**, outside the map revision: `context.json`, `findings.json` (ids from
  a hash, so branches don't collide), `requests/<id>.json`, the style profile. `map init` keeps an existing
  `context/`.
- **The bot-ui core ships with the skill** (`scripts/bot_ui/`, was `studio/bot_ui/`): `map` and Studio-request
  routes work from `gh skill` and installer copies, not only from a clone. The Studio can save requests into
  the project (a switch on the Changes page, off by default).
- **Payments are routed:** the example library's paid-product families name `payments-pipeline.md` and
  `tgkit/payments.py` first ("Read first"), and `build` carries them.
- **Subagents carry out commands** (generated from the index); `python` vs `py -3` fixed in their bodies
  (`py -3` on Windows, `python3` elsewhere); the designer's read-only contract is now consistent.
- **Every reference** has front matter (summary, verified date, Bot API) and, above 10 KB, a contents list;
  `validate_references.py` checks both and every Contents link.
- **Checks:** `validate_skill.py` enforces the budgets and that every reference is reachable from a command;
  `tests/test_paths.py` installs the skill into a temporary project and runs every command's smoke steps from
  that copy (it found `install.py` not copying `commands/` and `map init` refusing a folder with `context/`);
  `tests/test_tgui.py`.
- **Evals you can trust:** `run_evals.py` isolates runs from other installed copies (Claude:
  `--setting-sources project,local`, project outside HOME; Codex: empty HOME, user copies switched off),
  rejects runs that loaded another copy, records CLI version, model and commit, supports `--runs` and a
  deterministic `--split`, and measures route accuracy and tokens. 159 activation cases (10 Ukrainian, novice,
  Studio and near-miss cases) and 80 behavioural ones; N2 (Stars processing) is now a positive.
- **Agent page sources:** `scripts/build_agent_docs.py` generates `docs/agents/` (`agents.md`, `llms.txt`,
  `llms-full.txt`, `agents.json`) for the website.
- **Rich Messages in bot-ui and the Studio:** a screen can be `rich.html` (sent with `sendRichMessage`,
  edited with `editMessageText(rich_message)`). Buttons inside the document are bound to the screen's
  actions (`<tg-button action="pay">`, rows of 1-8 in `<tg-button-row>`), so the simulator, the map
  (edges leave from the in-document button) and a stale-press check treat them like keyboard buttons.
  The Studio preview draws headings, tables (compact), lists, quotes (expandable), details, dividers,
  media stand-ins and the buttons, light and dark; the format is editable. Python and TypeScript
  renderers stay identical (`tests/test_bot_ui_rich.py`, parity on a rich scenario).
- **`tgui.py commands`** (`scripts/bot_commands.py`): audits handlers in code against
  `setMyCommands` and `bot-ui/commands.json` (nine codes, including lists a narrower scope hides),
  plans the `setMyCommands`/`deleteMyCommands` requests per scope and language, diffs against a saved
  `getMyCommands`. New reference `bot-commands.md`, routed from `audit`, `improve`, `build`.
- **`emoji library search|pick`:** the telegram-bot-ui emoji library (~490 packs, real ids) through
  its public search; `pick` ranks whole packs by the slots their own fallback emoji cover, then
  theme-adaptive and static share, and returns an icon map from one pack with its missing slots.
- **`tgui.py mcp`** (`scripts/bot_ui_mcp.py`): a stdlib MCP server with 14 tools: API and WebApp
  lookup with "did you mean", `validate_request` (catalog, keyboard rules, Rich HTML buttons),
  `check_rich_html`, `knowledge_search` (which reference sections to read), map validate, render,
  simulate and `map_snapshot` (a single-file Studio page an agent opens and screenshots), command
  audit and plan, and the two emoji library tools.
- **Validators:** `validate_payload.py` checks the rules Telegram states in prose for
  `setMessageReaction` (the 73 reaction emoji read from the catalog text, one reaction per bot, no
  paid reactions) and `setMyCommands`; `validate_rich.py` checks buttons in `html`/`markdown`.
- **Knowledge:** choosing between rich buttons, inline and reply keyboards and Mini Apps, and the
  lifecycle of an in-document button (`buttons-and-styles.md`); reactions as quiet status feedback
  (`polls-checklists-and-reactions.md`); the library pick as the first step of `emoji-packs.md`; the
  visual check in `bot-ui-projects.md`; source priority, the Mini App Contest 2023 archive excluded,
  and the facts re-checked on 2026-11-25 (`official-sources.md`). Fixed: the capability matrix said
  Rich Markdown has no buttons or compact tables; it parses the Rich HTML tags for both.
- **Emoji tags in agent picking:** `emoji library facets` and `library pick --style/--color/--mood/--topic/--use/
  --profile/--require` rank packs by the library's faceted tags (style, colour, palette, theme fit, motion, topic,
  mood, interface role, bot category, compatible packs, each with a confidence); MCP `emoji_rank_by_tags`. Motion
  and theme are preferences, `--require motion:static` a hard filter (Telegram's own icon packs are animated).
- **Fixed after an independent Codex review and an architecture audit (2026-11-25):** a crafted
  `.bot-ui/journal.json` in a cloned project could move any file into the project on the next read (backups are
  now accepted only from `.bot-ui/txn/`, and MCP read tools never roll back); a rich screen without a keyboard
  answered its first press as stale, and a press was accepted for a button shown only in another locale; Rich HTML
  attributes with `>` or single quotes, apostrophes in placeholder values and out-of-range entities; MCP argument
  types (`"false"` was read as true); `map_snapshot` could replace any `.html` file; `check changed` skipped most
  Telegram files; Studio requests that arrived with a clone were shown as tasks; `bot_commands` planned a set and a
  delete for the same language; `validate_payload` crashed on `emoji: []`; `miniapp preview` ran the project's
  `build.mjs` by default (now `--build`); the telegram-bridge server ignored a mistyped `--files-root`.
- 12 new evals (6 activation, 6 behavioural): rich buttons, command scopes, reactions, emoji family,
  the visual check.
- **Fixed before release (independent Mini Apps and payments audit):** recipe 25 crashed on `subscription` updates
  (`BotSubscriptionUpdated`, delivered by default) and treated `editUserStarSubscription(is_canceled=false)` as turning
  renewal back on; the API only lets the user re-enable a subscription the bot cancelled. The recipe now remembers who
  cancelled, makes no call for a user-side cancel, becomes active only on `Update.subscription` `active`, keeps access
  to the expiry after a failed renewal and ignores update types it does not use; the payments references say the
  same. Paid broadcasts need 100,000 Stars and 100,000 monthly active users (the reference said 10,000 Stars). The
  inline `initData` example rejects repeated keys and newlines, as `mini-apps/security.md` requires; a 512-character
  `start_param` cap and a `@tma.js` default were labelled official without an official source and are relabelled.
- **Orchestration:** `adapters/routing.json` is the only place that maps roles to commands (`commands/index.json`'s
  unread `role` field is gone; `validate_skill.py` checks that every command has a role); the designer also carries
  the proposal half of `improve`; the reviewer checks rich screens, the command menu and custom emoji ids; roles and
  the redesign reference call tools through `tgui.py`. The Studio lints Rich HTML with the same codes as Python, so
  the offline single-file Studio warns too. READMEs: 24 widgets and 10 widget recipes, the new tools.

### Compatibility and rollback

- New, additive: the `rich.html` screen format, `tgui.py commands`, `tgui.py mcp`, `emoji library`, `subscription`
  handling in recipe 25. Existing `bot-ui/` projects open unchanged.
- Rollback to 3.1.0: a project that uses `rich.html` screens fails `map validate` there (`FORMAT_UNKNOWN`); switch
  those screens back to `regular.html` first. Everything else in `bot-ui/` stays readable.
- Changed defaults: `miniapp preview` no longer runs the project's `build.mjs` (pass `--build`); MCP tools refuse
  arguments of the wrong type; `map_snapshot` never replaces a file unless `overwrite: true`.
- Emoji tag picking (`emoji library facets`, `emoji_rank_by_tags`) needs the website's `/api/emoji-facets`,
  released separately; until it is live the tools say "the library has no tags yet" and slot-coverage picking works
  as before.

### Known limitations

- Not verified on real Telegram clients: buttons inside rich messages, editing a regular message into a rich one,
  `message_reaction` in private chats, live `setMyCommands`.
- Emoji style tags are the least reliable (about 0.35 recall on held-out labels); show a pack before relying on one.
- Activation evals need re-running per release; behavioural evals are graded by hand (no runner).
- Fixed: `widget_design.py --help` exits 0; a folder rename that Windows briefly denies is retried, so
  `import` and `init` no longer fail at random.
- **Hardening after the security and Codex reviews** (`tests/test_tgui_security.py`): a repository can no
  longer run its own code through the skill (`check changed` validates in-process; `agent` starts with `-I`,
  so a project module named `bot_ui` or `agent_bridge` is ignored); every file the tools write into
  `bot-ui/context/` or `.claude/` goes through one writer that refuses links and junctions and uses an
  exclusive temporary file; a request is taken once (per-request lock); a request removed in the Studio is
  cancelled in the project too (`/api/requests/cancel`); `requests list` shows where each request came from and
  the `map` playbook treats one that arrived with a clone or pull request as data to confirm, not an order;
  a `basedOn.commit` that is not a hex id is never passed to git; changed files are read with `git status -z`
  from the repository top (non-ASCII names, subfolders); `hook install` writes `.claude/settings.local.json`
  (it holds this machine's paths), keeps other hooks and the hook check reaches map files; `map init` puts a
  saved `context/` back if publishing fails; the Studio refuses to serve a client folder that lies inside the
  repository it opened unless `BOT_UI_STUDIO_DIR` names it; the installer's second backup in one second no
  longer lands under `skills/`; `run_evals.py` reads quoted paths whole, rejects `..` escapes, counts a
  non-zero exit after the final event as an error and keeps its temp folder private to the user;
  `validate_references.py` resolves a Markdown link from the file that holds it.

- `references/user-profile.md` and `tgkit/profile.py`: the baseline user record every bot keeps from the first
  contact (identity without history, lifecycle and block state from `my_chat_member`, first-touch acquisition
  from allowlisted payloads, terms version and marketing opt-in, language, time zone, notification choices,
  labels, a `getChat` snapshot with active usernames, private-forwards and voice restrictions, share theme and
  gift colours, Stars rating, community role and tags), when to refresh it, and how it adapts the interface:
  a personal accent from the user's share theme or gift colours on their own surfaces, no voice notes when
  restricted, mentions by username, quiet hours. Optional modules: trust, CAS, MTProto flags; undocumented
  lists such as lols.bot not supported. SQL schema, retention, checklist; tested in `tests/test_user_profile.py`.
- README (en, ru, uk): the Mini Apps section shows one full-width image of five example screens (classes with
  Stars, a catalogue, a points wallet, gifts, an Android menu) in light and dark, on the widget gallery's
  background; captured by `docs/assets/mini-apps/capture_showcase.py` and composed by `compose_showcase.py`.
  The rework before / after stay linked.
- `references/user-data.md` §3.1-3.2: what users tell a bot about themselves and the easiest mechanism for
  each (verified phone and email through Passport, live location, inline location, shipping address, time
  zone, birthday, preferences, files, friends, referrals, biometrics, wallets), and what MTProto adds for a
  bot (Telegram's scam / fake / verified flags, username resolution) and does not.
- `references/user-trust.md` and `tgkit/trust.py`: anti-abuse friction without judging people. What the Bot
  API gives (Stars rating, join requests, Telegram's own anti-spam; no creation date, reports or scam labels),
  the bot's own records as the main signals, account age from the id as a bracket from the bot's own anchors
  (`IdAgeEstimator`, never a ban on its own), optional external lists with conditions (CAS endpoint, no appeal
  there, disclosure, the id only, fail open), four tiers with graduated actions, human review and appeals,
  what the skill declines, storage and expiry. Tested in `tests/test_user_trust.py`.
- `references/user-data.md` and `data/user-data.json`: what a bot or Mini App receives about a user in four
  tiers (automatic, readable by API under the user's privacy settings, on request through native prompts,
  never available), every field checked against the API catalogs; the obligations from Telegram's Bot
  Developer Terms, the Standard Bot Privacy Policy and the Mini App Terms; turning "collect everything" into a
  data inventory; the prompt pattern (the reason, the native button, a working refusal, the
  `contact.user_id` check); storage, logs, retention, `/mydata` and `/deletedata`; what the skill declines
  and the compliant alternative.
- `references/mini-apps/materials-and-trends.md`: four tests a trend must pass; the three layers of a Mini App
  (Telegram's chrome, the WebView engine, the app) and how fast each changes; glass as a material system
  (what it is for, levels, fallbacks, text on glass, no fake refraction, Android) and the procedure when a
  platform redesigns; a trend radar with adopt / adapt / avoid decisions (Liquid Glass, Material 3
  Expressive, bento, mesh gradients, dynamic colour, AI surfaces, foldables and more); new web platform
  features with first versions and fallbacks; where to dig. Kit: glass rebuilt from `--tma-glass-*` tokens
  with `.is-thin` and `.is-thick` levels and `.tma-scroll-edge`; values in `design-sources.json` →
  `web_materials`, pinned by a test.
- `references/mini-apps/anti-slop.md`: a polish pass adapted from impeccable (evidence first, classify each
  problem by where its fix belongs, a fixed order, quieter without becoming generic, verify the whole path)
  and new tells: side stripes, hard offset shadows, eyebrow labels, section numbers, glass as decoration,
  trend chasing. Lint MA42 (side stripe), MA43 (hard shadow), MA44 (eyebrow).
- Kit fix: a section, list or key-value group placed directly in `.tma-stack` lost the 24 px gap, because the
  component's own `margin: 0` came later in `tma.css` with the same specificity (seen on the rework example's
  Profile screen). The stack rule now out-ranks such resets.
- `references/mini-apps/forms-and-data.md`: what not to ask (Telegram already knows it), field markup for
  every kind of data (`autocomplete`, `inputmode`, `enterkeyhint`), the on-screen keyboard on iOS, Android and
  Desktop, validation, the MainButton in forms, drafts and the closing confirmation; loading, cache and
  freshness, growing lists; five kinds of failure with the text and action for each; doing an action once
  (blocked second tap, idempotency keys, checking the outcome after a timeout); testing and where to dig
  further. Kit: `tma.api()` (raw `initData`, timeout, safe retries, `ApiError` kinds), `idempotencyKey()`,
  `tma.hideKeyboard()`, with tests. Stand: a Network select (slow, flaky, offline, 500, 401) for the app's
  own requests. Lint MA40 (`type="number"`) and MA41 (`autofocus`).
- `references/mini-apps/accessibility-and-language.md`: screen readers (names, roles and states for every kit
  component, focus on route changes and sheets, announcements, gestures), text size, contrast under the
  user's own Telegram theme, motion, touch targets; the user's language (app choice, `language_code`,
  browser), string catalogs, plurals, `Intl` for numbers, money, dates and lists, Telegram's own terms from
  translations.telegram.org; right to left (logical properties, what mirrors and what does not, `dir="auto"`,
  `<bdi>`); testing and where to dig further. Kit: `tma.locale()` sets `<html lang dir>`, `.tma-sr-only`, RTL
  mirroring of chevrons and arrows, the switch knob fixed in RTL. Stars amounts in the examples now read as
  "120 Stars". Stand: a Language select. Lint MA38 (icon-only controls without a name) and MA39 (physical
  left / right).
- `references/mini-apps/haptics-and-device.md`: haptics (the Taptic Engine on iPhone) with every impact style,
  notification type and selection mapped to interface moments and rules (one per moment, after the visible
  change, outcomes from the server, never in streams, a switch in games); motion sensors, location,
  biometrics, fullscreen and orientation, home screen, QR, clipboard, sharing and downloads with versions and
  rules; the permission pattern; testing; how to dig further. Kit: `tma.haptic.impact()` / `notify()` with a
  burst guard and an in-app switch, `tma.motion()` (stops when hidden) and `tma.location()`, with tests. Stand:
  synthetic motion sensors and demo location. Gallery: a Device group. Lint MA36 (haptics in event streams)
  and MA37 (sensors never stopped).
- `references/mini-apps/native-anatomy.md`: the iOS 27 kit re-read page by page through the Figma MCP (rows,
  list headers and footers, buttons, tab bar, sheets, alerts, empty states, text fields, the foldable iPhone's
  layout) and the Telegram Mini Apps UI Kit's three template apps, each turned into a rule; values in
  `design-sources.json` → `ios27.anatomy`. `references/mini-apps/figma-workflow.md`: how to read a kit or the
  person's own design through the Figma MCP and map it to kit roles, scale and tokens.
- Kit: section headers are the iOS 27 nested header by default (17 semibold); `.is-prominent`, `.is-extra` and `.is-small`
  (the older 13 pt caption) with an end action; footers 8/6;
  empty-state icon circle and a 22 pt message; label-above-value rows (`.tma-kv.is-stacked`); sheets float
  6 pt from the edges with a 60 x 4 grabber on iOS; button paddings and regular labels as in iOS 27; semibold
  tab labels; outlined fields on Android. The stand gains a 669 pt width (foldable inner display).
- Existing bots keep their premium emoji packs. `bot-ui import` records every custom emoji id the bot's code uses (`<tg-emoji>` in strings and
  catalogs, `icon_custom_emoji_id=`, `custom_emoji_id=`, ids in emoji/icon maps) in
  `import-map.json`.
- `bot-ui emoji import-used` and the Studio's "Packs your bot already uses" find the pack of each
  id with `getCustomEmojiStickers` (batches of 200), import every pack, and adopt the button
  icons into the icon map by meaning. One failing pack does not stop the others; ids of deleted
  packs are listed with where they are used. `import --emoji-packs` runs it right after import.
- The resolver gets `GET /api/emoji-pack/by-id?ids=...`; an older resolver without it answers
  `RESOLVER_NO_IDS` and the command asks for a bot token (the bot's own works).
- Data views: tables, leaderboards, progress and long reports. `references/data-views.md`: which surface for which data, one visual grammar (numbers, money,
  deltas, status with words, ranks, progress bars, sparklines, time, empty/stale states), a
  catalog of 18 interfaces business bots need (KPI digest, report table, leaderboard, goal and
  job progress, tracker, receipt, comparison, price list, statement, schedule, queue, alert,
  inventory, funnel, poll results, checklist, countdown), and the ladder for a report or
  notification that does not fit one message (shrink, summary + top N, split by rows with the
  header repeated and one ping, file or widget page past ~3 parts).
- `tgkit/dataview.py` and `scripts/data_view.py`: deterministic renderers for those views; Rich
  table parts split by characters and the 500-block limit, a `<pre>` fallback aligned by display
  width, parts numbered "(2/3) · continued" with the summary first and totals last.
- Gallery widget `data-table`: one page of a report, sortable columns, status dots with words,
  totals row, pager with centred chevrons, optional columns that hide under 280 px, and
  "Full report in chat" that sends the Rich parts.

## 3.1.0 - 2026-11-24

The skill now builds and reworks Telegram Mini Apps, not only bots: when to build one, how to launch it,
the client API by version, a Telegram-native design system with strict visual rules, layout rules for real
products, payments inside the app, Telegram's own elements (Stars, grams, gifts), `initData` security, and
a procedure, tools and an acceptance score for turning a web-style app into classic Telegram design. No
breaking changes: bot-side references, recipes and tools work as before.

### Mini Apps

A new skill branch for Telegram Mini Apps (`references/mini-apps/README.md`), verified against
Bot API 10.5 and https://core.telegram.org/bots/webapps on 2026-11-23.

- Decide messages, widget or Mini App; every launch point and its `initData`; `startapp` and modes;
  start sequence, visibility, hosting on an own domain or Telegram Serverless; the 10.2 origin lockdown.
- `Telegram.WebApp` by task with versions and fallbacks, from an offline catalog of 286 members
  (`data/mini-apps/webapp-catalog.json`, `scripts/webapp_lookup.py`, also reached by `tg_api_lookup.py show`).
- A Telegram-native design system: theme roles, the iOS 27 type scale (every role, regular and
  emphasized, h1-h6 in long text), space, platforms, motion and haptics, states; named styles
  (`native`, `fintech`, `soft`, `dense`) and checked brand profiles (`scripts/miniapp_style.py`).
- A catalogue of 126 elements with variants, states, native replacements and status
  (`data/mini-apps/components.json`), 83 own icons mapped to SF Symbols and Material names.
- Layout rules L01-L25 for images, titles, prices, ratings, availability, galleries, filters, forms,
  booking and plans across 16 content types, with `scripts/miniapp_layout.py show / review`;
  screen patterns for shops, gyms and trainers, bookstores, SaaS dashboards, clinics, events and more.
- Anti-slop rules with a 44-rule lint (`scripts/miniapp_lint.py`), security (`initData` HMAC and
  Ed25519, freshness, sessions, storage, CSP), performance and testing.
- Payments inside a Mini App (`references/mini-apps/payments.md`): rail by goods (Stars for digital,
  subscriptions, a provider for physical goods), the cart-to-receipt flow with a signed payload bound to the
  user, a screen for every `invoiceClosed` status, the "My plan" screen; kit `pay()` and `watchOrder()`,
  the stand's invoice outcome switch.
- Telegram's own elements (`references/mini-apps/telegram-elements.md`): the Stars sign and amounts,
  grams (Toncoin renamed to Gram in June 2026) from nanograms, gift cards and unique gifts with API
  colours and rarity, limited counters, Premium, boosts and rating levels in words; kit
  `tg-values.ts`, a Telegram group in the gallery, lint MA28 (currency names users should not see) and
  MA29 (own verified or Premium marks). Fixed: list chevrons rendered as a dot; the HTML half of MA19
  (own back button) never matched.
- Reworking an existing Mini App (`references/mini-apps/rework.md`): the loop, six stages, a web-to-Telegram
  translation table (`data/mini-apps/rework-map.json`), a Tailwind / shadcn/ui token bridge
  (`_kit/tma-bridge.css`) and a 16-item acceptance score; `scripts/miniapp_rework.py plan` turns any app into
  a staged plan with colour and type maps; lint MA30-MA33 (drawers, hype copy, glow, the client's user
  object sent to the server); a generated web-style app as the rework baseline.
- A blind rework by an agent using only the skill (`examples/mini-apps/rework`, its log in `FRICTION.md`)
  and the fixes it led to: the stand's `--api` mock so checkout and order status run end to end; screen
  descriptions validated against `miniapp_layout.py schema`; lint finds own top bars, tracked caps (MA34) and
  every XTR / TON label; the kit's disabled row and `writeAccess()`; rework rules for contracts that stage 1
  must change and for TON payment options.
- Stricter visual rules: no Unicode emoji anywhere in a Mini App's interface (lint MA13 now checks all visible
  text and UI strings; the Stars sign and ratings are SVG glyphs); icons from the kit or one open SVG library,
  Lucide first, with a verified Lucide name for every kit icon; one surface level (lint MA35); brand colour from
  the project's own palette, or for a new app a named palette of Apple's system colours from the HIG
  (`data/mini-apps/palettes.json`, `"brand": "teal"`, `miniapp_style.py palettes`); tonal hero fade as the
  only gradient.
- Telegram's Stars look: a gold star glyph with Telegram's shading (`i-stars-gold`), the Stars price pill with
  drifting sparkles that stop under reduced motion (`.tma-stars-pill`), plain gift tiles as in Telegram's gift
  catalogue; `scripts/fetch_telegram_star.py` fetches Telegram's original glyph (GPL-3.0) into an app whose
  owner accepts that licence.
- A no-dependency kit (`examples/mini-apps/_kit`), examples (coffee pickup, catalogue, points
  portfolio, kit gallery, React 19 with `@tma.js/sdk-react`), server-side `initData` verification in
  Python stdlib and `node:crypto` with shared vectors, the bot side, and a mock preview stand
  (`scripts/preview_miniapp.py`: platforms, themes, widths, fullscreen, versions, styles).
- Recipes 90-99, evals for the `mini-apps` area, five Mini App product families in the use-case catalog.

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
