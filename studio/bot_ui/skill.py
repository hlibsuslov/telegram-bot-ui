"""Bridge to the telegram-bot-ui skill: its validators, widget builder and tgkit.

The Studio is an optional package next to the skill, so the skill keeps one owner for
Telegram rules (keyboards, regular HTML, widget limits). BOT_UI_SKILL_DIR overrides the
location, for example an installed copy of the skill.
"""
from __future__ import annotations

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKILL = os.path.normpath(os.path.join(HERE, "..", "..", "skills", "telegram-bot-ui"))


def skill_dir() -> str:
    path = os.environ.get("BOT_UI_SKILL_DIR") or DEFAULT_SKILL
    if not os.path.isfile(os.path.join(path, "SKILL.md")):
        raise RuntimeError(f"telegram-bot-ui skill not found at {path}; set BOT_UI_SKILL_DIR")
    return path


def _ensure_path() -> None:
    root = skill_dir()
    for sub in ("scripts", os.path.join("examples", "python")):
        p = os.path.join(root, sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def load(name: str):
    """Import a skill module by name: 'validate_keyboard', 'build_widget', 'tgkit.transport', ..."""
    _ensure_path()
    return importlib.import_module(name)


def kit_dir() -> str:
    return os.path.join(skill_dir(), "examples", "widgets", "_kit")
