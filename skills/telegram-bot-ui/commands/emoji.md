# emoji: one premium emoji pack, applied everywhere eligible

**When:** premium or custom emoji in buttons, texts or posts; move to another pack.

## Read

- Eligibility and ids: `references/custom-emoji.md`.
- The decision path, choosing, resolving, applying, migrating, widgets:
  `references/emoji-packs.md` ("The agent's decision path" first).
- Posts and long texts: `references/emoji-in-posts.md`.
- One icon system per bot: `references/visual-language.md` §1-3.

## Steps

1. Check eligibility (Fragment usernames, or owner Premium outside channels). If ineligible, say
   so and keep Unicode fallbacks: Telegram strips the emoji silently and returns no error.
2. `tgui.py emoji suggest` → `emoji resolve` (ids from a real pack, never invented) →
   `emoji apply`; `emoji verify` against a sent message read back.
3. All icons of a message or none; one pack family per bot (`tgui.py check icons`).

## Without scripts

Use only ids from `data/emoji/packs.json`; if the pack isn't there, ask for a sticker-set link.

## Done

One family, every id resolved, Unicode fallback kept, eligibility stated.

## Next

`improve` the screens whose icons changed, or `post` for channel use (needs Fragment).
