# Contributing reusable examples

Search first (`python skills/telegram-bot-ui/scripts/example_library.py --query "..."`) and read
[the reuse contract](skills/telegram-bot-ui/references/example-library.md). A distinct state, audience, rights or
failure invariant justifies a new recipe; a new industry name or button color does not.

1. Take an unused recipe ID in `skills/telegram-bot-ui/recipes/manifest.json` and write `skills/telegram-bot-ui/recipes/NN-*.md` in the
   ten-point format of the existing recipes (request, reuse, context, screens, code, state,
   outcome, failure paths, checks, sources).
2. Reuse the existing transport, callback, keyboard and i18n helpers. Code runs offline
   with synthetic data and an injected clock; no tokens or live network by default.
3. Capture payloads from that code, never hand-written JSON, and test the distinctive
   failure path (cancellation race, foreign user, stale revision, capacity, replay).
4. Add the manifest row (`registry: []` unless it covers a real changelog item), a row in
   `skills/telegram-bot-ui/recipes/use-cases.json`, a link in `skills/telegram-bot-ui/recipes/README.md` and a case in `evals/evals.json`.
   Route new capabilities through `skills/telegram-bot-ui/commands/index.json` (a command's `refs` and
   playbook) and roles through `adapters/routing.json`; never hand-edit generated adapters, the command
   table in SKILL.md, `references/INDEX.md` or `docs/agents/`.
5. Run:

   ```bash
   python scripts/build_adapters.py
   python scripts/run_checks.py
   ```

   `run_checks.py` includes `scripts/api_coverage.py --check`: coverage of Bot API methods, types and
   `Telegram.WebApp` members may only grow. When your change covers something new, the check asks you to
   run `python scripts/api_coverage.py --update-floor` and commit the floor; `--report` lists what is missing.

## Agent notes and per-method examples

The card `tgui.py lookup card <Symbol>` merges the catalog with a curated note. Notes live in
`skills/telegram-bot-ui/data/bot-api/agent-notes/<domain>.json`, one file per domain; the shape and every
rule are in `skills/telegram-bot-ui/scripts/api_notes.py`.

- **Facts come from the catalog or Telegram.** Check each one with `tgui.py lookup show <Symbol>` (the
  official text) or core.telegram.org. Never write a parameter, limit or behaviour neither confirms.
- **Every pitfall has a source label:** `API` (catalog text; `cite` quotes the symbol or field),
  `Official` (another core.telegram.org page; `cite` is the URL), `Observed` (client and date),
  `Heuristic` (the skill's own design advice), `Unverified`, `Third-party` (name the library).
- **Short:** `purpose` is one line; two or three `use_when` / `avoid_when` items; the pitfalls an agent
  actually hits. A card over 1.5 KB fails the check.
- **Types are named, not described:** list the types an agent meets with a method in its `related`. A
  union in `related` also covers its members. Give a type its own note only when it needs a pitfall.
- **`refs`** point at an existing heading (`references/<file>.md#anchor`); **`example`** only at a file
  that really makes the call.
- **Examples are code.** Per-method requests go in `examples/python/recipes/api_<domain>.py` (one
  function per method, synthetic ids, `STEP_CONTEXT` for calls limited by chat type or rights; destructive
  calls are recorded requests, never sent), written to `examples/payloads/api-<domain>.json` by
  `python skills/telegram-bot-ui/examples/python/export_payloads.py --only api-<domain>`.
- Then: `python skills/telegram-bot-ui/scripts/api_notes.py check`, `python scripts/api_coverage.py --update-floor`,
  `python scripts/run_checks.py`.

For R80–R87 transcripts: `python skills/telegram-bot-ui/examples/python/recipes/r80_87_product_journeys.py --write-payload`.
