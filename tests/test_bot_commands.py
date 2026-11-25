"""bot_commands.py: scan, audit, plan and diff of a bot's command menu. Offline, no token."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _paths

import bot_commands as bc

FIX = os.path.join(_paths.TESTS, "fixtures", "commands")
TGUI = os.path.join(_paths.ROOT, "scripts", "tgui.py")
DECLARED = os.path.join(FIX, "declared")


def cli(*args):
    return subprocess.run([sys.executable, TGUI, "commands", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def line_of(path, needle, nth=1):
    """The line number of the nth line of `path` that contains `needle`."""
    with open(path, encoding="utf-8") as fh:
        hits = [i for i, line in enumerate(fh, 1) if needle in line]
    return hits[nth - 1]


def declaration(lists, **extra):
    return json.dumps({"format": bc.FORMAT, "default_language": "en", "lists": lists, **extra})


class TempProject(unittest.TestCase):
    def project(self, files):
        root = tempfile.mkdtemp(prefix="tgui-commands-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, text in files.items():
            path = os.path.join(root, *name.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        return root

    def scan(self, files):
        return bc.scan_project(self.project(files))

    def audit(self, files):
        findings, _ = bc.audit_scan(self.scan(files))
        return findings


# ---------------------------------------------------------------- scan


class ScanFixtureTest(unittest.TestCase):
    def test_aiogram_handlers_registrations_and_lines(self):
        path = os.path.join(FIX, "aiogram_bot", "bot.py")
        scan = bc.scan_project(os.path.dirname(path))
        handlers = {h.command: h for h in scan.handlers}
        self.assertEqual(set(handlers), {"start", "help", "orders", "history", "ping"})  # "old" is commented out
        self.assertEqual(handlers["start"].line, line_of(path, "CommandStart()"))
        self.assertEqual(handlers["help"].line, line_of(path, 'Command("help")'))
        self.assertEqual(handlers["history"].line, line_of(path, 'Command(commands=["orders", "history"])'))
        self.assertEqual(handlers["ping"].line, line_of(path, 'F.text == "/ping"'))
        self.assertEqual({h.framework for h in handlers.values()}, {"aiogram"})
        self.assertEqual(handlers["start"].file, "bot.py")

        menu, ru = scan.registrations
        self.assertEqual((menu.method, menu.scope, menu.language_code), ("set_my_commands", {"type": "default"}, ""))
        self.assertEqual(menu.line, line_of(path, "await bot.set_my_commands(MENU)"))
        self.assertEqual([(e.command, e.description, e.line) for e in menu.commands], [
            ("start", "Open the main menu", line_of(path, 'command="start", description="Open the main menu"')),
            ("help", "How the bot works", line_of(path, 'command="help"')),
            ("orders", "Show my orders", line_of(path, 'command="orders"'))])
        self.assertEqual((ru.scope, ru.language_code), ({"type": "all_private_chats"}, "ru"))
        self.assertEqual(ru.line, line_of(path, "await bot.set_my_commands(", nth=2))
        self.assertEqual(ru.commands[0].line, line_of(path, "Open the menu"))

    def test_python_telegram_bot_positional_commands_and_pairs(self):
        path = os.path.join(FIX, "ptb_bot", "main.py")
        scan = bc.scan_project(os.path.dirname(path))
        handlers = {h.command: h for h in scan.handlers}
        self.assertEqual(set(handlers), {"start", "about", "info"})
        self.assertEqual(handlers["start"].framework, "python-telegram-bot")
        self.assertEqual(handlers["info"].line, line_of(path, 'CommandHandler(["about", "info"]'))
        first, groups = scan.registrations
        self.assertEqual([(e.command, e.description) for e in first.commands],
                         [("start", "Start the bot"), ("about", "About us")])
        self.assertEqual(groups.scope, {"type": "all_group_chats"})
        self.assertEqual([e.command for e in groups.commands], ["start"])

    def test_grammy_handlers_and_a_list_reached_through_a_variable(self):
        path = os.path.join(FIX, "grammy_bot", "bot.ts")
        scan = bc.scan_project(os.path.dirname(path))
        handlers = {h.command: h for h in scan.handlers}
        self.assertEqual(set(handlers), {"start", "help", "about"})  # "legacy" is commented out
        self.assertEqual(handlers["start"].line, line_of(path, 'bot.command("start"'))
        self.assertEqual(handlers["about"].line, line_of(path, 'bot.command(["help", "about"]'))
        self.assertEqual({h.framework for h in handlers.values()}, {"grammY/Telegraf"})
        menu, ru = scan.registrations
        self.assertEqual((menu.method, menu.scope, menu.language_code), ("setMyCommands", {"type": "default"}, ""))
        self.assertEqual(menu.line, line_of(path, "await bot.api.setMyCommands(commands)"))
        self.assertEqual([(e.command, e.line) for e in menu.commands],
                         [("start", line_of(path, "Open the main menu")), ("help", line_of(path, "How the bot works"))])
        self.assertEqual((ru.scope, ru.language_code), ({"type": "all_private_chats"}, "ru"))
        self.assertEqual(ru.commands[0].description, "Открыть меню")

    def test_declaration_is_read_with_lines(self):
        scan = bc.scan_project(DECLARED)
        self.assertEqual(scan.declaration.file, "bot-ui/commands.json")
        path = os.path.join(DECLARED, "bot-ui", "commands.json")
        first = scan.declaration.lists[0].commands[0]
        self.assertEqual(first.line, line_of(path, '"command": "start"'))
        out = json.loads(cli("scan", "--root", DECLARED, "--json").stdout)
        self.assertEqual([r["source"] for r in out["registrations"]], ["declaration", "declaration"])


class ScanFormsTest(TempProject):
    def handler_names(self, files):
        return {h.command for h in self.scan(files).handlers}

    def test_pytelegrambotapi_raw_and_keyword_forms(self):
        names = self.handler_names({"bot.py": (
            "import telebot\nbot = telebot.TeleBot('t')\n"
            "@bot.message_handler(commands=['help', 'about'])\ndef a(m): ...\n"
            "@bot.message_handler(func=lambda m: m.text.startswith('/echo'))\ndef b(m): ...\n"
            "def c(message):\n    if message.text == '/ping':\n        pass\n"
            "    if message.text in ('/one', '/two'):\n        pass\n"
            "    if path.startswith('/api') or kind == '/skip':\n        pass\n"
            "from telegram.ext import CommandHandler\nCommandHandler(command='pay', callback=c)\n")})
        self.assertEqual(names, {"help", "about", "echo", "ping", "one", "two", "pay"})

    def test_aiogram_name_list_and_comments_are_respected(self):
        names = self.handler_names({"bot.py": (
            "from aiogram.filters import Command\n"
            "r.message(Command('a', 'b'))\n"
            "# r.message(Command('gone'))\n"
            "r.message(Command(commands=('c',)))\n")})
        self.assertEqual(names, {"a", "b", "c"})

    def test_command_in_a_non_telegram_cli_is_not_a_handler(self):
        self.assertEqual(self.handler_names({"cli.js": "program.command('serve').action(run);\n"}), set())

    def test_telegraf_shortcuts_and_raw_javascript(self):
        files = {"bot.js": (
            "const { Telegraf } = require('telegraf');\nconst bot = new Telegraf(t);\n"
            "bot.start((ctx) => ctx.reply('hi'));\nbot.help(async (ctx) => {});\n"
            "bot.command('pay', (ctx) => {});\n"
            "bot.on('text', (ctx) => { if (ctx.message.text === '/ping') {} "
            "if (ctx.message.text.startsWith('/echo')) {} });\n"
            "/* bot.command('hidden-in-comment') */\n"
            "bot.telegram.setMyCommands([{ command: 'start', description: 'Start' }], "
            "{ scope: { type: 'chat', chat_id: -1001 }, language_code: 'de' });\n")}
        scan = self.scan(files)
        self.assertEqual({h.command for h in scan.handlers}, {"start", "help", "pay", "ping", "echo"})
        (reg,) = scan.registrations
        self.assertEqual((reg.scope, reg.language_code), ({"type": "chat", "chat_id": -1001}, "de"))
        self.assertEqual(reg.line, 8)

    def test_grammy_start_without_a_handler_is_not_a_command(self):
        self.assertEqual(self.handler_names({"b.ts": "import { Bot } from 'grammy';\nconst bot = new Bot(t);\n"
                                                      "bot.start();\n"}), set())

    def test_dict_literals_and_a_concatenated_list(self):
        scan = self.scan({"bot.py": (
            "A = [{'command': 'start', 'description': 'Start'}]\n"
            "B = [BotCommand('help', 'Help')]\n"
            "await bot.set_my_commands(A + B, scope=BotCommandScope.ALL_PRIVATE_CHATS)\n")})
        (reg,) = scan.registrations
        self.assertEqual([e.command for e in reg.commands], ["start", "help"])
        self.assertEqual(reg.scope, {"type": "all_private_chats"})

    def test_a_list_built_at_run_time_is_reported_not_guessed(self):
        scan = self.scan({"bot.py": "for lang, cmds in MENUS.items():\n    bot.set_my_commands(cmds, "
                                    "language_code=lang)\n"})
        (reg,) = scan.registrations
        self.assertFalse(reg.resolved)
        self.assertIsNone(reg.language_code)
        _, notes = bc.audit_scan(scan)
        self.assertIn("bot.py:2", notes[0])

    def test_a_file_that_does_not_parse_is_listed_not_fatal(self):
        handler = "from aiogram.filters import Command\nr.message(Command('x'))\n"
        scan = self.scan({"broken.py": "def (:\n", "ok.py": handler})
        self.assertEqual(scan.unreadable, ["broken.py"])
        self.assertEqual({h.command for h in scan.handlers}, {"x"})

    def test_a_declaration_saved_with_a_bom_is_read(self):
        root = self.project({"bot-ui/commands.json": chr(0xFEFF) + declaration(
            [{"commands": [{"command": "start", "description": "Open"}]}])})
        self.assertEqual(cli("plan", "--root", root).returncode, 0)

    def test_skipped_folders(self):
        handler = "from aiogram.filters import Command\nr.message(Command('x'))\n"
        files = {"app/bot.py": handler, "node_modules/p/b.py": handler, "dist/b.py": handler,
                 "build/b.py": handler, "myenv/pyvenv.cfg": "home = x\n", "myenv/lib/b.py": handler,
                 ".hidden/b.py": handler}
        scan = self.scan(files)
        self.assertEqual([h.file for h in scan.handlers], ["app/bot.py"])


# ---------------------------------------------------------------- audit


MENU = [("start", "Open the main menu"), ("help", "Show what the bot can do"),
        ("settings", "Change language and alerts")]


def call(pairs, extra=""):
    items = ", ".join(f"BotCommand(command={c!r}, description={d!r})" for c, d in pairs)
    return f"    await bot.set_my_commands([{items}]{', ' + extra if extra else ''})"


def bot_py(*calls, handlers=("start", "help", "settings")):
    out = ["from aiogram import Router", "from aiogram.filters import Command, CommandStart",
           "from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats", "router = Router()", ""]
    for name in handlers:
        out += [f"@router.message({'CommandStart()' if name == 'start' else f'Command({name!r})'})",
                f"async def on_{name}(m): ...", ""]
    return {"bot.py": "\n".join([*out, "async def setup(bot):", *(calls or ["    pass"])]) + "\n"}


PRIVATE = "scope=BotCommandScopeAllPrivateChats()"
LONG_OK = "x" * 256


class AuditCodesTest(TempProject):
    def codes(self, files):
        return {f.code for f in self.audit(files)}

    def test_every_code_fires_on_a_crafted_case_and_stays_quiet_on_the_clean_one(self):
        many = lambda n: {"bot-ui/commands.json": declaration([{"commands": [  # noqa: E731
            {"command": f"c{i}", "description": "Do something"} for i in range(n)]}])}
        cases = {
            "COMMAND_NAME_INVALID": (bot_py(call([("Start", "Open"), *MENU[1:]])), bot_py(call(MENU))),
            "DESCRIPTION_LENGTH": (bot_py(call([*MENU[:2], ("settings", "x" * 257)])),
                                   bot_py(call([*MENU[:2], ("settings", LONG_OK)]))),
            "COMMAND_NOT_REGISTERED": (bot_py(call(MENU[:2])), bot_py(call(MENU))),
            "COMMAND_NO_HANDLER": (bot_py(call([*MENU, ("ghost", "Does nothing")])), bot_py(call(MENU))),
            "COMMAND_DUPLICATE": (bot_py(call([*MENU, ("help", "Help again")])), bot_py(call(MENU))),
            "TOO_MANY_COMMANDS": (many(101), many(100)),
            "LOCALE_MISSING": (bot_py(call(MENU), call(MENU[:2], 'language_code="ru"')),
                               bot_py(call(MENU), call(MENU, 'language_code="ru"'))),
            "SCOPE_SHADOWED": (bot_py(call(MENU), call(MENU[:1], PRIVATE)), bot_py(call(MENU), call(MENU, PRIVATE))),
            "DESCRIPTION_STYLE": (bot_py(call([MENU[0], ("help", "show what the bot can do"), MENU[2]])),
                                  bot_py(call(MENU))),
        }
        self.assertEqual(set(cases), {"COMMAND_NAME_INVALID", "DESCRIPTION_LENGTH", "COMMAND_NOT_REGISTERED",
                                      "COMMAND_NO_HANDLER", "COMMAND_DUPLICATE", "TOO_MANY_COMMANDS",
                                      "LOCALE_MISSING", "SCOPE_SHADOWED", "DESCRIPTION_STYLE"})
        for code, (bad, good) in cases.items():
            with self.subTest(code=code):
                self.assertIn(code, self.codes(bad))
                self.assertNotIn(code, self.codes(good))

    def test_the_clean_fixture_has_no_findings_and_exits_zero(self):
        findings, notes = bc.audit_scan(bc.scan_project(os.path.join(FIX, "clean_bot")))
        self.assertEqual((findings, notes), ([], []))
        self.assertEqual(cli("audit", "--root", os.path.join(FIX, "clean_bot")).returncode, 0)

    def test_findings_carry_severity_and_a_file_line(self):
        by_code = {f.code: f for f in self.audit(bot_py(call([*MENU[:2], ("ghost", "Does nothing")]),
                                                         handlers=("start", "help", "settings")))}
        self.assertEqual(by_code["COMMAND_NO_HANDLER"].severity, "error")
        self.assertEqual(by_code["COMMAND_NO_HANDLER"].file, "bot.py")
        self.assertEqual(by_code["COMMAND_NOT_REGISTERED"].severity, "warning")
        self.assertEqual(by_code["COMMAND_NOT_REGISTERED"].command, "settings")

    def test_start_is_info_everything_else_is_a_warning(self):
        findings = self.audit(bot_py(call([MENU[2]])))
        severity = {f.command: f.severity for f in findings if f.code == "COMMAND_NOT_REGISTERED"}
        self.assertEqual(severity, {"start": "info", "help": "warning"})

    def test_hidden_commands_in_the_declaration_silence_not_registered(self):
        files = bot_py(call(MENU[:2]))
        files["bot-ui/commands.json"] = declaration([{"commands": [
            {"command": "start", "description": "Open the main menu"},
            {"command": "help", "description": "Show what the bot can do"},
            {"command": "settings", "hidden": True}]}])
        findings = self.audit(files)
        self.assertEqual([f for f in findings if f.code == "COMMAND_NOT_REGISTERED"], [])

    def test_hidden_command_without_a_handler_is_a_warning_not_an_error(self):
        files = bot_py(call(MENU))
        files["bot-ui/commands.json"] = declaration([{"commands": [{"command": "ghost", "hidden": True}]}])
        (finding,) = [f for f in self.audit(files) if f.code == "COMMAND_NO_HANDLER"]
        self.assertEqual((finding.severity, finding.command), ("warning", "ghost"))

    def test_style_findings_are_info_and_do_not_fail_the_audit(self):
        root = self.project(bot_py(call([("start", "Open the main menu."), ("help", "show what the bot can do"),
                                         ("settings", "settings")])))
        findings, _ = bc.audit_scan(bc.scan_project(root))
        style = [f for f in findings if f.code == "DESCRIPTION_STYLE"]
        self.assertEqual(len(style), 3)  # mixed capitals, inconsistent periods, description repeats the name
        self.assertEqual({f.severity for f in style}, {"info"})
        self.assertEqual(cli("audit", "--root", root).returncode, 0)

    def test_scope_shadowing_explains_the_resolution(self):
        (finding,) = [f for f in self.audit(bot_py(call(MENU), call(MENU[:1], PRIVATE))) if f.code == "SCOPE_SHADOWED"]
        self.assertIn("/help", finding.message)
        self.assertIn("/settings", finding.message)
        self.assertIn("does not merge", finding.message)
        self.assertEqual(finding.scope, "all_private_chats")

    def test_a_language_list_hides_the_fallback_for_that_language_only(self):
        findings = self.audit(bot_py(call(MENU), call(MENU[:1], f'{PRIVATE}, language_code="ru"')))
        (finding,) = [f for f in findings if f.code == "SCOPE_SHADOWED"]
        self.assertIn("(ru)", finding.message)

    def test_admin_scope_must_not_drop_group_commands(self):
        group = "scope=BotCommandScopeAllGroupChats()"
        admins = "scope=BotCommandScopeAllChatAdministrators()"
        files = bot_py(call(MENU), call(MENU, group), call(MENU[:1], admins))
        files["bot.py"] = files["bot.py"].replace("BotCommandScopeAllPrivateChats",
                                                  "BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, "
                                                  "BotCommandScopeAllChatAdministrators")
        (finding,) = [f for f in self.audit(files) if f.code == "SCOPE_SHADOWED"]
        self.assertIn("group administrators", finding.message)

    def test_locale_missing_in_the_declaration_when_a_translation_is_absent(self):
        files = bot_py(call(MENU), handlers=("start", "help", "settings"))
        files["bot-ui/commands.json"] = declaration([{"commands": [
            {"command": "start", "description": {"en": "Open the main menu", "ru": "Открыть меню"}},
            {"command": "help", "description": {"en": "Show what the bot can do"}}]}])
        (finding,) = [f for f in self.audit(files) if f.code == "LOCALE_MISSING"]
        self.assertEqual((finding.command, finding.language_code), ("help", "ru"))
        self.assertIn("commands.json", finding.file)

    def test_no_menu_at_all_hints_at_botfather(self):
        findings = self.audit({"bot.py": bot_py()["bot.py"]})
        warning = next(f for f in findings if f.command == "help")
        self.assertIn("BotFather", warning.message)

    def test_findings_are_stable_and_sorted_by_severity(self):
        files = bot_py(call([*MENU[:1], ("ghost", "Nothing")]))
        first, second = self.audit(files), self.audit(files)
        self.assertEqual(first, second)
        severities = [bc.SEVERITY[f.severity] for f in first]
        self.assertEqual(severities, sorted(severities))

    def test_audit_exit_codes_and_json(self):
        bad = self.project(bot_py(call([*MENU, ("ghost", "Nothing")])))
        result = cli("audit", "--root", bad, "--json")
        self.assertEqual(result.returncode, 1)
        out = json.loads(result.stdout)
        self.assertGreaterEqual(out["summary"]["error"], 1)
        self.assertIn("COMMAND_NO_HANDLER", {f["code"] for f in out["findings"]})


# ---------------------------------------------------------------- plan


class PlanTest(TempProject):
    def plan(self, **kw):
        decl = bc.load_declaration(os.path.join(DECLARED, "bot-ui", "commands.json"))
        return bc.build_requests(decl)

    def test_two_scopes_two_locales_make_four_set_requests_then_the_removal(self):
        requests, problems = self.plan()
        self.assertEqual(problems, [])
        self.assertEqual([(r["method"], r["params"]["scope"]["type"], r["params"].get("language_code", ""))
                          for r in requests],
                         [("setMyCommands", "default", ""), ("setMyCommands", "default", "ru"),
                          ("setMyCommands", "all_group_chats", ""), ("setMyCommands", "all_group_chats", "ru"),
                          ("deleteMyCommands", "all_private_chats", "de")])
        default, default_ru, groups, groups_ru, removal = requests
        self.assertEqual(default["params"]["commands"], [
            {"command": "start", "description": "Open the main menu"},
            {"command": "help", "description": "How the bot works"}])  # "admin" is hidden: never sent
        self.assertEqual(default_ru["params"]["commands"][0],
                         {"command": "start", "description": "Открыть меню"})
        self.assertEqual(groups["params"]["commands"][1], {"command": "stats", "description": "Chat statistics",
                                                           "is_ephemeral": True})
        self.assertEqual(groups_ru["params"]["commands"][1]["description"], "Статистика чата")
        self.assertNotIn("language_code", default["params"])  # empty = the fallback list
        self.assertEqual(removal["params"], {"scope": {"type": "all_private_chats"}, "language_code": "de"})

    def test_requests_pass_the_offline_catalog_validator(self):
        requests, _ = self.plan()
        self.assertEqual(bc.catalog_problems(requests), ([], None))
        broken = [{"method": "setMyCommands", "params": {"commands": [{"command": "a", "desc": "x"}]}}]
        problems, _ = bc.catalog_problems(broken)
        self.assertTrue(any("desc" in p for p in problems))

    def test_cli_prints_a_json_array_and_exits_zero(self):
        result = cli("plan", "--root", DECLARED)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)), 5)
        wrapped = json.loads(cli("plan", "--root", DECLARED, "--json").stdout)
        self.assertEqual((len(wrapped["requests"]), wrapped["problems"]), (5, []))

    def test_file_option_is_relative_to_the_root_or_the_cwd(self):
        result = cli("plan", "--root", FIX, "--file", os.path.join("declared", "bot-ui", "commands.json"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_language_list_wins_over_the_expanded_one(self):
        root = self.project({"bot-ui/commands.json": declaration([
            {"language_code": "", "commands": [{"command": "start", "description": {"en": "Menu", "ru": "Меню"}}]},
            {"language_code": "ru", "commands": [{"command": "start", "description": "Старт"}]}])})
        requests = json.loads(cli("plan", "--root", root).stdout)
        ru = [r for r in requests if r["params"].get("language_code") == "ru"]
        self.assertEqual(len(ru), 1)
        self.assertEqual(ru[0]["params"]["commands"][0]["description"], "Старт")

    def test_a_language_without_text_reuses_the_default_text(self):
        decl = bc.parse_declaration(json.loads(declaration([{"commands": [
            {"command": "a", "description": {"en": "One", "ru": "Раз"}},
            {"command": "b", "description": {"en": "Two"}}]}])), "", "x")
        requests, _ = bc.build_requests(decl)
        ru = next(r for r in requests if r["params"].get("language_code") == "ru")
        self.assertEqual([c["description"] for c in ru["params"]["commands"]], ["Раз", "Two"])

    def test_invalid_commands_are_problems_and_exit_one(self):
        cases = {
            "invalid name": [{"command": "Bad-Name", "description": "Do it"}],
            "description too long": [{"command": "a", "description": "x" * 257}],
            "more than 100": [{"command": f"c{i}", "description": "Do it"} for i in range(101)],
            "nothing visible": [{"command": "a", "hidden": True}],
        }
        for label, commands in cases.items():
            with self.subTest(label):
                root = self.project({"bot-ui/commands.json": declaration([{"commands": commands}])})
                result = cli("plan", "--root", root)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("problem:", result.stderr)
                self.assertTrue(json.loads(result.stdout) is not None)

    def test_malformed_declarations_exit_two(self):
        cases = {
            "format": json.dumps({"lists": []}),
            "scope type": declaration([{"scope": {"type": "everyone"}, "commands": []}]),
            "chat scope needs chat_id": declaration([{"scope": {"type": "chat"}, "commands": []}]),
            "language": declaration([{"language_code": "english", "commands": []}]),
            "description": declaration([{"commands": [{"command": "a", "description": 5}]}]),
            "repeated list": declaration([{"commands": []}, {"commands": []}]),
            "set and removed": declaration([{"commands": []}], remove=[{"scope": {"type": "default"}}]),
            "removed language the fallback list expands into": declaration(
                [{"commands": [{"command": "a", "description": {"en": "A", "ru": "Я"}}]}],
                remove=[{"scope": {"type": "default"}, "language_code": "ru"}]),
            "not json": "{",
        }
        for label, text in cases.items():
            with self.subTest(label):
                root = self.project({"bot-ui/commands.json": text})
                self.assertEqual(cli("plan", "--root", root).returncode, 2)

    def test_a_removal_is_checked_against_the_localized_lists_not_only_the_written_ones(self):
        doc = json.loads(declaration([{"commands": [{"command": "a", "description": {"en": "A", "ru": "Я"}}]}],
                                     remove=[{"scope": {"type": "default"}, "language_code": "ru"}]))
        with self.assertRaises(bc.DeclarationError) as ctx:
            bc.parse_declaration(doc, "", "x")
        self.assertIn("ru", str(ctx.exception))
        doc["remove"][0]["language_code"] = "de"  # no text for German: removing it is fine
        requests, _ = bc.build_requests(bc.parse_declaration(doc, "", "x"))
        self.assertEqual([(r["method"], r["params"].get("language_code", "")) for r in requests],
                         [("setMyCommands", ""), ("setMyCommands", "ru"), ("deleteMyCommands", "de")])

    def test_missing_declaration_exits_two(self):
        self.assertEqual(cli("plan", "--root", self.project({"bot.py": "x = 1\n"})).returncode, 2)

    def test_chat_scopes_keep_their_ids(self):
        root = self.project({"bot-ui/commands.json": declaration([
            {"scope": {"type": "chat_member", "chat_id": -100123, "user_id": 42},
             "commands": [{"command": "ban", "description": "Ban a user"}]}])})
        (request,) = json.loads(cli("plan", "--root", root).stdout)
        self.assertEqual(request["params"]["scope"], {"type": "chat_member", "chat_id": -100123, "user_id": 42})


class CatalogTest(unittest.TestCase):
    def test_scope_types_match_the_offline_catalog(self):
        from sync_bot_api import load_catalog
        types = load_catalog()["types"]
        found = {}
        for name, spec in types.items():
            if name.startswith("BotCommandScope") and name != "BotCommandScope":
                kind = bc._snake(name[len("BotCommandScope"):])
                found[kind] = tuple(f["name"] for f in spec["fields"] if f["name"] != "type")
        self.assertEqual(found, dict(bc.SCOPE_FIELDS))


# ---------------------------------------------------------------- diff


class DiffTest(TempProject):
    def live(self, doc):
        return self.project({"live.json": json.dumps(doc)}) + os.sep + "live.json"

    def test_single_saved_list_reports_added_removed_changed_and_order(self):
        result = cli("diff", "--root", DECLARED, "--live-json", os.path.join(DECLARED, "live_partial.json"), "--json")
        self.assertEqual(result.returncode, 1)
        out = json.loads(result.stdout)
        self.assertFalse(out["compared_every_list"])
        (entry,) = out["lists"]  # only the list that was saved is compared
        self.assertEqual(entry["status"], "changed")
        self.assertEqual([c["command"] for c in entry["removed"]], ["old"])
        self.assertEqual(entry["changed"], [{"command": "help", "live": "Help", "declared": "How the bot works"}])
        self.assertTrue(entry["reordered"])

    def test_full_snapshot_compares_every_list(self):
        out = json.loads(cli("diff", "--root", DECLARED, "--live-json", os.path.join(DECLARED, "live_full.json"),
                             "--json").stdout)
        status = {(item["scope"]["type"], item["language_code"]): item["status"] for item in out["lists"]}
        self.assertEqual(status, {("default", ""): "same", ("default", "ru"): "changed",
                                  ("all_group_chats", ""): "new", ("all_group_chats", "ru"): "new",
                                  ("all_private_chats", "de"): "to_remove"})
        self.assertEqual(out["summary"], {"added": 5, "removed": 1, "changed": 0, "reordered": 0})

    def test_text_output_marks_plus_minus_and_tilde(self):
        text = cli("diff", "--root", DECLARED, "--live-json", os.path.join(DECLARED, "live_partial.json")).stdout
        self.assertIn("- /old", text)
        self.assertIn("~ /help", text)

    def test_matching_snapshot_exits_zero(self):
        requests, _ = bc.build_requests(bc.load_declaration(os.path.join(DECLARED, "bot-ui", "commands.json")))
        lists = [{"scope": r["params"]["scope"], "language_code": r["params"].get("language_code", ""),
                  "result": r["params"]["commands"]} for r in requests if r["method"] == "setMyCommands"]
        result = cli("diff", "--root", DECLARED, "--live-json", self.live({"lists": lists}))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 added, 0 removed, 0 changed, 0 reordered", result.stdout)

    def test_scope_and_language_flags_place_a_bare_response(self):
        live = self.live({"ok": True, "result": [{"command": "start", "description": "Открыть меню"},
                                                 {"command": "help", "description": "Как работает бот"}]})
        result = cli("diff", "--root", DECLARED, "--live-json", live, "--language-code", "ru")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_bad_inputs_exit_two(self):
        self.assertEqual(cli("diff", "--root", DECLARED, "--live-json", "missing.json").returncode, 2)
        error = self.live({"ok": False, "error_code": 401, "description": "Unauthorized"})
        self.assertEqual(cli("diff", "--root", DECLARED, "--live-json", error).returncode, 2)
        self.assertEqual(cli("diff", "--root", DECLARED, "--live-json", self.live({"x": 1})).returncode, 2)


# ---------------------------------------------------------------- CLI


class CliTest(unittest.TestCase):
    def test_help_exits_zero_through_tgui_and_for_every_subcommand(self):
        self.assertEqual(cli("--help").returncode, 0)
        for verb in ("scan", "audit", "plan", "diff"):
            with self.subTest(verb):
                result = cli(verb, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertIn("--root", result.stdout)

    def test_usage_errors_exit_two(self):
        self.assertEqual(cli().returncode, 2)
        self.assertEqual(cli("audit", "--root", os.path.join(FIX, "does-not-exist")).returncode, 2)
        self.assertEqual(cli("diff", "--root", DECLARED).returncode, 2)  # --live-json is required

    def test_scan_json_lists_handlers_and_registrations_with_lines(self):
        out = json.loads(cli("scan", "--root", os.path.join(FIX, "aiogram_bot"), "--json").stdout)
        self.assertEqual({h["command"] for h in out["handlers"]}, {"start", "help", "orders", "history", "ping"})
        self.assertTrue(all(h["line"] > 0 and h["file"] == "bot.py" for h in out["handlers"]))
        self.assertEqual(len(out["registrations"]), 2)

    def test_declaration_is_documented_in_the_module_docstring(self):
        for needle in (bc.FORMAT, "default_language", "hidden", "remove", "determining-list-of-commands"):
            self.assertIn(needle, bc.__doc__)


if __name__ == "__main__":
    unittest.main()
