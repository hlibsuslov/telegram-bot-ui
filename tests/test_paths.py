"""Every command's path works from an installed copy, and the directory edition keeps a path
without scripts.

For each command in commands/index.json, the skill is installed into a temporary project the
way users get it (scripts/install.py, project scope, a plain copy), a small aiogram bot is put
next to it, and each `smoke` step runs through the installed `scripts/tgui.py`. A step passes
when it exits with one of its `ok` codes (default 0). This is what "all paths work" means for
the tools; the reasoning in the playbooks is measured by evals.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.REPO, "scripts"))
import install  # noqa: E402
import build_directory_edition as edition  # noqa: E402

BOT = '''from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
MENU = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Pay", callback_data="pay")]])


@router.callback_query(F.data == "pay")
async def pay(cb):
    await cb.answer()
'''


def index() -> dict:
    with open(os.path.join(_paths.ROOT, "commands", "index.json"), encoding="utf-8") as fh:
        return json.load(fh)


class InstalledCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp(prefix="tgui-paths-")
        cls.project = os.path.join(cls.tmp, "my bot")
        os.makedirs(cls.project)
        with open(os.path.join(cls.project, "bot.py"), "w", encoding="utf-8") as fh:
            fh.write(BOT)
        home = os.path.join(cls.tmp, "home")
        os.makedirs(home)
        inst = install.Installer(home=home, project=cls.project, dry_run=False, link=False)
        inst.install("claude", "project", agents=False, instructions=False)
        cls.skill = os.path.join(cls.project, ".claude", "skills", "telegram-bot-ui")
        cls.tgui = os.path.join(cls.skill, "scripts", "tgui.py")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q", cls.project], check=False)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_step(self, verb: str, step: dict) -> None:
        for name, content in step.get("files", {}).items():
            with open(os.path.join(self.project, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        args = [a.replace("{project}", self.project).replace("{skill}", self.skill) for a in step["args"]]
        proc = subprocess.run([sys.executable, self.tgui, *args], cwd=self.project, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        ok = step.get("ok", [0])
        self.assertIn(proc.returncode, ok,
                      f"{verb}: tgui.py {' '.join(step['args'])} exited {proc.returncode}\n"
                      f"{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")

    def test_installed_copy_is_the_skill(self):
        self.assertTrue(os.path.isfile(self.tgui))
        self.assertTrue(os.path.isfile(os.path.join(self.skill, "scripts", "bot_ui", "cli.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.skill, "scripts", "bot_ui", "templates", "checkout",
                                                    "project.json")))

    def test_every_command_runs_from_the_installed_copy(self):
        for command in index()["commands"]:
            with self.subTest(verb=command["verb"]):
                self.assertTrue(command["smoke"], f"{command['verb']} has no smoke steps")
                for step in command["smoke"]:
                    self.run_step(command["verb"], step)

    def test_every_playbook_and_reference_is_installed(self):
        for command in index()["commands"]:
            for rel in [command["playbook"], *command["refs"]]:
                self.assertTrue(os.path.isfile(os.path.join(self.skill, *rel.split("/"))), rel)
        self.assertTrue(os.path.isfile(os.path.join(self.skill, "references", "floor.md")))


class DirectoryEdition(unittest.TestCase):
    def test_edition_has_playbooks_and_no_scripts(self):
        out = tempfile.mkdtemp(prefix="tgui-edition-")
        try:
            files = edition.build(out)
            skill = "skills/telegram-bot-ui/"
            self.assertFalse([f for f in files if f.startswith(skill + "scripts/")])
            for command in index()["commands"]:
                self.assertIn(skill + command["playbook"], files)
                with open(os.path.join(out, *(skill + command["playbook"]).split("/")), encoding="utf-8") as fh:
                    self.assertIn("## Without scripts", fh.read())
            with open(os.path.join(out, *(skill + "SKILL.md").split("/")), encoding="utf-8") as fh:
                self.assertIn("Directory edition", fh.read())
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
