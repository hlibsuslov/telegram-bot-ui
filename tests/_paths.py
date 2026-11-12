"""Import paths for the offline tests (standard library unittest only)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")
for p in (os.path.join(EXAMPLES, "python"), os.path.join(EXAMPLES, "python", "recipes"),
          os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()
