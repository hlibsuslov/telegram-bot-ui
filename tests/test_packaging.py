"""Packaging: adapter generator, subagents, plugin manifests, installer, eval files.

Standard library unittest only. The installer runs exclusively against temporary
directories passed as --home/--project; nothing touches the real user profile.
"""
import contextlib
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import _paths  # noqa: F401  (adds scripts/ to sys.path)

import build_adapters as ba
import install
import run_checks
import run_evals
import validate_skill

ROOT = _paths.REPO
SKILL = _paths.ROOT


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = fn(*args, **kwargs)
    return result, out.getvalue()


class AdapterGeneratorTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(ba.build(), ba.build())

    def test_checked_in_adapters_are_in_sync(self):
        self.assertEqual(ba.stale(ba.build()), [], "run `python scripts/build_adapters.py`")

    def test_outputs_cover_every_host(self):
        out = ba.build()
        for rel in (f"{ba.SKILL_REL}/agents/openai.yaml", f"{ba.SKILL_REL}/LICENSE",
                    "adapters/agents-md/AGENTS.snippet.md",
                    "adapters/cursor/telegram-bot-ui.mdc", "adapters/gemini/GEMINI.md",
                    "adapters/copilot/copilot-instructions.md",
                    "adapters/portable/telegram-bot-ui.prompt.md", "llms.txt",
                    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                    "plugin.json", ".codex-plugin/plugin.json"):
            self.assertIn(rel, out)
        roles = ba.load_routing()["roles"]
        for role in roles:
            self.assertIn(f"agents/claude/{role['name']}.md", out)
            self.assertIn(f"agents/codex/{ba.codex_name(role)}.toml", out)
        self.assertEqual(len(roles), 5)

    def test_pointer_blocks_are_marked_and_take_a_path(self):
        routing = ba.load_routing()
        text = ba.render_pointer(routing, "agents-md", "custom/place")
        self.assertTrue(text.startswith(ba.BEGIN_MARK))
        self.assertTrue(text.rstrip().endswith(ba.END_MARK))
        self.assertIn("custom/place/SKILL.md", text)
        self.assertLess(len(text.encode()), 4096, "AGENTS.md budget is shared (32 KiB in Codex)")

    def test_cursor_rule_is_agent_requested_mdc(self):
        text = ba.build()["adapters/cursor/telegram-bot-ui.mdc"]
        fm = text.split("---")[1]
        self.assertIn("description:", fm)
        self.assertIn("alwaysApply: false", fm)
        self.assertNotIn("globs:", fm)

    def test_portable_prompt_keeps_rules_and_lists_omissions(self):
        text = ba.build()["adapters/portable/telegram-bot-ui.prompt.md"]
        _, sections = ba.load_skill()
        for heading, _ in sections:
            if heading in ba.load_routing()["portable"]["exclude_sections"]:
                self.assertNotIn(f"\n## {heading}\n", text)
            else:
                self.assertIn(f"\n## {heading}\n", text)
        self.assertIn("## Left out of this prompt", text)
        self.assertIn("references/widgets.md", text.split("## Left out of this prompt")[1])

    def test_llms_txt_follows_the_format(self):
        lines = ba.build()["llms.txt"].splitlines()
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(any(line.startswith("> ") for line in lines[:4]))
        links = [line for line in lines if line.startswith("- [")]
        for line in links:
            target = re.match(r"- \[[^\]]+\]\(([^)]+)\)", line).group(1)
            self.assertTrue(os.path.exists(os.path.join(ROOT, target)), target)
        self.assertIn("## Optional", lines)

    def test_front_matter_parser_matches_skill(self):
        meta, _ = ba.load_skill()
        self.assertEqual(meta["name"], "telegram-bot-ui")
        self.assertNotIn("\n", meta["description"])


class SubagentFormatTest(unittest.TestCase):
    def _claude_agents(self):
        folder = os.path.join(ROOT, "agents", "claude")
        for name in sorted(os.listdir(folder)):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                yield name, fh.read()

    def test_claude_subagents_front_matter(self):
        for name, text in self._claude_agents():
            self.assertTrue(text.startswith("---\n"), name)
            fm, body = validate_skill.split_front_matter(text)
            meta = validate_skill.parse_front_matter(fm)
            self.assertEqual(meta["name"], name[:-3])
            self.assertNotIn(":", meta["name"])
            self.assertGreater(len(meta["description"]), 60)
            tools = {t.strip() for t in meta["tools"].split(",")}
            self.assertLessEqual(tools, validate_skill.CLAUDE_TOOLS)
            self.assertIn("Skill", tools)
            self.assertIn(meta["color"], validate_skill.CLAUDE_COLORS)
            self.assertIn("telegram-bot-ui", body)

    def test_read_only_roles_cannot_edit(self):
        for name, text in self._claude_agents():
            if name in ("telegram-bot-designer.md", "telegram-bot-reviewer.md"):
                tools_line = next(line for line in text.splitlines() if line.startswith("tools:"))
                self.assertNotIn("Edit", tools_line)
                self.assertNotIn("Write", tools_line)

    def test_codex_agents_are_valid_toml(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib needs Python 3.11+")
        folder = os.path.join(ROOT, "agents", "codex")
        files = sorted(os.listdir(folder))
        self.assertEqual(len(files), 5)
        for name in files:
            with open(os.path.join(folder, name), "rb") as fh:
                data = tomllib.load(fh)
            self.assertEqual(data["name"], name[:-5])
            self.assertTrue(data["description"].strip())
            self.assertIn("$telegram-bot-ui", data["developer_instructions"])
            self.assertEqual(set(data), {"name", "description", "developer_instructions"})

    def test_publisher_requires_approval_and_no_double_post(self):
        text = ba.build()["agents/claude/telegram-publisher.md"].lower()
        self.assertIn("approval before publish", text)
        self.assertIn("no double post", text)
        self.assertIn("never printed", text)


class ManifestTest(unittest.TestCase):
    def test_plugin_manifest(self):
        plugin = json.loads(ba.build()[".claude-plugin/plugin.json"])
        self.assertEqual(plugin["name"], "telegram-bot-ui")
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertNotIn("skills", plugin)
        # The default skills/ scan finds exactly one skill, and no root SKILL.md doubles it.
        self.assertEqual(os.listdir(os.path.join(ROOT, "skills")), ["telegram-bot-ui"])
        self.assertTrue(os.path.isfile(os.path.join(SKILL, "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "SKILL.md")))
        for rel in plugin["agents"]:
            self.assertTrue(rel.startswith("./agents/claude/") and rel.endswith(".md"))
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel[2:])))

    def test_portable_manifests_share_the_plugin_identity(self):
        out = ba.build()
        claude = json.loads(out[".claude-plugin/plugin.json"])
        portable = json.loads(out["plugin.json"])
        codex = json.loads(out[".codex-plugin/plugin.json"])
        self.assertEqual(portable["$schema"], ba.AGENT_PLUGINS_SCHEMA)
        for key in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(portable[key], claude[key], key)
            self.assertEqual(codex[key], claude[key], key)
        self.assertLessEqual(set(portable), validate_skill.AGENT_PLUGINS_KEYS)
        self.assertEqual(codex["skills"], "./skills/")
        errors = []
        validate_skill.check_portable_manifests(ROOT, "telegram-bot-ui", errors)
        self.assertEqual(errors, [])

    def test_marketplace_manifest(self):
        market = json.loads(ba.build()[".claude-plugin/marketplace.json"])
        self.assertRegex(market["name"], validate_skill.PLUGIN_ID_RE.pattern)
        self.assertTrue(market["owner"]["name"])
        entry = market["plugins"][0]
        self.assertEqual(entry["name"], "telegram-bot-ui")
        self.assertEqual(entry["source"], "./")
        reserved = ("claude-", "anthropic-")
        self.assertFalse(market["name"].startswith(reserved))

    def test_openai_yaml_uses_documented_keys(self):
        errors = []
        validate_skill.check_openai_yaml(ROOT, errors)
        self.assertEqual(errors, [])

    def test_validator_packaging_checks_pass(self):
        errors, warnings = [], []
        validate_skill.check_packaging(ROOT, "telegram-bot-ui", errors, warnings)
        self.assertEqual(errors, [])

    def test_skill_front_matter_suits_directories(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            fm, _ = validate_skill.split_front_matter(fh.read())
        # Skill directories show a folded `>-` literally; keep description one quoted line.
        self.assertRegex(fm, r'(?m)^description: "[^"\n]+"$')
        self.assertRegex(fm, r"(?m)^license: MIT$")
        errors = []
        validate_skill.check_metadata_version(ROOT, fm, errors)
        self.assertEqual(errors, [])
        validate_skill.check_metadata_version(ROOT, 'metadata:\n  version: "0.0.1"\n', errors)
        self.assertEqual(len(errors), 1)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.project = os.path.join(self.tmp.name, "project")
        os.makedirs(self.home)
        os.makedirs(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args):
        code, out = quiet(install.main, ["--home", self.home, "--project", self.project, *args])
        self.assertEqual(code, 0)
        return out

    def p(self, *parts):
        return os.path.join(self.project, *parts)

    def h(self, *parts):
        return os.path.join(self.home, *parts)

    def snapshot(self):
        found = []
        for base in (self.home, self.project):
            for dirpath, dirnames, filenames in os.walk(base):
                found += [os.path.join(dirpath, n) for n in dirnames + filenames]
        return sorted(found)

    def test_dry_run_changes_nothing(self):
        before = self.snapshot()
        out = self.run_install("--host", "all", "--scope", "project", "--with-instructions", "--dry-run")
        self.assertIn("[dry-run]", out)
        self.assertEqual(self.snapshot(), before)

    def test_installed_example_library_is_discoverable(self):
        self.run_install("--host", "codex", "--scope", "project")
        root = self.p(".agents", "skills", "telegram-bot-ui")
        for rel in ("recipes/use-cases.json", "references/example-library.md"):
            self.assertTrue(os.path.isfile(os.path.join(root, rel)), rel)
        result = subprocess.run([sys.executable, os.path.join(root, "scripts", "example_library.py"),
                                 "--query", "waitlist", "--json"], cwd=self.project,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]["id"], "events")

    def test_user_scope_locations_per_host(self):
        expected = {
            "claude": self.h(".claude", "skills", "telegram-bot-ui"),
            "codex": self.h(".agents", "skills", "telegram-bot-ui"),
            "cursor": self.h(".agents", "skills", "telegram-bot-ui"),
            "gemini": self.h(".gemini", "skills", "telegram-bot-ui"),
            "copilot": self.h(".agents", "skills", "telegram-bot-ui"),
        }
        for host, path in expected.items():
            self.run_install("--host", host, "--scope", "user")
            self.assertTrue(os.path.isfile(os.path.join(path, "SKILL.md")), host)
            self.assertTrue(os.path.isfile(os.path.join(path, install.MARKER)), host)
        self.assertTrue(os.path.isfile(self.h(".claude", "agents", "telegram-publisher.md")))
        self.assertTrue(os.path.isfile(self.h(".codex", "agents", "telegram_publisher.toml")))
        installed = self.h(".agents", "skills", "telegram-bot-ui")
        self.assertTrue(os.path.isfile(os.path.join(installed, "agents", "openai.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(installed, "LICENSE")))
        self.assertFalse(os.path.exists(os.path.join(installed, "tests")))
        self.assertFalse(os.path.exists(os.path.join(installed, ".git")))

    def test_all_hosts_share_one_agents_skills_copy(self):
        out = self.run_install("--host", "all", "--scope", "project")
        self.assertEqual(out.count("already handled"), 3)
        self.assertTrue(os.path.isdir(self.p(".claude", "skills", "telegram-bot-ui")))
        self.assertTrue(os.path.isdir(self.p(".agents", "skills", "telegram-bot-ui")))

    def test_reinstall_is_idempotent_for_files(self):
        self.run_install("--host", "claude", "--scope", "project")
        out = self.run_install("--host", "claude", "--scope", "project")
        self.assertIn("update", out)
        self.assertNotIn("backup", out)
        self.assertEqual(out.count("same"), 5)

    def test_foreign_skill_folder_is_backed_up(self):
        foreign = self.p(".claude", "skills", "telegram-bot-ui")
        os.makedirs(foreign)
        with open(os.path.join(foreign, "SKILL.md"), "w") as fh:
            fh.write("mine")
        self.run_install("--host", "claude", "--scope", "project", "--no-agents")
        backups = [n for n in os.listdir(self.p(".claude", "skills")) if ".bak-" in n]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.p(".claude", "skills", backups[0]), "SKILL.md")) as fh:
            self.assertEqual(fh.read(), "mine")

    def test_foreign_agent_file_backed_up_and_kept_on_uninstall(self):
        agents = self.p(".claude", "agents")
        os.makedirs(agents)
        mine = os.path.join(agents, "telegram-publisher.md")
        with open(mine, "w") as fh:
            fh.write("---\nname: telegram-publisher\ndescription: my own\n---\n")
        self.run_install("--host", "claude", "--scope", "project")
        self.assertEqual(len([n for n in os.listdir(agents) if ".bak-" in n]), 1)
        with open(mine, "w") as fh:  # user replaces ours with their own again
            fh.write("---\nname: telegram-publisher\ndescription: my own\n---\n")
        out = self.run_install("--host", "claude", "--scope", "project", "--uninstall")
        self.assertIn("not installed by this tool", out)
        self.assertTrue(os.path.isfile(mine))
        self.assertFalse(os.path.exists(os.path.join(agents, "telegram-bot-reviewer.md")))

    def test_instruction_block_insert_update_remove(self):
        agents_md = self.p("AGENTS.md")
        with open(agents_md, "w", encoding="utf-8") as fh:
            fh.write("# Team rules\n\nUse tabs.\n")
        self.run_install("--host", "codex", "--scope", "project", "--with-instructions")
        with open(agents_md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("# Team rules\n\nUse tabs.\n"))
        self.assertEqual(text.count(ba.BEGIN_MARK), 1)
        self.assertIn(".agents/skills/telegram-bot-ui/SKILL.md", text)
        self.assertTrue(any(".bak-" in n for n in os.listdir(self.project)))
        out = self.run_install("--host", "codex", "--scope", "project", "--with-instructions")
        self.assertIn("same", out)
        self.run_install("--host", "codex", "--scope", "project", "--uninstall")
        with open(agents_md, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# Team rules\n\nUse tabs.\n")

    def test_instruction_files_created_by_us_are_removed_cleanly(self):
        self.run_install("--host", "all", "--scope", "project", "--with-instructions")
        for rel in (("GEMINI.md",), (".github", "copilot-instructions.md"),
                    (".cursor", "rules", "telegram-bot-ui.mdc")):
            self.assertTrue(os.path.isfile(self.p(*rel)), rel)
        self.run_install("--host", "all", "--scope", "project", "--uninstall")
        self.assertEqual(os.listdir(self.project), [])

    def test_user_scope_never_writes_instruction_files(self):
        out = self.run_install("--host", "codex", "--scope", "user", "--with-instructions")
        self.assertIn("user-level files are personal", out)
        self.assertFalse(os.path.exists(self.h(".codex", "AGENTS.md")))

    def test_uninstall_keeps_foreign_skill_folder(self):
        foreign = self.h(".agents", "skills", "telegram-bot-ui")
        os.makedirs(foreign)
        out = self.run_install("--host", "codex", "--scope", "user", "--uninstall")
        self.assertIn("not installed by this tool", out)
        self.assertTrue(os.path.isdir(foreign))

    def test_link_mode_points_at_checkout_or_falls_back(self):
        out = self.run_install("--host", "codex", "--scope", "project", "--link", "--no-agents")
        dest = self.p(".agents", "skills", "telegram-bot-ui")
        if os.path.islink(dest):
            self.assertEqual(os.path.realpath(dest), os.path.realpath(SKILL))
            self.run_install("--host", "codex", "--scope", "project", "--uninstall")
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "SKILL.md")), "uninstall must not follow the link")
            self.assertFalse(os.path.lexists(dest))
        else:
            self.assertIn("fallback", out)
            self.assertTrue(os.path.isfile(os.path.join(dest, "SKILL.md")))

    def test_replace_block(self):
        block = f"{ba.BEGIN_MARK}\nX\n{ba.END_MARK}\n"
        self.assertEqual(install.replace_block("", block), block)
        once = install.replace_block("a\n", block)
        self.assertEqual(install.replace_block(once, block), once)
        self.assertEqual(install.replace_block(once, ""), "a\n")
        self.assertFalse(install.has_foreign_content(block))
        self.assertTrue(install.has_foreign_content(once))


class EvalFilesTest(unittest.TestCase):
    def test_eval_file_is_valid(self):
        self.assertEqual(run_evals.validate(run_evals.load(), run_evals.md_tables()), [])

    def test_validator_detects_problems(self):
        data = copy.deepcopy(run_evals.load())
        data["activation"].append(copy.deepcopy(data["activation"][0]))
        data["activation"] = [a for a in data["activation"]
                              if not (a["area"] == "publishing" and a["lang"] == "ru")]
        data["behavioral"] = [b for b in data["behavioral"] if b["id"] != "B31"]
        errors = run_evals.validate(data)
        self.assertTrue(any("duplicate id" in e for e in errors))
        self.assertTrue(any("ru positive" in e and "publishing" in e for e in errors))
        self.assertTrue(any("B31" in e for e in errors))

    def test_every_area_has_behavioral_and_transfer_tasks(self):
        data = run_evals.load()
        for area in run_evals.TRANSFER_AREAS:
            tasks = [b for b in data["behavioral"] if b["area"] == area]
            self.assertTrue(any("transfer" in b for b in tasks), area)
            self.assertTrue(all(b["critical_failures"] for b in tasks), area)

    def test_no_agent_run_is_claimed(self):
        self.assertEqual(run_evals.load()["runs"], [])

    def test_claude_detection(self):
        hit = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "telegram-bot-ui"}}]}})
        read = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read",
             "input": {"file_path": "C:\\p\\.claude\\skills\\telegram-bot-ui\\SKILL.md"}}]}})
        miss = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "telegram-bot-ui/SKILL.md mentioned in prose"}]}})
        self.assertTrue(run_evals.skill_loaded("claude", hit))
        self.assertTrue(run_evals.skill_loaded("claude", read))
        self.assertFalse(run_evals.skill_loaded("claude", miss))

    def test_codex_detection_and_read_only_commands(self):
        self.assertTrue(run_evals.skill_loaded("codex", '{"cmd":"cat .agents/skills/telegram-bot-ui/SKILL.md"}'))
        self.assertFalse(run_evals.skill_loaded("codex", '{"msg":"hello"}'))
        codex = run_evals.host_command("codex", "hi", "/tmp/p", "m1")
        self.assertIn("read-only", codex)
        self.assertEqual(codex[-1], "hi")
        claude = run_evals.host_command("claude", "hi", "/tmp/p", None)
        self.assertIn("Write", claude[claude.index("--disallowedTools") + 1])


class RunChecksDiscoveryTest(unittest.TestCase):
    def test_scripts_join_by_marker(self):
        found = {name: args for name, _, args in run_checks.discovered_scripts()}
        self.assertEqual(found.get("build_adapters"), ["--check"])
        self.assertEqual(found.get("run_evals"), [])
        self.assertNotIn("validate_skill", found)

    def test_node_tests_are_grouped_by_package(self):
        groups = {os.path.relpath(pkg, ROOT).replace(os.sep, "/"): (tests, needs)
                  for pkg, tests, needs in run_checks.node_groups()}
        self.assertIn("skills/telegram-bot-ui/examples/ts", groups)
        self.assertFalse(groups["skills/telegram-bot-ui/examples/ts"][1])
        self.assertIn("test/recipes.test.ts", groups["skills/telegram-bot-ui/examples/ts"][0])
        if "skills/telegram-bot-ui/examples/ts/sdk-grammy" in groups:
            self.assertTrue(groups["skills/telegram-bot-ui/examples/ts/sdk-grammy"][1])


if __name__ == "__main__":
    unittest.main()
