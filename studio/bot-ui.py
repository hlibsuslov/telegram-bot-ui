#!/usr/bin/env python3
"""Entry point: py -3 studio/bot-ui.py <command> ... (see `--help`)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot_ui.cli import main  # noqa: E402

raise SystemExit(main())
