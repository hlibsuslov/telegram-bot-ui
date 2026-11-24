"""The rework planner (scripts/miniapp_rework.py) on the generated web-style app in tests/fixtures/miniapp_rework."""
import contextlib
import io
import json
import os
import unittest

import _paths
import miniapp_lint as lint
import miniapp_rework as rework

BEFORE = os.path.join(_paths.REPO, "tests", "fixtures", "miniapp_rework", "before")


class Plan(unittest.TestCase):
    plan = rework.plan(BEFORE)

    def items(self):
        return {i["rule"]: (st["stage"], i) for st in self.plan["stages"] for i in st["items"]}

    def test_every_lint_rule_has_a_replacement_and_a_stage(self):
        data = rework.load_map()
        self.assertEqual(set(data["rules"]), set(lint.RULES))
        for rule, row in data["rules"].items():
            self.assertIn(str(row["stage"]), data["stages"], rule)
            self.assertTrue(row["telegram"] and row["ref"], rule)

    def test_security_comes_first_and_slop_late(self):
        items = self.items()
        for rule in ("MA25", "MA26", "MA27", "MA33"):
            self.assertEqual(items[rule][0], 1, rule)
        for rule in ("MA03", "MA07", "MA19", "MA30", "MA18"):
            self.assertEqual(items[rule][0], 2, rule)
        self.assertEqual(items["MA29"][0], 3)
        self.assertEqual(items["MA05"][0], 4)
        for rule in ("MA31", "MA32", "MA13", "stat-cards", "price-pill", "nested-cards", "ribbon"):
            self.assertEqual(items[rule][0], 5, rule)
        self.assertIn("sticky-header", items)
        stages = [st["stage"] for st in self.plan["stages"]]
        self.assertEqual(stages, sorted(stages))

    def test_colour_map(self):
        roles = {c["colour"].lower(): c["role"] for c in self.plan["colours"]}
        self.assertTrue(roles["#6c5ce7"].startswith("brand candidate"))
        self.assertTrue(roles["#f5f3ff"].startswith("--tma-page"))
        self.assertEqual(roles["#1a1a2e"], "--tma-text")
        self.assertEqual(roles["#ff4757"], "--tma-danger")
        self.assertEqual(roles["#ddd"], "--tma-separator")
        self.assertTrue(roles["rgba(108, 92, 231, .6)"].startswith("drop"))
        self.assertTrue(roles["#00cec9"].startswith("drop: gradient"))

    def test_type_map(self):
        sizes = {s["px"]: s for s in self.plan["type"]["sizes"]}
        self.assertEqual(sizes[34]["role"], "large-title")
        self.assertEqual(sizes[22]["role"], "title2")
        self.assertIn("floor", sizes[9]["note"])
        self.assertEqual([f["family"] for f in self.plan["type"]["families"]][:1], ["Poppins"])

    def test_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(rework.main(["plan", BEFORE]), 0)
        text = buf.getvalue()
        self.assertIn("## Stage 1. Security and payments", text)
        self.assertIn("Brand: keep `#6c5ce7`", text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rework.main(["plan", BEFORE, "--json"])
        self.assertEqual(json.loads(buf.getvalue())["errors"], self.plan["errors"])

    def test_kit_apps_plan_nothing_to_fix(self):
        for app in ("vanilla", "catalog", "portfolio", "gallery", "react"):
            with self.subTest(app=app):
                clean = rework.plan(os.path.join(_paths.ROOT, "examples", "mini-apps", app))
                self.assertEqual((clean["errors"], clean["warnings"]), (0, 0))
                self.assertEqual([i["rule"] for st in clean["stages"] for i in st["items"]], [])

    def test_bridge_maps_every_shadcn_token_to_a_kit_role(self):
        with open(os.path.join(_paths.ROOT, "examples", "mini-apps", "_kit", "tma-bridge.css"), encoding="utf-8") as fh:
            css = fh.read()
        with open(os.path.join(_paths.ROOT, "examples", "mini-apps", "_kit", "tma.css"), encoding="utf-8") as fh:
            kit = fh.read()
        for token in ("background", "foreground", "card", "primary", "primary-foreground", "muted-foreground",
                      "destructive", "border", "input", "ring", "radius"):
            self.assertRegex(css, rf"--{token}: var\(--tma-[a-z-]+\);", token)
        for role in set(__import__("re").findall(r"var\((--tma-[a-z0-9-]+)\)", css)):
            self.assertIn(role + ":", kit, role)
        self.assertEqual(lint.COLOR.findall(lint.COMMENT_CSS.sub("", css)), [])


if __name__ == "__main__":
    unittest.main()
