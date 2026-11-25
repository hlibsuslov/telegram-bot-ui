# Privacy policy

`telegram-bot-ui` is an open-source Agent Skill and plugin (MIT). It runs inside your coding
agent and on your machine. The one service the maintainer runs for it is the public emoji
library and pack resolver on the project website (`telegram-bot-ui.hlixli.com`), described below.

## What it collects

Nothing on its own. The skill, its subagents, scripts and examples have no telemetry, analytics,
accounts or remote logging. The emoji tools below send the website only what a lookup needs,
and only when you use them.

## What it reads

The instructions and reference files in the skill, and the files of the bot project you
point your agent at, so the agent can review and change that bot's interface. Secrets are
not opened: the style probe (`skills/telegram-bot-ui/scripts/style_profile.py`) skips `.env` and credential files,
and bot tokens are only ever taken from an environment variable you name.

## When it talks to the network

Only when you ask for it:

- **Bot API calls** (`api.telegram.org`) happen when you run a live mode yourself: publishing
  a channel post with `skills/telegram-bot-ui/scripts/tg_post.py --live`, the agent bridge with `--live`, or live
  emoji lookups. They use your own bot token and send only what that action needs, such as
  the post you approved. Without the flag the tools do a dry run.
- **Bot API documentation** (`core.telegram.org`) is downloaded when you run
  `skills/telegram-bot-ui/scripts/sync_bot_api.py` to refresh the offline catalog. No token, no personal data.
- **Emoji library and pack resolver** (`telegram-bot-ui.hlixli.com`), used by `tgui.py emoji library
  search|pick|facets`, the MCP emoji tools and pack import in bot-ui Studio: they send the search
  words, slot emoji, tag values, pack names, and for "which pack is this emoji from" the custom emoji
  ids you look up. No bot token, no message text, no file contents. The website keeps standard
  request logs of its host and counts searches without cookies (see the website's privacy page).
  Set `BOT_UI_EMOJI_RESOLVER=off` to switch all of it off, or to another URL to use your own.
- **Widget preview** (`skills/telegram-bot-ui/scripts/preview_widget.py --serve`) listens on `127.0.0.1` only.

What Telegram does with data sent to it is covered by Telegram's own privacy policy.

## Retention

The skill stores nothing outside the files it writes in your project at your request. The
website's emoji lookups are not tied to an account; its host keeps ordinary request logs.

## Children

The skill is a developer tool and is not directed at children under 18.

## Contact

Questions or concerns: open an issue at
<https://github.com/hlibsuslov/telegram-bot-ui/issues>, or report privately through
**Security → Report a vulnerability** on the repository (see [SECURITY.md](SECURITY.md)).

Last updated: 2026-11-25.
