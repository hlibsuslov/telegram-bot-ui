"""Surface rules S1-S6 (gaps, insets, radii) and the paywall P1-P12: the kit, the audit, lint MA48, layout L26,
the paywall example and the references agree."""
import json
import os
import re
import tempfile
import unittest

import _paths
import miniapp_layout as layout
import miniapp_lint as lint
import miniapp_rework as rework
import preview_miniapp as stand

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
EX = os.path.join(_paths.ROOT, "examples", "mini-apps")
PAYWALL = os.path.join(EX, "paywall")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class Surfaces(unittest.TestCase):
    def test_kit_never_lets_two_surfaces_touch(self):
        css = read(EX, "_kit", "tma.css")
        self.assertIn("--tma-gap-surface: 16px", css)
        self.assertRegex(css, r":is\(\.tma-card, \.tma-list[^)]*\) \+ :is\(\.tma-card, \.tma-list[^)]*\) \{\s*margin-top: var\(--tma-gap-surface\)")
        # the stack keeps 24 px: its rule comes after the adjacency rule with the same specificity
        self.assertLess(css.index("margin-top: var(--tma-gap-surface)"), css.index(".tma-stack.tma-stack > * + *"))

    def test_ma48_flags_cramped_card_like_rules_only(self):
        self.assertTrue(lint.surface_padding_issue(".settings-card", "background:var(--tma-surface);border-radius:26px;padding:8px"))
        self.assertTrue(lint.surface_padding_issue(".promo", "background:var(--x);border-radius:var(--tma-r-group)"))
        self.assertIsNone(lint.surface_padding_issue(".plan-card", "background:var(--x);border-radius:20px;padding:var(--tma-s4)"))
        self.assertIsNone(lint.surface_padding_issue(".chip", "background:var(--x);border-radius:20px;padding:4px"))
        self.assertIsNone(lint.surface_padding_issue(".card", "background:transparent;border-radius:20px;padding:0"))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "style.css")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(".settings-card { background: var(--tma-surface); border-radius: 26px; padding: 8px 10px; }\n")
            self.assertEqual([f.rule for f in lint.lint_files([p], d).findings], ["MA48"])

    def test_stand_serves_the_audit(self):
        self.assertTrue(os.path.isfile(stand.AUDIT_JS))
        self.assertIn("window.tmaAudit", stand.mock_js())
        audit = read(stand.AUDIT_JS)
        for rule in ("LA01", "LA02", "LA03", "LA04", "LA05"):
            self.assertIn(rule, audit)
        self.assertIn("export function analyze", audit)

    def test_design_system_states_the_rules_with_numbers(self):
        doc = read(REF, "design-system.md")
        for rule in ("S1 gap", "S2 inset", "S3 radius scale", "S4 nesting", "S5 edges", "S6 groups"):
            self.assertIn(f"**{rule}**", doc)
        self.assertIn("?audit=1", doc)
        self.assertIn("MA48 surface-padding", read(REF, "anti-slop.md"))


class Paywall(unittest.TestCase):
    app = read(PAYWALL, "app.ts")

    def test_example_is_built_lint_clean_and_has_nothing_to_rework(self):
        self.assertIn("paywall: { 'paywall/app.ts': 'app.js'", read(EX, "build.mjs"))
        rep = lint.lint_files(*lint.collect([PAYWALL]))
        self.assertEqual([f.text() for f in rep.findings], [])
        plan = rework.plan(PAYWALL)
        self.assertEqual((plan["errors"], plan["warnings"]), (0, 0))

    def test_server_owns_prices_and_unlocking(self):
        self.assertIn("body: { plan: plan.id }, idempotencyKey: idempotencyKey()", self.app)  # ids only (P10)
        self.assertIn("tma.pay(order.link)", self.app)
        self.assertIn("tma.watchOrder(", self.app)
        self.assertNotRegex(self.app, r"status === 'paid'\)[^\n]*active: true")  # never from invoiceClosed
        mock = json.loads(read(PAYWALL, "mock-api.json"))
        plans = mock["GET /api/premium/offer"]["body"]["plans"]
        self.assertEqual([p["kind"] for p in plans], ["subscription", "once"])
        self.assertEqual(plans[0]["days"], 30)  # Stars subscriptions are 30-day

    def test_every_state_and_the_main_button_names_the_price(self):
        for text in ("The offer did not load", "The payment did not go through", "Confirming the payment", "Still confirming",
                     "Premium is on", "Turn off renewal", "if (result === 'cancelled') return;", "Open the app in Telegram to pay"):
            self.assertIn(text, self.app)
        self.assertIn("{ text: `Subscribe · ⭐ ${plan.stars} / month`", self.app)
        self.assertIn("{ text: `Pay ⭐ ${plan.stars} for ${months} months`", self.app)

    def test_an_unsettled_order_is_resumed_not_paid_again(self):
        self.assertIn("if (pendingOrder) void confirmOrder(pendingOrder);", self.app)
        self.assertIn("remember(order.order_id)", self.app)
        self.assertEqual(self.app.count("remember(null);"), 2)  # cleared only by the server's paid or failed
        self.assertIn("'/api/premium/renewal'", self.app)  # renewal off goes through the server

    def test_layout_review_l26(self):
        data = layout.load()
        self.assertEqual(layout.review(layout.EXAMPLES["paywall"], data), [])
        bad = {"screen": "paywall", "primary_action": "main-button", "paywall": {
            "placement": "tab-root", "value": "adjectives", "comparison": False, "price": "emoji", "renewal_terms": "elsewhere",
            "terms_link": False, "faq": False, "states": ["loading"], "empty_space": True, "subscription_period": 365}}
        found = layout.review(bad, data)
        self.assertGreaterEqual(len(found), 9)
        self.assertEqual({f["rule"] for f in found}, {"L26"})
        self.assertTrue(any("30 days" in f["message"] for f in found))

    def test_payments_reference_has_p1_to_p12(self):
        doc = read(REF, "payments.md")
        self.assertIn("## 9. The paywall: P1-P12", doc)
        for n in range(1, 13):
            self.assertRegex(doc, rf"\n\| P{n} \|")
        self.assertNotIn("Yearly · 2 months free", read(EX, "catalog", "app.ts"))  # no yearly Stars subscription


if __name__ == "__main__":
    unittest.main()
