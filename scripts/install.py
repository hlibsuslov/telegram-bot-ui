#!/usr/bin/env python3
"""Install, update or remove the telegram-bot-ui skill for one or more agent hosts.

  python scripts/install.py --host claude --scope user
  python scripts/install.py --host all --scope project --project ../my-bot --with-instructions
  python scripts/install.py --host codex --scope user --dry-run
  python scripts/install.py --host all --scope project --uninstall

What goes where is documented, with sources, in docs/hosts.md:

  skill folder   claude: ~/.claude/skills/ or .claude/skills/
                 codex, cursor, copilot: ~/.agents/skills/ or .agents/skills/
                 gemini: ~/.gemini/skills/ (Gemini CLI and Antigravity CLI) or .agents/skills/
  subagents      claude: ~/.claude/agents/*.md or .claude/agents/*.md
                 codex:  ~/.codex/agents/*.toml or .codex/agents/*.toml
  instructions   (--with-instructions, project scope only) AGENTS.md (codex),
                 .cursor/rules/telegram-bot-ui.mdc (cursor), GEMINI.md (gemini),
                 .github/copilot-instructions.md (copilot)

Safety: a folder or file that this tool did not create is moved to `<name>.bak-<time>`
before anything is written there; a shared instruction file is backed up before its
marked block is inserted, replaced or removed; --uninstall removes only what this tool
created. Standard library only; never reads credentials; never touches the network.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_adapters as ba  # noqa: E402

ROOT = ba.ROOT
SKILL_SRC = ba.SKILL_DIR
NAME = "telegram-bot-ui"
MARKER = ".telegram-bot-ui-install.json"
HOSTS = ("claude", "codex", "cursor", "gemini", "copilot")
# Entries of the skill folder (skills/telegram-bot-ui/) that make up the installed skill.
SKILL_CONTENT = ("SKILL.md", "LICENSE", "agents/openai.yaml",
                 "references", "recipes", "examples", "scripts", "data")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".DS_Store")

SKILL_DIRS = {
    ("claude", "user"): "~/.claude/skills",
    ("claude", "project"): ".claude/skills",
    ("codex", "user"): "~/.agents/skills",
    ("codex", "project"): ".agents/skills",
    ("cursor", "user"): "~/.agents/skills",
    ("cursor", "project"): ".agents/skills",
    ("gemini", "user"): "~/.gemini/skills",
    ("gemini", "project"): ".agents/skills",
    ("copilot", "user"): "~/.agents/skills",
    ("copilot", "project"): ".agents/skills",
}
AGENT_DIRS = {
    ("claude", "user"): ("~/.claude/agents", "agents/claude", ".md"),
    ("claude", "project"): (".claude/agents", "agents/claude", ".md"),
    ("codex", "user"): ("~/.codex/agents", "agents/codex", ".toml"),
    ("codex", "project"): (".codex/agents", "agents/codex", ".toml"),
}
# host -> (instruction file, kind): "block" = marked block in a shared file, "file" = whole file.
INSTRUCTIONS = {
    "codex": ("AGENTS.md", "block", "agents-md"),
    "cursor": (".cursor/rules/telegram-bot-ui.mdc", "file", "cursor"),
    "gemini": ("GEMINI.md", "block", "gemini"),
    "copilot": (".github/copilot-instructions.md", "block", "copilot"),
}


class Installer:
    def __init__(self, home: str, project: str, dry_run: bool, link: bool):
        self.home, self.project = os.path.abspath(home), os.path.abspath(project)
        self.dry_run, self.link = dry_run, link
        self.stamp = time.strftime("%Y%m%d-%H%M%S")
        self.log: list[str] = []
        self.done: set[str] = set()

    # ------------------------------------------------------------ helpers
    def say(self, action: str, detail: str) -> None:
        line = f"{'[dry-run] ' if self.dry_run else ''}{action:<8} {detail}"
        self.log.append(line)
        print(line)

    def resolve(self, rel: str, scope: str) -> str:
        if rel.startswith("~/"):
            return os.path.join(self.home, *rel[2:].split("/"))
        base = self.project if scope == "project" else self.home
        return os.path.join(base, *rel.split("/"))

    def backup(self, path: str) -> None:
        target = f"{path}.bak-{self.stamp}"
        n = 1
        while os.path.lexists(target):
            n += 1
            target = f"{path}.bak-{self.stamp}-{n}"
        self.say("backup", f"{path} -> {target}")
        if not self.dry_run:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.copytree(path, target, symlinks=True)
            else:
                shutil.copy2(path, target, follow_symlinks=False)

    def move_aside(self, path: str) -> None:
        self.backup(path)
        if not self.dry_run:
            self._remove(path)

    def _remove(self, path: str) -> None:
        if os.path.islink(path) or os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)

    def prune(self, folder: str) -> None:
        """Remove now-empty parent folders, never above the project or home folder."""
        stops = {self.project, self.home}
        folder = os.path.abspath(folder)
        while folder not in stops and os.path.dirname(folder) != folder:
            if not os.path.isdir(folder) or os.listdir(folder):
                return
            os.rmdir(folder)
            folder = os.path.dirname(folder)

    def check_target(self, path: str) -> None:
        """Refuse to write through links: a cloned project could ship
        `AGENTS.md -> ~/.bashrc` or a linked `.claude/` folder to make the installer
        overwrite files outside it. Project paths must resolve inside the project;
        no target file may itself be a link."""
        if os.path.islink(path):
            raise SystemExit(f"refusing to write through a link: {path}")
        project = os.path.realpath(self.project)
        if os.path.abspath(path).startswith(os.path.abspath(self.project) + os.sep):
            real = os.path.realpath(path)
            if os.path.commonpath([real, project]) != project:
                raise SystemExit(f"refusing to write outside the project: {path} -> {real}")

    def write_text(self, path: str, content: str) -> None:
        self.check_target(path)
        if not self.dry_run:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)

    # ------------------------------------------------------------ skill folder
    def owns_skill_dir(self, dest: str) -> bool:
        if os.path.islink(dest):
            return os.path.realpath(dest) == os.path.realpath(SKILL_SRC)
        return os.path.isfile(os.path.join(dest, MARKER))

    def install_skill(self, host: str, scope: str) -> None:
        dest = os.path.join(self.resolve(SKILL_DIRS[(host, scope)], scope), NAME)
        if dest in self.done:
            self.say("skip", f"{dest} (already handled for another host)")
            return
        self.done.add(dest)
        if os.path.realpath(dest) == os.path.realpath(SKILL_SRC) and not os.path.islink(dest):
            self.say("skip", f"{dest} is this repository's skill folder itself")
            return
        if os.path.lexists(dest):
            if self.owns_skill_dir(dest):
                self.say("update", dest)
                if not self.dry_run:
                    self._remove(dest)
            else:
                self.move_aside(dest)
        if self.link and self._try_link(dest):
            return
        self.say("copy", f"skill -> {dest}")
        if self.dry_run:
            return
        os.makedirs(dest, exist_ok=True)
        files = []
        for rel in SKILL_CONTENT:
            src = os.path.join(SKILL_SRC, *rel.split("/"))
            dst = os.path.join(dest, *rel.split("/"))
            if os.path.isdir(src):
                shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)
                files.append(rel + "/")
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                files.append(rel)
        marker = {"name": NAME, "version": ba.load_routing()["plugin"]["version"],
                  "host": host, "scope": scope, "content": files}
        self.write_text(os.path.join(dest, MARKER), json.dumps(marker, indent=2) + "\n")

    def _try_link(self, dest: str) -> bool:
        self.say("link", f"{dest} -> {SKILL_SRC}")
        if self.dry_run:
            return True
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            os.symlink(SKILL_SRC, dest, target_is_directory=True)
            return True
        except OSError as exc:
            self.say("fallback", f"symlink not permitted ({exc.__class__.__name__}); copying")
            return False

    def uninstall_skill(self, host: str, scope: str) -> None:
        dest = os.path.join(self.resolve(SKILL_DIRS[(host, scope)], scope), NAME)
        if dest in self.done:
            return
        self.done.add(dest)
        if not os.path.lexists(dest):
            self.say("absent", dest)
        elif self.owns_skill_dir(dest):
            self.say("remove", dest)
            if not self.dry_run:
                self._remove(dest)
                self.prune(os.path.dirname(dest))
        else:
            self.say("keep", f"{dest} (not installed by this tool)")

    # ------------------------------------------------------------ subagents
    def agent_files(self, host: str, scope: str) -> list[tuple[str, str]]:
        if (host, scope) not in AGENT_DIRS:
            return []
        rel_dest, rel_src, ext = AGENT_DIRS[(host, scope)]
        dest_dir = self.resolve(rel_dest, scope)
        src_dir = os.path.join(ROOT, *rel_src.split("/"))
        return [(os.path.join(src_dir, n), os.path.join(dest_dir, n))
                for n in sorted(os.listdir(src_dir)) if n.endswith(ext)]

    @staticmethod
    def owns_file(path: str) -> bool:
        try:
            with open(path, encoding="utf-8") as fh:
                return ba.GENERATED in fh.read()
        except (OSError, UnicodeDecodeError):
            return False

    def install_file(self, src_text: str, dest: str) -> None:
        if os.path.isfile(dest):
            with open(dest, encoding="utf-8", errors="replace") as fh:
                if fh.read().replace("\r\n", "\n") == src_text:
                    self.say("same", dest)
                    return
            if not self.owns_file(dest):
                self.backup(dest)
            self.say("update", dest)
        elif os.path.lexists(dest):
            self.move_aside(dest)
            self.say("write", dest)
        else:
            self.say("write", dest)
        self.write_text(dest, src_text)

    def uninstall_file(self, dest: str) -> None:
        if not os.path.lexists(dest):
            self.say("absent", dest)
        elif self.owns_file(dest):
            self.say("remove", dest)
            if not self.dry_run:
                os.remove(dest)
                self.prune(os.path.dirname(dest))
        else:
            self.say("keep", f"{dest} (not installed by this tool)")

    # ------------------------------------------------------------ instruction blocks
    def instruction_target(self, host: str) -> tuple[str, str, str] | None:
        if host not in INSTRUCTIONS:
            return None
        rel, kind, adapter = INSTRUCTIONS[host]
        return os.path.join(self.project, *rel.split("/")), kind, adapter

    def skill_path_for(self, host: str) -> str:
        return f"{SKILL_DIRS[(host, 'project')]}/{NAME}"

    def install_instructions(self, host: str) -> None:
        target = self.instruction_target(host)
        if not target:
            return
        path, kind, adapter = target
        text = ba.render_pointer(ba.load_routing(), adapter, self.skill_path_for(host))
        if kind == "file":
            self.install_file(text, path)
            return
        current = self._read(path)
        updated = replace_block(current, text) if current is not None else text
        if current == updated:
            self.say("same", path)
            return
        if current is not None and has_foreign_content(current):
            self.backup(path)
        self.say("block", f"{'insert' if current is None or ba.BEGIN_MARK not in current else 'update'} in {path}")
        self.write_text(path, updated)

    def uninstall_instructions(self, host: str) -> None:
        target = self.instruction_target(host)
        if not target:
            return
        path, kind, _ = target
        if kind == "file":
            self.uninstall_file(path)
            return
        current = self._read(path)
        if current is None or ba.BEGIN_MARK not in current:
            self.say("absent", f"block in {path}")
            return
        remaining = replace_block(current, "")
        if remaining.strip():
            self.backup(path)
            self.say("block", f"remove from {path}")
            self.write_text(path, remaining)
        else:
            self.say("remove", f"{path} (held only the block)")
            if not self.dry_run:
                os.remove(path)
                self.prune(os.path.dirname(path))

    @staticmethod
    def _read(path: str) -> str | None:
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().replace("\r\n", "\n")

    # ------------------------------------------------------------ entry points
    def install(self, host: str, scope: str, agents: bool, instructions: bool) -> None:
        self.install_skill(host, scope)
        if agents:
            for src, dest in self.agent_files(host, scope):
                with open(src, encoding="utf-8") as fh:
                    self.install_file(fh.read().replace("\r\n", "\n"), dest)
        if instructions:
            if scope == "project":
                self.install_instructions(host)
            elif host in INSTRUCTIONS:
                self.say("skip", f"{host} instructions: user-level files are personal; use --scope project")

    def uninstall(self, host: str, scope: str) -> None:
        self.uninstall_skill(host, scope)
        for _, dest in self.agent_files(host, scope):
            self.uninstall_file(dest)
        if scope == "project":
            self.uninstall_instructions(host)


def has_foreign_content(text: str) -> bool:
    return bool(replace_block(text, "").strip())


def replace_block(text: str, block: str) -> str:
    """Insert, replace or (with an empty block) remove the marked telegram-bot-ui block."""
    start, end = text.find(ba.BEGIN_MARK), text.find(ba.END_MARK)
    if start != -1 and end != -1 and end > start:
        tail = text[end + len(ba.END_MARK):].lstrip("\n")
        head = text[:start].rstrip("\n")
        parts = [p for p in (head, block.strip("\n"), tail.rstrip("\n")) if p]
        return "\n\n".join(parts) + "\n" if parts else ""
    if not block:
        return text
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + block


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True, choices=HOSTS + ("all",))
    ap.add_argument("--scope", default="user", choices=("user", "project"))
    ap.add_argument("--project", default=os.getcwd(), help="project folder for --scope project (default: cwd)")
    ap.add_argument("--home", default=os.path.expanduser("~"), help="home folder for --scope user (default: ~)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    ap.add_argument("--uninstall", action="store_true", help="remove what this tool installed")
    ap.add_argument("--link", action="store_true", help="symlink the skill folder to this checkout instead of copying")
    ap.add_argument("--no-agents", action="store_true", help="skip Claude/Codex subagent files")
    ap.add_argument("--with-instructions", action="store_true",
                    help="also add pointer instructions (AGENTS.md, Cursor rule, GEMINI.md, Copilot); project scope")
    args = ap.parse_args(argv)

    hosts = HOSTS if args.host == "all" else (args.host,)
    inst = Installer(args.home, args.project, args.dry_run, args.link)
    for host in hosts:
        if args.uninstall:
            inst.uninstall(host, args.scope)
        else:
            inst.install(host, args.scope, not args.no_agents, args.with_instructions)
    verb = "would change" if args.dry_run else "done"
    print(f"\n{verb}: {len(inst.log)} step(s) for {', '.join(hosts)} ({args.scope} scope).")
    if not args.uninstall and not args.dry_run:
        print("Restart the agent (or start a new session) so it discovers the skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
