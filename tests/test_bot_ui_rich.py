"""Rich HTML screens in the bot-ui core and the Studio core (bot_ui/rich.py, studio/web/src/core/rich.ts)."""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _bot_ui import ROOT, STUDIO  # noqa: F401  (puts the core on sys.path)
from bot_ui import render, rich
from bot_ui.engine import parity_view, run_scenario
from bot_ui.project import open_snapshot
from bot_ui.validate import validate
from test_bot_ui_engine import require_node

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "rich_project")
CORE = os.path.join(STUDIO, "web", "src", "core")


def codes(diags) -> list[str]:
    return [d.code if hasattr(d, "code") else d["code"] for d in diags]


class Render(unittest.TestCase):
    def setUp(self):
        self.snap = open_snapshot(FIXTURE)
        self.project = self.snap.project
        self.screen = self.snap.screens["receipt.view"]
        self.values = {"order.no": "4821", "order.total": "$12.90"}

    def test_bound_buttons_become_official_buttons_with_the_action_route_and_style(self):
        lg = render.render_screen(self.project, self.screen, values=self.values)
        self.assertIn('<tg-button type="callback_data" data="receipt.view:pay" style="success">Pay $12.90</tg-button>', lg["text"])
        self.assertIn('<tg-button type="callback_data" data="receipt.view:why" style="link">Why this price?</tg-button>', lg["text"])
        self.assertNotIn("action=", lg["text"])
        ids = [b["actionId"] for b in lg["richButtons"]]
        self.assertEqual(ids, ["why", "pay", "track", None])

    def test_url_action_keeps_custom_content_and_escapes_the_url(self):
        lg = render.render_screen(self.project, self.screen, values=self.values)
        self.assertIn('<tg-button type="url" url="https://example.com/track?a=1&amp;b=2">Track &amp; trace</tg-button>', lg["text"])

    def test_request_is_send_rich_message_and_edit_uses_rich_message(self):
        lg = render.render_screen(self.project, self.screen, values=self.values)
        req = render.bot_request(lg, 1)
        self.assertEqual(req["method"], "sendRichMessage")
        self.assertEqual(set(req["params"]["rich_message"]), {"html"})
        self.assertEqual(req["params"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"], "receipt.view:back")
        edit = render.bot_request(lg, 1, edit_message_id=7)
        self.assertEqual(edit["method"], "editMessageText")
        self.assertNotIn("text", edit["params"])

    def test_placeholder_values_are_escaped_inside_attributes(self):
        lg = render.render_screen(self.project, self.screen, values={**self.values, "order.no": 'a"b<c>'})
        self.assertIn('text="a&quot;b&lt;c&gt;"', lg["text"])

    def test_link_style_is_dropped_on_url_buttons(self):
        s = copy.deepcopy(self.screen)
        s["actions"]["track"]["style"] = "link"
        lg = render.render_screen(self.project, s, values=self.values)
        track = next(b for b in lg["richButtons"] if b["actionId"] == "track")
        self.assertNotIn("style", track)

    def test_hidden_action_is_left_out_with_a_diagnostic(self):
        s = copy.deepcopy(self.screen)
        s["actions"]["why"]["hidden"] = True
        lg = render.render_screen(self.project, s, values=self.values)
        self.assertIn("RICH_BUTTON_ACTION_MISSING", codes(lg["diagnostics"]))
        self.assertNotIn("receipt.view:why", lg["text"])


class Check(unittest.TestCase):
    def test_official_examples_pass(self):
        ok = ('<p>x <tg-button type="callback_data" style="link" data="cb">cb</tg-button></p>'
              '<tg-button-row align="left"><tg-button type="url" url="https://t.me">url</tg-button>'
              '<tg-button type="copy_text" text="..">Copy</tg-button><tg-button type="disabled">Off</tg-button></tg-button-row>')
        self.assertEqual(rich.check(ok), [])

    def test_row_size_style_type_data_and_tags(self):
        nine = "<tg-button-row>" + '<tg-button type="disabled">x</tg-button>' * 9 + "</tg-button-row>"
        found = {c for c, _, _ in rich.check(nine)}
        self.assertIn("RICH_BUTTON_ROW_SIZE", found)
        found = {c for c, _, _ in rich.check('<tg-button type="url" url="https://t.me" style="link">u</tg-button>')}
        self.assertIn("RICH_BUTTON_STYLE", found)
        found = {c for c, _, _ in rich.check('<tg-button type="pay">p</tg-button>')}
        self.assertIn("RICH_BUTTON_TYPE", found)
        found = {c for c, _, _ in rich.check('<tg-button type="callback_data" data="' + "x" * 65 + '">c</tg-button>')}
        self.assertIn("RICH_BUTTON_DATA", found)
        found = {c for c, _, _ in rich.check("<marquee>no</marquee><tg-thinking>t</tg-thinking>")}
        self.assertIn("RICH_TAG_UNSUPPORTED", found)
        self.assertEqual(rich.check("<tg-thinking>t</tg-thinking>", draft=True), [])

    def test_button_row_is_not_mistaken_for_a_button(self):
        text = '<tg-button-row align="center"><tg-button action="a"></tg-button></tg-button-row>'
        self.assertEqual(rich.action_ids(text), ["a"])


class CustomEmoji(unittest.TestCase):
    def test_emoji_inside_a_button_are_the_buttons_own(self):
        html = ('<p><tg-emoji emoji-id="111">a</tg-emoji> text</p>'
                '<tg-button-row><tg-button action="pay"><tg-emoji emoji-id="222" >b</tg-emoji> Pay</tg-button>'
                '<tg-button type="url" url="https://t.me"><tg-emoji emoji-id="333">c</tg-emoji></tg-button></tg-button-row>'
                '<tg-emoji emoji-id="abc">x</tg-emoji><tg-emoji>y</tg-emoji>')
        self.assertEqual(rich.custom_emoji(html), [("111", "a", False), ("222", "b", True), ("333", "c", True)])
        self.assertEqual(rich.custom_emoji("plain <b>text</b>"), [])


class Contract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bot-ui-rich-")
        self.root = os.path.join(self.tmp, "bot-ui")
        shutil.copytree(FIXTURE, self.root)
        self.path = os.path.join(self.root, "screens", "receipt.view.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, fn):
        with open(self.path, encoding="utf-8") as fh:
            s = json.load(fh)
        fn(s)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(s, fh, ensure_ascii=False)
        return codes(validate(open_snapshot(self.root)))

    def test_fixture_is_clean(self):
        self.assertEqual([c for c in codes(validate(open_snapshot(FIXTURE)))], [])

    def test_unknown_action_media_field_and_double_placement(self):
        def broken(s):
            s["message"]["text"]["en"] += '<tg-button-row><tg-button action="nope"></tg-button></tg-button-row>'
            s["message"]["media"] = {"type": "photo", "file": {"url": "https://example.com/a.jpg"}}
            s["keyboard"]["rows"].append(["pay"])
        found = self.edit(broken)
        for code in ("RICH_BUTTON_ACTION_MISSING", "RICH_MEDIA_FIELD", "RICH_BUTTON_ON_KEYBOARD"):
            self.assertIn(code, found)

    def test_content_actions_only_on_the_keyboard_suggest_rich_buttons(self):
        def keyboard_only(s):
            for loc, text in s["message"]["text"].items():
                s["message"]["text"][loc] = re.sub(r"<tg-button-row>.*?</tg-button-row>|<tg-button\b.*?</tg-button>", "", text, flags=re.S)
            s["keyboard"]["rows"].append(["track"])  # a url action: content, not navigation
        found = self.edit(keyboard_only)
        self.assertIn("RICH_BUTTONS_UNUSED", found)
        self.assertNotIn("RICH_BUTTON_ON_KEYBOARD", found)

    def test_action_only_in_the_document_is_placed(self):
        self.assertNotIn("ACTION_NOT_PLACED", self.edit(lambda s: None))


class Engine(unittest.TestCase):
    def test_scenario_routes_presses_from_the_document(self):
        snap = open_snapshot(FIXTURE)
        result = run_scenario(snap, snap.scenarios["receipt.pay"])
        self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False)[:2000])


class Parity(unittest.TestCase):
    def test_typescript_matches_python_on_the_rich_fixture(self):
        out = subprocess.run([require_node(self), os.path.join(CORE, "parity-cli.ts"), FIXTURE], capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
        ts = json.loads(out)
        snap = open_snapshot(FIXTURE)
        for name, sc in snap.scenarios.items():
            py = parity_view(run_scenario(snap, sc))
            self.assertEqual(json.dumps(ts[name], sort_keys=True, ensure_ascii=False),
                             json.dumps(py, sort_keys=True, ensure_ascii=False))
            self.assertIn('{"actionId": "pay", "text": "Pay $12.90"}', json.dumps(ts[name], ensure_ascii=False))



EDGE_CASES = [
    '<tg-button type="copy_text" text="a > b">Copy</tg-button>',
    "<tg-button action='pay'></tg-button>",
    '<p>x &#1114112; &mdash; &#x41; &amp;</p><tg-button action="pay">Go &gt;</tg-button>',
    '<TG-BUTTON action="pay"></TG-BUTTON><tg-button-row align="right"><tg-button action="why"></tg-button></tg-button-row>',
    '<a href="{u}">x</a><tg-button type="url" url="https://t.me/?q=1&amp;b=2">u</tg-button>',
]
ACTIONS = {"pay": {"type": "navigate", "label": "Pay {t}", "style": "success"}, "why": {"type": "answer", "label": "Why", "style": "link"}}


class EdgeParity(unittest.TestCase):
    """The review's parser cases: quoted '>', single quotes, entities, case, rows; Python == TypeScript."""

    def test_compile_and_visible_text_match(self):
        script = ("import {compileRichButtons, richVisibleText, richEscape} from " + json.dumps("file:///" + os.path.join(CORE, "rich.ts").replace("\\", "/")) + ";"
                  "const cases = JSON.parse(process.argv[1]); const acts = JSON.parse(process.argv[2]);"
                  "const out = cases.map((t) => { const [h, b, d] = compileRichButtons(t, acts, (a, id) => a.label.replace('{t}', '$1'), (id) => 's:' + id);"
                  "return {h, b, d: d.map((x) => x.code), v: richVisibleText(h)}; });"
                  "out.push({esc: richEscape(\"Bob's <b> & \\\"q\\\"\")}); process.stdout.write(JSON.stringify(out));")
        ts = json.loads(subprocess.run([require_node(self), "--input-type=module", "-e", script, json.dumps(EDGE_CASES), json.dumps(ACTIONS)],
                                       capture_output=True, text=True, encoding="utf-8", check=True).stdout)
        py = []
        for t in EDGE_CASES:
            h, b, d = rich.compile_buttons(t, "s", ACTIONS, lambda a, i: a["label"].replace("{t}", "$1"), lambda i, a: "s:" + i)
            py.append({"h": h, "b": b, "d": [x["code"] for x in d], "v": rich.visible_text(h)})
        py.append({"esc": rich.escape("Bob's <b> & \"q\"")})
        self.assertEqual(json.dumps(ts, sort_keys=True, ensure_ascii=False), json.dumps(py, sort_keys=True, ensure_ascii=False))
        self.assertIn('text="a > b"', py[0]["h"])
        self.assertIn('data="s:pay"', py[1]["h"])
        self.assertIn("&#1114112;", py[2]["v"])
        self.assertEqual(py[-1]["esc"], "Bob&#39;s &lt;b&gt; &amp; &quot;q&quot;")


class EngineEdges(unittest.TestCase):
    """A rich screen with no keyboard is active; a press is checked against the shown locale."""

    def _snap(self, text: dict, keyboard: dict | None):
        snap = open_snapshot(FIXTURE)
        s = copy.deepcopy(snap.screens["receipt.view"])
        s["message"]["text"] = text
        if keyboard is None:
            s.pop("keyboard", None)
        snap.screens["receipt.view"] = s
        return snap

    def test_no_keyboard_document_buttons_work_on_first_press(self):
        snap = self._snap({"en": '<p>x</p><tg-button action="pay"></tg-button>', "ru": '<p>x</p><tg-button action="pay"></tg-button>'}, None)
        sc = {"scenarioId": "t", "locale": "en", "context": {"chat": "private"}, "data": {"order.total": "$1"},
              "steps": [{"command": "start"}, {"press": "pay"}, {"expect": {"screen": "receipt.paid"}}]}
        self.assertTrue(run_scenario(snap, sc)["ok"])

    def test_a_button_only_in_another_locale_is_stale(self):
        snap = self._snap({"en": "<p>no buttons</p>", "ru": '<p>x</p><tg-button action="pay"></tg-button>'}, {"type": "inline", "rows": [["back"]]})
        sc = {"scenarioId": "t", "locale": "en", "context": {"chat": "private"}, "data": {"order.total": "$1"},
              "steps": [{"command": "start"}, {"press": "pay"}, {"expect": {"screen": "receipt.view"}}]}
        r = run_scenario(snap, sc)
        self.assertTrue(r["ok"])
        self.assertTrue(any(t.get("action", {}) and t["action"].get("type") == "stale" for t in r["trace"]))


class EngineEdgeParity(unittest.TestCase):
    """The review's engine cases through both engines: a rich screen with keyboard 'none', and a Pay that
    exists only in the other language's document. The TypeScript engine must answer like the Python one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bot-ui-rich-parity-")
        self.root = os.path.join(self.tmp, "bot-ui")
        shutil.copytree(FIXTURE, self.root)
        os.remove(os.path.join(self.root, "scenarios", "receipt.pay.json"))
        self.path = os.path.join(self.root, "screens", "receipt.view.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _screen(self, text: dict, keyboard):
        with open(self.path, encoding="utf-8") as fh:
            s = json.load(fh)
        s["message"]["text"] = text
        if keyboard is None:
            s.pop("keyboard")
        else:
            s["keyboard"] = keyboard
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(s, fh, ensure_ascii=False)

    def _scenario(self, name, press_then):
        sc = {"scenarioId": name, "locale": "en", "context": {"chat": "private"}, "data": {"order.total": "$1"},
              "steps": [{"command": "start"}, {"press": "pay"}, press_then]}
        with open(os.path.join(self.root, "scenarios", name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(sc, fh)

    def _both(self):
        ts = json.loads(subprocess.run([require_node(self), os.path.join(CORE, "parity-cli.ts"), self.root], capture_output=True,
                                       text=True, encoding="utf-8", check=True).stdout)
        snap = open_snapshot(self.root)
        py = {name: run_scenario(snap, sc) for name, sc in snap.scenarios.items()}
        for name in py:
            self.assertEqual(json.dumps(ts[name], sort_keys=True, ensure_ascii=False),
                             json.dumps(parity_view(py[name]), sort_keys=True, ensure_ascii=False), name)
        return py

    def test_no_keyboard_and_other_locale_press(self):
        pay = '<p>x</p><tg-button action="pay"></tg-button>'
        self._screen({"en": pay, "ru": pay}, None)
        self._scenario("nokb", {"expect": {"screen": "receipt.paid"}})
        py = self._both()
        self.assertTrue(py["nokb"]["ok"])
        self.assertFalse(any((t.get("action") or {}).get("type") == "stale" for t in py["nokb"]["trace"]))
        self._screen({"en": "<p>no buttons</p>", "ru": pay}, {"type": "inline", "rows": [["back"]]})
        os.remove(os.path.join(self.root, "scenarios", "nokb.json"))
        self._scenario("otherlocale", {"expect": {"screen": "receipt.view"}})
        py = self._both()
        self.assertTrue(any((t.get("action") or {}).get("type") == "stale" for t in py["otherlocale"]["trace"]))



class CheckParity(unittest.TestCase):
    """The Studio lints Rich HTML with the same codes as the Python validator (offline artifact edits)."""

    CASES = [
        "<tg-button-row>" + '<tg-button type="disabled">x</tg-button>' * 9 + "</tg-button-row>",
        '<tg-button type="url" url="https://t.me" style="link">u</tg-button>',
        '<tg-button type="pay">p</tg-button><marquee>m</marquee>',
        '<tg-button type="callback_data" data="' + "x" * 65 + '">c</tg-button>',
        '<tg-button type="url">no url</tg-button><tg-button type="copy_text" text="a > b"></tg-button>',
        '<p>ok <tg-button action="pay"></tg-button></p>',
    ]

    def test_same_codes(self):
        script = ("import {richCheck} from " + json.dumps("file:///" + os.path.join(CORE, "rich.ts").replace("\\", "/")) + ";"
                  "const c = JSON.parse(process.argv[1]); process.stdout.write(JSON.stringify(c.map((t) => richCheck(t).map((x) => x[0]))));")
        ts = json.loads(subprocess.run([require_node(self), "--input-type=module", "-e", script, json.dumps(self.CASES)],
                                       capture_output=True, text=True, encoding="utf-8", check=True).stdout)
        py = [[c for c, _, _ in rich.check(t)] for t in self.CASES]
        self.assertEqual(ts, py)
        self.assertEqual(py[-1], [])


if __name__ == "__main__":
    unittest.main()
