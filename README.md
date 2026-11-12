# telegram-bot-ui

**Make your Telegram bot look and feel like a well-designed product.**
An Agent Skill that teaches AI coding agents (Claude Code, Codex and other Agent Skills hosts)
to design, build and fix Telegram bot interfaces — texts, buttons, menus, forms, streaming AI
answers, rich documents, widgets — using the newest Bot API correctly.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/format-Agent%20Skills-8A2BE2.svg)](https://github.com/anthropics/skills)
[![Verified: Bot API 10.4](https://img.shields.io/badge/Telegram%20Bot%20API-10.4%20verified%202026--11--12-26A5E4.svg)](https://core.telegram.org/bots/api-changelog)
[![Checks](https://img.shields.io/badge/offline%20checks-83%20Python%20%C2%B7%2010%20TS-2ea44f.svg)](#quality-and-honesty)

🇷🇺 / 🇺🇦 Коротко по-русски: [README.ru.md](README.ru.md)

---

## Why

Most bots feel unfinished not because of their logic but because of their interface: a wall of
text, ten buttons of equal weight, a spinner that never stops, a "Delete" one tap away, emoji
everywhere, icons from five different styles, and an AI answer you can't stop.

Telegram gives bots a real UI toolkit — colored and disabled buttons, custom emoji icons,
streamed drafts with a Stop button, private per-user replies in groups, rich documents with
tables, and since Bot API 10.4 interactive **HTML widgets** inside messages. Using it well takes
knowledge that is spread over dozens of pages and changes every release.

This skill packs that knowledge — plus design rules and working code — so your agent gets it
right the first time.

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

The same discipline applies everywhere:

| Situation | Without the skill | With the skill |
|---|---|---|
| AI answer takes 20 s | "typing…" then a wall of text | streamed draft with real stages, a **Stop** button, a clear "stopped — incomplete" ending |
| A form | "Send your phone" with no way back | buttons **and** a reply field in one step, Back keeps answers, **Submit** disabled until valid, no double orders |
| "My balance" in a group | posted for everyone to see | shown **only to the person who tapped**; never leaks on errors |
| Order status | four new messages per update | **one live card** (widget) that updates in place |
| A comparison | monospace pseudo-table | a real (compact) table; 3 facts stay 3 short lines |
| Premium icons | seven icon styles mixed | **one icon family**, same icon in titles and buttons, safe fallback |
| Old SDK | new features silently dropped | the gap is detected and bridged with an isolated adapter |

## Install

The skill is a folder. Put it where your agent looks for skills; the folder name must be
`telegram-bot-ui`.

**Claude Code** (all projects):

```bash
git clone https://github.com/hlibsuslov/telegram-bot-ui.git ~/.claude/skills/telegram-bot-ui
```

One project only: clone into `<your-repo>/.claude/skills/telegram-bot-ui`.
Windows: `%USERPROFILE%\.claude\skills\telegram-bot-ui`.

**Codex**:

```bash
git clone https://github.com/hlibsuslov/telegram-bot-ui.git ~/.agents/skills/telegram-bot-ui
```

Project level: `<your-repo>/.agents/skills/telegram-bot-ui`.

**Other Agent Skills hosts** (including Claude apps that support uploading custom skills): use the
repository folder as is, or upload a ZIP of it — `SKILL.md` is the entry point.

Update later with `git pull` inside the folder.

## Use

You don't need to remember any API names. Ask in plain words, in your bot's repository:

- *"Improve the UX of this Telegram bot."*
- *"The main menu is a mess — restructure it and make the main action stand out."*
- *"Add a Stop button to the AI answers."*
- *"In our group, 'My orders' must show each person only their own orders."*
- *"Turn the order status into one card that updates."*
- *"Our premium icons look mismatched — fix them."*
- *"Upgrade the bot to the latest Bot API features that make sense for it."*
- *"Fix `can't parse entities`."*

The skill activates automatically when a request is about a bot's interface or the Telegram
features behind it. You can also call it by name: *"use the telegram-bot-ui skill …"*
(Codex: `$telegram-bot-ui`).

What the agent then does: reads your project and SDK version → maps every screen and button →
fixes words first, then structure, then color and icons → implements in your project's style
without breaking `callback_data`, deep links, handlers or translations → adds tests → tells you
what it verified and what it couldn't.

## What it knows

| Area | Highlights |
|---|---|
| **Words** | microcopy, titles, prompts, empty/error/stale states, confirmations, localization and RTL |
| **Buttons & keyboards** | one action per button, hierarchy (`primary` / `success` / `danger`), disabled buttons, keyboard + reply field, pagination, back/home, commands, menu button, deep links |
| **Visual language** | choosing **premium custom-emoji icons from one consistent family**, emoji discipline, screen anatomy, one symbol per meaning |
| **Feedback** | callback spinners, chat actions, streamed drafts with Stop, honest progress, throttling, retries |
| **Messages** | HTML / MarkdownV2 / entities, Rich Messages: tables (compact), quotes, documents, buttons inside text, splitting long content safely |
| **Groups** | ephemeral personal replies and panels, audience-safe fallbacks, topics, channel direct messages |
| **Widgets (10.4)** | interactive cards in private chats, shared widgets (live polls, tickers), sizes and sandbox limits, Telegram's official widget-authoring prompt, TON wallet pay/sign |
| **Engineering** | `allowed_updates`, update routing, callback state, unknown send outcomes, 429 handling, SDK gaps (aiogram, grammY) |
| **Every 10.3 / 10.4 change** | 52 items, each with an explanation, an example and an automated check — [coverage registry](references/bot-api-10.3-10.4.md) |

And it knows **when not to** use something: no widget for a three-button menu, no table for two
facts, no group widgets in production (they are test-server only today).

## Recipes and examples

Ready-to-adapt, runnable offline (no bot token needed):

| Recipe | You get |
|---|---|
| [AI assistant with Stop](recipes/01-ai-assistant.md) | rich streaming, real stages, Stop, race-safe single final message |
| [Interactive document](recipes/02-interactive-document.md) | compact table, collapsible quote, attached file, buttons in text, quote-back |
| [Multi-step form](recipes/03-multi-step-form.md) | buttons + reply field, disabled Submit, Back, no duplicates |
| [Shared card + personal panel](recipes/04-shared-card-personal-panel.md) | per-user private views in a group |
| [Private widget](recipes/05-private-widget.md) | an order card that updates in place |
| [Shared widget](recipes/06-shared-widget.md) | one live poll in many chats |
| [Wallet](recipes/07-wallet.md) | pay and sign from a widget, honest payment states |
| [Multi-topic bot](recipes/08-multi-topic-bot.md) | parallel conversations, topic links |
| [Tracker bot upgrade](recipes/09-tracker-bot.md) | a real bot ([case study](references/case-study-btc-tracker.md)) moved to the new API |
| [Mini-recipes](recipes/mini-recipes.md) | gifts, communities, share themes, managed bots, verification and more |

Code: Python ([`examples/python/tgkit`](examples/python/tgkit), standard library) and TypeScript
([`examples/ts`](examples/ts), no dependencies), plus adapters for **aiogram 3.31** and
**grammY 1.46**. Index by task, API name or bot type: [`recipes/README.md`](recipes/README.md),
[`references/bot-archetypes.md`](references/bot-archetypes.md).

```bash
python examples/python/recipes/r01_ai_assistant.py   # prints the API calls and checks itself
node examples/ts/recipes.ts
```

## Tools you can use without an agent

All offline, standard library, never need a bot token (Windows: `py -3` instead of `python`):

```bash
python scripts/validate_keyboard.py keyboard.json   # button and keyboard payload rules
python scripts/validate_rich.py message.json        # Rich Message limits and rules
python scripts/validate_widget.py widget.html       # widget size (server algorithm) and sandbox gaps
python scripts/audit_icons.py icon-map.json         # one icon family? animated mixed in? shared ids?
python scripts/audit_copy.py strings.json           # translations: placeholders, symbols, label length
python scripts/run_checks.py                        # every check in this repository
```

## Quality and honesty

- Verified against the **official Bot API 10.4 docs on 2026-11-12**; sources and dates in
  [`references/official-sources.md`](references/official-sources.md). Each rule is marked as an
  API requirement, an official recommendation, or a design heuristic.
- 83 Python and 10 TypeScript offline tests, contract tests against the real aiogram and grammY
  packages, and `tsc --strict` on the TypeScript code. A Codex security review was run and its
  findings fixed.
- Not verified here: live calls to Telegram and rendering in the Telegram apps. The skill tells
  the agent to say which level of evidence it has — a JSON check is not a client test.
- Behavior evals for agents are prepared in [`evals/`](evals/) but have not been run yet.

## Compatibility

| | |
|---|---|
| Agents | Claude Code, Codex, any host that reads Agent Skills (`SKILL.md`) |
| Bot languages / SDKs | any — Python, TypeScript/JS, Go, C#, Java, PHP…; raw Bot API too |
| Verified SDK status | aiogram 3.31.0 and grammY 1.46.0 implement Bot API 10.3; widgets (10.4) need the included adapters |
| Bot API | 10.4 (older versions supported with version gates) |

## FAQ

**Does it change my bot?** No. It is knowledge for your agent; the agent edits your bot when you ask.

**Do I need Telegram Premium?** Only for custom emoji icons in a regular bot (or Fragment usernames).
Everything else works without it, and the icons degrade cleanly to normal emoji.

**Does it send messages or need my token?** No. All checks are offline. An optional live replay
works only with a separate **test** bot and an explicit opt-in.

**My bot uses an old SDK.** The skill checks what your SDK actually supports and either suggests an
upgrade or adds a small, isolated adapter with a "remove when" note.

## Repository layout

```
SKILL.md          entry point the agent reads first (routing, rules, invariants)
references/       focused guides, loaded only when a task needs them
recipes/          end-to-end recipes, registry.json (all 10.3/10.4 items), manifest.json
examples/         runnable Python/TS code, widgets, fixtures, payloads, SDK adapters, case study
scripts/          validators and auditors (offline)
tests/            offline test suite
evals/            activation and behavior evals
agents/           Codex metadata
```

## Contributing

Issues and pull requests are welcome — especially screenshots from real Telegram clients,
new recipes, and SDK support updates. Please cite official Telegram docs for capability claims,
mark anything unverified, keep `SKILL.md` compact, and run `python scripts/run_checks.py`.

## License

[MIT](LICENSE).

## Disclaimer

Community project; not affiliated with or endorsed by Telegram. Telegram changes the Bot API
often — verify current behavior against the [official docs](https://core.telegram.org/bots/api)
before relying on a capability.
