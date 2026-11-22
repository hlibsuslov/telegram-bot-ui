"""Premium pass: layout and meaning heuristics of validate_keyboard, and the before/after set
(examples/premium-pass/before-after.json) that the docs show. Offline, synthetic data."""
import re
import unittest

import _paths
import audit_copy
import validate_keyboard as vk

DOC = _paths.load("examples", "premium-pass", "before-after.json")
TAG = re.compile(r"<[^>]+>")


def btn(text, cb="x", **kw):
    return {"text": text, "callback_data": cb, **kw}


def warns(rows):
    rep = vk.validate(rows)
    assert rep.errors == [], rep.errors
    return rep.warnings


def callbacks(markup):
    return {b["callback_data"] for row in (markup or {}).get("inline_keyboard", []) for b in row
            if "callback_data" in b}


class LayoutHeuristics(unittest.TestCase):
    def test_styled_navigation(self):
        self.assertTrue(any("navigation/escape" in w for w in warns([[btn("Go", style="primary")],
                                                                     [btn("← Back", style="danger")]])))
        self.assertTrue(any("navigation/escape" in w for w in warns([[btn("Отмена", style="success")]])))
        # Cancelling a subscription is destructive, not navigation.
        self.assertFalse(any("navigation/escape" in w for w in warns([[btn("Cancel subscription", style="danger")]])))

    def test_actions_that_start_like_navigation(self):
        for label in ("Close account", "Home delivery", "Back up my data", "Menu of the day"):
            self.assertFalse(vk.is_navigation(label), label)
        for label in ("← Back to catalog", "Skip this step", "Назад к каталогу", "Скасувати", "🏠 Menu"):
            self.assertTrue(vk.is_navigation(label), label)
        self.assertFalse(any("navigation/escape" in w for w in warns([[btn("Close account", style="danger")]])))

    def test_status_symbol_on_navigation(self):
        self.assertTrue(any("status symbol" in w for w in warns([[btn("❌ Close")]])))
        self.assertFalse(any("status symbol" in w for w in warns([[btn("✅ Confirm order", style="success")]])))

    def test_navigation_above_actions(self):
        self.assertTrue(any("navigation sits above" in w
                            for w in warns([[btn("← Back"), btn("Cancel")], [btn("Place order", style="success")]])))
        # Back + Cancel in two bottom rows, Skip above them, and a confirmation's red last row are fine.
        self.assertFalse(any("navigation sits above" in w
                             for w in warns([[btn("Skip this step")], [btn("← Back")], [btn("Cancel")]])))
        self.assertFalse(any("navigation sits above" in w
                             for w in warns([[btn("Cancel")], [btn("Delete everything", style="danger")]])))

    def test_danger_next_to_main_action(self):
        self.assertTrue(any("shares a row" in w
                            for w in warns([[btn("Continue", style="primary"), btn("Delete", style="danger")]])))
        self.assertTrue(any("shares a row" in w
                            for w in warns([[btn("Settings"), btn("Reset", style="danger")]])))
        self.assertFalse(any("shares a row" in w
                             for w in warns([[btn("← Back"), btn("Delete", style="danger")]])))
        # Still found below a misplaced navigation row.
        found = warns([[btn("← Back")], [btn("Go", style="primary"), btn("Delete", style="danger")]])
        self.assertTrue(any("shares a row" in w for w in found) and any("navigation sits" in w for w in found))

    def test_vague_labels(self):
        for label in ("OK", "✅ Yes", "Submit", "Да", "Надіслати"):
            self.assertTrue(any("doesn't say what happens" in w for w in warns([[btn(label)]])), label)
        self.assertFalse(any("doesn't say what happens" in w for w in warns([[btn("Yes, delete it", style="danger")]])))

    def test_long_list(self):
        self.assertTrue(any("this is a list" in w for w in warns([[btn(f"Item {i}", f"i:{i}")] for i in range(9)])))


class BeforeAfter(unittest.TestCase):
    def test_every_before_has_a_finding_and_every_after_is_clean(self):
        for sc in DOC["scenarios"]:
            with self.subTest(scenario=sc["id"]):
                before, after = sc["before"].get("reply_markup"), sc["after"].get("reply_markup")
                if before:
                    self.assertTrue(vk.validate(before).warnings, "the before screen should show a defect")
                if after:
                    rep = vk.validate(after)
                    self.assertEqual((rep.errors, rep.warnings), ([], []))

    def test_callback_contract_preserved(self):
        routes = set().union(*(callbacks(sc["before"].get("reply_markup")) for sc in DOC["scenarios"]))
        for sc in DOC["scenarios"]:
            with self.subTest(scenario=sc["id"]):
                old, new = callbacks(sc["before"].get("reply_markup")), callbacks(sc["after"].get("reply_markup"))
                self.assertEqual(old - new - set(sc["handlers_kept"]), set(), "a payload lost its handler")
                # A cosmetic pass reuses the bot's existing routes ("Try again" = the route that opened the list).
                self.assertTrue(new <= routes, f"new callback_data {new - routes}")

    def test_first_line_names_the_screen(self):
        for sc in DOC["scenarios"]:
            text = sc["after"].get("text")
            if text:
                with self.subTest(scenario=sc["id"]):
                    first = text.split("\n", 1)[0]
                    self.assertTrue(first.startswith("<b>"), "bold title or event first")
                    self.assertLessEqual(len(TAG.sub("", first)), 80, "fits a notification preview")

    def test_stale_tap_is_answered_and_notification_resolves_in_place(self):
        scenarios = {sc["id"]: sc for sc in DOC["scenarios"]}
        toast = scenarios["stale"]["after"]["answerCallbackQuery"]["text"]
        self.assertTrue(0 < len(toast) <= 200)
        resolved = scenarios["notification"]["after"]["resolved"]
        self.assertEqual(resolved["method"], "editMessageText")
        self.assertIsNone(resolved["reply_markup"], "a resolved notification keeps no live buttons")

    def test_catalog_survives_the_longest_locale(self):
        errors, warnings = audit_copy.audit(DOC["catalog"])
        self.assertEqual((errors, warnings), ([], []))


if __name__ == "__main__":
    unittest.main()
