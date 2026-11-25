"""MCP example (stdlib server) over real stdio, plus agent payload drift."""
import json
import os
import subprocess
import sys
import unittest

import _paths

SERVER = os.path.join(_paths.EXAMPLES, "mcp", "telegram-bridge", "server.py")
TOKEN = "123456789:" + "Q" * 35


def session(*msgs, env_extra=None, args=()):
    env = {**os.environ, "AGENT_BRIDGE_TOKEN": TOKEN, "AGENT_BRIDGE_OPERATOR_ID": "111111111",
           "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    lines = "\n".join(json.dumps(m) for m in msgs) + "\n"
    p = subprocess.run([sys.executable, SERVER, *args], input=lines, capture_output=True, text=True,
                       encoding="utf-8", env=env, cwd=os.path.dirname(SERVER), timeout=60)
    return [json.loads(x) for x in p.stdout.splitlines() if x.strip()], p.stdout + p.stderr


def req(i, method, params=None):
    m = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        m["params"] = params
    return m


class StdioServer(unittest.TestCase):
    def test_handshake_tools_and_calls(self):
        out, raw = session(
            req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "test", "version": "0"}}),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            req(2, "tools/list"),
            req(3, "tools/call", {"name": "telegram_notify", "arguments": {"text": f"token {TOKEN}"}}),
            req(4, "tools/call", {"name": "telegram_ask", "arguments": {"question": "Branch?", "default": "main",
                                                                        "timeout_seconds": 60}}),
            req(5, "tools/call", {"name": "telegram_send_file", "arguments": {"path": os.path.abspath(__file__)}}),
            req(6, "tools/call", {"name": "rm_rf", "arguments": {}}),
            req(7, "server/discover"))
        by_id = {m["id"]: m for m in out}
        self.assertEqual(len(out), 7, "the notification gets no reply")
        self.assertEqual(by_id[1]["result"]["protocolVersion"], "2025-06-18")
        names = [t["name"] for t in by_id[2]["result"]["tools"]]
        self.assertEqual(names, ["telegram_notify", "telegram_progress", "telegram_ask",
                                 "telegram_request_approval", "telegram_send_file", "telegram_inbox"])
        self.assertFalse(by_id[3]["result"]["isError"])
        ask = by_id[4]["result"]["structuredContent"]
        self.assertEqual((ask["status"], ask["answer"]), ("timeout", "main"))
        self.assertTrue(by_id[5]["result"]["isError"], "files outside --files-root are refused")
        self.assertEqual(by_id[6]["error"]["code"], -32602)
        self.assertEqual(by_id[7]["error"]["code"], -32601, "2026-07-28 probe -> fall back to initialize")
        self.assertNotIn(TOKEN, raw)

    def test_arguments_outside_the_schema_are_refused(self):
        """L5: the declared inputSchema is enforced before a tool runs, so a model cannot block
        telegram_ask past its maximum, pass oversized text or smuggle extra keys."""
        bad = [
            ("telegram_ask", {"question": "Branch?", "timeout_seconds": 10 ** 9}, "timeout_seconds"),
            ("telegram_ask", {"question": "Branch?", "timeout_seconds": 5}, "timeout_seconds"),
            ("telegram_ask", {"question": "Branch?", "timeout_seconds": float("nan")}, "timeout_seconds"),
            ("telegram_ask", {"question": "x" * 3001}, "question"),
            ("telegram_ask", {"question": "Pick", "choices": [str(n) for n in range(9)]}, "choices"),
            ("telegram_ask", {"question": "Pick", "choices": ["x" * 65]}, "choices"),
            ("telegram_ask", {}, "question"),
            ("telegram_notify", {"text": ""}, "text"),
            ("telegram_notify", {"text": 123}, "text"),
            ("telegram_notify", {"text": "hi", "silent": "false"}, "silent"),
            ("telegram_notify", {"text": "hi", "chat_id": 222222222}, "chat_id"),
            ("telegram_progress", {"key": "../etc"}, "key"),
            ("telegram_progress", {"key": "job", "state": "exploded"}, "state"),
            ("telegram_request_approval", {"summary": "Deploy", "ttl_seconds": 10 ** 6}, "ttl_seconds"),
            ("telegram_inbox", {"max_events": True}, "max_events"),
            ("telegram_inbox", {"max_events": 51}, "max_events"),
        ]
        calls = [req(i, "tools/call", {"name": name, "arguments": args}) for i, (name, args, _) in enumerate(bad, 1)]
        out, _ = session(*calls, req(99, "tools/call", {"name": "telegram_notify", "arguments": "hi"}))
        by_id = {m["id"]: m for m in out}
        for i, (name, args, key) in enumerate(bad, 1):
            result = by_id[i]["result"]
            self.assertTrue(result["isError"], (name, args))
            self.assertIn(key, result["content"][0]["text"], (name, args))
        self.assertTrue(by_id[99]["result"]["isError"], "arguments must be an object")

    def test_null_optional_arguments_count_as_absent(self):
        """server_sdk.py passes None for every optional argument the model left out."""
        sys.path.insert(0, os.path.dirname(SERVER))
        import tools
        tools.check_arguments("telegram_progress", {"key": "job", "title": None, "stages": None,
                                                    "stage": None, "note": None, "state": "running"})
        with self.assertRaises(ValueError):
            tools.check_arguments("telegram_progress", {"key": None})

    def test_unknown_protocol_version_gets_ours(self):
        out, _ = session(req(1, "initialize", {"protocolVersion": "1999-01-01", "capabilities": {}}))
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-11-25")

    def test_garbage_line(self):
        env = {**os.environ, "AGENT_BRIDGE_OPERATOR_ID": "111111111", "PYTHONIOENCODING": "utf-8"}
        p = subprocess.run([sys.executable, SERVER], input="not json\n", capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=os.path.dirname(SERVER), timeout=60)
        self.assertEqual(json.loads(p.stdout)["error"]["code"], -32700)


class Payloads(unittest.TestCase):
    def test_agent_payload_files_match_the_code(self):
        p = subprocess.run([sys.executable, "-m", "agent_bridge", "export-payloads", "--check"],
                           cwd=os.path.join(_paths.EXAMPLES, "python"), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
