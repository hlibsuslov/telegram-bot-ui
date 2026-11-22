"""Shared helpers for the bot-ui (studio/) tests."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO = os.path.join(ROOT, "studio")
TEMPLATE = os.path.join(STUDIO, "templates", "checkout")
FIXTURES = os.path.join(STUDIO, "fixtures")
CLI = os.path.join(STUDIO, "bot-ui.py")
if STUDIO not in sys.path:
    sys.path.insert(0, STUDIO)
if os.path.join(STUDIO, "adapters") not in sys.path:
    sys.path.insert(0, os.path.join(STUDIO, "adapters"))


class ProjectCase(unittest.TestCase):
    """Each test gets a fresh copy of the checkout template under a path with a space and Cyrillic."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="bot-ui-test-")
        self.root = os.path.join(self._tmp, "мой бот", "bot-ui")
        shutil.copytree(TEMPLATE, self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def read(self, rel: str) -> dict:
        with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8") as fh:
            return json.load(fh)

    def raw(self, rel: str) -> bytes:
        with open(os.path.join(self.root, *rel.split("/")), "rb") as fh:
            return fh.read()

    def write_raw(self, rel: str, data: bytes) -> None:
        with open(os.path.join(self.root, *rel.split("/")), "wb") as fh:
            fh.write(data)
