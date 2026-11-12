"""One icon system for buttons AND text (custom emoji, Bot API 6.2 / 9.4).

* Buttons: `icon_custom_emoji_id` shows the icon before the label; the label itself
  carries no emoji then (no double icon).
* Text: `<tg-emoji emoji-id="…">⚙️</tg-emoji>` in regular HTML (or a custom_emoji entity)
  uses the SAME id, so a screen title and its button speak one visual language.
* Eligibility (API): custom emoji on buttons / in text need Fragment usernames, or messages
  sent directly by the bot to private/group/supergroup chats while the owner has Premium.
  When not eligible (or the kill switch is off) everything degrades together to the Unicode
  fallback - never icons on some buttons and emoji on others.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any


@dataclass
class IconSystem:
    icons: dict[str, dict[str, Any]]     # slot -> {"id", "fallback", "set", ...}
    enabled: bool = True                  # owner Premium / Fragment eligibility, env kill switch
    unicode_fallback: bool = True         # False = label-only when custom emoji are off

    def button(self, text: str, slot: str | None = None, *, style: str | None = None, **action: Any) -> dict[str, Any]:
        b: dict[str, Any] = {"text": text, **action}
        icon = self.icons.get(slot or "")
        if icon and self.enabled:
            b["icon_custom_emoji_id"] = icon["id"]
        elif icon and self.unicode_fallback and icon.get("fallback"):
            b["text"] = f"{icon['fallback']} {text}"
        if style:
            b["style"] = style
        return b

    def text(self, slot: str) -> str:
        """Icon for regular-HTML message text (escape the rest of the text yourself)."""
        icon = self.icons.get(slot)
        if not icon:
            return ""
        fb = html.escape(icon.get("fallback") or "•")
        if self.enabled:
            return f'<tg-emoji emoji-id="{icon["id"]}">{fb}</tg-emoji>'
        return fb if self.unicode_fallback else ""

    def title(self, slot: str, title: str) -> str:
        prefix = self.text(slot)
        return f"<b>{prefix + ' ' if prefix else ''}{html.escape(title)}</b>"
