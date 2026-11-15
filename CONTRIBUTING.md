# Contributing reusable examples

Search first (`python scripts/example_library.py --query "..."`) and read
[the reuse contract](references/example-library.md). A distinct state, audience, rights or
failure invariant justifies a new recipe; a new industry name or button color does not.

1. Take an unused recipe ID in `recipes/manifest.json` and write `recipes/NN-*.md` in the
   ten-point format of the existing recipes (request, reuse, context, screens, code, state,
   outcome, failure paths, checks, sources).
2. Reuse the existing transport, callback, keyboard and i18n helpers. Code runs offline
   with synthetic data and an injected clock; no tokens or live network by default.
3. Capture payloads from that code, never hand-written JSON, and test the distinctive
   failure path (cancellation race, foreign user, stale revision, capacity, replay).
4. Add the manifest row (`registry: []` unless it covers a real changelog item), a row in
   `recipes/use-cases.json`, a link in `recipes/README.md` and a case in `evals/evals.json`.
   Route new capabilities through `adapters/routing.json`; never hand-edit generated adapters.
5. Run:

   ```bash
   python scripts/build_adapters.py
   python scripts/run_checks.py
   ```

For R80–R87 transcripts: `python examples/python/recipes/r80_87_product_journeys.py --write-payload`.
