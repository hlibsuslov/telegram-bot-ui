"""native-anatomy.md, design-sources.json (ios27.anatomy) and the kit agree on the measured iOS 27 values."""
import os
import re
import unittest

import _paths

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
KIT = os.path.join(_paths.ROOT, "examples", "mini-apps", "_kit", "tma.css")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Anatomy(unittest.TestCase):
    a = _paths.load("data", "mini-apps", "design-sources.json")["ios27"]["anatomy"]
    doc = read(os.path.join(REF, "native-anatomy.md"))
    css = read(KIT)

    def test_rows_and_buttons_match_the_kit(self):
        self.assertEqual(self.a["list"]["row"], [52, 68])
        self.assertIn("--tma-row: 52px", self.css)
        self.assertIn("--tma-row-2: 68px", self.css)
        self.assertEqual([self.a["buttons"][s]["height"] for s in ("small", "medium", "large")], [28, 34, 50])
        self.assertIn("min-height: 28px; padding: 0 10px", self.css)
        self.assertIn("min-height: 34px; padding: 0 14px", self.css)
        self.assertRegex(self.css, r"\.tma-btn\.is-lg \{ min-height: 50px")

    def test_stack_gap_beats_component_margin_resets(self):
        """A section, list or kv directly in a .tma-stack keeps the 24 px gap: the stack rule must out-rank
        every one-class rule that resets margin, wherever it sits in the file (the Profile screen bug)."""
        m = re.search(r"\n(\.tma-stack[^{]*>\s*\*\s*\+\s*\*)\s*\{\s*margin-top:\s*var\(--tma-gap-section\)", self.css)
        self.assertTrue(m, "stack gap rule")
        self.assertGreaterEqual(m.group(1).count(".tma-stack"), 2, "the stack rule needs (0,2,0) specificity")
        resets = re.findall(r"\n(\.tma-[a-z_-]+) \{[^}]*\bmargin: 0[;\s]", self.css)
        self.assertIn(".tma-section", resets)

    def test_header_levels_and_sheet_shape(self):
        for cls in (".is-nested", ".is-prominent", ".is-extra", ".is-small"):
            self.assertIn(f".tma-section__header{cls}", self.css)
        default = re.search(r"\.tma-section__header \{([^}]*)\}", self.css).group(1)
        self.assertIn("font-size: var(--tma-fs-body); font-weight: 600", default)  # nested 17 semibold by default
        self.assertEqual(self.a["sheet"]["medium_detent_inset"], 6)
        self.assertEqual(self.a["sheet"]["grabber"], [60, 4])
        self.assertIn('[data-tma-platform="ios"] .tma-sheet {\n  inset-inline: 6px; bottom: 6px;', self.css)
        self.assertIn('[data-tma-platform="ios"] .tma-sheet::before { width: 60px; height: 4px;', self.css)

    def test_reference_covers_every_measured_area_and_labels_sources(self):
        for n, title in enumerate(["Layout", "Lists", "Buttons", "Tab bar", "Sheets", "Alerts", "Empty states",
                                   "Text fields", "How Telegram composes"], 1):
            self.assertRegex(self.doc, rf"\n## {n}\. {title}", title)
        self.assertGreater(self.doc.count("[iOS27]"), 10)
        self.assertGreater(self.doc.count("[TgKit]"), 3)
        self.assertIn("669", self.doc)

    def test_figma_workflow_is_routed_and_keeps_licences(self):
        wf = read(os.path.join(REF, "figma-workflow.md"))
        for step in ("create_session", "get_metadata", "get_design_context", "get_variable_defs", "get_screenshot"):
            self.assertIn(step, wf)
        self.assertRegex(wf, r"SF Symbols and other artwork")
        self.assertIn("figma-workflow.md", read(os.path.join(REF, "README.md")))
        self.assertIn("native-anatomy.md", _paths.routing_text())

    def test_stand_offers_the_foldable_width(self):
        import preview_miniapp as preview
        self.assertIn(669, preview.HEIGHTS)


if __name__ == "__main__":
    unittest.main()
