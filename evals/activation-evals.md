# Activation eval scenarios

Use these to check that the skill triggers on the right requests and stays out of
the wrong ones. The `description` in `SKILL.md` is what drives selection — if a
positive case doesn't trigger or a negative case does, refine the description.

## Positive (should activate)

| # | Request | Why it matches |
|---|---|---|
| P1 | "Fix Telegram `can't parse entities`." | escaping/entity defect |
| P2 | "Migrate the bot's messages from MarkdownV2 to HTML." | format migration |
| P3 | "Add Rich Messages for AI answers." | Rich Messages implementation |
| P4 | "Render a table inside a Telegram message." | rich structured content |
| P5 | "Add streaming via `sendRichMessageDraft`." | streaming drafts |
| P6 | "Fix RTL formatting in Telegram messages." | RTL presentation |
| P7 | "Audit our Telegram formatter utility." | formatter audit |
| P8 | "Update the Telegram bot to Bot API 10.2 formatting." | capability migration |
| P9 | "Safely format user-provided text for Telegram." | safe escaping |
| P10 | "Fix long-message splitting in Telegram." | limits & splitting |
| P11 | "HTML is showing as literal text in the bot's messages." | wrong parse_mode |
| P12 | "Our localized templates break MarkdownV2." | localization + escaping |

## Negative (should NOT activate)

| # | Request | Why it's out of scope |
|---|---|---|
| N1 | "Set up a Telegram webhook." | infrastructure, not presentation |
| N2 | "Add Telegram Stars payments." | payments |
| N3 | "Create a `/start` command." (no formatting) | bot logic, not formatting |
| N4 | "Fix the bot's user database." | data layer |
| N5 | "Write a marketing post for Telegram." | content strategy |
| N6 | "Open an RTF file." | Microsoft `.rtf`, unrelated |
| N7 | "Build a Telegram Mini App." (no message content) | Mini App, not messages |
| N8 | "Configure the bot's admin rights in a group." | group admin |

## Boundary notes

- N3/N7 flip to **positive** if the task is specifically about how the resulting
  message is *formatted/rendered*.
- "RTF" only means Microsoft `.rtf` here — never Telegram Rich Messages (N6 is a
  hard negative and a terminology trap).

## How to run the check

1. Read each request as the routing model would see only the `SKILL.md`
   `name` + `description`.
2. Confirm every P activates and every N does not.
3. If misrouted, tighten trigger terms or the "Do NOT use" clause in the
   description, then re-check — don't add scope the skill can't deliver.
