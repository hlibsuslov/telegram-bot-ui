"""Recipes 40-49: ten-point format, and every path a recipe names exists."""
import glob
import os
import re
import unittest

import _paths

PATH_RE = re.compile(r"(?:examples|references|recipes|scripts|tests)/[A-Za-z0-9._/-]+")


class AgentRecipes(unittest.TestCase):
    def docs(self):
        files = sorted(glob.glob(os.path.join(_paths.ROOT, "recipes", "4[0-9]-*.md")))
        self.assertEqual(len(files), 10)
        return files

    def test_ten_point_format(self):
        for f in self.docs():
            body = open(f, encoding="utf-8").read()
            for n in range(1, 11):
                self.assertRegex(body, rf"(?m)^{n}\. \*\*", f"{f} misses point {n}")

    def test_named_paths_exist_and_each_recipe_has_code_and_payload(self):
        for f in self.docs():
            body = open(f, encoding="utf-8").read()
            for p in PATH_RE.findall(body):
                p = p.rstrip(".,:;)").split("::")[0]
                self.assertTrue(os.path.exists(os.path.join(_paths.ROOT, p)), f"{os.path.basename(f)}: {p}")
            n = os.path.basename(f)[:2]
            self.assertIn(f"examples/payloads/r{n}-", body)
            self.assertTrue(glob.glob(os.path.join(_paths.EXAMPLES, "python", "recipes", f"r{n}_*.py")))


if __name__ == "__main__":
    unittest.main()
