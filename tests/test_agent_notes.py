"""Agent notes (data/bot-api/agent-notes/) and the card `tgui.py lookup card` builds from catalog + note."""
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest

import _paths
import api_notes
import sync_bot_api
import tg_api_lookup

API = tg_api_lookup.Api()
CAT = API.cat
VERSIONS = {r["version"] for r in API.changelog.get("releases", []) if r.get("version")}

GOOD = {
    "purpose": "Send one complete structured message.",
    "use_when": ["long answers"],
    "avoid_when": ["short replies"],
    "pitfalls": [{"text": "Exactly one of html, markdown or blocks.", "source": "API", "cite": "InputRichMessage"},
                 {"text": "Feels slow on old clients.", "source": "Heuristic"}],
    "related": ["sendRichMessageDraft", "InputRichMessage"],
    "rights": "send messages",
    "chat_types": ["private", "group"],
    "since": "10.1",
    "refs": ["references/telegram-capabilities.md#two-mechanisms-kept-separate"],
    "example": "examples/payloads/r31-long-read-rich-post.json",
}


def bare_symbol():
    """A catalog symbol no domain has noted yet (types last get notes, so start there)."""
    notes = api_notes.load_notes()
    return next(n for kind in ("types", "methods") for n in sorted(CAT[kind]) if n not in notes)


def problems(notes, domain="rich", extra_files=()):
    files = [(f"{domain}.json", {"domain": domain, "notes": notes}), *extra_files]
    return api_notes.validate(files, CAT, versions=VERSIONS)


class Schema(unittest.TestCase):
    def test_committed_notes_are_valid(self):
        files = api_notes.load_files()
        self.assertTrue(files, "no agent-notes files")
        self.assertEqual(api_notes.validate(files, CAT, versions=VERSIONS), [])

    def test_a_good_note_passes(self):
        self.assertEqual(problems({"sendRichMessage": GOOD}), [])

    def test_each_broken_rule_is_reported(self):
        cases = {
            "unknown field 'when'": {"when": "now"},
            "\"purpose\" is required": {"purpose": ""},
            "not in the catalog": {"related": ["sendRichMesage"]},
            "lists the symbol itself": {"related": ["sendRichMessage"]},
            "\"source\" must be one of": {"pitfalls": [{"text": "x", "source": "Blog"}]},
            "needs \"cite\"": {"pitfalls": [{"text": "x", "source": "Official"}]},
            "pitfalls[0] unknown field 'url'": {"pitfalls": [{"text": "x", "source": "Heuristic", "url": "u"}]},
            "\"chat_types\" must be": {"chat_types": ["dm"]},
            "is not a release": {"since": "1.99"},
            "no heading with that anchor": {"refs": ["references/telegram-capabilities.md#no-such-heading"]},
            "no such file": {"refs": ["references/no-such-file.md#x"]},
            "must be references/<file>.md": {"refs": ["../README.md"]},
            "records no sendRichMessage request": {"example": "examples/payloads/r07-wallet.json"},
            "must be a path under examples/": {"example": "references/api-catalog.md"},
            "\"review\" must be true or false": {"review": "yes"},
            "card is": {"use_when": ["x" * 1600]},
        }
        for expected, change in cases.items():
            with self.subTest(expected):
                found = problems({"sendRichMessage": {**GOOD, **change}})
                self.assertTrue(any(expected in p for p in found), found)

    def test_unknown_symbol_domain_and_duplicates(self):
        self.assertIn("rich.json: sendRichMesage: not in the Bot API catalog (check the exact case)",
                      problems({"sendRichMesage": GOOD}))
        self.assertTrue(any("\"domain\" must be 'rich'" in p for p in
                            api_notes.validate([("rich.json", {"domain": "x", "notes": {}})], CAT)))
        other = ("other.json", {"domain": "other", "notes": {"sendRichMessage": GOOD}})
        self.assertTrue(any("also noted in rich.json" in p for p in problems({"sendRichMessage": GOOD}, extra_files=[other])))

    def test_code_example_must_call_the_method(self):
        found = problems({"sendRichMessage": {**GOOD, "example": "examples/python/tgkit/__init__.py"}})
        self.assertTrue(any("never calls sendRichMessage" in p for p in found), found)


class Card(unittest.TestCase):
    def test_card_merges_catalog_note_and_example(self):
        text = api_notes.card(CAT["methods"]["sendRichMessage"], GOOD, CAT["meta"])
        self.assertIn("since 10.1", text)
        self.assertIn("Purpose: Send one complete structured message.", text)
        self.assertIn("Required: rich_message: InputRichMessage", text)
        self.assertIn("Required in some cases (see `lookup show`): chat_id", text)
        self.assertIn("- Exactly one of html, markdown or blocks. [API]", text)
        self.assertIn("- Feels slow on old clients. [Heuristic]", text)
        self.assertIn('Example: examples/payloads/r31-long-read-rich-post.json {"chat_id":', text)

    def test_every_catalog_symbol_fits_without_a_note(self):
        for kind in ("methods", "types"):
            for name, sym in CAT[kind].items():
                text = api_notes.card(sym, None, CAT["meta"])
                self.assertLessEqual(len(text.encode("utf-8")), api_notes.CARD_LIMIT, name)
                self.assertIn("Note: none yet", text)

    def test_long_optional_lists_are_cut_with_a_count(self):
        text = api_notes.card(CAT["types"]["Message"], None, CAT["meta"])
        self.assertRegex(text, r"Optional fields: .+… \+\d+ more")

    def test_review_flag_warns(self):
        text = api_notes.card(CAT["methods"]["sendRichMessage"], {**GOOD, "review": True}, CAT["meta"])
        self.assertIn("REVIEW:", text)

    def test_lookup_card_command(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tg_api_lookup.main(["card", "sendrichmessage"]), 0)
        self.assertIn("sendRichMessage · method · Rich messages", out.getvalue())
        self.assertIn("Example: examples/payloads/", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tg_api_lookup.main(["--json", "card", bare_symbol()]), 0)
        data = json.loads(out.getvalue())
        self.assertIsNone(data["note"])
        self.assertIn("Note: none yet", data["card"])


class ReviewFindings(unittest.TestCase):
    """Regression tests for the Codex review of the notes code (task 20261125-164444-review-5eb8)."""

    def test_parent_segments_cannot_move_a_path_out_of_its_folder(self):
        found = problems({"sendRichMessage": {**GOOD, "refs": ["references/../SKILL.md"]}})
        self.assertTrue(any("must be references/<file>.md" in p for p in found), found)
        found = problems({"sendRichMessage": {**GOOD, "example": "examples/../data/bot-api/catalog.json"}})
        self.assertTrue(any("must be a path under examples/" in p for p in found), found)

    def test_a_link_out_of_the_skill_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="notes-link-")
        self.addCleanup(shutil.rmtree, tmp, True)
        outside = tempfile.mkdtemp(prefix="notes-outside-")
        self.addCleanup(shutil.rmtree, outside, True)
        os.makedirs(os.path.join(tmp, "references"))
        try:
            os.symlink(outside, os.path.join(tmp, "references", "out"), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("no permission to create a symlink")
        self.assertIsNone(api_notes._inside(tmp, "references/out/x.md"))

    def test_review_flag_does_not_break_the_size_limit_check(self):
        note = self.note_near_limit("sendRichMessage")
        self.assertEqual(problems({"sendRichMessage": {**note, "review": True}}), [])

    def test_the_optional_line_never_pushes_a_card_over_the_limit(self):
        sym = CAT["methods"]["sendMessage"]
        for extra in range(0, 400, 7):
            note = {"purpose": "Send text.", "use_when": ["x" * (900 + extra)]}
            text = api_notes.card(sym, note, CAT["meta"])
            if len(text.encode("utf-8")) > api_notes.CARD_LIMIT:
                self.assertFalse(any(line.startswith("Optional") for line in text.splitlines()), extra)

    def test_an_example_must_really_make_the_call(self):
        tmp = tempfile.mkdtemp(prefix="notes-example-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "examples", "payloads"))
        with open(os.path.join(tmp, "examples", "only_a_comment.py"), "w", encoding="utf-8") as fh:
            fh.write("# sendRichMessage would go here\n")
        with open(os.path.join(tmp, "examples", "payloads", "no-params.json"), "w", encoding="utf-8") as fh:
            json.dump({"steps": [{"method": "sendRichMessage"}]}, fh)
        note = {"purpose": "x"}
        for example, expected in (("examples/only_a_comment.py", "never calls"),
                                  ("examples/payloads/no-params.json", "records no sendRichMessage request")):
            found = api_notes.validate([("rich.json", {"domain": "rich", "notes": {
                "sendRichMessage": {**note, "example": example}}})], CAT, skill_dir=tmp)
            self.assertTrue(any(expected in p for p in found), found)

    def test_malformed_values_are_reported_not_raised(self):
        for bad in ({"purpose": ["a list"]}, {"purpose": "x", "pitfalls": [{"text": "t", "source": ["API"]}]}):
            with self.subTest(bad):
                self.assertTrue(problems({"sendRichMessage": bad}))

    def test_exporter_flags_orphaned_api_payloads_and_parses_only(self):
        import export_payloads as ep
        tmp = tempfile.mkdtemp(prefix="payloads-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for name in ("api-gone.json", "api-messages.json", "r07-wallet.json"):
            open(os.path.join(tmp, name), "w").close()
        self.assertEqual(ep.orphans(tmp, {"api-messages", "r07-wallet"}), ["api-gone.json"])
        self.assertEqual(ep.parse_args(["--check", "--only", "a", "b"]).only, ["a", "b"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ep.parse_args(["--only"])

    @staticmethod
    def note_near_limit(symbol):
        sym = CAT["methods"][symbol]
        base = {k: v for k, v in GOOD.items() if k != "example"}
        size = len(api_notes.card(sym, base, CAT["meta"]).encode("utf-8"))
        return {**base, "use_when": base["use_when"] + ["y" * (api_notes.CARD_LIMIT - size - 10)]}


class SyncOrder(unittest.TestCase):
    def test_notes_are_marked_before_the_catalog_is_replaced(self):
        from unittest import mock
        fix = os.path.join(_paths.TESTS, "fixtures", "api")
        with open(os.path.join(fix, "bot_api_excerpt.html"), encoding="utf-8") as fh:
            built = sync_bot_api.build_catalog(fh.read(), None, "2026-11-15", min_methods=5, min_types=10)
        with tempfile.TemporaryDirectory() as out:
            page = os.path.join(out, "api.html")
            open(page, "w", encoding="utf-8").close()
            with mock.patch.object(sync_bot_api, "build_catalog", return_value=built), \
                    mock.patch.object(sync_bot_api, "mark_notes_for_review", side_effect=OSError("disk full")), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):
                    sync_bot_api.main(["--api-html", page, "--out", out])
            self.assertFalse(os.path.exists(os.path.join(out, "catalog.json")))


class SyncMarksReview(unittest.TestCase):
    def test_changed_and_removed_symbols_get_review(self):
        tmp = tempfile.mkdtemp(prefix="notes-")
        self.addCleanup(shutil.rmtree, tmp, True)
        notes = {"sendRichMessage": copy.deepcopy(GOOD), "sendRichMessageDraft": copy.deepcopy(GOOD),
                 "InputRichMessage": copy.deepcopy(GOOD)}
        with open(os.path.join(tmp, "rich.json"), "w", encoding="utf-8") as fh:
            json.dump({"domain": "rich", "notes": notes}, fh)
        diff = {"changed": {"methods": {"sendRichMessage": {"description_changed": True}}, "types": {}},
                "removed": {"methods": [], "types": ["InputRichMessage"]}}
        self.assertEqual(sync_bot_api.mark_notes_for_review(tmp, diff), ["InputRichMessage", "sendRichMessage"])
        with open(os.path.join(tmp, "rich.json"), encoding="utf-8") as fh:
            saved = json.load(fh)["notes"]
        self.assertTrue(saved["sendRichMessage"]["review"])
        self.assertTrue(saved["InputRichMessage"]["review"])
        self.assertNotIn("review", saved["sendRichMessageDraft"])
        self.assertEqual(sync_bot_api.mark_notes_for_review(tmp, diff), [])  # already marked

    def test_no_notes_folder_is_fine(self):
        self.assertEqual(sync_bot_api.mark_notes_for_review(os.path.join(tempfile.gettempdir(), "no-such-notes"),
                                                            {"changed": {"methods": {"x": {}}}}), [])


if __name__ == "__main__":
    unittest.main()
