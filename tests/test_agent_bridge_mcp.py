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
