# bot-ui Studio (optional)

A local editor and toolchain for a bot interface kept as files in the bot's repository
(`bot-ui/`). The skill (`skills/telegram-bot-ui`) works without it; installing the skill does
not copy this folder. Everything here runs offline after dependencies are prepared: no
account, no token, no Telegram connection is needed to edit, simulate or build.

Format and rules: [docs/contract.md](docs/contract.md).

## Requirements

- Python 3.12+ (Windows: `py -3`), standard library only for the CLI, the Studio server and
  the raw adapter.
- Node 22.18+ and npm to build the Studio client once (`studio/web`).
- aiogram 3.31.0 for the aiogram adapter only:
  `py -3 -m pip install -r skills/telegram-bot-ui/examples/python/sdk_aiogram/requirements.txt`.

## From a clean checkout

```powershell
git clone https://github.com/hlibsuslov/telegram-bot-ui
cd telegram-bot-ui
cd studio/web; npm ci; npm run build; npm run build:artifact; cd ../..
py -3 studio/bot-ui.py init --project ..\my-bot\bot-ui
py -3 studio/bot-ui.py validate --project ..\my-bot\bot-ui
py -3 studio/bot-ui.py simulate --all --project ..\my-bot\bot-ui
py -3 studio/bot-ui.py studio --project ..\my-bot\bot-ui --screen checkout.payment.confirm
```

`studio` prints `http://127.0.0.1:<port>/#/screen/<id>`; it serves only that project, only on
loopback, and stops with Ctrl+C. Saving in the browser writes the screen file in the bot's
repository; `git diff` shows it. Studio drafts live in the browser's local storage, never in
the repository.

## Without a reachable port

```powershell
py -3 studio/bot-ui.py export-snapshot --project ..\my-bot\bot-ui --output studio.html
# open studio.html, edit texts and rules, simulate both branches, "Export patch"
py -3 studio/bot-ui.py apply-patch --project ..\my-bot\bot-ui --patch-file bot-ui-patch-demo-shop-1a2b3c4d.json
```

The artifact is one self-contained HTML file (no network, no paths, no widget sources). The
patch is pending until `apply-patch` reports `written`; a patch exported from an older
revision is refused with `REVISION_CONFLICT` (exit 3): export a fresh snapshot
(`export-snapshot --format json`, then "Load snapshot JSON" in the artifact) and redo the edit.

## CLI

| Command | What it does |
| --- | --- |
| `init --project P [--template checkout]` | builds the project in a temp folder next to P, validates, then moves it into place; never overwrites |
| `list`, `show <id>` | screens; one screen by exact ID with file, incoming/outgoing links and rendering per locale |
| `validate` | every diagnostic with code, file and JSON pointer |
| `set <id> <pointer> <value> --expected-revision R`, `patch <id> --patch-file F`, `apply-patch --patch-file F` | the one write path; `--dry-run`, `--rebase` |
| `simulate --scenario S \| --all [--context f=v] [--locale l]` | replays fixtures, prints the trace (`simulated`) |
| `render <id>` | the Bot API request of a screen, structurally checked (`static`) |
| `build [--output D]` | widget builds per language + sendWidget payloads (default `<project>/.bot-ui/build`) |
| `studio`, `export-snapshot` | the two editors |
| `inventory --source <bot>` | read-only inventory of an existing aiogram bot: commands, callbacks, buttons, texts, proposed screens |

`--json` gives a stable object on stdout; messages for people go to stderr. Exit codes: 0 ok,
1 validation or scenario failure, 2 usage, 3 revision conflict, 4 refused or I/O. In Git Bash
set `MSYS_NO_PATHCONV=1` so `/message/text/ru` is not turned into a Windows path.

## Adapters

`adapters/aiogram_adapter.py` (aiogram 3.31.0) and `adapters/raw_adapter.py` (tgkit, no SDK)
share `bot_ui/runtime.py`: update -> engine event -> effects -> Bot API requests through an
injected transport. The project is re-read when its revision changes, so a Studio save
reaches the next update without a restart. Replay without network:

```powershell
py -3 studio/adapters/demo_bot.py --project ..\my-bot\bot-ui --replay studio/fixtures/updates/checkout.json
```

A live run needs a separate, approved task: a test bot, `BOT_TOKEN` in the environment outside
the repository, `demo_bot.py --live`, and a fresh check of the target clients. Messages sent
earlier keep their own life cycle: a new screen text applies to new sends and edits; an old
keyboard whose action was removed is answered as stale.

## What each surface does (22.11.2026)

| Scenario | CLI | Studio (localhost) | Artifact | Adapter |
| --- | --- | --- | --- | --- |
| Screens, map, links | list/show | list, map, inspector | list, map | reads |
| Edit text, labels, keyboard, actions, targets, rule | set/patch | edit + save | text + rule, export patch | renders |
| Create a screen / action | patch `create` | yes | no | - |
| Simulate (`/start`, Back, error + retry, loading, input, event, stale, fallback) | simulate | yes (TS engine, parity-tested) | yes | same engine, live |
| Widgets: build, sizes, mock preview, export | build | yes | no | sendWidget |
| Regular HTML / plain | edit, render | edit, safe preview | edit, safe preview | sendMessage / editMessageText |
| MarkdownV2 | render | read-only | read-only | render |
| Rich Messages, entities, media | kept, read-only | read-only with reason | read-only | not rendered (fallback text) |
| Streaming answer with Stop | not in v1 | not in v1 | not in v1 | not in v1 |
| Import an existing bot | inventory (aiogram, read-only) | - | - | - |

Levels: `static` (structure and limits checked offline), `simulated` (engine and test
transport), `live` (only after a separately approved run against Telegram; none so far).
