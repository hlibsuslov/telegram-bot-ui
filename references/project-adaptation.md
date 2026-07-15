# Project adaptation (investigate before you change)

This skill is project-agnostic. Before touching anything, build an accurate map
of how the target project produces and delivers messages. Never assume a specific
language, framework, or SDK.

## Step 1 — Read project instructions

`AGENTS.md`, `CLAUDE.md`, `README`, `CONTRIBUTING`, docs/. Note conventions,
existing formatter utilities, the required test/lint/typecheck commands, and any
"how we send messages" guidance.

## Step 2 — Detect stack and versions

Determine, with evidence from the repo (manifest/lockfiles, imports):

- Language(s) and framework.
- **Telegram SDK and its exact version** (e.g. `aiogram`, `python-telegram-bot`,
  `pyTelegramBotAPI`, `grammY`, `Telegraf`, `node-telegram-bot-api`,
  `Telegram.Bot`, `TelegramBots`, `go-telegram/bot`, or raw HTTP).
- The **Bot API version** that SDK version implements (from its changelog/release
  notes). This bounds which formatting features exist.
- Presence of any **raw HTTP** Bot API calls / adapters already in the codebase.

Manifest hints: `requirements*.txt` / `pyproject.toml` / `Pipfile`;
`package.json` + lockfile; `go.mod`; `pom.xml` / `build.gradle`; `*.csproj`;
`composer.json`; `Cargo.toml`.

## Step 3 — Find every message touchpoint

Search for where messages are **generated, formatted, sent, and edited**. Useful
patterns (adapt to the SDK):

- Send/edit methods: `sendMessage`, `sendPhoto`, `sendMediaGroup`,
  `editMessageText`, `answerInlineQuery`, `sendRichMessage`,
  `sendRichMessageDraft`, `answer(`, `reply(`, `.send_message`.
- Parse modes: `parse_mode`, `ParseMode`, `HTML`, `MarkdownV2`, `Markdown`.
- Entities: `entities`, `MessageEntity`, `offset`, `length`.
- Rich: `InputRichMessage`, `InputRichBlock`, `rich_message`, `markdown=`,
  `blocks=`, `draft_id`.
- Formatter utilities: files/functions named `format`, `escape`, `render`,
  `markup`, `template`, `md`, `html`.
- Templates & localization: i18n catalogs, `.ftl`/`.po`/`.json`/`.yaml`
  locale files, `gettext`, `_()`, `t(`, Fluent, ICU.
- AI-generated content and **streaming** loops (token/chunk handlers, partial
  edits).
- Inline mode, Web Apps, and business-connection code paths, if present.

## Step 4 — Classify messages

For each touchpoint, label it: notification / interactive prompt / document /
AI answer / media post / inline result. This drives format choice
(`format-selection.md`).

## Step 5 — Capture the current state

Record: which parse modes are used, whether escaping exists and is per-format or
one universal helper, where limits/magic numbers live, how splitting is done, how
keyboards/topics/reply context are attached, and where tests live.

## Step 6 — Identify real defects only

Examples of real defects: `can't parse entities` errors, user input breaking
MarkdownV2, HTML shown as literal text, code blocks split mid-fence, lost
keyboards, corrupted localized templates, oversized payloads. Do not "improve"
working code that isn't in scope.

## Step 7 — Produce a short message-flow map

Before implementing, output a concise map: entry points → formatter(s) →
transport → message classes → detected defects → proposed minimal change. Get
this right before writing code.

## What to build only when justified

Create these **only** if the audit proves the need — never by default:

- a custom AST or intermediate representation;
- a universal renderer;
- a separate formatting library;
- a CMS or visual editor;
- a complex message builder;
- a new transport layer.

Prefer extending the project's existing utilities in its existing style.

## SDK capability gap

If the installed SDK lacks a needed Rich Messages type/method, follow the
escalation in `sdk-compatibility.md` (check newer SDK → review breaking changes →
safe upgrade → else isolated typed Bot API adapter, never raw HTTP in business
logic, with a removal plan).
