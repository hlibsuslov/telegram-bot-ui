# emoji: one premium emoji pack, applied everywhere eligible

**When:** premium or custom emoji in buttons, texts or posts; move to another pack; a video, GIF or
picture made into an emoji mosaic pack (the "Mosaic" section below).

## Read

- Eligibility and ids: `references/custom-emoji.md`.
- The decision path, choosing, resolving, applying, migrating, widgets:
  `references/emoji-packs.md` ("The agent's decision path" first).
- Posts and long texts: `references/emoji-in-posts.md`.
- One icon system per bot: `references/visual-language.md` §1-3.
- A mosaic pack from a video or picture: `references/emoji-mosaic.md` only.

## Steps

1. Check eligibility (Fragment usernames, or owner Premium outside channels). If ineligible, say
   so and keep Unicode fallbacks: Telegram strips the emoji silently and returns no error.
2. **Choosing icons yourself: run the icon plan** (`references/emoji-packs.md`, "The icon plan"):
   `bot-ui emoji plan [--profile style-profile.json]` (no project: `emoji_packs.py library plan
   --needs … --route …`, MCP `emoji_plan_icons`). Stop at stage 0 when the route is `none`. Open
   `icon-plan.html`, look at every chosen slot at 20 px on light and dark, and record
   `bot-ui emoji verdict --slot <slot> --ok | --alt N | --reject "<why>"`; then
   `bot-ui emoji apply-plan` (only accepted slots; a person's own icons are never touched).
   Quick whole-pack ranking instead: `tgui.py emoji library pick --needs <slots>` (the ~490-pack library: one family ranked by real
   coverage, theme-adaptive, static; only slot emoji leave the machine) → `emoji apply`; offline:
   `emoji suggest` → `emoji resolve`. Ids come from a real pack, never invented; `emoji verify`
   against a sent message read back. One icon by meaning: `emoji library search <words>`. By look:
   `emoji library facets --use <bot kind> --style … --theme both` (tags with confidence; style
   tags are the least reliable, so show the pack before you rely on one).
3. All icons of a message or none; one pack family per bot (`tgui.py check icons`).
4. **Double check, required:** `bot-ui emoji review --out icon-review.html` (or `audit_icons.py`
   without a project), open the sheet and look at every row: the picture says what the label says
   (`ICON_MEANING_MISMATCH`), it is static (`BUTTON_EMOJI_ANIMATED`), it matches its neighbours
   in fill, weight and colour. Fix or drop every red row; a slot no pack says well stays label-only.

## Mosaic: a video, GIF or picture as an emoji pack

Offer it once when the user has a logo, clip, GIF or banner and works on a post, a launch, a welcome
screen or a community pack (`references/emoji-mosaic.md`, "What it is and when to offer it"). Then:

1. `tgui.py mosaic plan <file>` and propose one grid (8 columns or fewer is safe on phones).
2. `tgui.py mosaic make <file> --grid CxR [--corners X1,Y1,X2,Y2 | --crop X,Y,W,H] [--round R]
   [--start S --duration D] --out mosaic/`; open `mosaic/preview.html` and look at the seams. A ZIP from
   the website's generator (`/emoji/mosaic`) is the same format: `tgui.py mosaic check mosaic.zip`.
3. Tiles, preview and checks need no token. Creating the set needs the user's own bot token in an
   environment variable and their numeric user id, after they wrote `/start` to that bot; no Telegram login.
   With their go: `TELEGRAM_LIVE=1 TELEGRAM_TEST_BOT_TOKEN=… tgui.py mosaic publish mosaic/ --owner <id>`.
4. Done when `delivered` is true and the user saw the message on a phone. The person pastes it into a
   channel post; the agent doesn't publish it.

## Without scripts

Use only ids from `data/emoji/packs.json`; if the pack isn't there, ask for a sticker-set link.

## Done

One family, every id resolved, Unicode fallback kept, eligibility stated, the review sheet
looked at and clean, every chosen slot of `emoji/icon-plan.json` with a verdict.

## Next

`improve` the screens whose icons changed, or `post` for channel use (needs Fragment). After a mosaic:
`post` to plan the announcement it goes into.
