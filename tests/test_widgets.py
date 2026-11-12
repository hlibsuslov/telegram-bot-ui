"""Check 7: widgets respect production/test, the official size algorithm, state
audiences, answer-exactly-once, revisions, and the runtime they don't have."""
import json
import os
import random
import string
import unittest
import zlib

import _paths
from tgkit.errors import TelegramError
from tgkit.transport import FakeTransport, TelegramErrorResponse
from tgkit.widgets import (SharedWidgetWriter, StateRecord, WidgetStore, check_widget, compressed_size,
                           encode_state, handle_widget_query)

WIDGETS = os.path.join(_paths.EXAMPLES, "widgets")


class Size(unittest.TestCase):
    def test_compressed_size_is_zlib_level_9_of_utf8(self):
        html = "<p>Привет, мир</p>" * 50
        self.assertEqual(compressed_size(html), len(zlib.compress(html.encode("utf-8"), 9)))

    def test_small_raw_size_can_still_exceed_compressed_limit(self):
        rng = random.Random(3)
        noise = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(6000))
        rep = check_widget(f"<p>{noise}</p>", caption="x")
        self.assertLess(rep.raw_bytes, 32768)
        self.assertGreater(rep.compressed_bytes, 4096)
        self.assertTrue(any("zlib" in e for e in rep.errors))

    def test_large_repetitive_html_passes_compression_but_not_raw_limit(self):
        rep = check_widget("<p>a</p>" * 5000, caption="x")
        self.assertLess(rep.compressed_bytes, 4096)
        self.assertTrue(any("32768" in e for e in rep.errors))

    def test_state_limit_is_bytes_not_characters(self):
        self.assertTrue(check_widget("<p>x</p>", caption="c", chat_data="я" * 512).ok)       # 1024 bytes
        self.assertFalse(check_widget("<p>x</p>", caption="c", chat_data="я" * 513).ok)
        with self.assertRaises(ValueError):
            encode_state({"t": "я" * 600})

    def test_shipped_widgets_are_valid_for_production(self):
        for name in sorted(os.listdir(WIDGETS)):
            with self.subTest(widget=name):
                rep = check_widget(_paths.read("examples", "widgets", name), caption="Caption")
                self.assertEqual(rep.errors, [])
                self.assertEqual(rep.warnings, [], "shipped widgets avoid browser-only features")


class ContextAndRuntime(unittest.TestCase):
    def test_production_vs_test_contexts(self):
        for ctx in ("group", "supergroup", "inline", "forward"):
            self.assertFalse(check_widget("<p>x</p>", caption="c", context=ctx).ok, ctx)
            self.assertTrue(check_widget("<p>x</p>", caption="c", context=ctx, environment="test").ok, ctx)
        self.assertTrue(check_widget("<p>x</p>", caption="c", context="private").ok)

    def test_web_page_habits_are_flagged(self):
        page = ('<input type="text"><script src="https://cdn.example/lib.js"></script>'
                '<div style="height:100vh;overflow:auto"></div><script>fetch("/api");alert(1)</script>')
        warnings = " ".join(check_widget(page, caption="c").warnings)
        for needle in ("NetworkDisabledError", "form controls", "external scripts", "height-relative",
                       "scrolls", "dialogs"):
            self.assertIn(needle, warnings)

    def test_caption_and_secrets(self):
        self.assertTrue(any("caption" in w for w in check_widget("<p>x</p>").warnings))
        self.assertFalse(check_widget("<script>var API_KEY='abc'</script>", caption="c").ok)
        self.assertFalse(check_widget("<p>x</p>", caption="c", public_data='{"secret":"1"}').ok)


def query(qid, data="ship:fast", **extra):
    return {"id": qid, "from": {"id": 1}, "chat": {"id": 1, "type": "private"}, "message_id": 10,
            "chat_instance": "ci", "type": {"type": "data"}, "data": data, **extra}


def decide(q, action, record):
    if action["verb"] == "ship":
        return {**record.state, "opt": action["arg"]}, {"with_state": True}
    if action["verb"] == "deny":
        raise PermissionError
    return None, {}


class QueryFlow(unittest.TestCase):
    def setUp(self):
        self.t = FakeTransport()
        self.store = WidgetStore()
        self.store.records["msg:1:10"] = StateRecord(state={"opt": "std"})

    def answers(self):
        return [json.loads(p["data"]) for p in self.t.params_of("answerWidgetQuery")]

    def test_answer_exactly_once_including_failures(self):
        handle_widget_query(query("a"), self.store, self.t, decide)
        handle_widget_query(query("a"), self.store, self.t, decide)                 # duplicate update
        handle_widget_query(query("b", data="deny"), self.store, self.t, decide)
        handle_widget_query(query("c", data="x" * 65), self.store, self.t, decide)
        self.t.script("editMessageWidgetData", TelegramErrorResponse(400, "Bad Request: message to edit not found"))
        handle_widget_query(query("d"), self.store, self.t, decide)
        ids = [p["widget_query_id"] for p in self.t.params_of("answerWidgetQuery")]
        self.assertEqual(ids, ["a", "b", "c", "d"])

    def test_answer_does_not_replace_state_edit_and_revision_grows(self):
        handle_widget_query(query("a", data="ship:fast"), self.store, self.t, decide)
        handle_widget_query(query("b", data="ship:std"), self.store, self.t, decide)
        edits = [json.loads(p["chat_data"]) for p in self.t.params_of("editMessageWidgetData")]
        self.assertEqual([e["r"] for e in edits], [1, 2])
        self.assertEqual([a["r"] for a in self.answers()], [1, 2])
        self.assertEqual(self.t.methods(), ["editMessageWidgetData", "answerWidgetQuery"] * 2)

    def test_failed_edit_is_not_committed(self):
        self.t.script("editMessageWidgetData", TelegramErrorResponse(429, "Too Many Requests: retry after 2", 2))
        handle_widget_query(query("a"), self.store, self.t, decide)
        self.assertEqual(self.store.records["msg:1:10"].state, {"opt": "std"})
        self.assertFalse(self.answers()[0]["ok"])

    def test_not_modified_counts_as_done(self):
        self.t.script("editMessageWidgetData", TelegramErrorResponse(400, "Bad Request: message is not modified"))
        self.assertEqual(handle_widget_query(query("a"), self.store, self.t, decide), "ok")

    def test_late_answer_is_tolerated(self):
        self.t.script("answerWidgetQuery", TelegramErrorResponse(400, "Bad Request: query is too old"))
        self.assertEqual(handle_widget_query(query("a"), self.store, self.t, decide), "answered_late")

    def test_inline_and_forward_addressing(self):
        q = query("i", inline_message_id="IM1")
        del q["chat"], q["message_id"]
        self.store.records["inline:IM1"] = StateRecord(state={"opt": "std"})
        handle_widget_query(q, self.store, self.t, decide)
        self.assertEqual(self.t.params_of("editMessageWidgetData")[0]["inline_message_id"], "IM1")
        fwd = {"id": "f", "from": {"id": 2}, "widget_id": "W1", "type": {"type": "data"}, "data": "ship:fast"}
        self.store.records["shared:W1"] = StateRecord(state={"opt": "std"})
        handle_widget_query(fwd, self.store, self.t, decide)
        self.assertEqual(self.t.params_of("editSharedWidgetData")[0]["widget_id"], "W1")


class Coalescing(unittest.TestCase):
    def test_shared_edits_at_most_once_per_second(self):
        t = FakeTransport()
        w = SharedWidgetWriter(t, "W")
        for i in range(20):
            w.submit(f'{{"r":{i}}}', i * 0.1)
            w.flush(i * 0.1)
        w.flush(5.0)
        times = [i for i, (m, _) in enumerate(t.calls)]
        self.assertLessEqual(w.writes, 3)
        self.assertEqual(json.loads(t.params_of("editSharedWidgetData")[-1]["public_data"])["r"], 19)


if __name__ == "__main__":
    unittest.main()
