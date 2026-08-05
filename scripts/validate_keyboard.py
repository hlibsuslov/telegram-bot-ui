#!/usr/bin/env python3
"""Validate Telegram keyboard payloads against the Bot API's structural rules.

Portable: standard library only. Safe: reads local files (or stdin) only, never
needs a bot token, never touches the network, never sends a message.

Accepts either shape:
  * a full reply_markup object: {"inline_keyboard": [[...]]} or {"keyboard": [[...]]}
  * a bare list of rows: [[{...}, {...}], [{...}]]
  * an object containing "reply_markup"

Checks (errors -> exit 1):
  * inline buttons carry EXACTLY one action field; reply buttons AT MOST one
    (`text`, `style`, `icon_custom_emoji_id` never count as the action)
  * `style` is one of primary / success / danger
  * `callback_data` is 1-64 BYTES
  * `CopyTextButton.text` is 1-256 characters
  * `text` is present and non-empty
  * `pay` / `callback_game` buttons sit first in the first row
  * `icon_custom_emoji_id` is a plausible numeric string (never a file_id, a
    pack name, a URL, or a Unicode emoji)

Warnings (do not fail): more than one `primary` in a keyboard, every button
styled, duplicate labels in one keyboard, emoji-only labels, very wide rows,
very long labels, unstyled danger-sounding labels.

Usage:
  python scripts/validate_keyboard.py keyboard.json
  python scripts/validate_keyboard.py < keyboard.json
"""
from __future__ import annotations

import json
import re
import sys

# Button labels are full of emoji and non-Latin text; a legacy console codepage
# (e.g. cp1252 on Windows) would otherwise crash the report itself.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover - exotic environments
        pass

VALID_STYLES = ("primary", "success", "danger")

# Presentation fields — explicitly excluded from the "one action" rule by the
# Bot API wording for both KeyboardButton and InlineKeyboardButton.
PRESENTATION = ("text", "style", "icon_custom_emoji_id")

INLINE_ACTIONS = (
    "url",
    "callback_data",
    "web_app",
    "login_url",
    "switch_inline_query",
    "switch_inline_query_current_chat",
    "switch_inline_query_chosen_chat",
    "copy_text",
    "callback_game",
    "pay",
)

REPLY_ACTIONS = (
    "request_users",
    "request_chat",
    "request_managed_bot",
    "request_contact",
    "request_location",
    "request_poll",
    "web_app",
)

FIRST_ONLY = ("pay", "callback_game")

CUSTOM_EMOJI_ID_RE = re.compile(r"^\d{5,}$")
EMOJI_ONLY_RE = re.compile(
    r"^[\W_]+$"  # no letters or digits at all
)

MAX_CALLBACK_BYTES = 64
MAX_COPY_TEXT = 256
LONG_LABEL_WARN = 30
WIDE_ROW_WARN = 4


def load(source: str | None) -> object:
    raw = sys.stdin.read() if source is None else open(
        source, "r", encoding="utf-8"
    ).read()
    return json.loads(raw)


def extract(doc: object):
    """Return (rows, kind) where kind is 'inline' or 'reply'."""
    if isinstance(doc, dict) and "reply_markup" in doc:
        doc = doc["reply_markup"]
    if isinstance(doc, dict):
        if "inline_keyboard" in doc:
            return doc["inline_keyboard"], "inline"
        if "keyboard" in doc:
            return doc["keyboard"], "reply"
        raise ValueError(
            "object has neither 'inline_keyboard' nor 'keyboard'"
        )
    if isinstance(doc, list):
        return doc, "inline"
    raise ValueError("expected an object or a list of rows")


def check_button(btn, kind, r, c, errors, warnings):
    where = f"row {r + 1}, button {c + 1}"

    if isinstance(btn, str):
        if kind == "inline":
            errors.append(f"{where}: inline buttons cannot be plain strings")
        elif not btn.strip():
            errors.append(f"{where}: empty button text")
        return

    if not isinstance(btn, dict):
        errors.append(f"{where}: expected an object, got {type(btn).__name__}")
        return

    text = btn.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{where}: 'text' is required and must be non-empty")
        text = ""

    actions = INLINE_ACTIONS if kind == "inline" else REPLY_ACTIONS
    used = [k for k in btn if k not in PRESENTATION]
    unknown = [k for k in used if k not in actions]
    present = [k for k in used if k in actions]

    for key in unknown:
        warnings.append(f"{where}: unknown field '{key}' for a {kind} button")

    if kind == "inline":
        if len(present) != 1:
            errors.append(
                f"{where} ('{text}'): inline buttons need EXACTLY one action "
                f"field, found {len(present)} {present or '[]'}"
            )
    else:
        if len(present) > 1:
            errors.append(
                f"{where} ('{text}'): reply buttons allow AT MOST one non-text "
                f"field, found {len(present)} {present}"
            )

    style = btn.get("style")
    if style is not None and style not in VALID_STYLES:
        errors.append(
            f"{where} ('{text}'): style must be one of "
            f"{'/'.join(VALID_STYLES)}; got {style!r}"
        )

    cb = btn.get("callback_data")
    if cb is not None:
        if not isinstance(cb, str):
            errors.append(f"{where}: callback_data must be a string")
        else:
            n = len(cb.encode("utf-8"))
            if n == 0 or n > MAX_CALLBACK_BYTES:
                errors.append(
                    f"{where} ('{text}'): callback_data is {n} bytes "
                    f"(allowed 1-{MAX_CALLBACK_BYTES})"
                )
            elif not cb.isascii():
                warnings.append(
                    f"{where} ('{text}'): non-ASCII callback_data spends "
                    f"{n} bytes for {len(cb)} characters"
                )

    copy_text = btn.get("copy_text")
    if isinstance(copy_text, dict):
        ct = copy_text.get("text", "")
        if not isinstance(ct, str) or not 1 <= len(ct) <= MAX_COPY_TEXT:
            errors.append(
                f"{where}: copy_text.text must be 1-{MAX_COPY_TEXT} characters"
            )

    icon = btn.get("icon_custom_emoji_id")
    if icon is not None:
        if not isinstance(icon, str) or not CUSTOM_EMOJI_ID_RE.match(icon):
            errors.append(
                f"{where} ('{text}'): icon_custom_emoji_id must be the numeric "
                f"id string of a custom emoji — not a file_id, pack name, URL, "
                f"or Unicode emoji; got {icon!r}"
            )

    for key in FIRST_ONLY:
        if key in btn and not (r == 0 and c == 0):
            errors.append(
                f"{where}: a '{key}' button must be the first button in the "
                f"first row"
            )

    if text and EMOJI_ONLY_RE.match(text.strip()):
        warnings.append(
            f"{where}: label {text!r} has no words — add text next to the emoji"
        )
    if len(text) > LONG_LABEL_WARN:
        warnings.append(
            f"{where}: label is {len(text)} chars; it may truncate "
            f"(check the longest locale)"
        )


DANGER_WORDS = (
    "delete", "remove", "reset", "wipe", "unsubscribe", "leave", "log out",
    "logout", "удалить", "сбросить", "отписаться", "выйти", "slett", "slette",
)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        rows, kind = extract(load(src))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(rows, list) or not rows:
        print("FAIL: keyboard has no rows")
        return 1

    labels: list[str] = []
    styled = 0
    primaries = 0
    total = 0

    for r, row in enumerate(rows):
        if not isinstance(row, list):
            errors.append(f"row {r + 1}: expected a list of buttons")
            continue
        if len(row) > WIDE_ROW_WARN:
            warnings.append(
                f"row {r + 1}: {len(row)} buttons in one row — labels may "
                f"truncate on narrow screens"
            )
        for c, btn in enumerate(row):
            total += 1
            check_button(btn, kind, r, c, errors, warnings)
            if isinstance(btn, dict):
                label = str(btn.get("text", ""))
                labels.append(label.strip().lower())
                style = btn.get("style")
                if style in VALID_STYLES:
                    styled += 1
                if style == "primary":
                    primaries += 1
                elif style is None and any(
                    w in label.lower() for w in DANGER_WORDS
                ):
                    warnings.append(
                        f"row {r + 1}, button {c + 1}: {label!r} looks "
                        f"destructive but has no style — consider 'danger' "
                        f"plus a confirmation step"
                    )
            elif isinstance(btn, str):
                labels.append(btn.strip().lower())

    if primaries > 1:
        warnings.append(
            f"{primaries} 'primary' buttons — a screen should have at most one"
        )
    if total and styled == total and total > 1:
        warnings.append(
            "every button is styled — with no neutral buttons there is no "
            "hierarchy"
        )
    dupes = {x for x in labels if x and labels.count(x) > 1}
    for d in sorted(dupes):
        warnings.append(f"duplicate label in one keyboard: {d!r}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). INVALID.")
        return 1
    print(
        f"\nOK: {kind} keyboard valid "
        f"({len(rows)} row(s), {total} button(s)). {len(warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
