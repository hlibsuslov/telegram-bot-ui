"""scripts/bot_ui_mcp.py: the skill's MCP server over stdio (offline tools only; no network here)."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import _paths

SERVER = os.path.join(_paths.ROOT, "scripts", "bot_ui_mcp.py")
RICH = os.path.join(_paths.REPO, "tests", "fixtures", "rich_project")


def session(*calls):
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    for i, (name, args) in enumerate(calls, 1):
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
    env = {**os.environ, "BOT_UI_EMOJI_RESOLVER": "off"}
    out = subprocess.run([sys.executable, SERVER], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                         capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    replies = [json.loads(line) for line in out.stdout.splitlines()]
    return {r["id"]: r for r in replies}, out.stderr


class Protocol(unittest.TestCase):
    def test_handshake_list_and_only_json_on_stdout(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "nope"}]
        out = subprocess.run([sys.executable, SERVER], input="\n".join(json.dumps(m) for m in msgs) + "\nnot json\n",
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        replies = [json.loads(line) for line in out.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-11-25")
        names = {t["name"] for t in replies[1]["result"]["tools"]}
        self.assertTrue({"telegram_api_lookup", "validate_request", "check_rich_html", "map_render", "map_snapshot",
                         "knowledge_search", "emoji_pick_family"} <= names)
        self.assertEqual(replies[2]["error"]["code"], -32601)
        self.assertEqual(replies[3]["error"]["code"], -32700)


class Tools(unittest.TestCase):
    def test_lookup_suggests_on_a_typo_and_never_invents(self):
        r, _ = session(("telegram_api_lookup", {"symbol": "sendRichMesage"}), ("telegram_api_lookup", {"symbol": "RichTextButton"}))
        self.assertFalse(r[1]["result"]["structuredContent"]["found"])
        self.assertIn("sendRichMessage", r[1]["result"]["structuredContent"]["did_you_mean"])
        self.assertTrue(r[2]["result"]["structuredContent"]["found"])

    def test_lookup_returns_the_agent_card(self):
        r, _ = session(("telegram_api_lookup", {"symbol": "sendRichMessage"}),
                       ("telegram_api_lookup", {"symbol": "sendMessage"}))
        noted, bare = r[1]["result"]["structuredContent"], r[2]["result"]["structuredContent"]
        self.assertEqual(noted["note"]["since"], "10.1")
        self.assertIn("Purpose: " + noted["note"]["purpose"], noted["card"])
        self.assertIsNone(bare["note"])
        self.assertIn("Note: none yet", bare["card"])

    def test_validate_request_applies_keyboard_reaction_and_rich_rules(self):
        r, _ = session(
            ("validate_request", {"method": "sendMessage", "params": {"chat_id": 1, "text": "x", "reply_markup": {
                "inline_keyboard": [[{"text": "a", "callback_data": "a", "style": "link"}]]}}}),
            ("validate_request", {"method": "setMessageReaction", "params": {"chat_id": 1, "message_id": 2,
                                                                             "reaction": [{"type": "emoji", "emoji": "✅"}]}}),
            ("validate_request", {"method": "sendRichMessage", "params": {"chat_id": 1, "rich_message": {
                "html": '<tg-button type="url" url="https://t.me" style="link">x</tg-button>'}}}),
            ("validate_request", {"method": "setMessageReaction", "params": {"chat_id": 1, "message_id": 2,
                                                                             "reaction": [{"type": "emoji", "emoji": "👀"}]}}),
        )
        for i in (1, 2, 3):
            self.assertFalse(r[i]["result"]["structuredContent"]["ok"], i)
        self.assertTrue(r[4]["result"]["structuredContent"]["ok"])

    def test_knowledge_search_points_at_sections(self):
        r, _ = session(("knowledge_search", {"query": "buttons inside a rich message"}))
        files = [x["file"] for x in r[1]["result"]["structuredContent"]["results"]]
        self.assertIn("references/buttons-and-styles.md", files[:3])

    def test_map_tools_on_the_rich_fixture(self):
        r, _ = session(("map_validate", {"project": RICH}), ("map_render", {"project": RICH, "screen": "receipt.view"}),
                       ("map_simulate", {"project": RICH}), ("map_render", {"project": RICH, "screen": "nope"}))
        self.assertTrue(r[1]["result"]["structuredContent"]["ok"])
        self.assertEqual(r[2]["result"]["structuredContent"]["request"]["method"], "sendRichMessage")
        self.assertTrue(r[3]["result"]["structuredContent"]["ok"])
        self.assertTrue(r[4]["result"]["isError"])

    def test_network_tools_respect_the_switch(self):
        r, _ = session(("emoji_library_search", {"query": "settings"}))
        self.assertTrue(r[1]["result"]["isError"])
        self.assertIn("switched off", r[1]["result"]["content"][0]["text"])

    def test_snapshot_writes_one_html_file_outside_the_repository(self):
        web = os.path.join(_paths.REPO, "studio", "web", "dist-artifact", "index.html")
        if not os.path.isfile(web):
            self.skipTest("the artifact client is not built (npm run build:artifact)")
        tmp = tempfile.mkdtemp(prefix="bot-ui-mcp-")
        try:
            proj = os.path.join(tmp, "bot-ui")
            shutil.copytree(RICH, proj)
            out = os.path.join(tmp, "snap.html")
            r, err = session(("map_snapshot", {"project": proj, "output": out, "screens": ["receipt.view"]}))
            res = r[1]["result"]
            self.assertFalse(res["isError"], res)
            self.assertTrue(os.path.isfile(out))
            self.assertTrue(res["structuredContent"]["url"].endswith("#/screen/receipt.view"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ReadOnlyAndConfined(unittest.TestCase):
    """The tools' arguments and the project's files are untrusted: reads never repair a project, the
    snapshot never writes outside its allowed places and never truncates a file it was not told to replace."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bot-ui-mcp-")
        self.proj = os.path.join(self.tmp, "bot-ui")
        shutil.copytree(RICH, self.proj)
        # A place map_snapshot must refuse: not the temp folder and not next to the project. The
        # repository's fixtures qualify unless the checkout itself lies in the temp folder (a CI-style
        # clone under %TEMP%), where the parent of the temp folder is used instead.
        temp = os.path.realpath(tempfile.gettempdir())
        probe_dir = os.path.join(_paths.REPO, "tests", "fixtures")
        if os.path.realpath(probe_dir).lower().startswith(temp.lower() + os.sep):
            probe_dir = os.path.dirname(temp)
        self.outside = os.path.join(probe_dir, "mcp-confinement-probe.html")
        # A stand-in Studio build, so these rules are tested on a clean checkout too (CI does not build
        # studio/web); the real single-file client is exercised where it is built (Tools.test_snapshot_...).
        studio = os.path.join(tempfile.mkdtemp(prefix="bot-ui-studio-"), "studio")
        page = os.path.join(studio, "web", "dist-artifact", "index.html")
        os.makedirs(os.path.dirname(page))
        with open(page, "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><script type=\"application/json\" id=\"bot-ui-snapshot\">__BOT_UI_SNAPSHOT__</script>"
                     + "<!--" + "x" * 12_000 + "-->")
        self._studio_env = os.environ.get("BOT_UI_STUDIO_DIR")
        os.environ["BOT_UI_STUDIO_DIR"] = studio
        self._studio_root = os.path.dirname(studio)

    def tearDown(self):
        if self._studio_env is None:
            os.environ.pop("BOT_UI_STUDIO_DIR", None)
        else:
            os.environ["BOT_UI_STUDIO_DIR"] = self._studio_env
        shutil.rmtree(self._studio_root, ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)
        if os.path.exists(self.outside):
            os.remove(self.outside)

    def _victim(self, name="victim.html"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("keep me")
        return path

    def _snapshot_error(self, args):
        r, _ = session(("map_snapshot", {"project": self.proj, **args}))
        res = r[1]["result"]
        self.assertTrue(res["isError"], res)
        return res["content"][0]["text"]

    def test_read_tools_leave_a_pending_journal_alone(self):
        screen = os.path.join(self.proj, "screens", "receipt.view.json")
        before = pathlib.Path(screen).read_bytes()
        state = os.path.join(self.proj, ".bot-ui")
        os.makedirs(state)
        journal = os.path.join(state, "journal.json")
        with open(journal, "w", encoding="utf-8") as fh:  # a crafted journal: recovery would delete the screen
            json.dump({"files": [{"path": "screens/receipt.view.json", "backup": None}]}, fh)
        r, _ = session(("map_validate", {"project": self.proj}), ("map_render", {"project": self.proj, "screen": "receipt.view"}),
                       ("map_simulate", {"project": self.proj}))
        self.assertFalse(any(r[i]["result"]["isError"] for i in (1, 2, 3)), r)
        self.assertIn("WRITE_PENDING", json.dumps(r[1]["result"]["structuredContent"]))
        self.assertEqual(pathlib.Path(screen).read_bytes(), before)
        self.assertTrue(os.path.exists(journal))

    def test_a_failed_expectation_is_listed_with_its_step(self):
        sc = {"scenarioId": "wrong", "locale": "en", "context": {"chat": "private"}, "data": {},
              "steps": [{"command": "start"}, {"expect": {"screen": "receipt.paid"}}]}
        with open(os.path.join(self.proj, "scenarios", "wrong.json"), "w", encoding="utf-8") as fh:
            json.dump(sc, fh)
        r, _ = session(("map_simulate", {"project": self.proj, "scenario": "wrong"}))
        out = r[1]["result"]["structuredContent"]
        self.assertFalse(out["ok"])
        (failure,) = out["scenarios"][0]["failures"]
        self.assertEqual(failure["step"], 2)
        self.assertEqual(failure["diagnostics"][0]["code"], "EXPECT_SCREEN")

    def test_overwrite_must_be_the_boolean_true(self):
        victim = self._victim()
        for value in ("false", "true", 1, "yes"):
            self._snapshot_error({"output": victim, "overwrite": value})
            self.assertEqual(pathlib.Path(victim).read_text(encoding="utf-8"), "keep me", value)

    def test_an_existing_file_is_kept_unless_overwrite_is_true(self):
        victim = self._victim()
        self.assertIn("overwrite", self._snapshot_error({"output": victim}))
        self.assertEqual(pathlib.Path(victim).read_text(encoding="utf-8"), "keep me")
        r, _ = session(("map_snapshot", {"project": self.proj, "output": victim, "overwrite": True}))
        self.assertFalse(r[1]["result"]["isError"], r)
        self.assertGreater(os.path.getsize(victim), 10_000)

    def test_output_outside_the_temp_folder_and_the_project_neighbourhood_is_refused(self):
        self.assertIn("output must be", self._snapshot_error({"output": self.outside, "overwrite": True}))
        self.assertFalse(os.path.exists(self.outside))
        self.assertIn(".html", self._snapshot_error({"output": os.path.join(self.tmp, "page.txt")}))

    def test_default_output_sits_next_to_the_project(self):
        r, _ = session(("map_snapshot", {"project": self.proj}))
        self.assertFalse(r[1]["result"]["isError"], r)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, ".bot-ui-snapshot.html")))

    def test_a_link_is_not_followed(self):
        victim = self._victim()
        link = os.path.join(self.tmp, "link.html")
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError):
            self.skipTest("no permission to create symbolic links")
        self.assertIn("link", self._snapshot_error({"output": link, "overwrite": True}))
        self.assertEqual(pathlib.Path(victim).read_text(encoding="utf-8"), "keep me")



class AuditFixes(unittest.TestCase):
    """Defects found by the independent review and the architecture audit (2026-11-25)."""

    def test_tag_ranking_needs_a_brief_checks_types_and_respects_the_network_switch(self):
        r, _ = session(("emoji_rank_by_tags", {}), ("emoji_rank_by_tags", {"style": "outline"}),
                       ("emoji_rank_by_tags", {"style": ["outline"]}), ("map_snapshot", {"project": RICH, "overwrite": "false"}))
        self.assertIn("at least one", r[1]["result"]["content"][0]["text"])
        self.assertIn("must be array", r[2]["result"]["content"][0]["text"])
        self.assertIn("switched off", r[3]["result"]["content"][0]["text"])
        self.assertIn("overwrite must be boolean", r[4]["result"]["content"][0]["text"])

    def test_read_tools_never_roll_back_a_journal(self):
        tmp = tempfile.mkdtemp(prefix="bot-ui-mcp-journal-")
        try:
            proj = os.path.join(tmp, "bot-ui")
            shutil.copytree(RICH, proj)
            outside = os.path.join(tmp, "outside.txt")
            with open(outside, "w") as fh:
                fh.write("keep me")
            os.makedirs(os.path.join(proj, ".bot-ui"), exist_ok=True)
            with open(os.path.join(proj, ".bot-ui", "journal.json"), "w") as fh:
                json.dump({"files": [{"path": "project.json", "backup": outside}]}, fh)
            r, _ = session(("map_validate", {"project": proj}))
            self.assertIn("WRITE_PENDING", json.dumps(r[1]["result"]))
            self.assertTrue(os.path.isfile(outside), "a read-only tool moved a file")
            import _bot_ui  # noqa: F401  (core on sys.path)
            from bot_ui.store import StoreError, recover_if_needed
            with self.assertRaises(StoreError):  # a backup outside .bot-ui/txn/ is refused, nothing moves
                recover_if_needed(proj)
            self.assertTrue(os.path.isfile(outside))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BridgeArgs(unittest.TestCase):
    def test_a_mistyped_flag_is_refused(self):
        bridge = os.path.join(_paths.ROOT, "examples", "mcp", "telegram-bridge", "server.py")
        out = subprocess.run([sys.executable, bridge, "--file-root", "x"], input="", capture_output=True, text=True, timeout=60)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("unknown arguments", out.stderr + out.stdout)



class DocsMatchCode(unittest.TestCase):
    """The tool list agents read (api-catalog.md, READMEs) is the server's list."""

    def test_every_tool_is_documented_and_the_count_is_right(self):
        sys.path.insert(0, os.path.join(_paths.ROOT, "scripts"))
        import bot_ui_mcp
        names = [t["name"] for t in bot_ui_mcp.TOOLS]
        self.assertEqual(sorted(names), sorted(bot_ui_mcp.HANDLERS))
        with open(os.path.join(_paths.ROOT, "references", "api-catalog.md"), encoding="utf-8") as fh:
            catalog = fh.read()
        self.assertEqual([n for n in names if f"`{n}`" not in catalog], [])
        for readme in ("README.md", "README.ru.md", "README.uk.md"):
            with open(os.path.join(_paths.REPO, readme), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn(f"({len(names)} ", text, f"{readme}: MCP tool count")


if __name__ == "__main__":
    unittest.main()
