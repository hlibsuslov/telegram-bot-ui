"""agent_bridge: allowlist, approval binding, asks, restart, progress, intake."""
import copy
import os
import tempfile
import unittest

import _paths
from agent_bridge.approvals import IdFactory
from agent_bridge.bridge import AgentBridge, BridgeConfig, VirtualClock
from agent_bridge.intake import FixtureSource, webhook_events
from agent_bridge.redact import Redactor
from agent_bridge.security import Allowlist, classify
from agent_bridge.store import JsonStore
from agent_bridge.transport import DryRunTransport
from tgkit.transport import TelegramErrorResponse

OP, STRANGER, MEMBER, GROUP = 111111111, 333333333, 222222222, -1001234567890


def fx(name):
    return _paths.load("examples", "fixtures", name)


def make(updates=(), *, store=None, transport=None, members=None, groups=None, seed="offline"):
    clock = VirtualClock(1_762_900_000.0)
    allow = Allowlist({OP}, set(members or ()), set(groups or ()))
    t = transport or DryRunTransport()
    b = AgentBridge(t, BridgeConfig(chat_id=OP, allow=allow, bot_username="agent_demo_bot"),
                    store=store or JsonStore(), source=FixtureSource(list(updates), clock=clock),
                    clock=clock, sleep=clock.sleep, ids=IdFactory(seed))
    return b, t, clock


def tap(rec, choice, *, user=OP, chat=OP, mid=None, uid=920000, data=None):
    chat_obj = {"id": chat, "type": "private" if chat > 0 else "supergroup"}
    return {"update_id": uid, "callback_query": {
        "id": f"q{uid}", "from": {"id": user, "is_bot": False, "first_name": "Alice"},
        "message": {"message_id": mid or rec["message_id"], "date": 0, "chat": chat_obj},
        "data": data or f"{'ap' if rec['kind'] == 'approval' else 'aq'}:{rec['rid']}:{rec['nonce']}:{choice}"}}


def reply(rec, text, *, user=OP, uid=930000, **extra):
    m = {"message_id": 5000 + uid % 1000, "date": 0, "chat": {"id": OP, "type": "private"},
         "from": {"id": user, "is_bot": False, "first_name": "Alice"}, "text": text,
         "reply_to_message": {"message_id": rec["message_id"], "date": 0, "chat": {"id": OP, "type": "private"}}}
    m.update(extra)
    return {"update_id": uid, "message": m}


class Allowlisting(unittest.TestCase):
    def test_non_allowlisted_sender_is_ignored_silently(self):
        b, t, _ = make([fx("agent_stranger_message.json")])
        events = list(b.listen())
        self.assertEqual(events, [])
        self.assertEqual(b.intake.stats["rejected"], 1)
        self.assertEqual(t.calls, [], "no reply, no API call for a stranger")

    def test_same_display_name_or_username_does_not_grant_access(self):
        ev = classify(fx("agent_stranger_message.json"), Allowlist({OP}))
        self.assertEqual((ev["type"], ev["reason"]), ("rejected", "unknown_sender"))
        self.assertNotIn("text", ev, "a rejected update carries no stranger text")

    def test_usernames_are_refused_in_the_allowlist(self):
        with self.assertRaises(ValueError):
            Allowlist.parse("@alice_ops")
        self.assertEqual(Allowlist.parse("111111111, 222222222").operators, {OP, MEMBER})

    def test_anonymous_admin_and_bots_are_rejected(self):
        base = {"message_id": 1, "date": 0, "chat": {"id": GROUP, "type": "supergroup"}, "text": "/status"}
        allow = Allowlist({OP}, group_chats={GROUP})
        anon = {"update_id": 1, "message": {**base, "from": {"id": 1087968824, "is_bot": True, "first_name": "Group"},
                                            "sender_chat": {"id": GROUP, "type": "supergroup"}}}
        bot = {"update_id": 2, "message": {**base, "from": {"id": OP, "is_bot": True, "first_name": "x"}}}
        self.assertEqual(classify(anon, allow)["reason"], "anonymous_sender")
        self.assertEqual(classify(bot, allow)["reason"], "bot_sender")

    def test_operator_in_unknown_group_is_rejected(self):
        upd = {"update_id": 3, "message": {"message_id": 1, "date": 0, "text": "/status",
                                           "chat": {"id": -100555, "type": "supergroup"},
                                           "from": {"id": OP, "is_bot": False, "first_name": "Alice"}}}
        self.assertEqual(classify(upd, Allowlist({OP}))["reason"], "unknown_chat")

    def test_commands_table_validation_and_forwarded_commands(self):
        b, _, _ = make(fx("agent_commands.json")["updates"])
        evs = list(b.listen())
        kinds = [(e["type"], e.get("command")) for e in evs]
        self.assertEqual(kinds, [("command", "status"), ("command", "stop"), ("invalid_command", "stop"),
                                 ("text", None), ("text", None)])
        self.assertTrue(evs[3]["forwarded"], "a forwarded /stop is data, not a command")
        self.assertEqual(b.intake.stats, {"duplicates": 1, "rejected": 1, "throttled": 0})

    def test_command_for_another_bot_is_not_ours(self):
        upd = {"update_id": 4, "message": {"message_id": 1, "date": 0, "text": "/stop@other_bot job1",
                                           "chat": {"id": OP, "type": "private"},
                                           "from": {"id": OP, "is_bot": False, "first_name": "A"}}}
        self.assertEqual(classify(upd, Allowlist({OP}), "agent_demo_bot")["type"], "text")

    def test_member_may_not_run_operator_commands(self):
        allow = Allowlist({OP}, {MEMBER}, {GROUP})
        upd = {"update_id": 5, "message": {"message_id": 1, "date": 0, "text": "/stop job1",
                                           "chat": {"id": GROUP, "type": "supergroup"},
                                           "from": {"id": MEMBER, "is_bot": False, "first_name": "M"}}}
        self.assertEqual(classify(upd, allow)["reason"], "command_needs_operator")
        upd["message"]["text"] = "/status"
        self.assertEqual(classify(upd, allow)["type"], "command")

    def test_unknown_chat_added_leaves_and_alerts_operator(self):
        b, t, _ = make([fx("agent_added_to_unknown_group.json")])
        list(b.listen())
        self.assertEqual(t.methods(), ["leaveChat", "sendMessage"])
        self.assertEqual(t.params_of("leaveChat")[0]["chat_id"], -1009876543210)
        alert = t.params_of("sendMessage")[0]
        self.assertEqual(alert["chat_id"], OP)
        self.assertNotIn("Free crypto signals", alert["text"], "untrusted chat titles are not echoed")

    def test_flooding_sender_is_throttled(self):
        ups = [{"update_id": 940000 + i, "message": {"message_id": i, "date": 0, "text": f"hi {i}",
                                                     "chat": {"id": OP, "type": "private"},
                                                     "from": {"id": OP, "is_bot": False, "first_name": "A"}}}
               for i in range(25)]
        b, _, _ = make(ups)
        self.assertEqual(len(list(b.listen())), 20)
        self.assertEqual(b.intake.stats["throttled"], 5)


class ApprovalBinding(unittest.TestCase):
    def _pending(self, **kw):
        b, t, clock = make(**kw)
        rec = b.request_approval("Deploy v1.4 to production", details="3 migrations", ttl=600)
        return b, t, clock, rec

    def test_valid_tap_approves_and_disables_buttons(self):
        b, t, _, rec = self._pending()
        b.source.queue.append(tap(rec, "a"))
        res = b.wait(rec["rid"])
        self.assertEqual((res["decision"], res["by"]), ("approved", OP))
        edit = t.params_of("editMessageText")[-1]
        self.assertEqual(edit["reply_markup"]["inline_keyboard"], [[{"text": "Approved by Alice", "disabled": {}}]])
        self.assertEqual(t.params_of("answerCallbackQuery")[-1]["text"], "Approved")

    def test_forged_nonce_is_rejected(self):
        b, t, _, rec = self._pending()
        b.source.queue.append(tap(rec, "a", data=f"ap:{rec['rid']}:nAAAAAAA:a"))
        res = b.wait(rec["rid"])
        self.assertEqual(res["decision"], "expired")
        self.assertEqual(t.params_of("answerCallbackQuery")[0]["text"], "This button is no longer valid")

    def test_garbage_and_unknown_request_are_rejected(self):
        b, t, _, rec = self._pending()
        b.source.queue.extend([tap(rec, "a", data="ap:deadbeef:n0000000:a", uid=1),
                               tap(rec, "a", data="ap:' OR 1=1 --", uid=2),
                               tap(rec, "x", uid=3)])
        res = b.wait(rec["rid"])
        self.assertEqual(res["decision"], "expired")
        self.assertEqual(len(t.params_of("answerCallbackQuery")), 3, "every tap is answered, none decides")

    def test_tap_from_a_copied_message_is_rejected(self):
        b, _, _, rec = self._pending()
        b.source.queue.append(tap(rec, "a", mid=rec["message_id"] + 7))
        self.assertEqual(b.wait(rec["rid"])["decision"], "expired")

    def test_non_approver_in_group_cannot_decide(self):
        b, t, _ = make(members={MEMBER}, groups={GROUP})
        rec = b.request_approval("Restart staging", chat_id=GROUP, ttl=300)
        b.source.queue.extend([tap(rec, "a", user=MEMBER, chat=GROUP, uid=11),
                               tap(rec, "r", user=OP, chat=GROUP, uid=12)])
        res = b.wait(rec["rid"])
        self.assertEqual((res["decision"], res["by"]), ("rejected", OP))
        first = t.params_of("answerCallbackQuery")[0]
        self.assertEqual((first["text"], first["show_alert"]), ("You can't decide this request", True))

    def test_stale_tap_after_expiry_is_rejected(self):
        b, t, clock, rec = self._pending()
        late = tap(rec, "a")
        late["_at"] = clock() + 700
        b.source.queue.append(late)
        self.assertEqual(b.wait(rec["rid"])["decision"], "expired")
        clock.sleep(200)
        b.pump()                                       # the late tap arrives after the request closed
        self.assertEqual(t.params_of("answerCallbackQuery")[-1]["text"], "Already decided")
        self.assertEqual(b.store.get_pending(rec["rid"])["decision"], "expired")

    def test_duplicate_and_conflicting_taps(self):
        b, t, _, rec = self._pending()
        b.source.queue.extend([tap(rec, "a", uid=21), tap(rec, "a", uid=22), tap(rec, "r", uid=23),
                               tap(rec, "a", uid=21)])        # redelivered update_id
        self.assertEqual(b.wait(rec["rid"])["decision"], "approved")
        b.pump()
        b.pump()
        b.pump()
        texts = [p["text"] for p in t.params_of("answerCallbackQuery")]
        self.assertEqual(texts, ["Approved", "Already recorded", "Already decided"])
        self.assertEqual(len(t.params_of("editMessageText")), 1, "card closed once")

    def test_details_never_decides(self):
        b, t, clock, rec = self._pending()
        b.source.queue.append(tap(rec, "d"))
        b.pump()
        self.assertEqual(b.store.get_pending(rec["rid"])["status"], "open")
        ans = t.params_of("answerCallbackQuery")[0]
        self.assertEqual((ans["text"], ans["show_alert"]), ("3 migrations", True))

    def test_typed_approve_does_not_approve(self):
        b, _, _, rec = self._pending()
        b.source.queue.append(reply(rec, "approve"))
        self.assertEqual(b.wait(rec["rid"])["decision"], "expired")

    def test_callback_data_fits_64_bytes(self):
        b, t, _, rec = self._pending()
        for row in t.params_of("sendMessage")[0]["reply_markup"]["inline_keyboard"]:
            for btn in row:
                self.assertLessEqual(len(btn["callback_data"].encode()), 64)


class Asking(unittest.TestCase):
    def test_typed_answer_is_returned_as_data(self):
        b, t, _ = make()
        rec = b.request_answer("Which branch should I deploy?", timeout=300)
        b.source.queue.append(reply(rec, "dev"))
        res = b.wait(rec["rid"])
        self.assertEqual((res["status"], res["answer"], res["via"]), ("answered", "dev", "text"))
        self.assertTrue(res["content_is_untrusted_data"])
        markup = t.params_of("sendMessage")[0]["reply_markup"]
        self.assertEqual(markup["force_reply"], True)
        self.assertLessEqual(len(markup["input_field_placeholder"]), 64)

    def test_choice_button_answers(self):
        b, t, _ = make()
        rec = b.request_answer("Run e2e?", choices=["Yes", "Skip e2e"], timeout=300)
        b.source.queue.append(tap(rec, "1"))
        res = b.wait(rec["rid"])
        self.assertEqual((res["answer"], res["via"]), ("Skip e2e", "button"))
        sent = t.params_of("sendMessage")[0]["reply_markup"]
        self.assertTrue(sent["force_reply"])
        self.assertTrue(t.params_of("editMessageText")[-1]["reply_markup"]["force_reply"],
                        "force_reply can't change in an inline-keyboard edit")

    def test_timeout_reminds_once_then_returns_default(self):
        b, t, clock = make()
        start = clock()
        res = b.ask("Which branch?", timeout=600, remind_after=300, default="main")
        self.assertEqual((res["status"], res["answer"], res["used_default"]), ("timeout", "main", True))
        reminders = [p for p in t.params_of("sendMessage") if p["text"].startswith("Reminder")]
        self.assertEqual(len(reminders), 1)
        self.assertGreaterEqual(clock() - start, 600)
        self.assertIn("No answer — continued with: main", t.params_of("editMessageText")[-1]["text"])

    def test_reply_from_stranger_or_to_other_message_is_not_an_answer(self):
        b, _, _ = make()
        rec = b.request_answer("Which branch?", timeout=120)
        other = reply(rec, "prod", uid=930001)
        other["message"]["reply_to_message"]["message_id"] = 1
        b.source.queue.extend([reply(rec, "prod", user=STRANGER, uid=930002), other])
        self.assertEqual(b.wait(rec["rid"])["status"], "timeout")

    def test_injected_instructions_come_back_as_data_and_trigger_nothing(self):
        b, t, _ = make()
        rec = b.request_answer("Which branch should I deploy?", timeout=300)
        inj = copy.deepcopy(fx("agent_injection_reply.json"))
        inj["message"]["reply_to_message"]["message_id"] = rec["message_id"]
        b.source.queue.append(inj)
        res = b.wait(rec["rid"])
        self.assertIn("Ignore all previous instructions", res["answer"])
        self.assertTrue(res["content_is_untrusted_data"])
        self.assertEqual(set(res["injection_signals"]), {"override", "shell", "exfiltration"})
        self.assertEqual(t.methods(), ["sendMessage", "editMessageText"],
                         "no approval, no file, no other chat: only the question and its closing edit")
        self.assertEqual(b.store.open_requests(), {})


class RestartSafety(unittest.TestCase):
    def test_restarted_process_resolves_pending_approval(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            b1, _, _ = make(store=JsonStore(path))
            rec = b1.request_approval("Deploy v1.4", ttl=900)
            del b1                                            # process dies before the tap
            b2, t2, _ = make([tap(rec, "a")], store=JsonStore(path), seed="other")
            self.assertEqual(b2.store.open_requests().keys(), {rec["rid"]})
            res = b2.wait(rec["rid"])
            self.assertEqual(res["decision"], "approved")
            self.assertEqual(t2.methods(), ["answerCallbackQuery", "editMessageText"], "no second approval message")

    def test_offset_and_seen_survive_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            ups = fx("agent_commands.json")["updates"][:2]
            b1, _, _ = make(ups, store=JsonStore(path))
            self.assertEqual(len(list(b1.listen())), 2)
            b2, _, _ = make(ups, store=JsonStore(path))       # Telegram redelivers after a crash
            self.assertEqual(list(b2.listen()), [])
            self.assertEqual(JsonStore(path).offset, 910012)

    def test_progress_card_is_reused_after_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            b1, t1, _ = make(store=JsonStore(path))
            b1.progress("build-142", title="Build #142", stages=["Install", "Compile", "Test"], stage="Install")
            b2, t2, clock = make(store=JsonStore(path))
            clock.sleep(10)
            b2.progress("build-142", stage="Compile")
            self.assertEqual(t2.methods(), ["editMessageText"])
            self.assertEqual(t2.params_of("editMessageText")[0]["message_id"], 1001)


class Progress(unittest.TestCase):
    def test_throttle_skip_same_and_final(self):
        b, t, clock = make()
        acts = [b.progress("j", title="Tests", stages=["Lint", "Unit", "E2E"], stage="Lint")["action"]]
        clock.sleep(1)
        acts.append(b.progress("j", stage="Unit")["action"])               # < 3 s: throttled
        clock.sleep(3)
        acts.append(b.progress("j", stage="Unit")["action"])               # pending state sent now
        clock.sleep(5)
        acts.append(b.progress("j", stage="Unit")["action"])               # identical: no call
        clock.sleep(0.5)
        acts.append(b.progress("j", stage="E2E", state="done")["action"])  # final: never throttled
        self.assertEqual(acts, ["sent", "skipped_throttled", "edited", "skipped_same", "edited"])
        self.assertEqual(t.methods(), ["sendMessage", "editMessageText", "editMessageText", "sendMessage"])
        final = t.params_of("editMessageText")[-1]["text"]
        self.assertEqual(final.count("✅"), 3)
        notice = t.params_of("sendMessage")[-1]
        self.assertEqual(notice["reply_parameters"]["message_id"], 1001, "a short notice: edits don't notify")

    def test_not_modified_is_success_and_deleted_card_is_resent(self):
        t = DryRunTransport().script("editMessageText",
                                     TelegramErrorResponse(400, "Bad Request: message is not modified"),
                                     TelegramErrorResponse(400, "Bad Request: message to edit not found"))
        b, _, clock = make(transport=t)
        b.progress("j", title="Job", stages=["A", "B"], stage="A")
        clock.sleep(5)
        self.assertEqual(b.progress("j", stage="B")["action"], "edited")
        clock.sleep(20)                                            # note-only change: >= 15 s
        self.assertEqual(b.progress("j", stage="B", note="retrying")["action"], "resent")

    def test_failed_state_marks_current_stage(self):
        b, t, clock = make()
        b.progress("j", title="Deploy", stages=["Build", "Migrate"], stage="Migrate")
        clock.sleep(5)
        b.progress("j", stage="Migrate", state="failed", note="migration 0042 timed out")
        self.assertIn("❌ Migrate", t.params_of("editMessageText")[-1]["text"])


class Intake(unittest.TestCase):
    def test_webhook_secret_and_redelivery(self):
        store, allow = JsonStore(), Allowlist({OP})
        body = (_paths.read("examples", "fixtures", "agent_operator_reply.json")).encode()
        self.assertEqual(webhook_events({}, body, "s3cret-value", store, allow)[0], 401)
        hdr = {"X-Telegram-Bot-Api-Secret-Token": "s3cret-value"}
        status, evs = webhook_events(hdr, body, "s3cret-value", store, allow)
        self.assertEqual((status, evs[0]["type"]), (200, "reply"))
        self.assertEqual(webhook_events(hdr, body, "s3cret-value", store, allow), (200, []))

    def test_polling_passes_allowed_updates_and_offset(self):
        from agent_bridge.intake import PollingSource
        t = DryRunTransport().script("getUpdates", [])
        store = JsonStore()
        store.mark_seen(910020)
        PollingSource(t.call, store).fetch(25)
        p = t.params_of("getUpdates")[0]
        self.assertEqual(p["offset"], 910021)
        self.assertIn("stopped_message_generation", p["allowed_updates"])
        self.assertIn("callback_query", p["allowed_updates"])


class Redaction(unittest.TestCase):
    def test_patterns(self):
        token = "123456789:" + "A" * 35
        r = Redactor([token])
        out = r.text(f"url https://api.telegram.org/bot{token}/getMe password=hunter22 ghp_{'x' * 30}")
        self.assertNotIn(token, out)
        self.assertNotIn("hunter22", out)
        self.assertNotIn("ghp_", out)

    def test_secret_file_is_refused(self):
        b, t, _ = make()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "deploy.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("ok\nAWS key AKIA" + "ABCDEFGHIJKLMNOP" + "\n")
            with self.assertRaises(PermissionError):
                b.send_file(path)
            self.assertEqual(t.calls, [])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("all green\n")
            res = b.send_file(path, caption="Deploy log")
            self.assertEqual((res["name"], res["size"]), ("deploy.log", os.path.getsize(path)))
            self.assertEqual(t.uploads[0]["document"]["sha256"], res["sha256"])

    def test_files_never_go_to_groups_by_default(self):
        b, _, _ = make(groups={GROUP})
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("hello")
        try:
            with self.assertRaises(PermissionError):
                b.send_file(fh.name, chat_id=GROUP)
        finally:
            os.unlink(fh.name)


if __name__ == "__main__":
    unittest.main()
