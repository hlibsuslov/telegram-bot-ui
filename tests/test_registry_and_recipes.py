"""Coverage proof: every 10.3/10.4 row points at an existing section, example and
check; every recipe runs; the payload layer matches the code."""
import contextlib
import io
import os
import re
import runpy
import subprocess
import sys
import unittest

import _paths

REG = _paths.load("recipes", "registry.json")
ROWS = REG["rows"]


def slug(heading: str) -> str:
    h = heading.strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def corpus() -> str:
    out = []
    for base in ("examples", "tests", "references", "recipes"):
        for dirpath, dirs, files in os.walk(os.path.join(_paths.ROOT, base)):
            dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__")]
            for f in files:
                if f.endswith((".py", ".ts", ".json", ".md", ".html")):
                    out.append(open(os.path.join(dirpath, f), encoding="utf-8").read())
    return "\n".join(out)


class Registry(unittest.TestCase):
    def test_counts_match_the_changelog(self):
        self.assertEqual(sum(r["version"] == "10.3" for r in ROWS), 21)   # bullets in "Bot API 10.3"
        self.assertEqual(sum(r["version"] == "10.4" for r in ROWS), 31)   # bullets in "Bot API 10.4"
        self.assertEqual(len({r["id"] for r in ROWS}), 52)

    def test_every_row_is_complete_and_resolves(self):
        text = corpus()
        for r in ROWS:
            with self.subTest(row=r["id"]):
                self.assertIn(r["status"], REG["statuses"])
                for key in ("change", "use", "availability", "symbols"):
                    self.assertTrue(r[key])
                path, _, anchor = r["skill"].partition("#")
                body = _paths.read(path)
                headings = {slug(h) for h in re.findall(r"^#{1,6} (.+)$", body, re.M)}
                self.assertIn(anchor, headings, f"{path} lacks a heading for #{anchor}")
                self.assertTrue(os.path.exists(os.path.join(_paths.ROOT, r["recipe"])))
                self.assertTrue(os.path.exists(os.path.join(_paths.ROOT, r["example"])), r["example"])
                file, _, name = r["check"].partition("::")
                src = _paths.read(file)
                if name:
                    self.assertRegex(src, rf"(def|class) {re.escape(name)}\b")
                for sym in r["symbols"]:
                    self.assertGreaterEqual(text.count(sym), 2, f"symbol {sym} not exemplified")

    def test_markdown_registry_is_generated_from_json(self):
        p = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "render_registry.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_manifest_covers_every_row_once(self):
        man = _paths.load("recipes", "manifest.json")
        ids = [i for rec in man["recipes"] for i in rec["registry"]]
        self.assertEqual(sorted(ids), sorted(r["id"] for r in ROWS))
        for rec in man["recipes"]:
            for key in ("doc", "payload", "python"):
                self.assertTrue(os.path.exists(os.path.join(_paths.ROOT, rec[key])), rec[key])

    def test_recipes_follow_the_ten_point_format(self):
        for rec in _paths.load("recipes", "manifest.json")["recipes"][:-1]:
            body = _paths.read(rec["doc"])
            for n in range(1, 11):
                self.assertRegex(body, rf"(?m)^{n}\. \*\*", f"{rec['doc']} misses point {n}")


class Recipes(unittest.TestCase):
    def test_every_python_recipe_runs_and_checks_itself(self):
        folder = os.path.join(_paths.EXAMPLES, "python", "recipes")
        for f in sorted(os.listdir(folder)):
            if f.endswith(".py") and not f.startswith("_"):
                with self.subTest(recipe=f), contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(os.path.join(folder, f), run_name="__main__")

    def test_payload_files_match_the_code(self):
        p = subprocess.run([sys.executable, os.path.join(_paths.EXAMPLES, "python", "export_payloads.py"), "--check"],
                           capture_output=True, text=True, cwd=_paths.ROOT)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_widget_validator_cli(self):
        p = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "validate_widget.py"),
                            os.path.join(_paths.EXAMPLES, "widgets", "order-card.html"), "--caption", "Order", "--context", "group"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 1)
        self.assertIn("test-server only", p.stdout)


if __name__ == "__main__":
    unittest.main()
