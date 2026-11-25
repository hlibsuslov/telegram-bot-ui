"""Bridge to the rest of the telegram-bot-ui skill (validators, widget builder, tgkit) and to
the optional Studio web client.

This package lives inside the skill (`scripts/bot_ui/`), so the skill root is two levels up.
The web client lives only in a clone or a plugin install of the repository (`studio/web`).
BOT_UI_SKILL_DIR and BOT_UI_STUDIO_DIR override either location.
"""
from __future__ import annotations

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKILL = os.path.normpath(os.path.join(HERE, "..", ".."))
# skills/telegram-bot-ui/scripts/bot_ui -> repository root -> studio
DEFAULT_STUDIO = os.path.normpath(os.path.join(DEFAULT_SKILL, "..", "..", "studio"))


def skill_dir() -> str:
    path = os.environ.get("BOT_UI_SKILL_DIR") or DEFAULT_SKILL
    if not os.path.isfile(os.path.join(path, "SKILL.md")):
        raise RuntimeError(f"telegram-bot-ui skill not found at {path}; set BOT_UI_SKILL_DIR")
    return path


def studio_dir() -> str:
    """Folder that holds `web/` (the Studio client); may not exist in a skill-only install."""
    return os.environ.get("BOT_UI_STUDIO_DIR") or DEFAULT_STUDIO


def web_dir(*parts: str) -> str:
    return os.path.join(studio_dir(), "web", *parts)


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
