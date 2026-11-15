"""TypeScript twins of the product recipes (examples/ts/usecases) replay the Python payloads.
Skipped when Node >= 22.18 (built-in type stripping) is not installed."""
import os
import re
import shutil
import subprocess
import unittest

import _paths

NODE = shutil.which("node")
FOLDER = os.path.join(_paths.EXAMPLES, "ts", "usecases")


def node_ok() -> bool:
    if not NODE:
        return False
    out = subprocess.run([NODE, "--version"], capture_output=True, text=True).stdout
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 18)


@unittest.skipUnless(node_ok(), "node >= 22.18 not available")
class TypeScriptTwins(unittest.TestCase):
    def test_twins_match_the_python_protocol(self):
        p = subprocess.run([NODE, "--test", "usecases.test.ts"], cwd=FOLDER, capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout[-4000:] + p.stderr[-2000:])

    def test_at_least_four_twins(self):
        twins = [f for f in os.listdir(FOLDER) if f.endswith(".ts") and f not in ("flows.ts", "usecases.test.ts")]
        self.assertGreaterEqual(len(twins), 4, twins)


if __name__ == "__main__":
    unittest.main()
