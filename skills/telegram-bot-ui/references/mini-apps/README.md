# Mini Apps: start here

This folder is the skill's branch for **Telegram Mini Apps** (web apps opened inside Telegram through
`window.Telegram.WebApp`): deciding when to build one, launching it, the client API, a design system that
looks native in both themes and on both platforms, components and screens, anti-slop rules, `initData`
security, performance and testing. Verified against **Bot API 10.5 (2026-11-22)** and
https://core.telegram.org/bots/webapps on **2026-11-23**; the newest Mini App change is Bot API 10.1, the
highest version gate in `telegram-web-app.js` is `9.6`.

The bot side (launch buttons, `web_app_data`, `answerWebAppQuery`, prepared messages and buttons) stays in
[../mini-apps-bridge.md](../mini-apps-bridge.md). Payments from a Mini App: [../payments-and-stars.md](../payments-and-stars.md).
TON wallet: [../wallet-and-ton.md](../wallet-and-ton.md). Widgets inside a message: [../widgets.md](../widgets.md).

## Route by task

| The task | Read | Then |
|---|---|---|
| "Should this be a Mini App?" | [decide.md](decide.md) | recipe 90 |
| Open a Mini App from a button, link, menu or profile; `startapp`; hosting | [launch-and-lifecycle.md](launch-and-lifecycle.md) | recipe 91 |
| "Does `Telegram.WebApp` have X, since which version?" | [webapp-api.md](webapp-api.md), `scripts/webapp_lookup.py` | — |
| Verify `initData`, sessions, what to trust | [security.md](security.md) | recipe 92 |
| Make it look like Telegram in light and dark, iOS and Android | [telegram-design-guidelines.md](telegram-design-guidelines.md), [design-sources.md](design-sources.md), `design-system.md` | `examples/mini-apps/_kit` |
| Build a screen: shop, form, dashboard, settings, game, editor | `screen-patterns.md`, `components.md` | recipes 93-99 |
| "It looks generated / web-like / off" | `anti-slop.md`, `scripts/miniapp_lint.py` | — |
| Speed, weak Android, how to test without a phone | `performance-and-testing.md`, `scripts/preview_miniapp.py` | — |

## Reading order for a new Mini App

1. [decide.md](decide.md): is it a Mini App, which entry point, what the bot says before and after.
2. [launch-and-lifecycle.md](launch-and-lifecycle.md): start sequence, `ready()`, visibility, hosting.
3. [security.md](security.md): the server contract, before any API route exists.
4. [telegram-design-guidelines.md](telegram-design-guidelines.md) G1-G7, then the design system and kit.
5. The closest screen pattern and recipe; then build, lint, preview, test on a device.

## Sources and labels

| Label | Meaning |
|---|---|
| **[Official]** | core.telegram.org/bots/webapps, including its Design Guidelines |
| **[API]** | the Bot API page and changelog |
| **[Heuristic]** | this skill's decision; can change with evidence |

Figma sources read for the design files (2026-11-23): Apple iOS and iPadOS 27 and the Telegram Mini Apps UI
Kit (Community). Not read: the Telegram UI community kit, Appetite UI (paid, licence forbids
redistribution). [design-sources.md](design-sources.md) says what was taken from each.

## Offline data and tools

| File | What |
|---|---|
| `data/mini-apps/webapp-catalog.json` | every `Telegram.WebApp` member with version, evidence and anchor URL |
| `data/mini-apps/theme-params.json` | `themeParams` key → CSS variable → role → fallbacks |
| `data/mini-apps/design-sources.json` | iOS 27 colours, type scale, glass, sizes; mapping to theme roles |
| `scripts/webapp_lookup.py` | `show`, `search`, `since`, `gates`, `theme`, `sync` over the catalog |

Refresh after a Telegram release: `py -3 scripts/webapp_lookup.py sync --fetch` prints the diff;
add `--write` to update the catalog, then re-run the tests.
