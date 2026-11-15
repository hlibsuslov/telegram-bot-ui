# Agent hosts: how each one finds and loads this skill

This note drives the adapters in `adapters/`, the subagents in `agents/`, the plugin
manifests in `.claude-plugin/` and `scripts/install.py`. Every claim below was checked
against the host's official documentation on **2026-11-15**; the source URL is given per
host. Anything the docs did not state is marked **unverified** and the tooling does not
depend on it.

Summary: every target host except Cline now reads Agent Skills (`SKILL.md` folders)
natively. `.agents/skills/` is the shared project location for Codex, Cursor, Gemini CLI /
Antigravity, Copilot and Devin; Claude Code uses `.claude/skills/`. Rule and instruction
files (Cursor rules, `AGENTS.md`, `GEMINI.md`, Copilot instructions) are therefore shipped
as **optional pointers** for setups where the skill is not loaded, not as a second copy
of the skill.

## At a glance

| Host | Native skills | Project skill path | User skill path | Explicit call | Subagents | Hooks | MCP |
|---|---|---|---|---|---|---|---|
| Claude Code | yes | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` | `/telegram-bot-ui` | yes (`.claude/agents/*.md`) | yes | yes |
| Claude Code plugin | yes | — | via `/plugin install` | `/telegram-bot-ui:telegram-bot-ui` | plugin `agents` | yes | yes |
| Codex CLI | yes | `.agents/skills/<name>/` (cwd up to repo root) | `~/.agents/skills/<name>/` | `$telegram-bot-ui`, `/skills` | yes (`.codex/agents/*.toml`) | not checked | yes (unverified details) |
| Cursor | yes | `.agents/skills/`, `.cursor/skills/` (+ `.claude/skills/`, `.codex/skills/` compat) | `~/.agents/skills/`, `~/.cursor/skills/` | `/` menu | not checked | not checked | not checked |
| Gemini CLI | yes | `.agents/skills/`, `.gemini/skills/` | `~/.agents/skills/`, `~/.gemini/skills/` | `activate_skill` (consent prompt) | preview (extensions) | not checked | yes (extensions) |
| Antigravity CLI / app | yes | `.agents/skills/` (+ legacy `.agent/skills/`) | `~/.gemini/config/skills/`; CLI also `~/.gemini/skills/` | `/<skill-name>` | unverified | not checked | not checked |
| GitHub Copilot | yes | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `~/.copilot/skills/`, `~/.agents/skills/` | — (not documented) | not checked | not checked | not checked |
| Devin Desktop / CLI (formerly Windsurf) | yes | `.devin/skills/`, `.agents/skills/`, legacy `.windsurf/skills/` | `~/.config/devin/skills/`, `~/.agents/skills/` | `/<plugin>:<skill>` for plugin skills | not checked | not checked | not checked |
| Cline | **not documented** | — | — | — | — | — | — |
| API-driven custom agent | no file access by default | — | — | — | — | — | — |

## Claude Code

Sources (checked 2026-11-15): <https://code.claude.com/docs/en/skills>,
<https://code.claude.com/docs/en/sub-agents>,
<https://code.claude.com/docs/en/plugins-reference>,
<https://code.claude.com/docs/en/plugin-marketplaces>,
<https://code.claude.com/docs/en/plugins/marketplace-reference.md>. Local CLI 2.1.321.

**Skills.** Personal `~/.claude/skills/<skill-name>/SKILL.md`, project
`.claude/skills/<skill-name>/SKILL.md` (start directory and every parent up to the repo
root; nested `.claude/skills/` in subdirectories load when Claude first touches a file
there), `--add-dir` directories, enterprise managed directory, plugin
`<plugin>/skills/<name>/SKILL.md`. Precedence: enterprise > personal > project; plugin
skills are namespaced (`/plugin-name:skill-name`).

Frontmatter (all optional, `description` recommended): `name`, `description`,
`when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`,
`user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`
(`fork`), `agent`, `background`, `hooks`, `paths`, `shell`, plus spec fields `metadata`,
`license`, `compatibility` (≤ 500 chars). Unknown fields are ignored. Outside Claude Code
(claude.ai upload, Skills API) only `name`, `description`, `license`, `compatibility`,
`metadata`, `allowed-tools` are accepted — **other fields are a hard upload error**, so
the canonical `SKILL.md` keeps to `name`, `description`, `license` and `metadata`, with
`description` as one double-quoted line (some skill directories do not unfold `>-`).

Limits: `description` + `when_to_use` truncated at **1,536 characters** in the listing;
`SKILL.md` recommended under 500 lines. Invocation: automatic by description, or
`/skill-name` at the start of a message. Bundled scripts are "executed, not loaded";
`${CLAUDE_SKILL_DIR}` resolves to the skill folder in the body and in `allowed-tools`.

**Subagents.** Markdown with YAML frontmatter; the body is the system prompt. Locations
by priority: managed settings > `--agents` flag > `.claude/agents/` (project, recursive)
> `~/.claude/agents/` (user, recursive) > plugin `agents/`. Required: `name` (≤ 256
chars, no leading `-`, no `:`) and `description`. Optional fields used here: `tools`
(comma-separated string or YAML list; omitted = inherit all), `model`
(`sonnet|opus|haiku|fable|inherit|<id>`), `color`. Other documented fields:
`disallowedTools`, `permissionMode`, `skills` (preload full skill content), `hooks`,
`mcpServers`, `memory`, `maxTurns`, `background`, `effort`, `isolation`, … For **plugin**
subagents `permissionMode`, `hooks` and `mcpServers` are ignored. Without `skills`, a
subagent can still invoke skills through the `Skill` tool if `Skill` is in its tools.
We do not use `skills:` preload because the skill's registered name differs between a
plain install (`telegram-bot-ui`) and a plugin install (`telegram-bot-ui:telegram-bot-ui`)
and the docs do not say how preload resolves a namespaced name (**unverified**).

**Plugins.** Manifest `.claude-plugin/plugin.json` (optional; only `name` required).
Component paths must start with `./` and stay inside the plugin root. `skills` adds to
the default `skills/` scan; `agents` **replaces** the default `agents/` scan and accepts
`.md` files only; subfolders of the default `agents/` scan become part of the agent name.
"A plugin with `SKILL.md` at its root, no `skills/`, and no `skills` key loads as a single
skill." Setting `version` pins users to it until it changes. Names starting with
`claude-`/`anthropic-` are reserved. A root `CLAUDE.md` is not loaded and triggers a
validator warning.

**Marketplace.** `.claude-plugin/marketplace.json` with required `name`, `owner.name`,
`plugins[]` (`name`, `source`). A relative source must start with `./`; `"./"`/`"."` is
the marketplace root itself. Entry name should equal the manifest name. Install:
`claude plugin marketplace add owner/repo` then `claude plugin install
<plugin>@<marketplace>` (or `/plugin marketplace add`, `/plugin install` in a session).
Authoritative check: `claude plugin validate <dir>` (`--strict` turns warnings into
failures).

**What this repo ships:** the repository root is both the marketplace and the plugin
(`source: "./"`); the default `skills/` scan finds the single skill in
`skills/telegram-bot-ui/` (no `skills` key, no root `SKILL.md`); `agents` lists the five
files in `agents/claude/` explicitly so that the Codex TOML files are never scanned.
Validated locally with `claude plugin validate . --strict`; an install into a scratch
`CLAUDE_CONFIG_DIR` reports `Skills (1) telegram-bot-ui`.

**Agent Plugins and Copilot CLI** (checked 2026-11-15: <https://agent-plugins.org/specification>,
<https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference>).
The root `plugin.json` is an Agent Plugins 1.0.0 manifest: closed schema (`$schema`, `name`,
`version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`,
`extensions`), skills only from `skills/<name>/SKILL.md`, no component paths. In Copilot CLI
a root Agent Plugins `plugin.json` takes precedence over `.claude-plugin/plugin.json`; the
skill is still found in `skills/`, but Copilot agents would have to live in
`com.github.copilot/agents/`, which this repo does not ship (**unverified** whether Copilot
loaded our `.md` subagents before). No official validator exists; `scripts/validate_skill.py`
checks the schema rules.

## OpenAI Codex CLI

Sources (checked 2026-11-15; old `developers.openai.com/codex/*` URLs redirect here):
<https://learn.chatgpt.com/docs/build-skills>,
<https://learn.chatgpt.com/docs/agent-configuration/agents-md>,
<https://learn.chatgpt.com/docs/agent-configuration/subagents>. Local CLI 0.167.0.

**Skills.** Repo: `.agents/skills` in every directory from cwd up to the repo root. User:
`$HOME/.agents/skills`. Admin: `/etc/codex/skills`. System: bundled (`skill-creator`,
`skill-installer`). Symlinked skill folders are followed. Required frontmatter: `name`,
`description` (no documented length limit). The initial skills list uses at most 2 % of
the context window (8,000 chars if unknown, configurable via `skills.max_context_tokens`);
descriptions are shortened first, skills may be omitted with a warning. Explicit call:
`$telegram-bot-ui` or `/skills`; implicit selection by description. `scripts/` is allowed;
**how Codex runs them is not documented** (in practice the agent runs them through its
shell tool under the session sandbox — unverified).

**`agents/openai.yaml`** (inside the skill folder, optional): `interface.display_name`,
`interface.short_description`, `interface.icon_small`, `interface.icon_large`,
`interface.brand_color`, `interface.default_prompt`; `policy.allow_implicit_invocation`
(default `true`); `dependencies.tools[]` (`type`, `value`, `description`, `transport`,
`url`). Generated here from `SKILL.md` + `adapters/routing.json`.

**`AGENTS.md`.** Global: `~/.codex/AGENTS.override.md` else `AGENTS.md` (or under
`CODEX_HOME`). Project: from the git root down to cwd, per directory
`AGENTS.override.md`, then `AGENTS.md`, then `project_doc_fallback_filenames`; one file
per directory; concatenated root-first; combined size capped by `project_doc_max_bytes`
(default **32 KiB**). The snippet we ship is a few hundred bytes for that reason.

**Custom agents (roles).** Standalone TOML, one agent per file, in `~/.codex/agents/`
(personal) or `.codex/agents/` (project). Required: `name`, `description`,
`developer_instructions`; optional `model`, `model_reasoning_effort`,
`model_reasoning_summary`, `model_verbosity`, `features.*` capability reductions, and
`skills.config` / `skills.bundled.enabled` / `skills.include_instructions`. Sandbox and
approval settings are **not** overridable from the agent file. Invoked by naming the
agent in a prompt ("Have telegram_bot_reviewer review this diff"). We generate the five
roles as TOML from the same source as the Claude subagents and set only the three
required fields.

Codex plugins (<https://developers.openai.com/codex/plugins/build>, checked 2026-11-15): the
portable root `plugin.json` plus the compatibility manifest `.codex-plugin/plugin.json`
(`skills: "./skills/"`, `interface` for the directory listing), which Codex reads while the
root manifest has no `extensions.com.openai`. Codex 0.167 reads the marketplace from
`.claude-plugin/marketplace.json`; in a scratch `CODEX_HOME`, `codex plugin marketplace add
<repo>` and `codex plugin add telegram-bot-ui@telegram-bot-ui` install it and the skill shows
up as `telegram-bot-ui:telegram-bot-ui`. There is no `codex plugin validate`.

## Cursor

Sources (checked 2026-11-15): <https://cursor.com/docs/context/skills>,
<https://cursor.com/docs/context/rules>.

Skills: project `.agents/skills/`, `.cursor/skills/`; user `~/.agents/skills/`,
`~/.cursor/skills/`; compatibility roots `.claude/skills/`, `.codex/skills/`,
`~/.claude/skills/`, `~/.codex/skills/`; nested skill roots apply to files under their
directory. Frontmatter: `name` (must match the folder), `description`, `paths`,
`disable-model-invocation`, `icon`, `color`, `metadata`. Automatic or `/` invocation;
scripts in `scripts/` are run by the agent.

Rules: project rules are **`.mdc`** files in `.cursor/rules/` (plain `.md` there is
ignored). Frontmatter `description`, `globs` (comma-separated), `alwaysApply`. A rule
with only `description` is "Apply Intelligently" (agent-requested). Keep rules under
500 lines. User rules live in the UI only (no file path). `AGENTS.md` in the root and
subdirectories is read. We ship `adapters/cursor/telegram-bot-ui.mdc` as an
agent-requested pointer rule for projects that prefer rules over skills.

## Gemini CLI and Antigravity

Sources (checked 2026-11-15): <https://geminicli.com/docs/cli/skills/>,
<https://geminicli.com/docs/cli/gemini-md/>,
<https://geminicli.com/docs/extensions/reference/>,
<https://antigravity.google/docs/skills.md>. Local Gemini CLI 0.40.1.

The Gemini CLI docs state that for unpaid-tier and Google One users Gemini CLI "was
replaced by Antigravity CLI on June 18th, 2026". Both read `.agents/skills/`, so one
project install covers both.

Gemini CLI skills (lowest → highest precedence): built-in, extension `skills/`, user
`~/.gemini/skills/` or `~/.agents/skills/`, workspace `.gemini/skills/` or
`.agents/skills/` (`.agents` wins within a tier). Name + description are injected at
session start; the model calls `activate_skill`, the user approves a consent prompt, then
the body is added and the skill folder becomes readable. Install: `gemini skills install
<git-url|dir> [--scope user|workspace]`. Script execution is not described.

Antigravity: workspace `.agents/skills/` (and parents up to the repo root); global
`~/.gemini/config/skills/`; the CLI also reads `~/.gemini/skills/` and
`~/.gemini/antigravity-cli/skills/`. `description` required, `name` optional. Skills
become slash commands in the CLI; helper scripts may be executed.

Context files: `~/.gemini/GEMINI.md` global, then workspace directories and parents, then
just-in-time scans; all concatenated and sent with every prompt. `@file.md` imports;
`context.fileName` can add `AGENTS.md`. We ship `adapters/gemini/GEMINI.md` as an optional
pointer block. Extensions (`gemini-extension.json`, required `name`, `version`; optional
`contextFileName`, `mcpServers`, `excludeTools`, `settings`, …; skills in `skills/`) are
**not shipped**: an extension must hold the skill under `skills/<name>/`, which would
duplicate the repository layout; `gemini skills install` covers the need.

## GitHub Copilot

Sources (checked 2026-11-15):
<https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>,
<https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions>.

Skills: project `.github/skills/`, `.claude/skills/`, `.agents/skills/`; personal
`~/.copilot/skills/`, `~/.agents/skills/` (cloud sandbox: `.copilot/skills` in the
dotfiles repo). Supported on the Copilot app, Copilot CLI, cloud agent, code review and
agent mode in VS Code / Visual Studio / JetBrains (version dependent). Frontmatter and
script execution are not specified on that page.

Instructions: `.github/copilot-instructions.md` (repository-wide), path-specific
`.github/instructions/*.instructions.md` with `applyTo` globs and optional `excludeAgent`
(`code-review` | `cloud-agent`); `AGENTS.md` anywhere (nearest wins) or a single root
`CLAUDE.md`/`GEMINI.md`. No platform size limit is stated. We ship
`adapters/copilot/copilot-instructions.md` as a pointer block. Copilot CLI was not
installed here, so nothing was executed against it.

## Devin Desktop / Devin CLI (formerly Windsurf)

Source (checked 2026-11-15; `docs.windsurf.com` redirects here):
<https://docs.devin.ai/desktop/cascade/memories>.

Rules: `.devin/rules/*.md`, `.devin/global_rules.md`, `~/.devin/rules/*.md`; legacy
`.windsurf/rules/*.md`, `.windsurf/global_rules.md`, `.windsurfrules` still imported.
Frontmatter `trigger` = `always_on | glob | model_decision | manual`, plus `globs`.
`AGENTS.md`, `AGENTS.local.md`, `AGENT.md` read as always-on. Skills: `.devin/skills/`,
`.agents/skills/`, legacy `.windsurf/skills/`; global `~/.config/devin/skills/`,
`~/.agents/skills/`. Covered by the `.agents/skills` install; no rule file is shipped
(the `description` field for `model_decision` is referenced but not shown as
frontmatter — **unverified**).

## Cline

Source (checked 2026-11-15): <https://docs.cline.bot/features/cline-rules>.

Workspace rules in `.clinerules/` or `.cline/rules/` (directories); global
`~/Documents/Cline/Rules` (Windows `Documents\Cline\Rules`), `~/.cline/rules`,
`~/Cline/Rules`; reads `AGENTS.md` and `~/.agents/AGENTS.md`; detects `.cursorrules` and
`.windsurfrules`. Frontmatter `paths` (array of globs; none = always on). The page does
**not** mention Agent Skills, so Cline is served by the `AGENTS.md` snippet (or the same
text as a `.clinerules/telegram-bot-ui.md` file). No dedicated adapter is generated.

## API-driven custom agents

An agent built on a model API gets only a system prompt and whatever tools its author
wires up. Two options:

1. **No file tools:** use `adapters/portable/telegram-bot-ui.prompt.md` as (part of) the
   system prompt. It carries the core rules and lists every section that was left out.
2. **File-read tool available:** give the agent `adapters/llms.txt` and let it fetch the
   linked documents on demand — the same progressive disclosure the native hosts use.

## Generic `AGENTS.md` readers

`AGENTS.md` is plain Markdown with no frontmatter; Codex, Cursor, Copilot, Devin and
Cline read it. `adapters/agents-md/AGENTS.snippet.md` is a short block that points at the
installed skill; `scripts/install.py --with-instructions` inserts it between
`<!-- telegram-bot-ui:begin -->` / `<!-- telegram-bot-ui:end -->` markers and removes it on
`--uninstall`.

## What was executed vs. read

- Executed locally: `claude plugin validate` on this repository (see `tests/` and the
  README evidence section for the result), `gemini --version`, `codex --version`.
- Read only (docs): everything else. Copilot CLI, Cursor, Antigravity, Devin and Cline
  were not installed on the check machine; their behaviour is as documented, not observed.
