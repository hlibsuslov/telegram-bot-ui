"""bot-ui folder renames survive a moment of 'Access is denied' on Windows (antivirus, indexer)."""
from __future__ import annotations

import os
import unittest
from unittest import mock

import _bot_ui  # noqa: F401  (puts the core on sys.path)
from bot_ui import project


class ReplaceDir(unittest.TestCase):
    def test_retries_a_transient_denial_on_windows(self):
        calls = []

        def flaky(src, dst):
            calls.append((src, dst))
            if len(calls) < 3:
                raise PermissionError(5, "Access is denied")

        with mock.patch.object(project.os, "replace", flaky), mock.patch.object(project.os, "name", "nt"), \
                mock.patch.object(project.time, "sleep"):
            project.replace_dir("a", "b")
        self.assertEqual(len(calls), 3)

    def test_gives_up_and_raises(self):
        with mock.patch.object(project.os, "replace", side_effect=PermissionError(5, "denied")), \
                mock.patch.object(project.os, "name", "nt"), mock.patch.object(project.time, "sleep"):
            with self.assertRaises(PermissionError):
                project.replace_dir("a", "b", attempts=3)

    def test_no_retry_elsewhere(self):
        with mock.patch.object(project.os, "replace", side_effect=PermissionError(13, "denied")) as rep, \
                mock.patch.object(project.os, "name", "posix"):
            with self.assertRaises(PermissionError):
                project.replace_dir("a", "b")
        self.assertEqual(rep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
