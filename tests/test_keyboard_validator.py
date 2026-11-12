"""Check 1-3: disabled buttons, model separation, callback bytes, force_reply edits."""
import json
import os
import subprocess
import sys
import unittest

import _paths
import validate_keyboard as vk

CASES = os.path.join(_paths.ROOT, "tests", "fixtures", "keyboards")


class RegressionFixtures(unittest.TestCase):
    def test_every_fixture_behaves(self):
        for case in _paths.load("tests", "fixtures", "keyboards", "cases.json"):
            with self.subTest(case=case["file"]):
                doc = _paths.load("tests", "fixtures", "keyboards", case["file"])
                prev = _paths.load("tests", "fixtures", "keyboards", case["previous"]) if case.get("previous") else None
                rep = vk.validate(doc, context=case.get("context"), previous=prev)
                if case["expect"] == "ok":
                    self.assertEqual(rep.errors, [])
                else:
                    self.assertTrue(rep.errors, "expected a structural error")
                    self.assertTrue(any(case["field"] in e for e in rep.errors), rep.errors)

    def test_reported_10_2_regression_cli(self):
        """The exact payload from the task: must pass, with no 'unknown field'."""
        p = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "validate_keyboard.py")],
                           input='{"inline_keyboard":[[{"text":"Unavailable","disabled":{}}]]}',
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertNotIn("unknown field", p.stdout)
        self.assertNotIn("found 0", p.stdout)


class Semantics(unittest.TestCase):
    def test_absent_null_false_empty_are_different(self):
        base = {"text": "X"}
        self.assertTrue(vk.validate([[dict(base)]]).errors)                         # absent: no action
        self.assertTrue(vk.validate([[{**base, "disabled": None}]]).errors)         # null
        self.assertTrue(vk.validate([[{**base, "disabled": False}]]).errors)        # false
        self.assertFalse(vk.validate([[{**base, "disabled": {}}]]).errors)          # {}

    def test_force_reply_false_is_noop_on_keyboards(self):
        rep = vk.validate({"inline_keyboard": [[{"text": "A", "callback_data": "a"}]], "force_reply": False})
        self.assertEqual(rep.errors, [])

    def test_absent_previous_force_reply_equals_false(self):
        prev = {"inline_keyboard": [[{"text": "A", "callback_data": "a"}]]}
        now = {"inline_keyboard": [[{"text": "B", "callback_data": "b"}]], "force_reply": False}
        self.assertEqual(vk.validate(now, previous=prev).errors, [])

    def test_errors_and_warnings_are_separate(self):
        rep = vk.validate([[{"text": "Delete account", "callback_data": "del"}]])
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("destructive" in w for w in rep.warnings))

    def test_every_payload_keyboard_is_valid(self):
        root = os.path.join(_paths.EXAMPLES, "payloads")
        for name in sorted(os.listdir(root)):
            doc = _paths.load("examples", "payloads", name)
            for step in doc["steps"]:
                markup = (step.get("params") or {}).get("reply_markup")
                if markup:
                    with self.subTest(payload=name, method=step.get("method")):
                        self.assertEqual(vk.validate(markup).errors, [])


if __name__ == "__main__":
    unittest.main()
