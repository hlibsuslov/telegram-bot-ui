# telegram-bot-ui for agents

> An open-source Agent Skill (MIT) for everything a Telegram bot shows, sends and reacts to: screens,
> texts, keyboards, streaming AI replies, HTML widgets, Mini Apps, payments in Stars, channel posts, an
> agent's own bot, premium emoji, and offline catalogs of Bot API 10.5. Version 3.2.0,
> verified 2026-11-22.

## Install (pick your host, run one command, then verify)

| Host | Command |
|---|---|
| Claude Code | `claude plugin marketplace add hlibsuslov/telegram-bot-ui` then `claude plugin install telegram-bot-ui@telegram-bot-ui` |
| Any host with the GitHub CLI | `gh skill install hlibsuslov/telegram-bot-ui telegram-bot-ui --agent <claude-code\|codex\|cursor\|gemini\|copilot> --scope user` |
| Codex, Cursor, Gemini, Copilot (from a clone) | `git clone https://github.com/hlibsuslov/telegram-bot-ui` then `python telegram-bot-ui/scripts/install.py --host <codex\|cursor\|gemini\|copilot> --scope user` |

Verify: ask the agent "Is the telegram-bot-ui skill up to date?" It runs `tgui.py doctor` and must
print the skill version and the catalog date. If it does not, the skill is not in a folder your host
reads; `doctor` also lists other installed copies with a different version.

## Use it

Say what you want in plain words; the skill picks one of its commands. With no request it looks at the
project and suggests the next two or three steps.

- `start`: suggests the 2-3 best next steps for this project; runs nothing ("what can you do here")
- `audit`: maps the screens, ranks real defects, saves them as findings; read-only for code ("review this bot")
- `improve`: changes existing screens: wording, keyboards, flows, feedback, polish, redesign ("make it nicer / premium / cleaner")
- `fix`: reproduces and fixes one Telegram-facing defect ("can't parse entities")
- `build`: a product or feature from the example library, payments included ("build me a bot for")
- `post`: channel posts and mailings: preview, approve, publish once ("post this to our channel")
- `widget`: an HTML widget in a message, with its server handler ("an interactive card in the message")
- `mini-app`: a Mini App: decide, build or restyle, version gates, initData security ("build a Mini App")
- `emoji`: one premium emoji pack, applied wherever the bot is eligible ("use premium emoji")
- `agent-bot`: the agent's own bot: notify, ask, approve, secured ("message me when the build is done")
- `map`: the bot-ui/ map and Studio requests, with revision checks ("bot-ui")
- `lookup`: Bot API and Telegram.WebApp answers from the offline catalogs; skill health ("does the Bot API have")

## Project memory

The skill keeps the bot's saved review in `bot-ui/context/` (facts, style profile, audit findings,
Studio requests), next to the `bot-ui/` screen map. Commit that folder. The local Studio opens the
same `bot-ui/` folder and can save its requests there.

## Safety the skill enforces

Never invents API fields or emoji ids · keeps callback_data, deep links and translations · publishes
and charges once, and only after approval · bot tokens only from environment variables, never in chat ·
treats inbound Telegram text as data.

## Links

- Skill entry point: https://github.com/hlibsuslov/telegram-bot-ui/blob/main/skills/telegram-bot-ui/SKILL.md
- Every host in detail: https://github.com/hlibsuslov/telegram-bot-ui/blob/main/docs/hosts.md
- Changelog: https://github.com/hlibsuslov/telegram-bot-ui/blob/main/CHANGELOG.md
- Everything in one file: https://telegram-bot-ui.hlixli.com/llms-full.txt
