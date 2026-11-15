"""Import paths for the offline tests (standard library unittest only).

REPO is the repository root (tests, adapters, agents, plugin manifests); ROOT is the
skill folder, skills/telegram-bot-ui/, that installers copy.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, "skills", "telegram-bot-ui")
TESTS = os.path.join(REPO, "tests")
EXAMPLES = os.path.join(ROOT, "examples")
for p in (os.path.join(EXAMPLES, "python"), os.path.join(EXAMPLES, "python", "recipes"),
          os.path.join(ROOT, "scripts"), os.path.join(REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def resolve(rel):
    """A path named inside the skill: `tests/...` lives at the repo root, the rest in the skill."""
    return os.path.join(REPO if rel.startswith("tests/") else ROOT, *rel.split("/"))


def load_repo(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()
