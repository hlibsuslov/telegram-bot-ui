# Anti-slop for Mini Apps

How a Mini App ends up looking generated or "like a website in a sheet", and what to do instead. It joins
three sources: Telegram's Design Guidelines (always first), the craft floor of the impeccable skill
(contrast, states, browser surfaces) and the unslop catalogue of AI-UI tells (Damir Sokolovsky, CC BY 4.0,
adapted). A Mini App is almost always an **Operate** product (people come to do a task), with small
**Persuade** moments (onboarding, a promo) inside it. Labels: **[Official]**, **[Heuristic]**.

## 1. The two principles

1. **Telegram-native beats general taste.** Where a general design rule and Telegram's own UI disagree,
   Telegram wins (§3).
2. **Quiet chrome, one moment.** Grouped lists, system type, the theme's colours; one rich element per
   screen (a figure, a promo, an illustration, a chart). Everything else stays calm.

## 2. Telegram-specific tells

| Tell | Fix |
|---|---|
| Own header with a back or close arrow | `BackButton`; Telegram draws the header |
| Own fixed CTA at the bottom while the MainButton is available | `MainButton` / `SecondaryButton` |
| Hard-coded `#fff` / `#000` surfaces; a white flash in dark mode | theme roles; chrome colours before `ready()` |
| `100vh` | `var(--tg-viewport-stable-height)` and safe-area variables |
| Content under the notch or Telegram's buttons in fullscreen | `--tg-safe-area-inset-*` + `--tg-content-safe-area-inset-*` |
| Splash screen with a logo, a landing hero on every launch | straight to a useful screen with skeletons; onboarding once |
| Hamburger menu, sidebar, desktop grid | tab bar 2-5, sections, BackButton |
| `alert()`, own confirmation dialogs for a yes/no | `showConfirm`, `showPopup` |
| Hover-only hints, cursor effects | taps and long-press |
| Confetti, pulsing dots, endless loops | one success animation + `notificationOccurred('success')` |
| Haptics on everything | the table in [design-system.md](design-system.md) §7 |
| Custom fonts in lists and buttons; web fonts from a CDN | the system font |
| "Login with Telegram" inside the app; asking for a phone without a reason | `initData` already identifies the user; `requestContact` only with a visible reason |
| Tokens in the client; trusting `initDataUnsafe` | [security.md](security.md) |
| `localStorage` for user data or session tokens | `CloudStorage` / `DeviceStorage`; secrets in `SecureStorage` |
| The app inside another site's iframe, a redirect to another domain | one origin (Bot API 10.2) |
| Launch params read after the router rewrote the hash | read them on the first line |
| An own splash over Telegram's loading screen | loading screen in @BotFather; `ready()` after the first useful screen |
| BackButton that does nothing, Android back that leaves the app | one navigation stack, `BackButton.onClick` |
| A blank screen on a network error | an error state with retry; plain offline text |
| A brand-blue button in a user's green theme | the theme's `button_color`; brand on one moment only |

## 3. Conflicts and decisions [Heuristic]

| Conflict | Decision |
|---|---|
| "No emoji" vs Telegram, where emoji is a native language | Unicode emoji as UI icons and in labels: slop. Animated or premium emoji and stickers (TGS / WEBM from the bot's packs, `iconCustomEmojiId` 9.5, `setEmojiStatus`) as the illustration of a moment: native, at most one per screen |
| "No coloured gradients" vs a brand header and CTA | only a tonal gradient of one hue on one moment (hero, promo), fading into the page; buttons solid; cross-hue gradients and gradient text banned |
| "No glass as decoration" vs Telegram's glass chrome on iOS | glass only on floating controls over scrolling content (tab bar, side circle), with a solid fallback; cards and cells solid |
| "No NEW badges" vs a coachmark in the reference | a one-time coachmark naming the new feature, remembered; no permanent badges |
| Stars prices ("⭐ 250") vs "no emoji in labels" | `⭐` directly before an amount is the Telegram Stars currency sign (as in Telegram's own payment UI): allowed in prices and MainButton text; every other emoji in a label stays slop (lint MA13 makes the same exception) |
| "Primary is off-white on dark" | in a Mini App the primary action is the MainButton in the theme's `button_color` |
| "Own typeface for an own world" | a Mini App operates inside Telegram: system font; a brand face only inside the one moment |
| Corner ribbons on cards (reference) | a quiet tag text, one per card |

## 4. General tells, adapted (unslop, impeccable)

- **Surfaces and colour:** purple-to-blue gradients, glows, blurred blobs, neon borders, many tints of one
  hue, everything highlighted → one neutral surface ramp from the theme, one accent used once or twice.
- **Type:** weights 800-900, uppercase tracked labels, many sizes, mixed number formats, italics for
  emphasis → the scale in design-system §4, weights 400/500/600, one number format in tabular figures.
- **Icons:** emoji as icons or status, icons of mixed sizes and strokes, a sparkle for AI → one line set
  (stroke 1.8), one size per context, same icon box in every row.
- **Spacing:** arbitrary values, uneven rows, groups closer to neighbours than to their own items → the
  4 px steps, one row height per list, smaller gaps inside groups than between them.
- **Copy:** greetings ("Welcome back! 👋"), exclamation marks, changes without a reference ("+12%!!"),
  hype words, trailing periods on buttons, fake data ("$123,456") → the screen's title, plain statements,
  "+12 % vs last month", what the thing does, plausible numbers.
- **Components:** same-size icon-heading-text cards as the page, cards in cards, a sparkline on every stat,
  pills on everything → grouped lists, one main chart, radius by size.
- **Motion:** `transition: all`, `hover:scale`, bouncy springs, everything flying in, animating layout →
  one ease-out curve, transform and opacity, one entrance at most.
- **Browser surfaces (impeccable craft floor):** default text selection, caret, scrollbars, focus ring and
  proportional digits in tables give away an assembled page → the kit themes `::selection`, `caret-color`,
  `:focus-visible`, scrollbars and `tabular-nums` from the theme.
- **States:** a screen with only the happy path → loading, empty, error, disabled and success for every
  list and action (design-system §8).

## 5. The craft pass ("make it premium / nicer")

In this order, stopping when the screen is right: 1) copy and the first line of each screen; 2) structure:
native buttons, grouped lists, one primary action; 3) states; 4) hierarchy: one moment, one figure, type
scale; 5) colour roles and the style ([design-system.md](design-system.md) §9); 6) icons and imagery last.
Then lint and preview both themes.

## 6. Checklist

- [ ] No tell from §2 on any screen.
- [ ] One moment per screen; the rest grouped and quiet.
- [ ] Copy without greetings, exclamation marks, hype or fake data.
- [ ] One icon set, no emoji in UI chrome or button labels.
- [ ] Browser surfaces themed; numbers tabular.
- [ ] `py -3 scripts/miniapp_lint.py <app> --strict` clean.

## Linter rules

`scripts/miniapp_lint.py` checks what is visible in code. Pattern-based: a clean report is static evidence,
not proof of how real clients render.

| Rule | Level | Catches | Source |
|---|---|---|---|
| MA01 bot-token | error | a bot token or `BOT_TOKEN` in client code | security §2 |
| MA02 unsafe-server | error | `initDataUnsafe` in server code | security §1 |
| MA03 native-dialog | error | `alert()`, `confirm()`, `prompt()` | G3 |
| MA04 script-order | error | `telegram-web-app.js` missing from `<head>` or not first | Official |
| MA05 raw-color | warning | colour literal outside `var()` fallbacks, `light-dark()`, `--tma-fb-*`, neutral alpha greys | G1 |
| MA06 vh | warning | `100vh` / `dvh` / `svh` outside a `var(--tg-viewport-*)` fallback | G2 |
| MA07 fixed-cta | warning | own fixed bottom button not marked `data-tma-fallback` | G3 |
| MA08 safe-area | warning | `requestFullscreen` with no safe-area insets in CSS | G6 |
| MA09 transition-all | warning | `transition: all`, `animate-pulse`, `animate-ping` | G4 |
| MA10 infinite | warning | infinite animation on a non-loader | G4 |
| MA11 gradient-text | warning | `background-clip: text` | §4 |
| MA12 glass-fallback | warning | `backdrop-filter` without a solid fallback | §3 |
| MA13 emoji-ui | warning | Unicode emoji in buttons, navigation, headings, bottom-button text | §3 |
| MA14 local-storage | warning | `localStorage`, `sessionStorage` | security §6 |
| MA15 version-gate | warning | a member newer than 6.0 used with no gate in the file (`isVersionAtLeast`, the kit's `has()`, or `@tma.js/sdk` `isAvailable()` / `ifAvailable()`) | webapp-api §2 |
| MA16 web-font | warning | `@font-face`, web-font CDNs | §3 |
| MA17 reduced-motion | warning | motion with no `prefers-reduced-motion` rule | G4 |
| MA18 ready | warning | `ready()` never called | Official |
| MA19 own-back | warning | `history.back()` or an own back button | G3 |
| MA20 web-login | warning | Telegram login widget inside the app | security |
| MA21 hover-only | warning | content revealed only on `:hover` | G2 |
| MA22 small-text | warning | font size below 11 px | G5 |
| MA23 viewport-meta | warning | no `<meta name="viewport">` | G2 |
| MA24 label | warning | `<input>` without a label, `<img>` without `alt` | G5 |
