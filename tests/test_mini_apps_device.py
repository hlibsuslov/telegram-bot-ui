"""haptics-and-device.md, the kit's device helpers, the stand's mock and lint MA36-MA37 agree."""
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
    doc = read(REF, "haptics-and-device.md")

    def test_sections_and_every_haptic_value(self):
        for n in range(0, 10):
            self.assertRegex(self.doc, rf"\n## {n}\. ")
        for v in ("light", "medium", "heavy", "rigid", "soft", "success", "warning", "error", "selectionChanged"):
            self.assertIn(f"`{v}`" if v != "selectionChanged" else "selectionChanged()", self.doc, v)

    def test_kit_calls_named_in_the_map_exist(self):
        ts = read(KIT, "tma.ts")
        for call in re.findall(r"`(?:tma\.haptic\.)?((?:select|tap|impact|success|warning|error|notify|setEnabled))\(", self.doc):
            self.assertRegex(ts, rf"\b{call}[:(]", call)
        for fn in ("function motion(", "function location("):
            self.assertIn(fn, ts)

    def test_every_member_cited_exists_with_its_version(self):
        cat = _paths.load("data", "mini-apps", "webapp-catalog.json")
        members = cat.get("members", cat)
        for name, ver in re.findall(r"\| `(\w+)\([^`]*`(?: / `\w+\([^`]*`)? \| (\d+\.\d+) \|", self.doc):
            key = name if name in members else f"WebApp.{name}"
            self.assertIn(key, members, name)
            self.assertEqual(members[key]["version"], ver, name)

    def test_routes(self):
        self.assertIn("haptics-and-device.md", read(REF, "README.md"))
        self.assertIn("haptics-and-device.md", read(REF, "design-system.md"))
        self.assertIn("haptics-and-device.md", _paths.routing_text())


class StandAndLint(unittest.TestCase):
    def test_mock_has_sensors_and_location(self):
        import preview_miniapp as preview
        js = preview.mock_js()
        for part in ("Accelerometer: sensor(", "Gyroscope: sensor(", "DeviceOrientation: sensor(", "LocationManager: {", "getLocation:"):
            self.assertIn(part, js)

    def test_haptics_in_streams_and_sensors_left_running(self):
        self.assertIn("MA36", lint_text("a.ts", "el.addEventListener('scroll', () => {\n  tma.haptic.select();\n});\n"))
        self.assertIn("MA36", lint_text("a.ts", "setInterval(() => tg.HapticFeedback.impactOccurred('light'), 500);\n"))
        self.assertNotIn("MA36", lint_text("a.ts", "setInterval(tick, 1000);\nbtn.onclick = () => tma.haptic.success();\n"))
        self.assertIn("MA37", lint_text("a.ts", "tg.Gyroscope.start({ refresh_rate: 20 });\n"))
        self.assertNotIn("MA37", lint_text("a.ts", "const stop = tma.motion('orientation', draw);\nback.onclick = () => stop?.();\n"))


if __name__ == "__main__":
    unittest.main()
