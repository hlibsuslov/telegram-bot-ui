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
| "Create a Mini App" or "improve / restyle / fix this one": the whole order of work | [orchestration.md](orchestration.md) | the steps link the rest |
| "Should this be a Mini App?" | [decide.md](decide.md) | recipe 90 |
| Open a Mini App from a button, link, menu or profile; `startapp`; hosting | [launch-and-lifecycle.md](launch-and-lifecycle.md) | recipe 91 |
| "Does `Telegram.WebApp` have X, since which version?" | [webapp-api.md](webapp-api.md), `scripts/webapp_lookup.py` | — |
| Verify `initData`, sessions, what to trust | [security.md](security.md) | recipe 92 |
| Make it look like Telegram in light and dark, iOS and Android | [telegram-design-guidelines.md](telegram-design-guidelines.md), [design-sources.md](design-sources.md), [design-system.md](design-system.md) | `examples/mini-apps/_kit` |
| "Make it look like X", "use our brand", "calmer / denser / fintech", restyle an existing app | [design-system.md](design-system.md) §9 styles, `scripts/miniapp_style.py` | `data/mini-apps/styles.json` |
| Build a screen: shop, form, dashboard, settings, game, editor | `screen-patterns.md`, [components.md](components.md) | recipes 93-99 |
| "It looks generated / web-like / off", "make it premium" | [anti-slop.md](anti-slop.md), `scripts/miniapp_lint.py` | — |
| Speed, weak Android, how to test without a phone | [performance-and-testing.md](performance-and-testing.md), `scripts/preview_miniapp.py` | — |

## Reading order for a new Mini App

1. [decide.md](decide.md): is it a Mini App, which entry point, what the bot says before and after.
2. [launch-and-lifecycle.md](launch-and-lifecycle.md): start sequence, `ready()`, visibility, hosting.
3. [security.md](security.md): the server contract, before any API route exists.
4. [telegram-design-guidelines.md](telegram-design-guidelines.md) G1-G7, then [design-system.md](design-system.md):
   pick a style (§9), use the kit, check [anti-slop.md](anti-slop.md).
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
| `data/mini-apps/styles.json` | named design styles: intent, tokens, components, do and don't |
| `data/mini-apps/components.json` | 97 elements (structure, navigation, actions, settings, input, display, media, tables, overlays) with variants, states, kit class, native replacement and status |
| `data/mini-apps/icons.json` | 81 kit icons mapped to SF Symbol and Material names |
| `scripts/webapp_lookup.py` | `show`, `search`, `since`, `gates`, `theme`, `sync` over the catalog |
| `scripts/miniapp_style.py` | `presets`, `show`, `css`, `check` for styles and custom brand profiles |
| `scripts/miniapp_lint.py` | 24 rules: security, native controls, theme, motion, labels, slop (`--json`, `--strict`) |
| `scripts/preview_miniapp.py` | local stand with a mock client: platforms, themes, widths, fullscreen, versions |
| `examples/mini-apps/_kit` | `tma.css` (roles, scales, primitives, style presets), `tma.ts` (no-dependency kit), `icons.svg` |
| `examples/mini-apps/gallery` | every kit element on one page: open it in the stand and switch platform, theme, width, style |

Refresh after a Telegram release: `py -3 scripts/webapp_lookup.py sync --fetch` prints the diff;
add `--write` to update the catalog, then re-run the tests.
