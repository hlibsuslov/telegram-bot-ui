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

For R80–R87 transcripts: `python skills/telegram-bot-ui/examples/python/recipes/r80_87_product_journeys.py --write-payload`.
