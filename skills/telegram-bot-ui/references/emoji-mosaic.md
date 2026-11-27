---
summary: "A video, GIF or picture cut into a premium emoji pack laid out as a mosaic: limits, grid sizes, crop and corners, what needs a token, the tool and the website generator."
verified: "2026-11-27"
bot_api: "10.5"
---

# Emoji mosaics: a video or picture as a premium emoji pack

> Labels: **API** = Bot API catalog text (`tgui.py lookup show <Symbol>`), **Official** = another
> core.telegram.org page, **Observed** = seen in real clients, **Heuristic** = this skill's design rule,
> **Unverified** = the sources do not say. Tool: `scripts/emoji_mosaic.py` (`tgui.py mosaic …`).
> Website: telegram-bot-ui.hlixli.com/emoji/mosaic makes the same tiles in the browser and, after a Telegram
> login, can create the pack itself; its ZIP is the format `check` and `publish` read.

## Contents

- [What it is and when to offer it](#what-it-is-and-when-to-offer-it)
- [Telegram's limits](#telegrams-limits)
- [What needs a token or a login](#what-needs-a-token-or-a-login)
- [Grid sizes](#grid-sizes)
- [Crop, corners and the loop](#crop-corners-and-the-loop)
- [Steps](#steps)
- [Putting the mosaic into a channel post](#putting-the-mosaic-into-a-channel-post)
- [Failures](#failures)

## What it is and when to offer it

The source is cut into a grid of 100x100 tiles. Each tile becomes one custom emoji of a new set, and one
message holds them all, a line per row, so the picture reassembles in the chat. An animated source gives
video emoji that play together.

**Offer it once, unprompted** (**Heuristic**), when the user has a logo, a short clip, a GIF or a banner
and is working on: a channel post or announcement, a launch or a giveaway, the bot's welcome or about
screen, a branded pack for a community. One line is enough: "I can turn this clip into an animated emoji
mosaic: a pack of N emoji that shows it in one message. Want it?" Do not offer it for buttons (a mosaic tile
means nothing alone; button icons are `references/emoji-packs.md`), and never for a source the user has
no rights to.

## Telegram's limits

| Rule | Value | Basis |
|---|---|---|
| Emoji size, static and video | exactly 100x100 px | **Official** (core.telegram.org/stickers) |
| Static format | PNG or WEBP | **Official** |
| Video format | WEBM, VP9, no audio stream, up to 30 FPS, at most 3 s, should loop | **Official** |
| Video file size | at most 256 KB | **Official** |
| Initial stickers in `createNewStickerSet` | 1-50; more go one by one through `addStickerToSet` | **API** |
| Emoji in one set | up to 200 | **API** (`addStickerToSet`) |
| Custom emoji in one message | `message_animated_emoji_max` from the client's appConfig; 100 observed | **Official** name, **Observed** value |
| Entity offsets and lengths | UTF-16 code units | **API** (`MessageEntity`) |
| Each custom emoji entity | wraps exactly one regular emoji | **Official** (core.telegram.org/api/custom-emoji) |
| Set name | letters, digits, underscores, starts with a letter, no `__`, ends in `_by_<bot_username>`, 1-64 chars | **API** |
| Using custom sets in messages | Telegram Premium for users | **Official** |
| A bot sending custom emoji | Fragment usernames, or owner Premium in private, group and supergroup chats | **API** (`references/custom-emoji.md`) |

The tool keeps the default grid at 100 emoji or fewer; `--max-emoji` changes the cap if Telegram's
value changes.

## What needs a token or a login

| Step | Needs | Why |
|---|---|---|
| Plan the grid, crop, cut tiles, preview, check | nothing; offline | local ffmpeg, or the browser on the website |
| Create the set and add tiles | a bot token and the owner's numeric `user_id` | `uploadStickerFile`, `createNewStickerSet` and `addStickerToSet` are bot methods; the set belongs to the user and carries the bot's name |
| Send the mosaic message | the same bot; the owner has written `/start` to it | a bot can't open a private chat first |
| Show it as custom emoji | owner Premium (private chat) or Fragment usernames | otherwise Telegram strips the entities silently |
| Put it in a channel post | the person's own Premium, pasting as themselves | channel posts by a bot need Fragment |

**No Telegram login is needed** by any of these methods. A login (the Login Widget or a Mini App's
`initData`) only proves who the visitor is; it matters when a hosted service uses *its own* bot to create
packs for visitors. Then the service carries the abuse risk under its bot's name (every set is
`…_by_<its bot>`), needs rate limits and a way to take sets down (`deleteStickerSet`), and its token stays on
its server. The website's mosaic maker works that way when its owner sets it up: a separate pack bot, the
Login Widget with write access, each set owned by the visitor's own id. Here, in the skill, the user brings
their own bot. **Unverified:** whether `uploadStickerFile` itself requires the owner to have started the
bot; ask for `/start` first anyway.

Token rules: it comes from an environment variable only (`TELEGRAM_TEST_BOT_TOKEN`, or the name passed to
`--token-env`), never in chat, code, logs or the manifest. A dedicated bot for packs is fine: the set name
ends in its username, and only that bot can edit the set later.

## Grid sizes

`emoji_mosaic.py plan <file>` lists grids for the source's shape: the share a cover fit would crop, and
how the row fits a bubble. Rows wrap where the chat bubble ends, which breaks the picture:

- **up to 8 columns: safe** on phones (**Heuristic**);
- **9-12: check on the narrowest phone** you support (**Heuristic**);
- **13+: likely wraps** (**Heuristic**); `check` warns.

Telegram puts about 1 px between emoji and about 5 px between lines (**Observed**). Text or thin lines
lying on a row seam look broken: move them in the crop or pick another row count. Fewer, larger tiles read
better: a simple logo often looks best at 6x3 or 8x4. Shapes that fit well: square 8x8, 4:5 8x10,
16:9 8x5 or 7x4, wide banner 12x5.

## Crop, corners and the loop

- **Auto (cover):** scale to fill the grid and cut the overflow evenly from both sides. Default.
- **Choose the region:** `--crop X,Y,W,H` (top-left corner and size) or `--corners X1,Y1,X2,Y2` (two
  opposite corners), in source pixels; then the fit applies to that region. On the website, drag the box or
  its corners; it keeps the grid's shape.
- **Fit:** `cover`, `contain` (pads with `--background`, transparent by default) or `fill` (stretch).
- **Rounded corners:** `--round R` cuts the mosaic's four outer corners with radius R canvas px; the
  corner tiles get real transparency (VP9 with alpha, or PNG).
- **Time:** `--start`, `--duration` (at most 3 s; default 2.9), `--fps` (at most 30). `--pingpong`
  plays forward then back (each half at most 1.45 s) for a seamless loop.
- `--still` takes the first frame and makes static PNG tiles (smaller, never out of sync).

## Steps

1. Ask for the file and the use (post, welcome, community pack). Confirm the user may use the material.
2. `py -3 scripts/emoji_mosaic.py plan clip.mp4` → propose one grid with its reason ("8x4: safe on
   phones, crops 3%").
3. `make clip.mp4 --grid 8x4 [--corners …] [--round 40] [--start 1.5] --out mosaic/`. It writes
   `mosaic.json` (`tg-emoji-mosaic/v1`), `tiles/`, `canvas.png`, `preview.html`, and runs `check`.
   Tiles over 256 KB are encoded again at a lower bitrate.
4. Open `preview.html` and look: seams, faces or text on a row line, the loop point. Adjust and redo.
5. Live, after the user's go: `TELEGRAM_LIVE=1 TELEGRAM_TEST_BOT_TOKEN=… py -3 scripts/emoji_mosaic.py
   publish mosaic/ --owner <user_id> --title "…" --save mosaic-pack.json`. It reads the set back, sends the
   mosaic to the owner and compares the `custom_emoji` entities that came back with the tiles. Same tiles,
   same set name: a second run finishes an interrupted set instead of creating another.
6. Done only when: `delivered` is true, the set is `custom_emoji` with one unique id per tile, the
   `t.me/addemoji/<set>` link opens, and the user looked at the message on a phone.

The website's ZIP is the same format: `check mosaic.zip`, then `publish mosaic.zip --owner …`.
Offline helpers: `message mosaic/ --ids mosaic-pack.json [--html]` rebuilds the text and entities (UTF-16
offsets) or `<tg-emoji>` HTML from saved ids.

## Putting the mosaic into a channel post

The owner opens the bot's message, copies it and pastes it into a post (their Premium lets them use the
set), or forwards it without the author. A person publishes, not the agent. A bot posting it to a channel
itself needs Fragment usernames (`references/custom-emoji.md`) and the `post` playbook's approval.

## Failures

| Symptom | Cause | Fix |
|---|---|---|
| The message shows ⬜ squares | the bot can't use custom emoji there, or the viewer can't render them | owner Premium in a private chat, or Fragment; `delivered` is false |
| `PEER_ID_INVALID` on send | the owner never wrote to the bot | `/start` the bot, run `publish` again |
| `STICKER_VIDEO_LONG`, `file too big` | over 3 s or 256 KB | shorter `--duration`, `--still`, or a simpler clip |
| The picture shifts sideways | rows wrapped: too many columns for the bubble | 8 columns or fewer |
| A seam cuts a face or a word | it lies on a row line | move the crop or change the row count |
| A second, half-filled set | the name changed between runs (different tiles) | keep `mosaic/` and rerun `publish` with the same tiles |
