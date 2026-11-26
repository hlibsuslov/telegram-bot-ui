"""Check 1-3: disabled buttons, model separation, callback bytes, force_reply edits."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths
import validate_keyboard as vk

CASES = os.path.join(_paths.TESTS, "fixtures", "keyboards")


class RegressionFixtures(unittest.TestCase):
    def test_every_fixture_behaves(self):
        for case in _paths.load_repo("tests", "fixtures", "keyboards", "cases.json"):
            with self.subTest(case=case["file"]):
                doc = _paths.load_repo("tests", "fixtures", "keyboards", case["file"])
                prev = _paths.load_repo("tests", "fixtures", "keyboards", case["previous"]) if case.get("previous") else None
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


LIBRARY = {"format": "bot-ui-emoji/v1", "bot": "", "icons": {}, "packs": {"demo": {"emoji": [
    {"id": "1111111111", "fallback": "🏠", "format": "static"},
    {"id": "2222222222", "fallback": "🔥", "format": "animated"},
    {"id": "3333333333", "fallback": "🎬", "format": "video"}]}}}
MOVING = {"2222222222": "animated", "3333333333": "video"}


def custom_emoji(eid):
    return {"type": "custom_emoji", "custom_emoji_id": eid, "alternative_text": "x"}


class MovingEmojiOnButtons(unittest.TestCase):
    """--emoji-library: a button never carries an animated or video custom emoji (BUTTON_EMOJI_ANIMATED)."""

    def test_an_inline_or_reply_icon_that_moves_is_an_error(self):
        icons = [{"text": t, "callback_data": t, "icon_custom_emoji_id": i} for t, i in
                 (("Home", "1111111111"), ("Fire", "2222222222"), ("Film", "3333333333"), ("Own", "4444444444"))]
        rep = vk.validate([icons], moving_emoji=MOVING)
        self.assertEqual(len(rep.errors), 2, rep.errors)
        self.assertTrue(all("BUTTON_EMOJI_ANIMATED" in e for e in rep.errors))
        self.assertIn("animated", rep.errors[0])
        self.assertIn("video", rep.errors[1])
        reply = vk.validate({"keyboard": [[{"text": "Fire", "icon_custom_emoji_id": "2222222222"}]]}, moving_emoji=MOVING)
        self.assertEqual(len(reply.errors), 1, reply.errors)

    def test_without_the_library_nothing_changes(self):
        kb = [[{"text": "Fire", "callback_data": "f", "icon_custom_emoji_id": "2222222222"}]]
        self.assertEqual(vk.validate(kb).errors, [])
        self.assertEqual(vk.validate(kb, moving_emoji={}).errors, [])

    def test_a_rich_button_with_a_moving_custom_emoji_in_its_text_is_an_error(self):
        def blocks(*texts):
            return {"blocks": [{"type": "buttons", "buttons": [{"text": t, "callback_data": "g"} for t in texts]}]}

        doc = blocks([custom_emoji("2222222222"), " Go"], [custom_emoji("1111111111"), " Home"], "Plain",
                     [custom_emoji("3333333333"), " Film"])
        rep = vk.validate(doc, moving_emoji=MOVING)
        self.assertEqual(len(rep.errors), 2, rep.errors)
        self.assertTrue(all("BUTTON_EMOJI_ANIMATED" in e for e in rep.errors))
        self.assertEqual(vk.validate(doc).errors, [])
        inline = {"blocks": [{"type": "paragraph", "text": [
            {"type": "button", "button": {"text": [custom_emoji("2222222222"), " Go"], "callback_data": "g"}, "text": "Go"}]}]}
        self.assertTrue(any("BUTTON_EMOJI_ANIMATED" in e for e in vk.validate(inline, moving_emoji=MOVING).errors))

    def test_html_button_text_is_read_for_custom_emoji(self):
        html = ('<p><tg-emoji emoji-id="2222222222">🔥</tg-emoji> Fire</p>'
                '<tg-button type="callback_data" data="g"><tg-emoji emoji-id="3333333333">🎬</tg-emoji> Film</tg-button>'
                '<tg-button type="callback_data" data="h"><tg-emoji emoji-id="1111111111">🏠</tg-emoji> Home</tg-button>')
        found = vk.moving_in_html(html, MOVING)
        self.assertEqual(len(found), 1, "the emoji in the paragraph is text, not a button")
        self.assertIn("3333333333", found[0])

    def test_the_cli_reads_the_project_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, kb = os.path.join(tmp, "library.json"), os.path.join(tmp, "kb.json")
            with open(lib, "w", encoding="utf-8") as fh:
                json.dump(LIBRARY, fh)
            with open(kb, "w", encoding="utf-8") as fh:
                json.dump([[{"text": "Fire", "callback_data": "f", "icon_custom_emoji_id": "2222222222"}]], fh)
            script = os.path.join(_paths.ROOT, "scripts", "validate_keyboard.py")

            def run(*args):
                return subprocess.run([sys.executable, script, kb, *args], capture_output=True, text=True, encoding="utf-8")

            self.assertEqual(run().returncode, 0)
            bad = run("--emoji-library", lib)
            self.assertEqual(bad.returncode, 1, bad.stdout)
            self.assertIn("BUTTON_EMOJI_ANIMATED", bad.stdout)
            missing = run("--emoji-library", os.path.join(tmp, "nope.json"))
            self.assertEqual(missing.returncode, 1)
            self.assertIn("FAIL", missing.stdout)

    def test_tgui_check_passes_the_flag_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, kb = os.path.join(tmp, "library.json"), os.path.join(tmp, "kb.json")
            with open(lib, "w", encoding="utf-8") as fh:
                json.dump(LIBRARY, fh)
            with open(kb, "w", encoding="utf-8") as fh:
                json.dump([[{"text": "Film", "callback_data": "f", "icon_custom_emoji_id": "3333333333"}]], fh)
            p = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "tgui.py"), "check", "keyboard", kb,
                                "--emoji-library", lib], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("BUTTON_EMOJI_ANIMATED", p.stdout)


if __name__ == "__main__":
    unittest.main()
