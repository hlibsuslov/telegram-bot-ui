#!/usr/bin/env python3
"""Entry point: py -3 studio/bot-ui.py <command> ... (see `--help`).

The bot-ui core lives in the skill (`skills/telegram-bot-ui/scripts/bot_ui/`), so an installed
skill runs the same commands as `tgui.py map ...`; this wrapper keeps the old path working.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "telegram-bot-ui", "scripts"))
from bot_ui.cli import main  # noqa: E402

raise SystemExit(main())
