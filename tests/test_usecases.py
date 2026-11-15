"""Use-case cookbook (recipes 20-29, 60-69): every recipe runs offline, every
payload passes the repo validators, copy resolves in every sample language, the
payload files match the code, and the shared flow guards hold.

Regenerate payload files:  py -3 tests/test_usecases.py --write-payloads
"""
import contextlib
import glob
import importlib
import io
import os
import re
import sys
import unittest

import _paths

import audit_copy
import validate_keyboard
import validate_rich
from tgkit import flows as f
from tgkit.transport import FakeTransport

RECIPE_DIR = os.path.join(_paths.EXAMPLES, "python", "recipes")
MODULES = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(RECIPE_DIR, "r[26][0-9]_*.py")))


def load(name):
    with contextlib.redirect_stdout(io.StringIO()):
        return importlib.import_module(name)


def scenario(mod):
    with contextlib.redirect_stdout(io.StringIO()):
        return mod.run()[0]


def context_of(params):
    if "ephemeral_message_parameters" in params:
        return "ephemeral"
    if "business_connection_id" in params:
        return "business"
    return None


def wire_markups(t):
    """(method, context, markup-or-rich) for everything a scenario sent."""
    for method, params in t.calls:
        ctx = context_of(params)
        if "reply_markup" in params:
            yield method, ctx, params["reply_markup"], params
        if "rich_message" in params:
            yield method, ctx, {"rich_message": params["rich_message"]}, params
        for r in params.get("results") or []:
            if "reply_markup" in r:
                yield method, ctx, r["reply_markup"], r


class EveryRecipe(unittest.TestCase):
    def test_there_are_at_least_fourteen(self):
        self.assertGreaterEqual(len(MODULES), 14, MODULES)

    def test_runs_and_checks_itself(self):
        for name in MODULES:
            with self.subTest(recipe=name), contextlib.redirect_stdout(io.StringIO()):
                load(name).main()

    def test_payloads_pass_the_validators(self):
        for name in MODULES:
            t = scenario(load(name))
            for i, (method, ctx, doc, params) in enumerate(wire_markups(t)):
                with self.subTest(recipe=name, call=i, method=method):
                    if "rich_message" in doc:
                        errors, _, _ = validate_rich.validate(doc, draft=method.endswith("Draft"))
                    else:
                        errors = validate_keyboard.validate(doc, context=ctx).errors
                    self.assertEqual(errors, [], doc)

    def test_callback_data_within_64_bytes(self):
        for name in MODULES:
            t = scenario(load(name))
            for _, _, doc, _ in wire_markups(t):
                for b in f.callback_buttons(doc):
                    if "callback_data" in b:
                        with self.subTest(recipe=name, data=b["callback_data"]):
                            self.assertLessEqual(len(b["callback_data"].encode("utf-8")), 64)

    def test_copy_resolves_in_every_language(self):
        for name in MODULES:
            mod = load(name)
            with self.subTest(recipe=name):
                self.assertTrue(hasattr(mod, "COPY"), "recipe needs a COPY catalog")
                self.assertGreaterEqual(len(mod.COPY), 2, "at least two sample languages")
                self.assertEqual(f.I18n(mod.COPY).missing(), {})
                errors, _ = audit_copy.audit(mod.COPY)
                self.assertEqual(errors, [])

    def test_payload_files_match_the_code(self):
        for name in MODULES:
            mod = load(name)
            with self.subTest(recipe=name):
                path = f.payload_path(mod.PAYLOAD)
                self.assertTrue(os.path.exists(path), f"run: py -3 tests/test_usecases.py --write-payloads")
                with open(path, encoding="utf-8") as fh:
                    on_disk = fh.read()
                doc = f.payload_doc(mod.PAYLOAD, scenario(mod), status=mod.STATUS, context=mod.CONTEXT)
                self.assertEqual(on_disk, f.payload_text(doc), "payload drifted from the code")

    def test_doc_follows_the_ten_point_format(self):
        for name in MODULES:
            num = name[1:3]
            docs = glob.glob(os.path.join(_paths.ROOT, "recipes", f"{num}-*.md"))
            with self.subTest(recipe=name):
                self.assertEqual(len(docs), 1, f"recipes/{num}-*.md")
                body = open(docs[0], encoding="utf-8").read()
                for n in range(1, 11):
                    self.assertRegex(body, rf"(?m)^{n}\. \*\*", f"{docs[0]} misses point {n}")
                self.assertIn(f"examples/python/recipes/{name}.py", body)
                self.assertIn(f"examples/payloads/{load(name).PAYLOAD}.json", body)

    def test_no_secrets_and_no_personal_paths(self):
        token = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")
        for name in MODULES:
            src = open(os.path.join(RECIPE_DIR, name + ".py"), encoding="utf-8").read()
            with self.subTest(recipe=name):
                self.assertIsNone(token.search(src))
                self.assertNotRegex(src, r"(?i)c:\\\\users|/home/")


class Callbacks(unittest.TestCase):
    def test_pack_counts_bytes_not_characters(self):
        self.assertEqual(f.pack("a", "b"), "a:b")
        cyr = "п" * 31                      # 62 bytes in UTF-8
        self.assertEqual(len(f.pack("x", cyr).encode()), 64)
        with self.assertRaises(f.CallbackTooLong):
            f.pack("xy", cyr)               # 65 bytes although only 34 characters
        with self.assertRaises(ValueError):
            f.pack("a:b")

    def test_disabled_button_has_no_other_action(self):
        b = f.btn("Sold out", "x", disabled=True)
        self.assertEqual(b, {"text": "Sold out", "disabled": {}})


def tiny_flow():
    t = FakeTransport()
    fl = f.ScreenFlow(t, "tf")

    @fl.screen("a")
    def a(fl, s):
        return {"text": f"A {s.data.get('n', 0)}", "reply_markup": f.kb([f.btn("+", fl.cb(s, "inc")),
                                                                            f.btn("B", fl.cb(s, "b"))])}

    @fl.screen("b")
    def b(fl, s):
        return {"text": "B", "reply_markup": f.kb([f.btn("Back", fl.cb(s, "back"))])}

    @fl.action("inc")
    def inc(fl, s, args, cq):
        s.data["n"] = s.data.get("n", 0) + 1
        fl.refresh(s)

    @fl.action("b")
    def go_b(fl, s, args, cq):
        fl.go(s, "b")

    @fl.action("back")
    def back(fl, s, args, cq):
        fl.back(s)
    return t, fl


class Guards(unittest.TestCase):
    def setUp(self):
        self.t, self.fl = tiny_flow()
        self.s = self.fl.session(-100, 1)
        self.fl.open(self.s, "a")

    def cq(self, uid, data, qid="q"):
        return f.callback(qid, f.user(uid), data, chat_id=-100, message_id=self.s.message_id, chat_type="supergroup")

    def test_stale_and_duplicate_taps_are_rejected(self):
        data = self.fl.cb(self.s, "inc")
        self.assertEqual(self.fl.handle(self.cq(1, data, "q1")), "ok")
        self.assertEqual(self.fl.handle(self.cq(1, data, "q2")), "stale")     # same button again
        self.assertEqual(self.s.data["n"], 1)

    def test_one_user_cannot_act_on_another_users_menu(self):
        self.assertEqual(self.fl.handle(self.cq(2, self.fl.cb(self.s, "inc"))), "not_yours")
        self.assertNotIn("n", self.s.data)

    def test_back_restores_the_previous_screen(self):
        self.fl.handle(self.cq(1, self.fl.cb(self.s, "b"), "q1"))
        self.assertEqual(self.s.screen, "b")
        self.fl.handle(self.cq(1, self.fl.cb(self.s, "back"), "q2"))
        self.assertEqual(self.s.screen, "a")

    def test_every_query_answered_exactly_once(self):
        for i, data in enumerate([self.fl.cb(self.s, "inc"), "tf:zz:inc", "tf:0:nope"]):
            self.fl.handle(self.cq(1, data, f"q{i}"))
        ids = [p["callback_query_id"] for p in self.t.params_of("answerCallbackQuery")]
        self.assertEqual(sorted(ids), ["q0", "q1", "q2"])

    def test_foreign_callbacks_are_left_alone(self):
        self.assertEqual(self.fl.handle(self.cq(1, "other:1:x")), "foreign")
        self.assertEqual(self.t.params_of("answerCallbackQuery"), [])


class Primitives(unittest.TestCase):
    def test_once_store_runs_once(self):
        store, calls = f.OnceStore(), []
        r1 = store.run("order-7", lambda: calls.append(1) or "ORD-7")
        r2 = store.run("order-7", lambda: calls.append(1) or "ORD-8")
        self.assertEqual((r1, r2, calls), (("ORD-7", True), ("ORD-7", False), [1]))

    def test_update_dedup(self):
        d = f.UpdateDedup()
        self.assertTrue(d.first_time({"update_id": 5}))
        self.assertFalse(d.first_time({"update_id": 5}))

    def test_machine_refuses_illegal_transitions(self):
        m = f.Machine({"new": {"pay": "paid"}, "paid": {"ship": "shipped"}}, "new")
        self.assertEqual(m.next("new", "pay"), "paid")
        with self.assertRaises(f.IllegalTransition):
            m.next("shipped", "pay")

    def test_paginate_clamps(self):
        self.assertEqual(f.paginate(list(range(7)), 9, 3), ([6], 2, 3))
        self.assertEqual(f.paginate([], 0, 3), ([], 0, 1))

    def test_scheduler_replaces_by_key(self):
        s = f.Scheduler()
        s.at(10, "bk:1:remind", n=1)
        s.at(20, "bk:1:remind", n=2)
        self.assertEqual([j.payload["n"] for j in s.due(30)], [2])
        s.at(5, "bk:2:a")
        self.assertEqual(s.cancel("bk:2"), 1)

    def test_i18n_escapes_values_and_reports_missing_keys(self):
        i = f.I18n({"en": {"hi": "<b>{name}</b>", "x": "1"}, "uk": {"hi": "<b>{name}</b>"}})
        self.assertEqual(i.t("uk", "hi", name="<script>"), "<b>&lt;script&gt;</b>")
        self.assertEqual(i.missing(), {"uk": ["x"]})
        self.assertEqual(i.t("uk", "x"), "1")          # falls back to the default language
        self.assertEqual(i.lang_for("uk-UA"), "uk")
        self.assertEqual(i.lang_for("pt"), "en")


def write_payloads():
    for name in MODULES:
        mod = load(name)
        doc = f.payload_doc(mod.PAYLOAD, scenario(mod), status=mod.STATUS, context=mod.CONTEXT)
        print(f.write_payload(doc))


if __name__ == "__main__":
    if "--write-payloads" in sys.argv:
        write_payloads()
    else:
        unittest.main()
