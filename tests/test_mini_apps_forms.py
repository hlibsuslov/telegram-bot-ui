"""forms-and-data.md, the kit's api() and hideKeyboard(), the stand's Network control and lint MA40-MA41 agree."""
import json
import os
import re
import tempfile
import unittest

import _paths
import miniapp_lint as lint

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
KIT = os.path.join(_paths.ROOT, "examples", "mini-apps", "_kit")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def lint_text(name, text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return [f.rule for f in lint.lint_files([p], d).findings]


class Reference(unittest.TestCase):
    doc = read(REF, "forms-and-data.md")

    def test_sections(self):
        for n in range(0, 12):
            self.assertRegex(self.doc, rf"\n## {n}\. ")

    def test_every_error_kind_has_a_row_and_exists_in_the_kit(self):
        ts = read(KIT, "tma.ts")
        kinds = re.search(r"export type ApiErrorKind = ([^;]+);", ts).group(1)
        for kind in re.findall(r"'(\w+)'", kinds):
            self.assertRegex(self.doc, rf"\| `{kind}` \|", kind)

    def test_cross_references_point_at_real_sections(self):
        for ref, num in re.findall(r"\b([a-z-]+) §(\d+)", self.doc):
            path = os.path.join(REF, ref + ".md")
            if os.path.exists(path):
                self.assertRegex(read(path), rf"\n## {num}\. ", f"{ref} §{num}")

    def test_cloudstorage_limits_match_the_catalog(self):
        cat = read(_paths.ROOT, "data", "mini-apps", "webapp-catalog.json")
        flat = " ".join(self.doc.split())
        for fact in ("1024 keys", "4096 characters", "1-128 characters"):
            self.assertIn(fact.split()[0], cat)
            self.assertIn(fact, flat)

    def test_members_cited_exist_with_their_versions(self):
        cat = json.loads(read(_paths.ROOT, "data", "mini-apps", "webapp-catalog.json"))
        since = {m["name"]: m["version"] for m in cat["members"].values() if m.get("owner") == "WebApp"}
        cited = re.findall(r"`(\w+)\(\)` \((\d+\.\d+)\)", self.doc)
        self.assertGreaterEqual(len(cited), 4)
        for name, ver in cited:
            self.assertEqual(since.get(name), ver, name)

    def test_routed(self):
        for f in ("README.md", "orchestration.md", "components.md", "security.md"):
            self.assertIn("forms-and-data.md", read(REF, f), f)
        self.assertIn("references/mini-apps/forms-and-data.md", read(_paths.ROOT, "SKILL.md"))


class Kit(unittest.TestCase):
    def test_api_and_keyboard_exported(self):
        ts = read(KIT, "tma.ts")
        for piece in ("export class ApiError", "export function idempotencyKey(", "async function api<", "function hideKeyboard("):
            self.assertIn(piece, ts)
        self.assertRegex(ts, r"return \{[^}]*\bapi, hideKeyboard\b")
        self.assertIn("Authorization: `tma ${tg?.initData", ts)

    def test_stand_network_modes(self):
        src = read(_paths.ROOT, "scripts", "preview_miniapp.py")
        for mode in ("slow", "flaky", "offline", 'value="error"', 'value="session"'):
            self.assertIn(mode, src)
        self.assertIn("url.pathname.indexOf('/app/') !== 0", src, "the app's own files are never broken")


class Lint(unittest.TestCase):
    def test_ma40_number_inputs(self):
        self.assertIn("MA40", lint_text("a.html", '<input id="a" type="number" aria-label="Amount">'))
        self.assertIn("MA40", lint_text("a.tsx", 'const f = <input type="number" aria-label="Amount" />;\n'))
        self.assertNotIn("MA40", lint_text("a.html", '<input type="text" inputmode="decimal" aria-label="Amount">'))

    def test_ma41_autofocus(self):
        self.assertIn("MA41", lint_text("a.html", '<input aria-label="Name" autofocus>'))
        self.assertIn("MA41", lint_text("a.tsx", 'const f = <input aria-label="Name" autoFocus />;\n'))
        self.assertNotIn("MA41", lint_text("a.ts", "title.focus();\n"))


if __name__ == "__main__":
    unittest.main()
