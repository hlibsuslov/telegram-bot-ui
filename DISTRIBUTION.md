# Distribution registry

Where Telegram Bot UI is listed or submitted, and what happens next. Last full check: **2026-11-25**.
A row is `PUBLISHED` only with a public page or merged entry; unverified submissions stay `SUBMITTED`.

Statuses: PUBLISHED, VERIFIED, INDEXED, SUBMITTED, PR_OPEN, UNDER_REVIEW, ACTION_REQUIRED, BLOCKED, REJECTED, NOT_ELIGIBLE, NOT_SUBMITTED.

## Source of truth for descriptions

- Short (<=80): `Agent Skill that designs the whole UI of a Telegram bot`
- Medium (<=160): `Agent Skill for Claude Code, Codex, Cursor, Gemini CLI, Copilot: Telegram bot screens, keyboards, streaming replies, widgets, Mini Apps, Bot API lookup.`
- Long description and features: the top of [README.md](README.md). Manifest text comes from `adapters/routing.json` via `scripts/build_adapters.py`; edit there, never in the generated manifests.
- Site: https://telegram-bot-ui.hlixli.com

## Registry

| Platform | Category | Priority | Status | Listing URL | Submission URL | Last Checked | Next Action |
|---|---|---|---|---|---|---|---|
| Skills.sh | Skill registry | S | INDEXED | https://skills.sh/hlibsuslov/telegram-bot-ui | auto (install telemetry) | 2026-11-25 | none |
| awesome-copilot (external plugins) | Catalog | A | PUBLISHED | https://github.com/github/awesome-copilot/pull/6510 | https://github.com/github/awesome-copilot/issues/6435 | 2026-11-25 | none |
| awesome-codex-plugins (hashgraph-online) | Catalog | A | PUBLISHED | https://github.com/hashgraph-online/awesome-codex-plugins/tree/main/plugins/hlibsuslov/telegram-bot-ui | n/a | 2026-11-25 | none |
| Awesome Gemini CLI (Piebald-AI) | Awesome list | A | PUBLISHED | https://github.com/Piebald-AI/awesome-gemini-cli | n/a | 2026-11-25 | none |
| Awesome Agentic Atlas | Catalog | B | PUBLISHED | https://github.com/crazy54/awesome-agentic-atlas | n/a | 2026-11-25 | none |
| Awesome AI Telegram Bots | Awesome list | B | PUBLISHED | https://github.com/zhuyansen/awesome-ai-telegram-bots | n/a | 2026-11-25 | none |
| kalanakt/awesome-telegram | Awesome list | B | PUBLISHED | https://github.com/kalanakt/awesome-telegram | n/a | 2026-11-25 | none |
| askill.sh | Skill registry | A | INDEXED | https://askill.sh (indexed 2026-11-25) | https://askill.sh/submit | 2026-11-25 | none |
| agentskill.sh | Skill registry | S | SUBMITTED | not confirmed | https://agentskill.sh/submit | 2026-11-25 | Import page stayed on "Analyzing"; re-check the listing in a few days |
| heilcheng/awesome-agent-skills | Awesome list | A | PR_OPEN | n/a | https://github.com/heilcheng/awesome-agent-skills/pull/727 | 2026-11-25 | Fix anything the automated check reports |
| VoltAgent/awesome-agent-skills | Awesome list | A | PR_OPEN | n/a | https://github.com/VoltAgent/awesome-agent-skills/pull/1487 | 2026-11-25 | May be declined for adoption; revisit as usage grows |
| BehiSecc/awesome-claude-skills | Awesome list | A | PR_OPEN | n/a | https://github.com/BehiSecc/awesome-claude-skills/pull/1360 | 2026-11-25 | Waiting for maintainer |
| composio-community/awesome-codex-skills | Awesome list | A | PR_OPEN | n/a | https://github.com/composio-community/awesome-codex-skills/pull/435 | 2026-11-25 | Mergeable, waiting for maintainer |
| ebertti/awesome-telegram | Awesome list | A | PR_OPEN | n/a | https://github.com/ebertti/awesome-telegram/pull/459 | 2026-11-25 | Format check passed, waiting for maintainer |
| ComposioHQ/awesome-claude-skills | Awesome list | A | SUBMITTED | n/a | https://github.com/ComposioHQ/awesome-claude-skills/issues/2460 | 2026-11-25 | No reply since 2026-11-15; ask once after two more weeks |
| Gemini CLI extensions gallery | Extension catalog | S | SUBMITTED | not listed yet | topic `gemini-cli-extension` + root `gemini-extension.json` (both on main since 2026-11-25) | 2026-11-25 | Wait for the gallery crawler; re-check in a few days |
| awesome-claude-code (hesreallyhim) | Awesome list | A | ACTION_REQUIRED | n/a | https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml | 2026-11-25 | Rules: the recommendation must be filed by a human through the web form (not `gh`, not an agent) |
| travisvn/awesome-claude-skills | Awesome list | A | ACTION_REQUIRED | n/a | https://github.com/travisvn/awesome-claude-skills | 2026-11-25 | Rules close AI-assisted PRs; the owner may submit by hand |
| mcpmarket.com | Marketplace | A | ACTION_REQUIRED | not listed | https://mcpmarket.com/submit (type: Agent Skill) | 2026-11-25 | Form asks for an email; the owner supplies it. Free review path; a $29 fast listing is optional and not used |
| claudemarketplaces.com | Marketplace | A | ACTION_REQUIRED | unknown | https://claudemarketplaces.com/submit | 2026-11-25 | Needs "Sign in with GitHub" by the owner |
| OpenAI Plugin Directory | Plugin directory | S | ACTION_REQUIRED | not listed | https://developers.openai.com/plugins/deploy/submission | 2026-11-25 | Needs an organization account and publisher verification; the plugin ships `.codex-plugin/plugin.json` |
| Claude plugin directory (Anthropic) | Plugin directory | S | BLOCKED | not listed | https://claude.ai/directory/manage | 2026-11-25 | Directory accepts no scripts from unverified publishers. The documentation-only `claude-directory` branch already exists; the owner resubmits it with the original review message if not done yet |
| SkillsMP | Skill registry | S | NOT_SUBMITTED | unknown (site blocks bots) | auto-index from GitHub | 2026-11-25 | Check manually; the FAQ names the topic `claude-code-skill`, which the repo lacks |
| LobeHub Skills | Skill registry | S | NOT_SUBMITTED | unknown | no self-serve path found | 2026-11-25 | Check manually |
| claudemarketplace.net | Marketplace | A | NOT_SUBMITTED | unknown | https://claudemarketplace.net/submit | 2026-11-25 | Review by message; not sent |
| markdownregistry.com | Registry | A | NOT_SUBMITTED | not found | auto-index | 2026-11-25 | Re-check later |
| claude-plugins.dev, cursor.directory, aitmpl.com, buildwithclaude.com | Marketplaces | A | NOT_SUBMITTED | unknown | see each site | 2026-11-25 | Sites blocked automated reads (HTTP 402/429); aitmpl and buildwithclaude take PRs to component repos and need a format check |
| Smithery | MCP directory | A | NOT_ELIGIBLE | n/a | n/a | 2026-11-25 | This project is not an MCP server; the site now lists MCP servers only |
| skillsllm.com | Skill directory | B | NOT_ELIGIBLE | n/a | n/a | 2026-11-25 | Reported minimum of 100 stars |

## Rejections and requirements

- **Anthropic directory**: scripts and runnable examples are not accepted from unverified publishers. The full repository keeps its code; the `claude-directory` branch is a generated documentation-only edition (see README, "Two editions").
- **awesome-claude-code**: human-only web form; not met by agents.
- **travisvn/awesome-claude-skills**: PRs made with AI help are closed without comment.
- **VoltAgent**: asks for proven community usage; the PR may be declined.
