# shadcnblocks provenance

| | |
| --- | --- |
| Block | `application-shell1` (Application Shell 1 - Sidebar Shell with Breadcrumbs), free, no API key |
| Page | https://www.shadcnblocks.com/block/application-shell1 |
| Registry item | https://www.shadcnblocks.com/r/new-york/application-shell1.json (license field: https://www.shadcnblocks.com/license) |
| Date | 2026-11-22 |
| Command | `npx shadcn@4.23.0 add @shadcnblocks/application-shell1 -y` with a temporary `"registries": {"@shadcnblocks": "https://www.shadcnblocks.com/r/{style}/{name}"}` in components.json (removed after the install; registry config stays local) and `npm_config_dry_run=true`, so the CLI wrote the files but installed no npm package |

## Files the CLI added

- `src/components/application-shell1.tsx` (the block)
- `src/components/ui/`: avatar, breadcrumb, button, collapsible, dropdown-menu, input, scroll-area, separator, sheet, sidebar, skeleton, tooltip (registry dependencies of the block)
- `src/hooks/use-mobile.ts`

Added separately with the same CLI (same `npm_config_dry_run=true` install) for the Studio itself: `src/components/ui/` textarea, label, badge, tabs, dialog, alert, card, switch (round 1); select, popover, command, slider (round 2, 2026-11-22; `command` without overwriting `dialog`). `native-select` was added in round 1 and removed in round 2 when every dropdown moved to Select or the searchable screen picker.

## What changed

- The block declares npm dependencies `lucide-react`, `motion` and `cn`. `cn` (npm, maintainer shadcn, no install scripts) and `motion` were not installed: every `import { cn } from "cn"` in the generated files points to the local `@/lib/utils` (clsx + tailwind-merge), and the motion-only active pill animation was dropped.
- `application-shell1.tsx`: kept the sidebar, grouped navigation with collapsible submenus, rail, footer and the breadcrumb header; replaced the demo brand, workspaces, account dropdown, avatar and placeholder content with props: project name, revision chip and draft-changes indicator (header), the Studio sections Map, Screens, Simulator, Widgets, Changes (and "What works here" in the artifact), a mode footer, header actions and the routed page as children. Remote logo and avatar URLs are gone, so the app loads nothing from the network.
- `command.tsx`, `select.tsx`, `slider.tsx`, `popover.tsx`: `cn` import pointed to `@/lib/utils`, otherwise as generated.

## Terms

Used inside the bot-ui Studio app (`studio/web`) only. The block is not redistributed in the skill, its templates or any generated bot project.

## Other dependencies added for the Studio (round 2)

| Package | Version | License | Use |
| --- | --- | --- | --- |
| `@dagrejs/dagre` (+ `@dagrejs/graphlib`) | 3.1.3 | MIT | left-to-right map layout over measured node sizes |
| `cmdk` | 1.1.1 | MIT | `command` component: searchable screen picker and map search |
| `@fontsource-variable/inter` | 5.3.0 | OFL-1.1 | UI font, latin + cyrillic woff2 only |
| `@fontsource-variable/jetbrains-mono` | 5.3.0 | OFL-1.1 | code font, latin + cyrillic woff2 only |

Fonts are self-hosted: separate files in `dist/` (Studio CSP `font-src 'self'`), `data:` URIs in the one-file artifact (`font-src data:`).

## Behavioural reference (no code used)

The widget constructor (`src/features/widgets/`) follows the arrangement and flow of the playground in
https://github.com/advanceddev/telegram-widget-kit at commit `4887119ac44a62130a5dd6a2b7d1b588ae915154`:
a settings rail (preview options, size budget and checks, send settings, actions), a resizable split between
source tabs (plus the built output) and a chat-bubble preview that follows every edit, and export of the built
HTML. That repository has no license, so none of its code, CSS, templates, icons or texts were copied; it was
read as a behavioural reference only, and the Studio's implementation is its own React/shadcn code on the bot-ui
backend (`/api/widget/build`, `/api/widget/runtime`, `/api/widget/export` with the stale-build rule).
