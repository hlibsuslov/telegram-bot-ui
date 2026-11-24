"""tgkit.trust weighs anti-abuse signals as user-trust.md describes; the reference keeps its safeguards."""
import os
import re
import sys
import unittest
from datetime import date, timedelta

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "examples", "python"))
from tgkit.trust import AgeAnchor, IdAgeEstimator, Signals, assess  # noqa: E402

TODAY = date(2026, 11, 24)


class Estimator(unittest.TestCase):
    est = IdAgeEstimator([
        AgeAnchor(1_000, date(2015, 1, 1), "created"),
        AgeAnchor(5_000, date(2020, 6, 1), "created"),
        AgeAnchor(9_000, date(2026, 11, 1), "created"),
        AgeAnchor(7_000, date(2024, 3, 1), "seen"),
    ])

    def test_bracket_between_anchors(self):
        self.assertEqual(self.est.bracket(6_000), (date(2020, 6, 1), date(2024, 3, 1)))

    def test_no_upper_anchor_means_no_upper_bound(self):
        self.assertEqual(self.est.bracket(9_500), (date(2026, 11, 1), None))

    def test_seen_anchors_never_give_a_lower_bound(self):
        est = IdAgeEstimator([AgeAnchor(7_000, date(2026, 11, 20), "seen")])
        self.assertEqual(est.bracket(8_000), (None, None))
        self.assertEqual(est.bracket(6_000), (None, date(2026, 11, 20)))

    def test_upper_bound_is_the_earliest_at_or_above(self):
        est = IdAgeEstimator([AgeAnchor(10, date(2025, 1, 1)), AgeAnchor(20, date(2024, 1, 1))])
        self.assertEqual(est.bracket(5)[1], date(2024, 1, 1))


class Assess(unittest.TestCase):
    def test_unknown_is_normal(self):
        self.assertEqual(assess(Signals(), TODAY).tier, "normal")

    def test_thin_profile_alone_never_counts(self):
        self.assertEqual(assess(Signals(has_username=False, has_photo=False), TODAY).tier, "normal")

    def test_new_account_is_watch_not_restricted(self):
        a = assess(Signals(created_after=TODAY - timedelta(days=5), has_username=False, has_photo=False), TODAY)
        self.assertEqual(a.tier, "watch")
        self.assertIn("no username", a.reasons)

    def test_blocklist_or_upheld_reports_restrict_with_reasons(self):
        self.assertEqual(assess(Signals(blocklist_hit=True), TODAY).tier, "restricted")
        a = assess(Signals(confirmed_reports=2), TODAY)
        self.assertEqual(a.tier, "restricted")
        self.assertTrue(a.reasons)

    def test_history_earns_trust(self):
        a = assess(Signals(completed_orders=4, first_seen_by_bot=TODAY - timedelta(days=400)), TODAY)
        self.assertEqual(a.tier, "trusted")

    def test_moderator_clearance_wins(self):
        self.assertEqual(assess(Signals(blocklist_hit=True, manual_allow=True), TODAY).tier, "trusted")


class Reference(unittest.TestCase):
    doc = open(os.path.join(_paths.ROOT, "references", "user-trust.md"), encoding="utf-8").read()
    flat = " ".join(doc.split())

    def test_sections(self):
        for n in range(0, 9):
            self.assertRegex(self.doc, rf"\n## {n}\. ")

    def test_safeguards_present(self):
        for s in ("appeal", "privacy policy", "never bans on age alone", "api.cas.chat", "no appeal",
                  "does not publish", "human"):
            self.assertIn(s, self.flat, s)

    def test_routed(self):
        skill = open(os.path.join(_paths.ROOT, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("references/user-trust.md", skill)
        self.assertIn("user-trust.md", open(os.path.join(_paths.ROOT, "references", "user-data.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
