"""The knowledge base works as one system: one route per topic, no links to moved sections,
duplicated maps kept in step.
"""
from __future__ import annotations

import os
import re
import unittest

import _paths

REF = os.path.join(_paths.ROOT, "references")
LINK = re.compile(r"\]\(([^)#]+\.md)")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start:nxt if nxt > 0 else len(text)]


class MiniAppRoutes(unittest.TestCase):
    def test_agent_route_and_people_map_name_the_same_files(self):
        agent = set(LINK.findall(section(read(REF, "mini-apps", "orchestration.md"), "## 1. What to load")))
        people = set(LINK.findall(section(read(REF, "mini-apps", "README.md"), "## Route by task")))
        agent -= {"orchestration.md", "README.md"}
        people.discard("orchestration.md")
        agent = {a for a in agent if not a.startswith("../")}
        self.assertEqual(sorted(people - agent), [], "in README's map but not in orchestration §1")
        self.assertEqual(sorted(agent - people), [], "in orchestration §1 but not in README's map")

    def test_the_playbook_does_not_hop_through_both_tables(self):
        book = read(_paths.ROOT, "commands", "mini-app.md")
        self.assertIn("orchestration.md` §1", book)
        self.assertNotIn("Route by task", book)


class MovedSections(unittest.TestCase):
    """SKILL.md became a router in 3.2.0; nothing may still send the agent to its old sections."""

    OLD = ("initiative rule", "Core workflow", "Pick the capability", "Which reference to read",
           "non-negotiable rules", "Mode: how much process", "Buttons essentials")

    def test_no_reference_points_to_a_removed_skill_section(self):
        hits = []
        for folder in ("references", "recipes", "commands"):
            base = os.path.join(_paths.ROOT, folder)
            for dirpath, _dirs, files in os.walk(base):
                for name in files:
                    if not name.endswith(".md"):
                        continue
                    text = read(dirpath, name)
                    hits += [f"{name}: {old}" for old in self.OLD if old.lower() in text.lower()]
        self.assertEqual(hits, [])


class PlaybookLinks(unittest.TestCase):
    """A Markdown link in SKILL.md or a playbook is relative to the file that holds it."""

    def test_links_resolve_from_the_file_not_from_the_skill_root(self):
        import shutil
        import tempfile
        import validate_references as vr
        root = tempfile.mkdtemp(prefix="tgui-links-")
        self.addCleanup(shutil.rmtree, root, True)
        for folder in ("commands", "references"):
            os.makedirs(os.path.join(root, folder))
        for rel, body in (("SKILL.md", "[a](references/a.md)"), ("commands/fix.md", "[b](../references/b.md) and "
                                                                                  "[c](sibling.md#x) and [d](https://x.dev/y.md)")):
            with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.write(body)
        self.assertEqual(vr.collect_referenced_paths(root), {"references/a.md", "references/b.md",
                                                             "commands/sibling.md"})


class Anchors(unittest.TestCase):
    """`file.md#heading` in a reference, recipe or playbook (link or code span) names a heading that exists."""

    MENTION = re.compile(r"(?<![\w/.-])((?:references|commands|recipes)/)?([\w./-]+\.md)#([\w%-]+)")

    @staticmethod
    def slug(heading: str) -> str:
        return re.sub(r"\s", "-", re.sub(r"[^\w\- ]", "", heading.strip().lower().strip("# ")))

    def headings(self, path: str) -> set[str]:
        return {self.slug(m.group(1)) for m in re.finditer(r"^#{1,6} +(.+?) *$", read(path), re.M)}

    def test_every_anchor_resolves(self):
        broken = []
        for folder in ("references", "recipes", "commands"):
            for dirpath, _dirs, files in os.walk(os.path.join(_paths.ROOT, folder)):
                for name in sorted(files):
                    if not name.endswith(".md"):
                        continue
                    here = os.path.join(dirpath, name)
                    for m in self.MENTION.finditer(read(here)):
                        prefix, target, anchor = m.groups()
                        candidates = [os.path.join(_paths.ROOT, prefix or "", target), os.path.join(dirpath, target),
                                      os.path.join(REF, target)]
                        found = next((c for c in candidates if os.path.isfile(c)), None)
                        if found and anchor not in self.headings(found):
                            broken.append(f"{os.path.relpath(here, _paths.ROOT)}: {target}#{anchor}")
        self.assertEqual(broken, [])



class FormattingDocsMatchSources(unittest.TestCase):
    """regular-formatting.md lists what the validator allows and what the catalog defines (both drifted once)."""

    def setUp(self):
        import json as _json
        import os as _os
        import sys as _sys
        self.ref = open(_os.path.join(_paths.ROOT, "references", "regular-formatting.md"), encoding="utf-8").read()
        _sys.path.insert(0, _os.path.join(_paths.ROOT, "scripts"))
        import audit_copy
        self.allowed = audit_copy.ALLOWED
        with open(_os.path.join(_paths.ROOT, "data", "bot-api", "catalog.json"), encoding="utf-8") as fh:
            self.cat = _json.load(fh)

    def test_every_allowed_html_tag_is_documented(self):
        missing = [t for t in sorted(self.allowed) if t not in ("span",) and f"<{t}" not in self.ref]
        self.assertEqual(missing, [])

    def test_every_entity_type_in_the_catalog_is_documented(self):
        import re as _re
        field = next(f for f in self.cat["types"]["MessageEntity"]["fields"] if f["name"] == "type")
        types = _re.findall(r"“([a-z_]+)”|\"([a-z_]+)\"", field["description"])
        names = {a or b for a, b in types}
        self.assertGreater(len(names), 15)
        self.assertEqual(sorted(n for n in names if f"`{n}`" not in self.ref), [])


def catalog():
    import json
    with open(os.path.join(_paths.ROOT, "data", "bot-api", "catalog.json"), encoding="utf-8") as fh:
        return json.load(fh)


def field_names(cat, type_name: str) -> list[str]:
    return [f["name"] for f in cat["types"][type_name]["fields"]]


class ApiListsMatchTheCatalog(unittest.TestCase):
    """Counts and field lists that the knowledge audit found short of the catalog (2026-11-25)."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.cat = catalog()
        with open(os.path.join(_paths.ROOT, "data", "bot-api", "changelog.json"), encoding="utf-8") as fh:
            cls.log = json.load(fh)

    def test_richtext_class_count_is_the_one_10_1_added(self):
        rel = next(r for r in self.log["releases"] if r["version"] == "10.1")
        added = {s for g in rel["groups"] for i in g["items"] if i["text"].startswith("Added the classes RichText")
                 for s in i["symbols"] if s.startswith("RichText")}
        self.assertGreater(len(added), 20)
        for name in ("telegram-capabilities.md", "official-sources.md"):
            counts = [int(n) for n in re.findall(r"(\d+) `RichText\*`", read(REF, name))]
            self.assertTrue(counts, name)
            self.assertEqual(set(counts), {len(added)}, name)

    def test_inline_keyboard_table_lists_every_button_action(self):
        actions = set(field_names(self.cat, "InlineKeyboardButton")) - {"text", "style", "icon_custom_emoji_id"}
        rows = set(re.findall(r"^\| `(\w+)` \|", section(read(REF, "inline-keyboards.md"), "## Button types"), re.M))
        self.assertEqual(sorted(actions - rows), [])

    def test_link_preview_option_lists_are_complete(self):
        fields = field_names(self.cat, "LinkPreviewOptions")
        text = read(REF, "official-sources.md")
        lists = [item for item in re.split(r"\n- ", text) if "`prefer_small_media`" in item]
        self.assertTrue(lists)
        for item in lists:
            self.assertEqual([f for f in fields if f"`{f}`" not in item], [], item[:60])

    def test_shared_widget_query_lists_every_field(self):
        line = next(ln for ln in read(REF, "widgets.md").splitlines() if "`shared_widget_query` (" in ln)
        listed = re.findall(r"`(\w+)`", line.split("`shared_widget_query` (", 1)[1].split(")", 1)[0])
        self.assertEqual(sorted(listed), sorted(field_names(self.cat, "SharedWidgetQuery")))

    def test_rich_media_names_every_media_block_and_link_scheme(self):
        text = read(REF, "rich-media.md")
        types = self.cat["types"]
        blocks = [n for n in types["InputRichBlock"]["subtypes"]
                  if any("InputMedia" in str(f.get("type")) for f in types[n]["fields"])]
        self.assertGreaterEqual(len(blocks), 6)
        self.assertEqual([b for b in blocks if f"`{b}`" not in text], [])
        media = next(f for f in types["InputRichMessage"]["fields"] if f["name"] == "media")
        schemes = re.findall(r"tg://\w+\?id=", media["description"])
        self.assertEqual([s for s in schemes if f"`{s}`" not in text], [])


class VerificationStamps(unittest.TestCase):
    """A reference's opening "Checked/Verified against Bot API X" names the version in its front matter."""

    STAMP = re.compile(r"(?i)(?<![-\w])(?:checked|verified)\b[^.]{0,80}?(?:against|\()[^.]{0,40}?Bot API \**(\d+\.\d+)")

    def test_intro_stamp_matches_front_matter(self):
        stale = []
        for dirpath, _dirs, files in os.walk(REF):
            for name in sorted(files):
                if not name.endswith(".md"):
                    continue
                text = read(dirpath, name)
                head = re.match(r"---\n(.*?)\n---\n", text, re.S)
                if not head:
                    continue
                version = re.search(r'^bot_api: "?([\d.]+)', head.group(1), re.M)
                stamp = self.STAMP.search(" ".join(text[head.end():].splitlines()[:25]))
                if version and stamp and stamp.group(1) != version.group(1):
                    stale.append(f"{name}: front matter {version.group(1)}, intro {stamp.group(1)}")
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
