#!/usr/bin/env python3
"""Check an HTML widget before sendWidget (Bot API 10.4). Offline, no token.

Errors: > 32768 UTF-8 bytes; > 4096 bytes after zlib level 9 (counted exactly
like the server, per the Widgets guide); NUL; chat_data / public_data > 1024
UTF-8 bytes; secrets in code or public state; a context that production does
not offer (groups, inline, forwards are test-server only on 2026-11-12).
Warnings: no caption; browser features a widget doesn't have (network, form
controls, external resources, vh, scrolling, dialogs, keyboard/touch events…).

The runtime warnings are pattern-based (a heuristic, not a parser): a clean
report does not prove the widget renders - test it in Telegram clients.

Usage:
  python scripts/validate_widget.py widget.html [--caption TEXT] [--chat-data JSON]
         [--public-data JSON] [--context private|group|supergroup|inline|forward]
         [--environment production|test]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "python"))
from tgkit.widgets import check_widget  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--caption")
    ap.add_argument("--chat-data")
    ap.add_argument("--public-data")
    ap.add_argument("--context", default="private")
    ap.add_argument("--environment", default="production", choices=("production", "test"))
    a = ap.parse_args(argv)
    with open(a.file, encoding="utf-8") as fh:
        html = fh.read()
    rep = check_widget(html, caption=a.caption, chat_data=a.chat_data, public_data=a.public_data,
                       context=a.context, environment=a.environment)
    for w in rep.warnings:
        print(f"WARN: {w}")
    for e in rep.errors:
        print(f"FAIL: {e}")
    print(f"\nsize: {rep.raw_bytes} bytes raw, {rep.compressed_bytes} bytes zlib-9 "
          f"(limits 32768 / 4096). {'INVALID' if rep.errors else 'OK'}.")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
