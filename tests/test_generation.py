"""Check 4: success / stop / error / timeout end differently; late chunks and a
repeated Stop never create a second result; throttling can't be bypassed."""
import random
import unittest

import _paths  # noqa: F401
from tgkit.generation import Generation, GenerationConfig, OperationRegistry, State, execute
from tgkit.transport import FakeTransport


def finals(t):
    return [p for m, p in t.calls if m in ("sendRichMessage", "sendMessage")]


class Endings(unittest.TestCase):
    def drive(self, events, policy="keep_marked"):
        t = FakeTransport()
        cancelled = []
        g = Generation(op_id="op", chat_id=1, draft_id=9, config=GenerationConfig(stop_policy=policy, deadline=30))
        execute(g.start(0.0), t, g, now=0.0)
        for ts, kind, val in events:
            eff = {"chunk": lambda: g.on_chunk(val, ts), "stop": lambda: g.on_stop(ts),
                   "done": lambda: g.on_done(ts), "error": lambda: g.on_error(ts),
                   "tick": lambda: g.on_tick(ts)}[kind]()
            execute(eff, t, g, now=ts, cancel_upstream=lambda: cancelled.append(ts))
        return t, g, cancelled

    def test_distinct_endings(self):
        cases = {"done": State.COMPLETED, "stop": State.STOPPED, "error": State.FAILED}
        seen = {}
        for kind, state in cases.items():
            t, g, _ = self.drive([(1.0, "chunk", "Hello world. "), (2.0, kind, None)])
            self.assertEqual(g.outcome, state)
            self.assertEqual(len(finals(t)), 1)
            seen[kind] = json_of(finals(t)[0])
        t, g, _ = self.drive([(1.0, "chunk", "Hello. "), (31.0, "tick", None)])
        self.assertEqual(g.outcome, State.TIMED_OUT)
        seen["timeout"] = json_of(finals(t)[0])
        self.assertEqual(len(set(seen.values())), 4, "each ending renders differently")

    def test_stop_vs_done_race_both_orders(self):
        for order in (("stop", "done"), ("done", "stop")):
            t, g, _ = self.drive([(1.0, "chunk", "Part. "), (2.0, order[0], None), (2.0, order[1], None)])
            self.assertEqual(g.finalizations, 1)
            self.assertEqual(len(finals(t)), 1)
            self.assertEqual(g.outcome, State.STOPPED if order[0] == "stop" else State.COMPLETED)

    def test_late_chunks_and_repeated_stop(self):
        t, g, cancelled = self.drive([(1.0, "chunk", "Kept. "), (2.0, "stop", None), (2.1, "chunk", "LATE"),
                                      (2.2, "stop", None), (9.0, "tick", None)])
        self.assertEqual(len(finals(t)), 1)
        self.assertNotIn("LATE", json_of(finals(t)[0]))
        self.assertEqual(g.dropped_chunks, 1)
        self.assertEqual(cancelled, [2.0], "upstream cancelled once")

    def test_no_draft_after_terminal(self):
        t, g, _ = self.drive([(1.0, "chunk", "x" * 50), (2.0, "done", None), (3.0, "tick", None), (4.0, "chunk", "y" * 80)])
        last_final = max(i for i, (m, _) in enumerate(t.calls) if m == "sendRichMessage")
        self.assertFalse(any(m.endswith("Draft") for m, _ in t.calls[last_final:]))

    def test_sentence_ends_do_not_bypass_min_interval(self):
        events = [(0.1 * i, "chunk", "Short. ") for i in range(1, 30)]   # a sentence every 100 ms
        t, g, _ = self.drive(events)
        drafts = [i for i, (m, _) in enumerate(t.calls) if m == "sendRichMessageDraft"]
        self.assertLessEqual(len(drafts), 4, "~3 s of input at >= 1 s spacing (+ the start draft)")

    def test_randomised_event_orders_keep_one_finalization(self):
        rng = random.Random(1234)
        kinds = ["chunk", "chunk", "chunk", "tick", "stop", "done", "error"]
        for _ in range(300):
            events = [(i * rng.uniform(0.05, 2.0), rng.choice(kinds), "abc. ") for i in range(1, 12)]
            events.sort(key=lambda e: e[0])
            t, g, _ = self.drive(events, policy=rng.choice(["keep_marked", "discard", "offer_continue"]))
            self.assertLessEqual(g.finalizations, 1)
            self.assertLessEqual(len(finals(t)), 1)
            if g.terminal:
                idx = [i for i, (m, _) in enumerate(t.calls) if m in ("sendRichMessage", "sendMessage")]
                self.assertTrue(all(not m.endswith("Draft") for m, _ in t.calls[idx[0] + 1:]))

    def test_stop_matching_needs_chat_thread_and_draft(self):
        reg = OperationRegistry()
        g = Generation(op_id="a", chat_id=1, draft_id=5, message_thread_id=7)
        reg.add(g)
        self.assertIs(reg.find_for_stop({"chat": {"id": 1}, "message_thread_id": 7, "draft_id": 5}), g)
        self.assertIsNone(reg.find_for_stop({"chat": {"id": 1}, "draft_id": 5}))
        self.assertIsNone(reg.find_for_stop({"chat": {"id": 2}, "message_thread_id": 7, "draft_id": 5}))

    def test_thinking_label_is_allowlisted(self):
        g = Generation(op_id="a", chat_id=1, draft_id=5)
        g.start(0.0)
        eff = g.on_stage("<model reasoning: the user is probably lying>", 5.0)
        label = eff[0]["params"]["rich_message"]["blocks"][0]["text"]
        self.assertNotIn("reasoning", label)

    def test_zero_draft_id_rejected(self):
        with self.assertRaises(ValueError):
            Generation(op_id="a", chat_id=1, draft_id=0)


def json_of(params):
    import json
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
