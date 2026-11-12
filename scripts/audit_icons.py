#!/usr/bin/env python3
"""Audit a bot's icon system: one consistent custom-emoji family per bot.

Input: an icon map JSON (offline, no token):
  {"bot": "...", "icons": {"<slot>": {"id": "<custom_emoji_id>", "set": "<sticker set name>",
     "fallback": "<unicode emoji or ''>", "animated": false, "family": "<optional style family>"}},
   "text_prefixes": {"<slot>": "<unicode emoji used in message text for the same meaning>"}}
`set` is Sticker.set_name from getCustomEmojiStickers; `animated` = is_animated or is_video.
Build the map live with examples/python/icons/build_icon_map.py.

Errors (exit 1): non-numeric ids; the same id used for two meanings; missing fallback.
Warnings: icons from more than one set / family; animated mixed with static; a slot whose
text prefix differs from its button fallback (two visual languages for one meaning);
a set contributing a single icon (likely a gap-filler from another style).

These are design rules of this skill (Heuristic), not Bot API requirements.
Usage: python scripts/audit_icons.py icon-map.json [--max-sets 1]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ID_RE = re.compile(r"^\d{5,}$")


def audit(doc: dict, max_sets: int = 1):
    errors: list[str] = []
    warnings: list[str] = []
    icons: dict = doc.get("icons", {})
    by_id = defaultdict(list)
    sets = Counter()
    families = Counter()
    animated = Counter()
    for slot, icon in icons.items():
        iid = str(icon.get("id", ""))
        if not ID_RE.match(iid):
            errors.append(f"{slot}: id {iid!r} is not a custom_emoji_id (numeric string)")
        by_id[iid].append(slot)
        if not icon.get("fallback") and icon.get("fallback") != "":
            errors.append(f"{slot}: no Unicode fallback (use '' to mean 'label only')")
        sets[icon.get("set") or "<unknown>"] += 1
        families[icon.get("family") or icon.get("set") or "<unknown>"] += 1
        animated[bool(icon.get("animated"))] += 1
    for iid, slots in by_id.items():
        if len(slots) > 1:
            errors.append(f"id {iid} is used for different meanings: {', '.join(sorted(slots))}")
    if "<unknown>" in sets:
        warnings.append(f"{sets['<unknown>']} icon(s) without a recorded set - resolve with getCustomEmojiStickers")
    real_sets = {k: v for k, v in sets.items() if k != "<unknown>"}
    if len(families) > max_sets:
        warnings.append(f"{len(families)} icon families on one bot ({', '.join(f'{k}×{v}' for k, v in families.most_common())}) "
                        f"- pick one family; fill gaps from its sibling pack or drop the icon")
    family_of = {(i.get("set") or "<unknown>"): (i.get("family") or i.get("set") or "<unknown>") for i in icons.values()}
    for name, n in real_sets.items():
        if n == 1 and len(real_sets) > 1 and families[family_of[name]] == 1:
            warnings.append(f"set {name!r} supplies a single icon - a likely style outlier")
    if animated[True] and animated[False]:
        warnings.append(f"{animated[True]} animated and {animated[False]} static icons mixed - choose one")
    for slot, prefix in (doc.get("text_prefixes") or {}).items():
        fb = (icons.get(slot) or {}).get("fallback")
        if fb is not None and prefix and fb and prefix != fb:
            warnings.append(f"{slot}: text uses {prefix!r} but the button fallback is {fb!r} - one symbol per meaning")
    return errors, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--max-sets", type=int, default=1, help="allowed families (default 1)")
    a = ap.parse_args(argv)
    doc = json.load(open(a.file, encoding="utf-8"))
    errors, warnings = audit(doc, a.max_sets)
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    print(f"\n{len(doc.get('icons', {}))} icon(s): {len(errors)} error(s), {len(warnings)} warning(s). "
          f"{'INVALID' if errors else 'OK'}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
