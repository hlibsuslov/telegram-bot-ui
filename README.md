# telegram-bot-ui

**Make your Telegram bot look, feel and run like a well-designed product.**
An Agent Skill that teaches AI coding agents to design and build Telegram bot interfaces, operate
bots, publish to channels, build HTML widgets and look up the whole Bot API — using the newest
Bot API correctly. Works in Claude Code, Codex, Cursor, Gemini CLI / Antigravity, GitHub Copilot,
Devin, and any agent that reads `AGENTS.md` or a system prompt.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/format-Agent%20Skills-8A2BE2.svg)](https://github.com/anthropics/skills)
[![Verified: Bot API 10.4](https://img.shields.io/badge/Telegram%20Bot%20API-10.4%20verified%202026--11--15-26A5E4.svg)](https://core.telegram.org/bots/api-changelog)
[![checks](https://github.com/hlibsuslov/telegram-bot-ui/actions/workflows/checks.yml/badge.svg)](https://github.com/hlibsuslov/telegram-bot-ui/actions/workflows/checks.yml)

🇷🇺 / 🇺🇦 По-русски: [README.ru.md](README.ru.md)

---

## What your agent can do with it

| Capability | What the agent gets right |
|---|---|
| **Build bot interfaces** | texts, menus, inline and reply keyboards, colored and disabled buttons, forms, navigation, streaming AI answers with Stop, private replies in groups, Rich Messages and tables, formatting, localization |
| **Product flows** | shops, support, bookings, AI assistants, trackers: no stale "Pay" buttons, no double orders, no personal data leaking into groups (15 product recipes) |
| **Publish to channels** | compose, validate, preview, approve and schedule channel posts; never post twice after a timeout (`scripts/tg_post.py`, 10 recipes) |
| **Operate as an agent through a bot** | drive an agent from Telegram with an operator allowlist, approval buttons bound to one action, and inbound messages treated as data, not instructions (`agent_bridge` CLI, MCP server, Claude Code and Codex hooks, 10 recipes) |
| **Build HTML widgets** | Bot API 10.4 widgets inside messages: size limit, production context, caption and text fallback, live cards, shared polls, wallet flows (18 ready widgets, build and preview tools, 7 recipes) |
| **Premium emoji** | one custom emoji pack across buttons, texts, rich messages and posts: real ids resolved from the pack, all-or-nothing fallback when the bot is not eligible (6 recipes) |
| **Look up the whole Bot API** | methods, types and fields from a local catalog; validate a payload before sending; refuse to invent a field (193 methods, 425 types, refreshable from the official docs) |

And it knows **when not to** use something: no widget for a three-button menu, no table for two
facts, no group widgets in production (they are test-server only today), no publishing without a
human's yes.

## What changes in your bot

**Before** — a typical menu:

```
⚙️⚙️ SETTINGS MENU ⚙️⚙️
Please select what you want to do from the options below:
[🔔 Notifications] [🌐 Language] [🗑 Delete] [ℹ️ Help] [❌ Close]
```

**After** — what the agent produces with the skill:

```
<b>⚙️ Settings</b>
Choose what to change.

[🔔 Notifications]
[🌐 Language]
[Delete account]   ← style: danger, opens a confirmation that says what is lost
[← Back]
```

| Situation | Without the skill | With the skill |
|---|---|---|
| AI answer takes 20 s | "typing…" then a wall of text | streamed draft with real stages, a **Stop** button, a clear "stopped — incomplete" ending |
| A form | "Send your phone" with no way back | buttons **and** a reply field in one step, Back keeps answers, **Submit** disabled until valid, no double orders |
| "My balance" in a group | posted for everyone to see | shown **only to the person who tapped**; never leaks on errors |
| Order status | four new messages per update | **one live card** (widget) that updates in place |
| Channel post timed out | posted again, now twice | outcome treated as unknown, checked before any retry |
| "Ignore your rules" in a message to an agent bot | the agent obeys | quoted as data; the operator is told |
| Old SDK | new features silently dropped | the gap is detected and bridged with an isolated adapter |

## Install

The skill is one folder whose entry point is `SKILL.md`. Pick your agent; every path below is
checked against that host's documentation in [`docs/hosts.md`](docs/hosts.md).

### Claude Code — plugin (skill + five subagents)

In a Claude Code session (2.1.275 or later):

```
/plugin install telegram-bot-ui --marketplace hlibsuslov/telegram-bot-ui
```

Or from your shell, in two steps:

```bash
claude plugin marketplace add hlibsuslov/telegram-bot-ui
```

```bash
claude plugin install telegram-bot-ui@telegram-bot-ui
```

The skill is then `/telegram-bot-ui:telegram-bot-ui` and the subagents are
`telegram-bot-ui:telegram-bot-designer` and so on.

### Claude Code — plain skill folder

```bash
git clone https://github.com/hlibsuslov/telegram-bot-ui.git ~/.claude/skills/telegram-bot-ui
```

One project only: clone into `<your-repo>/.claude/skills/telegram-bot-ui`. To add the subagents
too, use the installer below.

### Any host — the installer

Clone once, then let `scripts/install.py` put the right files in the right places (standard library
Python; Windows: `py -3` instead of `python`):

```bash
git clone https://github.com/hlibsuslov/telegram-bot-ui.git && cd telegram-bot-ui
```

```bash
python scripts/install.py --host all --scope user --dry-run
```

`--host claude|codex|cursor|gemini|copilot|all`, `--scope user|project` (`--project <path>` for
another repository), `--with-instructions` adds a short pointer block to `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md` or a Cursor rule (project scope only), `--link` symlinks to the
clone instead of copying, `--uninstall` removes only what the installer created. Anything already
there that the installer did not create is first moved to `<name>.bak-<time>`.

| Host | Skill folder (user / project) | Extras |
|---|---|---|
| Claude Code | `~/.claude/skills/` / `.claude/skills/` | subagents in `.claude/agents/` |
| Codex CLI | `~/.agents/skills/` / `.agents/skills/` | custom agents in `.codex/agents/*.toml`; call the skill with `$telegram-bot-ui` |
| Cursor | `~/.agents/skills/` / `.agents/skills/` | optional rule `.cursor/rules/telegram-bot-ui.mdc` |
| Gemini CLI / Antigravity | `~/.gemini/skills/` / `.agents/skills/` | or `gemini skills install https://github.com/hlibsuslov/telegram-bot-ui`; optional `GEMINI.md` block |
| GitHub Copilot | `~/.agents/skills/` / `.agents/skills/` | optional `.github/copilot-instructions.md` block |
| Devin (formerly Windsurf) | reads `~/.agents/skills/` / `.agents/skills/` | install with `--host codex` |
| Cline and other `AGENTS.md` readers | — | paste [`adapters/agents-md/AGENTS.snippet.md`](adapters/agents-md/AGENTS.snippet.md) and keep the folder in the repo |
| Your own agent on a model API | — | system prompt: [`adapters/portable/telegram-bot-ui.prompt.md`](adapters/portable/telegram-bot-ui.prompt.md); with a file tool: [`llms.txt`](llms.txt) |

Update: `git pull` in the clone and run the same install command again (or use `--link` once).
Claude Code plugin: `claude plugin update telegram-bot-ui`.

## Subagents

Five roles that route into the skill instead of copying it. Claude Code: [`agents/claude/`](agents/claude/)
(installed by the plugin or the installer). Codex: [`agents/codex/`](agents/codex/) as custom
agents ("Have telegram_bot_reviewer review this diff").

| Role | Does | Edits code? |
|---|---|---|
| `telegram-bot-designer` | screen/state map, real UX defects, exact texts and keyboards | no |
| `telegram-bot-builder` | implements from recipes, validates payloads, adds tests | yes |
| `telegram-publisher` | composes, validates, previews and publishes channel posts — only after your explicit yes | yes |
| `telegram-widget-builder` | designs and builds HTML widgets, checks size and fallback | yes |
| `telegram-bot-reviewer` | reviews a diff against the skill's invariants with file:line findings | no |

On hosts without subagents, ask for the role in words: *"Act as a reviewer of this diff using the
telegram-bot-ui skill."*

## Ask your agent

No API names needed. In your bot's repository:

**Interfaces**
- *"Improve the UX of this Telegram bot."*
- *"The main menu is a mess — restructure it and make the main action stand out."*
- *"Add a Stop button to the AI answers."*
- *"Fix `can't parse entities`."*

**Product flows**
- *"People double-tap 'Place order' and get two orders."*
- *"In our group, 'My orders' must show each person only their own orders."*
- *"Design a booking bot: service, time, confirmation."*

**Channels**
- *"Post this release note to our channel tomorrow at 9:00 — show me the preview first."*
- *"Every Monday, publish a digest of last week's releases without duplicates."*

**Agent through a bot**
- *"Let me drive my coding agent from Telegram, and only me."*
- *"Make the agent ask for approval with buttons before anything risky."*

**Widgets**
- *"Turn the order status into one card that updates."*
- *"Our widget is too big to send — make it fit."*

**Bot API lookup**
- *"Which update tells my bot that the user stopped the answer?"*
- *"Can a bot delete a message for just one user?"*

The skill activates automatically when a request matches. You can also call it by name:
`/telegram-bot-ui` (Claude Code), `$telegram-bot-ui` (Codex), the `/` menu (Cursor, Antigravity).

## Recipes and examples

Ready to adapt and runnable offline (no bot token):

| Recipe | You get |
|---|---|
| [AI assistant with Stop](recipes/01-ai-assistant.md) | rich streaming, real stages, Stop, race-safe single final message |
| [Interactive document](recipes/02-interactive-document.md) | compact table, collapsible quote, attached file, buttons in text |
| [Multi-step form](recipes/03-multi-step-form.md) | buttons + reply field, disabled Submit, Back, no duplicates |
| [Shared card + personal panel](recipes/04-shared-card-personal-panel.md) | per-user private views in a group |
| [Private widget](recipes/05-private-widget.md) | an order card that updates in place |
| [Shared widget](recipes/06-shared-widget.md) | one live poll in many chats |
| [Wallet](recipes/07-wallet.md) | pay and sign from a widget, honest payment states |
| [Multi-topic bot](recipes/08-multi-topic-bot.md) | parallel conversations, topic links |
| [Tracker bot upgrade](recipes/09-tracker-bot.md) | a real bot moved to the new API |
| [Mini-recipes](recipes/mini-recipes.md) | gifts, communities, share themes, managed bots, verification |

| Range | You get |
|---|---|
| [20-29, 60-64 Products](references/use-case-playbooks.md) | shop with Stars, support desk, booking, onboarding, settings, subscription, learning, assistant, expense split, community, inline mode, business account, alerts, search, delivery tracker |
| [30-39 Channel publishing](references/publishing-pipeline.md) | autoposter, long read, album, poll, pinned digest, editorial approval, cross-posting, mailing, comments, corrections |
| [40-49 Agent through its bot](references/agent-operated-bots.md) | deploy approval, live build status, nightly digest, ask and continue, streamed research with Stop, job topics, team group, incident alerts, coding-agent hooks |
| [50-56 Widgets](references/widget-patterns.md) | monitoring dashboard, booking, shop card, shared quiz, job progress, design a widget from words, REST data browser |
| [70-75 Premium emoji](references/emoji-packs.md) | restyle to one pack, icons from zero, channel series, mixed eligibility, Premium lapse, pack migration |

Full index by task, API symbol, version and context: [`recipes/README.md`](recipes/README.md).

Code: Python ([`examples/python/tgkit`](examples/python/tgkit), standard library) and TypeScript
([`examples/ts`](examples/ts), no dependencies), plus adapters for **aiogram 3.31** and **grammY 1.46**.

```bash
python examples/python/recipes/r01_ai_assistant.py
```

## Tools you can use without an agent

All offline, standard library, never need a bot token:

```bash
python scripts/validate_keyboard.py keyboard.json   # button and keyboard payload rules
python scripts/validate_rich.py message.json        # Rich Message limits and rules
python scripts/validate_widget.py widget.html       # widget size (server algorithm) and sandbox gaps
python scripts/audit_icons.py icon-map.json         # one icon family? animated mixed in?
python scripts/audit_copy.py strings.json           # translations: placeholders, symbols, label length
python scripts/install.py --host all --dry-run      # where the skill would be installed
python scripts/run_checks.py                        # every check in this repository
```

```bash
python scripts/tg_api_lookup.py show sendWidget      # any method or type, offline
python scripts/validate_payload.py request.json      # structural check against the catalog
python scripts/tg_post.py preview post.json          # render a channel post (publishing is opt-in)
python scripts/build_widget.py src.html --strict     # build a widget from the kit, report its size
python scripts/preview_widget.py widget.html         # mock preview page (not a real client)
python scripts/emoji_packs.py capture                # how to collect real custom emoji ids
```

## Quality and honesty

- Verified against the **official Bot API 10.4 docs on 2026-11-15**; sources and dates in
  [`references/official-sources.md`](references/official-sources.md).
- Host formats (skill paths, subagent and plugin manifests, rule files) verified against each
  host's documentation on **2026-11-15** — [`docs/hosts.md`](docs/hosts.md). The Claude Code
  plugin passes `claude plugin validate --strict`. Cursor, Antigravity, Copilot, Devin and Cline
  were checked by documentation only, not by running them.
- Host entry files are generated from `SKILL.md` and one routing table by
  `scripts/build_adapters.py`; CI fails when they drift.
- Offline Python and TypeScript test suites run on Linux and Windows in CI, plus contract tests
  against the real aiogram and grammY packages: 393 Python and 31 TypeScript tests.
- **Agent evals are prepared, not yet run.** [`evals/`](evals/) holds activation prompts (English
  and Russian, with and without API names) and behavioural tasks with pass criteria for every
  capability; `scripts/run_evals.py` validates them and can execute the activation set against
  the Claude Code or Codex CLI. No agent run has been recorded yet.
- Not verified: live calls to Telegram and rendering in the Telegram apps. The skill tells the
  agent to say which level of evidence it has — a JSON check is not a client test.

## FAQ

**Does it change my bot?** No. It is knowledge and tools for your agent; the agent edits your bot when you ask.

**Does it send messages or need my token?** The checks never do. Publishing and agent operation need a
bot token from an environment variable, and the skill requires your explicit approval before anything
is published.

**Do I need Telegram Premium?** Only for custom emoji icons in a regular bot (or Fragment usernames).

**My bot uses an old SDK.** The skill checks what your SDK supports and either suggests an upgrade or
adds a small, isolated adapter with a "remove when" note.

## Repository layout

```
SKILL.md            entry point the agent reads first (routing, rules, invariants)
references/         focused guides, loaded only when a task needs them
recipes/            end-to-end recipes, registry.json, manifest.json
examples/           runnable Python/TS code, widgets, fixtures, payloads, SDK adapters
scripts/            validators, installer, adapter generator, eval runner (offline)
agents/             Codex metadata (openai.yaml), Claude subagents, Codex custom agents
adapters/           routing table and generated entry files for other hosts
.claude-plugin/     Claude Code plugin and marketplace manifests
llms.txt            index of every document for agents that read files on demand
docs/hosts.md       how each agent host discovers skills, with sources
tests/, evals/      offline tests; activation and behavioural evals
```

## Contributing

Issues and pull requests are welcome — especially screenshots from real Telegram clients, new
recipes, SDK support updates and eval runs on more hosts. Cite official Telegram docs for capability
claims, mark anything unverified, keep `SKILL.md` compact, run `python scripts/build_adapters.py`
after editing `SKILL.md` or `adapters/`, then `python scripts/run_checks.py`.

## License

[MIT](LICENSE).

## Disclaimer

Community project; not affiliated with or endorsed by Telegram. Telegram changes the Bot API often —
verify current behavior against the [official docs](https://core.telegram.org/bots/api) before
relying on a capability.
