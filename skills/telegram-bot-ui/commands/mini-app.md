# mini-app: a Mini App, from the decision to the release

**When:** build or restyle a Mini App, `Telegram.WebApp`, `initData`, where the photo, title
and price go, a Figma file to build from.

## Read

- Start: `references/mini-apps/README.md` "Route by task", then
  `references/mini-apps/orchestration.md` §1 (what to load, by request).
- Decide first: `references/mini-apps/decide.md` (Mini App, widget or keyboard).
- Building (all in `references/mini-apps/`): `launch-and-lifecycle.md`, `webapp-api.md`,
  `design-system.md`, `components.md`, `layout-rules.md`, `screen-patterns.md`,
  `native-anatomy.md`, `telegram-design-guidelines.md`, `design-sources.md`, `figma-workflow.md`,
  `forms-and-data.md`, `haptics-and-device.md`, `accessibility-and-language.md`,
  `telegram-elements.md`, `materials-and-trends.md`, `anti-slop.md`.
- Reworking an existing app: `references/mini-apps/rework.md` (`tgui.py miniapp rework plan`).
- Money `references/mini-apps/payments.md`; security `references/mini-apps/security.md`;
  testing `references/mini-apps/performance-and-testing.md`; the bot side
  `references/mini-apps-bridge.md`.

## Steps

1. Decide and say why (`decide.md`). Recipes 90-99 are the starting points.
2. Gate every `Telegram.WebApp` call by version: `tgui.py webapp show <Name>`, `webapp gates`.
3. Layout and style: `tgui.py miniapp layout review`, `tgui.py miniapp style ...`.
4. Validate `initData` on the server before trusting any user field.
5. `tgui.py miniapp lint <app>` and `tgui.py miniapp preview <app>` (a mock client).

## Without scripts

Look names up in the Telegram.WebApp catalog under `data/` and apply the lint rules from
`performance-and-testing.md` by hand.

## Done

The floor rules plus version gates, a server-side `initData` check, lint clean, evidence level.

## Next

The bot side (`improve` the launch button and messages) or `build` for payments in the app.
