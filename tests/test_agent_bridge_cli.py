"""agent_bridge CLI: exit codes, hook adapters, and the token never leaking."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths
from agent_bridge import cli, hooks
from agent_bridge.transport import DryRunTransport, LiveTransport

FIX = os.path.join(_paths.EXAMPLES, "fixtures")
TOKEN = "123456789:" + "Z" * 35            # built at runtime: no token-shaped literal in the repo
ENV = {"AGENT_BRIDGE_TOKEN": TOKEN, "AGENT_BRIDGE_OPERATOR_ID": "111111111"}


def run(argv, env=None, stdin="", transport=None):
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run(argv, environ=ENV if env is None else env, transport=transport)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


class ExitCodes(unittest.TestCase):
    def test_approve_paths(self):
        cases = [("agent_approve_tap.json", 0, "approved"), ("agent_reject_tap.json", 3, "rejected"),
                 ("agent_forged_callback.json", 4, "expired")]
        for fixture, code, decision in cases:
            with self.subTest(fixture=fixture):
                c, out, _ = run(["approve", "Deploy v1.4", "--ttl", "120", "--fixture", os.path.join(FIX, fixture)])
                self.assertEqual((c, json.loads(out)["decision"]), (code, decision))

    def test_ask_timeout_returns_default_and_exit_4(self):
        c, out, _ = run(["ask", "Which branch?", "--default", "main", "--timeout", "60", "--quiet"])
        res = json.loads(out)
        self.assertEqual((c, res["status"], res["answer"]), (4, "timeout", "main"))

    def test_listen_emits_json_lines(self):
        c, out, _ = run(["listen", "--fixture", os.path.join(FIX, "agent_commands.json"), "--quiet"])
        lines = [json.loads(x) for x in out.splitlines()]
        self.assertEqual(c, 0)
        self.assertEqual([x["type"] for x in lines], ["command", "command", "invalid_command", "text", "text"])

    def test_progress_and_pending_with_state(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "s.json")
            run(["progress", "--key", "b1", "--title", "Build", "--stages", "A,B", "--stage", "A", "--state", state])
            c, out, _ = run(["progress", "--key", "b1", "--stage", "A", "--state", state, "--quiet"])
            self.assertEqual(json.loads(out)["action"], "skipped_same")
            c, out, _ = run(["pending", "--state", state])
            self.assertEqual(json.loads(out), {"open": []})

    def test_refused_file_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "env.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("BOT=" + TOKEN)
            c, out, err = run(["send-file", path])
            self.assertEqual(c, 1)
            self.assertIn("possible secrets", json.loads(out)["error"])
            self.assertNotIn(TOKEN, out + err)

    def test_live_requires_env_and_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            run(["--live", "notify", "hi"], env={"AGENT_BRIDGE_OPERATOR_ID": "111111111"})
        self.assertIn("AGENT_BRIDGE_TOKEN", str(ctx.exception))
        self.assertNotIn(TOKEN, str(ctx.exception))
        c, out, err = run(["notify", "hi"])             # no --live: dry-run even with a token set
        self.assertIn("DRY-RUN sendMessage", err)


class TokenNeverLeaks(unittest.TestCase):
    def test_token_in_text_args_logs_and_errors_is_redacted(self):
        from tgkit.transport import TelegramErrorResponse
        t = DryRunTransport().script("sendMessage", TelegramErrorResponse(
            400, f"Bad Request: chat not found (url /bot{TOKEN}/sendMessage)"))
        outputs = []
        for argv, tr in ((["notify", f"debug: token is {TOKEN}"], None),
                         (["report", "--json", os.path.join(FIX, "agent_report.json")], None),
                         (["notify", "x"], t)):
            try:
                code, out, err = run(argv, transport=tr)
            except Exception as exc:                       # an API error surfaces as an exception...
                out, err = "", str(exc)
            outputs.append(out + err)
        blob = "\n".join(outputs)
        self.assertNotIn(TOKEN, blob)
        self.assertIn("[REDACTED]", blob)

    def test_live_transport_repr_hides_token(self):
        self.assertNotIn(TOKEN, repr(LiveTransport(TOKEN)))

    def test_directory_entry_point_runs_from_anywhere(self):
        pkg = os.path.join(_paths.EXAMPLES, "python", "agent_bridge")
        env = {**os.environ, **ENV, "PYTHONIOENCODING": "utf-8"}
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, pkg, "notify", f"tok {TOKEN}"], cwd=d, env=env,
                               capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn(TOKEN, p.stdout + p.stderr)


class Hooks(unittest.TestCase):
    def test_claude_notification_and_stop(self):
        payload = {"hook_event_name": "Notification", "cwd": "/work/shop-api", "title": "Permission needed",
                   "message": "Claude needs your permission to use Bash", "notification_type": "permission_prompt"}
        c, out, err = run(["hook", "claude-notification"], stdin=json.dumps(payload))
        self.assertEqual((c, out), (0, ""), "Notification hooks print nothing on stdout")
        self.assertIn("Permission needed — shop-api", err)
        stop = {"hook_event_name": "Stop", "cwd": "/work/shop-api", "stop_hook_active": False,
                "last_assistant_message": "Refactor done; 42 tests pass."}
        c, out, err = run(["hook", "claude-stop"], stdin=json.dumps(stop))
        self.assertEqual((c, out), (0, ""))
        self.assertIn('"disable_notification": true', err)
        self.assertIsNone(hooks.stop_text({**stop, "stop_hook_active": True}))

    def test_codex_stop_prints_json(self):
        c, out, _ = run(["hook", "codex-stop", "--quiet"], stdin=json.dumps({"last_assistant_message": "done"}))
        self.assertEqual((c, json.loads(out)), (0, {}))

    def test_permission_request_allow_deny_and_timeout(self):
        req = {"hook_event_name": "PermissionRequest", "cwd": "/work/shop-api", "tool_name": "Bash",
               "tool_input": {"command": "npm run deploy -- --prod", "description": "Deploy"}}
        c, out, _ = run(["hook", "claude-permission", "--quiet", "--fixture",
                         os.path.join(FIX, "agent_approve_tap.json")], stdin=json.dumps(req))
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                                                  "decision": {"behavior": "allow"}}})
        c, out, _ = run(["hook", "codex-permission", "--quiet", "--fixture",
                         os.path.join(FIX, "agent_reject_tap.json")], stdin=json.dumps(req))
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["decision"]["behavior"], "deny")
        c, out, _ = run(["hook", "claude-permission", "--quiet", "--ttl", "30"], stdin=json.dumps(req))
        self.assertEqual((c, json.loads(out)), (0, {}), "timeout -> no decision -> local prompt")
        c, out, _ = run(["hook", "claude-permission", "--quiet", "--ttl", "30", "--on-timeout", "deny"],
                        stdin=json.dumps(req))
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["decision"]["behavior"], "deny")

    def test_garbage_stdin_does_not_crash(self):
        c, out, _ = run(["hook", "claude-stop", "--quiet"], stdin="not json")
        self.assertEqual(c, 0)
        c, out, _ = run(["hook", "codex-notify", "--quiet", '{"type": "agent-turn-complete"}'])
        self.assertEqual(c, 0)


if __name__ == "__main__":
    unittest.main()
