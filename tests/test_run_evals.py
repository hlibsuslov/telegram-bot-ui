"""run_evals.py: case splits, loaded-copy classification, run counting and result files.

Pure functions only: transcripts are synthetic stream-json lines, no agent CLI is started.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401  (adds scripts/ to sys.path)

import run_evals as ev

SKILL = ev.SKILL_NAME


def line(**event):
    return json.dumps(event)


def skill_call():
    return line(type="assistant", message={"content": [
        {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": SKILL}}]})


def base_dir(path, name=SKILL):
    return line(type="user", message={"content": [
        {"type": "tool_result", "tool_use_id": "t1",
         "content": f"Base directory for this skill: {path}\n\n# {name}\nbody"}]})


def read_call(path):
    return line(type="assistant", message={"content": [
        {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": path}}]})


def result(**usage):
    return line(type="result", subtype="success", is_error=False, usage=usage)


class Folders(unittest.TestCase):
    """A throwaway project and a second folder that stands for a user-level copy."""

    def setUp(self):
        self._tmp = [tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()]
        self.addCleanup(lambda: [t.cleanup() for t in self._tmp])
        self.project = self.make(self._tmp[0].name)
        self.elsewhere = self.make(self._tmp[1].name)

    @staticmethod
    def make(root):
        skill = os.path.join(root, ".claude", "skills", SKILL)
        os.makedirs(os.path.join(skill, "references"))
        return skill


class SplitTest(unittest.TestCase):
    def test_split_is_deterministic_and_pinned(self):
        # Pinned values: changing the hash or the percentage silently re-shuffles every past result.
        self.assertEqual({c: ev.split_of(c) for c in ("P1", "N1", "PUB4", "NV1", "ST2")},
                         {"P1": "validation", "N1": "validation", "PUB4": "validation",
                          "NV1": "train", "ST2": "train"})
        self.assertEqual(ev.split_of("NV1"), ev.split_of("NV1"))

    def test_splits_partition_the_real_set_about_60_40(self):
        cases = ev.load()["activation"]
        train = ev.select_cases(cases, None, "train", None)
        valid = ev.select_cases(cases, None, "validation", None)
        every = ev.select_cases(cases, None, "all", None)
        self.assertEqual({c["id"] for c in train} | {c["id"] for c in valid}, {c["id"] for c in every})
        self.assertFalse({c["id"] for c in train} & {c["id"] for c in valid})
        self.assertTrue(0.5 <= len(train) / len(every) <= 0.7, len(train) / len(every))

    def test_ids_and_limit_apply_before_and_after_the_split(self):
        cases = ev.load()["activation"]
        picked = ev.select_cases(cases, "P1,NV1,ST2", "all", None)
        self.assertEqual({c["id"] for c in picked}, {"P1", "NV1", "ST2"})
        self.assertEqual({c["id"] for c in ev.select_cases(picked, None, "train", None)}, {"NV1", "ST2"})
        self.assertEqual([c["id"] for c in ev.select_cases(cases, "P1,NV1,ST2", "validation", None)], ["P1"])
        self.assertEqual(len(ev.select_cases(cases, None, "all", 4)), 4)


class RunCountingTest(unittest.TestCase):
    def test_majority_is_ceil_half(self):
        self.assertTrue(ev.passes(1, 1))
        self.assertFalse(ev.passes(0, 1))
        self.assertTrue(ev.passes(1, 2))     # ceil(2/2) = 1
        self.assertFalse(ev.passes(1, 3))    # ceil(3/2) = 2
        self.assertTrue(ev.passes(2, 3))
        self.assertTrue(ev.passes(2, 4))
        self.assertFalse(ev.passes(2, 5))


class ResultFileTest(unittest.TestCase):
    def test_name_has_date_time_host_and_run_id(self):
        self.assertEqual(ev.result_filename("claude", "ab12cd", when=0), "1970-01-01T000000-claude-ab12cd.json")
        name = ev.result_filename("codex", "ff00ee")
        self.assertRegex(name, r"^\d{4}-\d\d-\d\dT\d{6}-codex-ff00ee\.json$")

    def test_two_runs_in_one_second_do_not_collide(self):
        self.assertNotEqual(ev.result_filename("claude", "aaaaaa", when=5), ev.result_filename("claude", "bbbbbb", when=5))


class ClaudeClassifierTest(Folders):
    def analyze(self, *lines):
        return ev.analyze_output("claude", "\n".join(lines), self.project_root)

    @property
    def project_root(self):
        return self._tmp[0].name

    def test_project_copy(self):
        info = self.analyze(
            line(type="system", subtype="init", model="claude-x"),
            skill_call(), base_dir(self.project),
            read_call(os.path.join(self.project, "references", "inline-keyboards.md")),
            result(input_tokens=10, output_tokens=7, cache_read_input_tokens=100, cache_creation_input_tokens=5))
        self.assertTrue(info["activated"])
        self.assertEqual(info["copy"], "project")
        self.assertEqual(info["reads"], ["references/inline-keyboards.md"])
        self.assertEqual(info["tokens"], {"input": 115, "output": 7, "cached": 100})
        self.assertEqual(info["model"], "claude-x")
        self.assertTrue(info["finished"])

    def test_copy_outside_the_project_is_other(self):
        info = self.analyze(skill_call(), base_dir(self.elsewhere), result(input_tokens=1, output_tokens=1))
        self.assertTrue(info["activated"])
        self.assertEqual(info["copy"], "other")
        self.assertEqual(info["loaded"], [self.elsewhere])

    def test_any_other_copy_wins_over_the_project_copy(self):
        info = self.analyze(skill_call(), base_dir(self.project), skill_call(), base_dir(self.elsewhere))
        self.assertEqual(info["copy"], "other")

    def test_sibling_folder_with_the_project_name_prefix_is_not_inside(self):
        sibling = self.project_root + "-copy"
        self.assertFalse(ev.inside(os.path.join(sibling, "x"), self.project_root))
        self.assertTrue(ev.inside(os.path.join(self.project_root, "x"), self.project_root))

    def test_direct_read_of_skill_md_names_the_copy(self):
        inside = self.analyze(read_call(os.path.join(self.project, "SKILL.md")))
        outside = self.analyze(read_call(os.path.join(self.elsewhere, "SKILL.md")))
        self.assertEqual((inside["activated"], inside["copy"]), (True, "project"))
        self.assertEqual((outside["activated"], outside["copy"]), (True, "other"))

    def test_skill_call_without_a_path_is_unknown_and_no_skill_is_none(self):
        self.assertEqual(self.analyze(skill_call())["copy"], "unknown")
        quiet = self.analyze(line(type="assistant", message={"content": [
            {"type": "text", "text": f"{SKILL}/SKILL.md mentioned in prose"}]}))
        self.assertEqual((quiet["activated"], quiet["copy"]), (False, "none"))

    def test_another_skills_base_directory_is_ignored(self):
        info = self.analyze(base_dir(os.path.join(self._tmp[1].name, ".claude", "skills", "impeccable"),
                                     name="impeccable"))
        self.assertEqual((info["activated"], info["copy"]), (False, "none"))

    def test_only_reads_after_the_load_inside_a_skill_folder_count(self):
        early = read_call(os.path.join(self.project, "references", "early.md"))
        info = self.analyze(early, skill_call(), base_dir(self.project),
                            read_call(os.path.join(self.project_root, "bot.py")),
                            read_call(os.path.join(self.project, "references", "buttons-and-styles.md")))
        self.assertEqual(info["reads"], ["references/buttons-and-styles.md"])

    def test_error_result_and_missing_result_are_visible(self):
        failed = self.analyze(line(type="result", subtype="success", is_error=True, result="usage limit reached"))
        self.assertIn("usage limit", failed["error"])
        self.assertFalse(self.analyze(skill_call(), base_dir(self.project))["finished"])

    def test_legacy_skill_loaded_helper_still_answers(self):
        self.assertTrue(ev.skill_loaded("claude", skill_call()))
        self.assertFalse(ev.skill_loaded("claude", line(type="assistant", message={"content": []})))


class CodexClassifierTest(Folders):
    def command(self, text):
        return line(type="item.completed", item={"id": "i", "type": "command_execution", "command": text,
                                                 "exit_code": 0, "status": "completed"})

    def analyze(self, *lines):
        return ev.analyze_output("codex", "\n".join(lines), self._tmp[0].name)

    def test_absolute_path_inside_the_project(self):
        path = os.path.join(self.project, "SKILL.md").replace("\\", "/")
        ref = os.path.join(self.project, "references", "widgets.md").replace("\\", "/")
        info = self.analyze(self.command(f"bash -lc \"cat '{path}'\""), self.command(f"sed -n '1,80p' {ref}"),
                            line(type="turn.completed", usage={"input_tokens": 50, "output_tokens": 9,
                                                               "cached_input_tokens": 20}))
        self.assertEqual((info["activated"], info["copy"]), (True, "project"))
        self.assertEqual(info["reads"], ["references/widgets.md"])
        self.assertEqual(info["tokens"], {"input": 50, "output": 9, "cached": 20})

    def test_windows_command_with_backslashes(self):
        path = os.path.join(self.project, "SKILL.md")
        info = self.analyze(self.command(f"pwsh -Command \"Get-Content -Raw '{path}'\""))
        self.assertEqual((info["activated"], info["copy"]), (True, "project"))

    def test_relative_path_is_the_project_copy_and_home_path_is_other(self):
        rel = self.analyze(self.command("cat .agents/skills/telegram-bot-ui/SKILL.md"))
        home = self.analyze(self.command("cat ~/.codex/skills/telegram-bot-ui/SKILL.md"))
        elsewhere = self.analyze(self.command("cat " + os.path.join(self.elsewhere, "SKILL.md").replace("\\", "/")))
        self.assertEqual(rel["copy"], "project")
        self.assertEqual(home["copy"], "other")
        self.assertEqual(elsewhere["copy"], "other")

    def test_a_quoted_path_with_spaces_is_read_whole_and_is_not_the_project_copy(self):
        folder = os.path.join(self._tmp[1].name, "Some One", ".codex", "skills", SKILL).replace("\\", "/")
        for quote in ('"', "'"):
            info = self.analyze(self.command(f"cat {quote}{folder}/SKILL.md{quote}"))
            self.assertEqual((info["activated"], info["copy"]), (True, "other"), quote)
            self.assertEqual(info["loaded"], [folder])

    def test_a_relative_path_that_climbs_out_of_the_project_is_other(self):
        for climbing in ("../../.codex/skills/telegram-bot-ui/SKILL.md", "./../x/.agents/skills/telegram-bot-ui/SKILL.md",
                         ".agents/../../elsewhere/telegram-bot-ui/SKILL.md"):
            self.assertEqual(self.analyze(self.command(f"cat {climbing}"))["copy"], "other", climbing)
        self.assertEqual(self.analyze(self.command("cat ./.agents/skills/telegram-bot-ui/SKILL.md"))["copy"], "project")

    def test_prose_and_listing_commands_do_not_activate(self):
        prose = line(type="item.completed", item={"type": "agent_message", "text": "see telegram-bot-ui/SKILL.md"})
        listing = self.command("ls .agents/skills/telegram-bot-ui")
        self.assertFalse(self.analyze(prose, listing)["activated"])

    def test_legacy_skill_loaded_helper_still_answers(self):
        self.assertTrue(ev.skill_loaded("codex", '{"cmd":"cat .agents/skills/telegram-bot-ui/SKILL.md"}'))
        self.assertFalse(ev.skill_loaded("codex", '{"msg":"hello"}'))


class RouteTest(unittest.TestCase):
    def test_first_read_is_compared_with_routes(self):
        self.assertEqual(ev.route_check(["references/tables.md", "x.md"], ["references/tables.md"], {}),
                         ("references/tables.md", True))
        self.assertEqual(ev.route_check(["references/other.md"], ["references/tables.md"], {}),
                         ("references/other.md", False))
        self.assertEqual(ev.route_check([], ["references/tables.md"], {}), (None, False))

    def test_directory_routes_and_skill_md_route(self):
        self.assertTrue(ev.route_check(["data/bot-api/methods.json"], ["data/bot-api/"], {})[1])
        self.assertTrue(ev.route_check([], ["SKILL.md"], {})[1])

    def test_playbook_refs_count_as_the_route(self):
        books = {"commands/audit.md": ["references/auditing-existing-bots.md", "references/inline-keyboards.md"]}
        self.assertEqual(ev.route_check(["commands/audit.md"], ["references/inline-keyboards.md"], books),
                         ("commands/audit.md", True))
        self.assertFalse(ev.route_check(["commands/audit.md"], ["references/tables.md"], books)[1])
        self.assertFalse(ev.route_check(["commands/audit.md"], ["references/tables.md"], {})[1])

    def test_playbook_index_shapes_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ev.playbook_refs(os.path.join(tmp, "absent.json")), {})
            path = os.path.join(tmp, "index.json")
            for shape in ({"audit": {"refs": ["references/a.md"]}},
                          {"commands": {"audit": {"refs": ["references/a.md"]}}},
                          [{"verb": "audit", "refs": ["references/a.md"]}],
                          [{"name": "x", "file": "commands/audit.md", "refs": ["references/a.md"]}],
                          {"commands": [{"verb": "x", "playbook": "commands/audit.md", "refs": ["references/a.md"]}]}):
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(shape, fh)
                self.assertEqual(ev.playbook_refs(path), {"commands/audit.md": ["references/a.md"]}, shape)

    def test_the_real_index_maps_every_playbook_to_its_refs(self):
        with open(ev.PLAYBOOK_INDEX, encoding="utf-8") as fh:
            index = json.load(fh)
        books = ev.playbook_refs()
        self.assertEqual(set(books), {c["playbook"] for c in index["commands"]})
        self.assertIn("references/updates-and-delivery.md", books["commands/fix.md"])

    def test_the_first_playbook_read_decides_even_after_other_skill_files(self):
        books = ev.playbook_refs()
        for reads in (["commands/index.json", "commands/fix.md"],
                      ["references/floor.md", "commands/fix.md", "references/streaming-and-editing.md"]):
            self.assertEqual(ev.route_check(reads, ["references/updates-and-delivery.md"], books),
                             (reads[0], True), reads)
        self.assertEqual(ev.first_playbook(["commands/index.json", "references/floor.md", "commands/fix.md",
                                            "commands/audit.md"]), "commands/fix.md")
        self.assertIsNone(ev.first_playbook(["commands/index.json", "references/floor.md"]))

    def test_a_route_may_name_the_playbook_itself(self):
        self.assertTrue(ev.route_check(["commands/index.json", "commands/lookup.md"],
                                       ["commands/lookup.md", "data/bot-api/"], {})[1])

    def test_a_wrong_playbook_is_a_miss_even_when_the_reference_is_read_later(self):
        books = {"commands/audit.md": ["references/auditing-existing-bots.md"]}
        self.assertFalse(ev.route_check(["commands/audit.md", "references/tables.md"], ["references/tables.md"],
                                        books)[1])
        # Read straight away, without a playbook, the reference itself is the route.
        self.assertTrue(ev.route_check(["references/tables.md", "commands/audit.md"], ["references/tables.md"],
                                       books)[1])


class SummaryTest(unittest.TestCase):
    @staticmethod
    def run_of(copy="project", error=None, activated=True, route_ok=True, tokens=None):
        return {"activated": activated, "ok": not error, "copy": copy, "error": error,
                "route_ok": route_ok, "tokens": tokens}

    def case(self, expect, ok, *runs):
        return {"id": "X", "expect": expect, "ok": ok, "correct_runs": 1, "runs": list(runs)}

    def test_clean_run_is_valid_with_route_accuracy_and_mean_tokens(self):
        t1, t2 = {"input": 100, "output": 10}, {"input": 300, "output": 30}
        results = [self.case("activate", True, self.run_of(tokens=t1)),
                   self.case("activate", False, self.run_of(route_ok=False, tokens=t2)),
                   self.case("skip", True, self.run_of(copy="none", activated=False, route_ok=None))]
        summary = ev.summarize(results)
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["route_accuracy"], {"correct": 1, "of": 2})
        self.assertEqual(summary["mean_tokens"], {"input": 200.0, "output": 20.0, "runs": 2})
        self.assertEqual((summary["true_positive"], summary["false_negative"], summary["false_positive"]), (1, 1, 0))
        self.assertEqual(summary["copies"], {"project": 2, "other": 0, "none": 1, "unknown": 0})

    def test_other_copy_makes_the_run_invalid(self):
        summary = ev.summarize([self.case("activate", True, self.run_of(copy="other"))])
        self.assertFalse(summary["valid"])
        self.assertEqual(summary["copies"]["other"], 1)
        self.assertTrue(summary["invalid_reasons"])

    def test_an_unidentified_copy_makes_the_run_invalid(self):
        summary = ev.summarize([self.case("activate", True, self.run_of(copy="unknown"))])
        self.assertFalse(summary["valid"])
        self.assertEqual(summary["copies"]["unknown"], 1)

    def test_errored_runs_make_the_run_invalid(self):
        summary = ev.summarize([self.case("skip", False, self.run_of(copy="none", error="exit 1", activated=False))])
        self.assertFalse(summary["valid"])
        self.assertEqual(summary["errors"], 1)


class TimeoutTest(unittest.TestCase):
    """A timeout is not a miss: it is counted apart, and a finished retry makes the run valid."""

    POSITIVE = {"id": "X1", "expect": "activate", "routes_to": ["references/tables.md"]}
    NEGATIVE = {"id": "X2", "expect": "skip", "routes_to": []}

    @staticmethod
    def info(activated=True, finished=True, error=None, reads=("references/tables.md",)):
        return {"activated": activated, "copy": "project" if activated else "none", "loaded": [], "reads": list(reads),
                "tokens": None, "model": None, "finished": finished, "error": error}

    def attempts(self, case, *outcomes):
        """An attempt function that replays (info, status) pairs, one per call."""
        queue = list(outcomes)
        return lambda: ev.score_run(case, *queue.pop(0), {})

    def test_a_timed_out_attempt_is_not_scored(self):
        run = ev.score_run(self.NEGATIVE, self.info(activated=False, finished=False), "timeout", {})
        self.assertEqual((run["ok"], run["timed_out"], run["error"]), (None, True, None))
        positive = ev.score_run(self.POSITIVE, self.info(finished=False), "timeout", {})
        self.assertIsNone(positive["route_ok"])

    def test_an_error_in_the_transcript_wins_over_the_timeout(self):
        run = ev.score_run(self.POSITIVE, self.info(finished=False, error="usage limit reached"), "timeout", {})
        self.assertEqual((run["ok"], run["timed_out"], run["error"]), (False, False, "usage limit reached"))

    def test_without_retries_a_timeout_leaves_the_case_unscored_and_the_run_invalid(self):
        case = ev.run_case(self.NEGATIVE, 1, self.attempts(self.NEGATIVE, (self.info(False, False), "timeout")),
                           retry_timeouts=0, log=lambda *_: None)
        self.assertIsNone(case["ok"])
        self.assertEqual((case["runs"][0]["timeouts"], case["runs"][0]["attempts"]), (1, 1))
        summary = ev.summarize([case])
        self.assertEqual((summary["false_negative"], summary["false_positive"], summary["unscored"]), (0, 0, 1))
        self.assertEqual(summary["timeouts"], {"unresolved": 1, "retried": 0, "attempts": 1})
        self.assertEqual(summary["errors"], 0)
        self.assertFalse(summary["valid"])

    def test_a_retry_that_finishes_replaces_the_timeout_and_the_run_is_valid(self):
        attempt = self.attempts(self.POSITIVE, (self.info(finished=False), "timeout"), (self.info(), 0))
        case = ev.run_case(self.POSITIVE, 1, attempt, retry_timeouts=1, log=lambda *_: None)
        run = case["runs"][0]
        self.assertEqual((run["ok"], run["timed_out"], run["timeouts"], run["attempts"], run["route_ok"]),
                         (True, False, 1, 2, True))
        self.assertTrue(case["ok"])
        summary = ev.summarize([case])
        self.assertEqual(summary["timeouts"], {"unresolved": 0, "retried": 1, "attempts": 1})
        self.assertTrue(summary["valid"], summary["invalid_reasons"])
        self.assertEqual(summary["route_accuracy"], {"correct": 1, "of": 1})

    def test_retries_stop_at_the_limit(self):
        attempt = self.attempts(self.NEGATIVE, *[(self.info(False, False), "timeout")] * 3)
        case = ev.run_case(self.NEGATIVE, 1, attempt, retry_timeouts=2, log=lambda *_: None)
        self.assertEqual((case["runs"][0]["attempts"], case["runs"][0]["timeouts"], case["ok"]), (3, 3, None))
        self.assertEqual(ev.summarize([case])["timeouts"], {"unresolved": 1, "retried": 0, "attempts": 3})

    def test_the_majority_counts_only_scored_runs(self):
        outcomes = [(self.info(False, False), "timeout"), (self.info(False), 0), (self.info(True), 0)]
        case = ev.run_case(self.NEGATIVE, 3, self.attempts(self.NEGATIVE, *outcomes), retry_timeouts=0,
                           log=lambda *_: None)
        self.assertEqual((case["correct_runs"], case["scored_runs"], case["ok"]), (1, 2, True))   # ceil(2/2) = 1

    def test_the_retry_flag_defaults_to_off_and_bare_means_one(self):
        parser = ev.build_parser()
        self.assertEqual(parser.parse_args([]).retry_timeouts, 0)
        self.assertEqual(parser.parse_args(["--retry-timeouts"]).retry_timeouts, 1)
        self.assertEqual(parser.parse_args(["--retry-timeouts", "2"]).retry_timeouts, 2)


class FixtureTest(unittest.TestCase):
    """Cases that only make sense inside a bot project run in a copy of evals/fixtures/<name>."""

    def test_the_four_context_cases_use_the_bot_fixture(self):
        cases = {a["id"]: a for a in ev.load()["activation"]}
        for cid in ("P8", "P22", "P31", "P33"):
            self.assertEqual(cases[cid].get("fixture"), "bot-project", cid)

    def test_validator_rejects_an_unknown_or_escaping_fixture(self):
        for bad in ("no-such-fixture", "../evals", ""):
            data = ev.load()
            data["activation"][0]["fixture"] = bad
            self.assertTrue(any("fixture" in e for e in ev.validate(data)), bad)

    def test_copy_fixture_puts_the_bot_into_the_project(self):
        with tempfile.TemporaryDirectory() as project:
            ev.copy_fixture("bot-project", project)
            self.assertTrue(os.path.isfile(os.path.join(project, "bot.py")))
            self.assertFalse(os.path.exists(os.path.join(project, "__pycache__")))


class CommandAndIsolationTest(unittest.TestCase):
    def test_claude_drops_user_sources_and_keeps_write_tools_denied(self):
        cmd = ev.host_command("claude", "hi", "/tmp/p", None)
        at = cmd.index("--setting-sources")
        self.assertEqual(cmd[at + 1], "project,local")
        self.assertIn("Write", cmd[cmd.index("--disallowedTools") + 1])
        self.assertIn("hi", cmd)

    def test_prompt_moves_to_stdin_when_asked(self):
        claude = ev.host_command("claude", "hi", "/tmp/p", None, via_stdin=True)
        self.assertNotIn("hi", claude)
        codex = ev.host_command("codex", "hi", "/tmp/p", "m1", via_stdin=True)
        self.assertEqual(codex[-1], "-")
        self.assertEqual(ev.host_command("codex", "hi", "/tmp/p", "m1")[-1], "hi")

    def test_codex_child_gets_an_empty_home_and_the_real_codex_home(self):
        with mock.patch.dict(os.environ, {"CODEX_HOME": "/real/codex", "HOME": "/h", "USERPROFILE": "/h"}):
            env = ev.child_env("codex", "/empty")
            self.assertEqual((env["HOME"], env["USERPROFILE"], env["CODEX_HOME"]), ("/empty", "/empty", "/real/codex"))
        with mock.patch.dict(os.environ, {"HOME": "/h", "USERPROFILE": "/h"}):
            os.environ.pop("CODEX_HOME", None)
            env = ev.child_env("codex", "/empty")
            self.assertEqual(env["CODEX_HOME"], os.path.join(os.path.expanduser("~"), ".codex"))

    def test_codex_switches_off_user_level_copies_without_touching_them(self):
        with tempfile.TemporaryDirectory() as codex_dir, tempfile.TemporaryDirectory() as home:
            copy = os.path.join(codex_dir, "skills", SKILL)
            os.makedirs(copy)
            skill_md = os.path.join(copy, "SKILL.md")
            with open(skill_md, "w", encoding="utf-8") as fh:
                fh.write("---\nname: telegram-bot-ui\n---\n")
            with mock.patch.dict(os.environ, {"CODEX_HOME": codex_dir, "HOME": home, "USERPROFILE": home}):
                found = ev.user_level_copies("codex")
                self.assertEqual(found, [skill_md.replace("\\", "/")])
                self.assertEqual(ev.user_level_copies("claude"), [])
            cmd = ev.host_command("codex", "hi", "/tmp/p", None, True, found)
            override = cmd[cmd.index("-c") + 1]
            self.assertEqual(override, f"skills.config=[{{path='{found[0]}', enabled=false}}]")
            self.assertNotIn('"', override)
            self.assertNotIn("-c", ev.host_command("codex", "hi", "/tmp/p", None, True, []))
            with open(skill_md, encoding="utf-8") as fh:
                self.assertTrue(fh.read().startswith("---"))   # untouched

    def test_claude_child_keeps_the_real_home_for_the_login(self):
        with mock.patch.dict(os.environ, {"HOME": "/h", "USERPROFILE": "/h"}):
            env = ev.child_env("claude", "/empty")
            self.assertEqual((env["HOME"], env["USERPROFILE"]), ("/h", "/h"))

    def test_workspace_root_is_outside_the_home_folder(self):
        root = ev.make_root()
        try:
            self.assertFalse(ev.inside(root, os.path.expanduser("~")), root)
        finally:
            ev.remove_tree(root)

    def test_workspace_root_is_private_to_the_current_user(self):
        root = ev.make_root()
        try:
            if os.name == "nt":
                out = subprocess.run(["icacls", root], capture_output=True, text=True).stdout
                principals = {m.group(1).strip().lower() for m in re.finditer(r"(\S[^:\n]*?):\(", out)}
                self.assertTrue(principals, out)
                open_to_others = {"everyone", "builtin\\users", "nt authority\\authenticated users"}
                self.assertFalse(principals & open_to_others, out)
            else:
                self.assertEqual(os.stat(root).st_mode & 0o077, 0)
        finally:
            ev.remove_tree(root)

    def test_a_clean_transcript_with_a_failing_exit_code_is_an_error(self):
        done = {"error": None, "finished": True}
        self.assertIsNone(ev.run_error(done, 0))
        self.assertEqual(ev.run_error(done, 1), "exit 1 after the final event")
        self.assertEqual(ev.run_error(done, "timeout"), "timeout")
        self.assertEqual(ev.run_error({"error": None, "finished": False}, 0), "no final event (exit 0)")
        self.assertEqual(ev.run_error({"error": "boom", "finished": True}, 0), "boom")

    def test_child_gets_the_prompt_on_stdin_unchanged_and_a_hung_child_is_killed(self):
        echo = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"]
        out, status = ev.run_child(echo, "line one\nline two ✓", os.getcwd(), dict(os.environ), 30)
        self.assertEqual((out, status), ("line one\nline two ✓", 0))   # no CRLF, UTF-8 intact
        hang = [sys.executable, "-c", "import time; time.sleep(60)"]
        self.assertEqual(ev.run_child(hang, "", os.getcwd(), dict(os.environ), 1)[1], "timeout")

    def test_validator_rejects_a_route_that_does_not_exist(self):
        data = ev.load()
        data["activation"][0]["routes_to"] = ["references/no-such-file.md"]
        self.assertTrue(any("does not exist" in e for e in ev.validate(data)))


if __name__ == "__main__":
    unittest.main()
