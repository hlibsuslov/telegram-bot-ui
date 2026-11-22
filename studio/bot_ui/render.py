"""Screen -> logical message -> Bot API request. One renderer for the CLI, the Studio
preview checks, the simulator and the adapters."""
from __future__ import annotations

import hashlib
import html
import re
from typing import Any

FORMATS = {"regular.plain": None, "regular.html": "HTML", "regular.markdownv2": "MarkdownV2"}
EDITABLE_FORMATS = {"regular.plain", "regular.html"}
KNOWN_FORMATS = set(FORMATS) | {"regular.entities", "rich", "media.photo"}
PLACEHOLDER = re.compile(r"\{\{|\}\}|\{([a-z0-9_.-]+)\}")
CALLBACK_MAX = 64
TEXT_MAX = 4096
_MD2 = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def localized(value: Any, locale: str, default: str) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    out = value.get(locale)
    return out if isinstance(out, str) else value.get(default) if isinstance(value.get(default), str) else None


def escape(value: str, fmt: str) -> str:
    if fmt == "regular.html":
        return html.escape(value, quote=False)
    if fmt == "regular.markdownv2":
        return _MD2.sub(r"\\\1", value)
    return value


def fill(text: str, values: dict[str, Any], fmt: str) -> tuple[str, list[str]]:
    """Replace {field} with the escaped value; {{ and }} are literal braces."""
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        if m.group(0) == "{{":
            return "{"
        if m.group(0) == "}}":
            return "}"
        name = m.group(1)
        if name not in values or values[name] is None:
            missing.append(name)
            return m.group(0)
        return escape(str(values[name]), fmt)

    return PLACEHOLDER.sub(sub, text), missing


def placeholders(text: str) -> list[str]:
    return [m.group(1) for m in PLACEHOLDER.finditer(text) if m.group(1)]


def callback_data(screen_id: str, action_id: str, action: dict | None = None) -> str:
    """Explicit legacy value, else `screenId:actionId`, else a stable hash when that is > 64 bytes."""
    if action and isinstance(action.get("callbackData"), str):
        return action["callbackData"]
    plain = f"{screen_id}:{action_id}"
    if len(plain.encode("utf-8")) <= CALLBACK_MAX:
        return plain
    return "h:" + hashlib.sha256(plain.encode("utf-8")).hexdigest()[:32]


def visible_text(text: str, fmt: str) -> str:
    if fmt == "regular.html":
        return html.unescape(re.sub(r"<[^>]+>", "", text))
    return text


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def keyboard_rows(screen: dict) -> list[list[str]]:
    kb = screen.get("keyboard") or {}
    rows = kb.get("rows") or []
    return [[a for a in row if isinstance(a, str)] for row in rows if isinstance(row, list)]


def render_screen(project: dict, screen: dict, *, locale: str | None = None, state: str | None = None,
                  values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Logical message of a screen in one locale and state variant."""
    default = project.get("defaultLocale", "en")
    locale = locale or default
    values = values or {}
    msg = screen.get("message") or {}
    fmt = msg.get("format", "regular.plain")
    source = msg.get("text")
    if state and isinstance((msg.get("states") or {}).get(state), dict):
        source = msg["states"][state].get("text", source)
    raw = localized(source, locale, default) or ""
    text, missing = fill(raw, values, fmt)
    diags = [{"code": "PLACEHOLDER_VALUE_MISSING", "severity": "warning", "pointer": "/message/text",
              "message": f"no value for {{{name}}} in this run"} for name in missing]
    if fmt not in FORMATS:
        diags.append({"code": "FORMAT_NOT_RENDERED", "severity": "warning", "pointer": "/message/format",
                      "message": f"{fmt} is kept as is but not rendered by this version; the fallback text is used"})
    kb = screen.get("keyboard") or {}
    ktype = kb.get("type", "none") if kb else "none"
    actions = screen.get("actions") or {}
    rows_out = []
    for row in keyboard_rows(screen):
        out_row = []
        for aid in row:
            act = actions.get(aid)
            if not isinstance(act, dict) or act.get("hidden"):
                continue
            label, _ = fill(localized(act.get("label"), locale, default) or aid, values, "regular.plain")
            btn: dict[str, Any] = {"actionId": aid, "text": label, "type": act.get("type")}
            if ktype == "inline":
                if act.get("type") == "url":
                    btn["url"] = act.get("url")
                else:
                    btn["callbackData"] = callback_data(screen["id"], aid, act)
                if act.get("style") in ("primary", "success", "danger"):
                    btn["style"] = act["style"]
            out_row.append(btn)
        if out_row:
            rows_out.append(out_row)
    return {"screenId": screen.get("id"), "messageId": msg.get("id", "main"), "locale": locale, "state": state,
            "format": fmt, "text": text, "parseMode": FORMATS.get(fmt),
            "keyboard": {"type": ktype, "rows": rows_out, "placeholder": localized(kb.get("placeholder"), locale, default)},
            "widget": (screen.get("widget") or {}).get("ref"), "diagnostics": diags}


def reply_markup(logical: dict) -> dict | None:
    kb = logical["keyboard"]
    t, rows = kb["type"], kb["rows"]
    if t == "inline" and rows:
        out = []
        for row in rows:
            r = []
            for b in row:
                btn = {"text": b["text"]}
                if "url" in b:
                    btn["url"] = b["url"]
                else:
                    btn["callback_data"] = b["callbackData"]
                if "style" in b:
                    btn["style"] = b["style"]
                r.append(btn)
            out.append(r)
        return {"inline_keyboard": out}
    if t == "reply" and rows:
        markup: dict[str, Any] = {"keyboard": [[{"text": b["text"]} for b in row] for row in rows],
                                  "resize_keyboard": True}
        if kb.get("placeholder"):
            markup["input_field_placeholder"] = kb["placeholder"]
        return markup
    if t == "force_reply":
        markup = {"force_reply": True}
        if kb.get("placeholder"):
            markup["input_field_placeholder"] = kb["placeholder"]
        return markup
    if t == "remove":
        return {"remove_keyboard": True}
    return None


def bot_request(logical: dict, chat_id: int | str, *, edit_message_id: int | None = None,
                inline_message_id: str | None = None) -> dict[str, Any]:
    """sendMessage, or editMessageText when an existing message is edited in place."""
    params: dict[str, Any] = {"chat_id": chat_id, "text": logical["text"]}
    if logical["parseMode"]:
        params["parse_mode"] = logical["parseMode"]
    markup = reply_markup(logical)
    method = "sendMessage"
    if edit_message_id is not None or inline_message_id is not None:
        method = "editMessageText"
        if inline_message_id is not None:
            params.pop("chat_id")
            params["inline_message_id"] = inline_message_id
        else:
            params["message_id"] = edit_message_id
        if markup is not None and "inline_keyboard" not in markup:
            markup = None  # only an inline keyboard can be attached by an edit
    if markup is not None:
        params["reply_markup"] = markup
    return {"method": method, "params": params}
