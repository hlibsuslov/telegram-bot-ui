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

Added separately with the same CLI for the Studio itself: `src/components/ui/` textarea, label, badge, tabs, dialog, alert, card, switch, native-select.

## What changed

- The block declares npm dependencies `lucide-react`, `motion` and `cn`. `cn` (npm, maintainer shadcn, no install scripts) and `motion` were not installed: every `import { cn } from "cn"` in the generated files points to the local `@/lib/utils` (clsx + tailwind-merge), and the motion-only active pill animation was dropped.
- `application-shell1.tsx`: kept the sidebar, grouped navigation with collapsible submenus, rail, footer and the breadcrumb header; replaced the demo brand, workspaces, account dropdown, avatar and placeholder content with props: project name, revision chip and draft-changes indicator (header), the Studio sections Map, Screens, Simulator, Widgets, Changes (and "What works here" in the artifact), a mode footer, header actions and the routed page as children. Remote logo and avatar URLs are gone, so the app loads nothing from the network.
- `native-select.tsx`: the wrapper spans the full width when the select does (`w-full`), plus an optional `wrapperClassName`.

## Terms

Used inside the bot-ui Studio app (`studio/web`) only. The block is not redistributed in the skill, its templates or any generated bot project.
