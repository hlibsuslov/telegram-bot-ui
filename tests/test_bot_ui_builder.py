"""bot-ui visual widget builder (builder/v1): schema, validation, generator, preview, eject, Studio hooks.

Behaviour of the generated JavaScript is checked by running the built widget in Node against a
small DOM and TelegramWidget stand-in (skipped without Node); everything else is static.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import unittest

from _bot_ui import ProjectCase
from bot_ui import builder, widgets
from bot_ui.project import open_snapshot, parse_files
from bot_ui.skill import kit_dir, load
from bot_ui.store import write_patch

LANGS = ("en", "ru", "uk")
BUDGET = 3800  # widget_lint working budget; the hard limit is 4096 zlib-9 bytes
NODE = shutil.which("node")

# A DOM with only the elements the markup declares (by id), and a TelegramWidget that records
# requests, links and copies and answers from `answers` (data -> result object).
HARNESS = r"""
const inp = JSON.parse(require("fs").readFileSync(0, "utf8"));
const ids = new Set([...inp.html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]));
function El(tag, id) {
  return { tagName: tag, id: id || "", className: "", textContent: "", style: {}, disabled: false, onclick: null,
    children: [], _h: "", appendChild(c) { this.children.push(c); return c; },
    set innerHTML(v) { this.children = []; this._h = v; }, get innerHTML() { return this._h; } };
}
const els = {};
const document = { documentElement: { dir: "" }, createElement: t => El(t),
  getElementById: i => ids.has(i) ? (els[i] = els[i] || El("x", i)) : null };
const log = { requests: [], links: [], copies: [] };
let now = inp.now * 1000;
Date.now = () => now;
const timers = [];
global.setInterval = f => (timers.push(f), timers.length);
global.clearInterval = n => { timers[n - 1] = null; };
const ev = {};
const TW = inp.telegram ? {
  viewer: { id: 1 }, isPreview: false, isForward: false, chatType: "private",
  chatData: inp.chatData ? JSON.stringify(inp.chatData) : null, publicData: null,
  HapticFeedback: { notificationOccurred() {} },
  onEvent(t, f) { (ev[t] = ev[t] || []).push(f); }, ready() {},
  openLink(u) { log.links.push(u); }, copyText(t) { log.copies.push(t); },
  request(d) { log.requests.push(d); const r = inp.answers[d] || { ok: true }; return Promise.resolve({ result: JSON.stringify(r) }); },
} : undefined;
global.window = { TelegramWidget: TW };
global.navigator = { language: inp.lang };
global.document = document;
const code = [...inp.html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join("\n;\n");
(0, eval)(code);
const flush = () => new Promise(r => setTimeout(r, 0));
const snap = () => { const o = {}; for (const [k, e] of Object.entries(els))
  o[k] = { text: e.textContent, display: e.style.display || "", disabled: !!e.disabled, cls: e.className,
           width: e.style.width || "", kids: e.children.map(c => c.textContent) }; return o; };
(async () => {
  const steps = [];
  for (const s of inp.steps) {
    if (s[0] === "click") els[s[1]].onclick();
    if (s[0] === "child") els[s[1]].children[s[2]].onclick();
    if (s[0] === "time") { now = s[1] * 1000; timers.forEach(f => f && f()); }
    await flush(); await flush();
    steps.push(snap());
  }
  process.stdout.write(JSON.stringify({ first: steps.length ? null : snap(), steps, log, final: snap() }));
})();
"""


def build_cfg(cfg: dict, lang: str = "en", **kw) -> object:
    bw = load("build_widget")
    return bw.build_text(builder.generate(cfg, lang, **kw), caption="x", strict=True, kit_dir=kit_dir(), langs=(lang,))


def cfg_of(type_: str, preset: str = "telegram", **content) -> dict:
    cfg = builder.default_config(type_, list(LANGS), now=1794736800)
    cfg["style"]["preset"] = preset
    cfg["content"].update(content)
    return cfg


def run(html: str, steps=(), *, chat=None, answers=None, now: int = 1794736800, lang: str = "en", telegram=True) -> dict:
    inp = {"html": html, "steps": list(steps), "chatData": chat, "answers": answers or {}, "now": now,
           "lang": lang, "telegram": telegram}
    p = subprocess.run([NODE, "-e", HARNESS], input=json.dumps(inp), capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    if p.returncode:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


def codes(diags: list[dict]) -> set[tuple[str, str]]:
    return {(d["pointer"], d["code"]) for d in diags}


class Generator(unittest.TestCase):
    def test_every_type_builds_strictly_in_every_language_with_margin(self):
        sizes = {}
        for t in builder.TYPES:
            cfg = cfg_of(t)
            self.assertEqual(builder.validate_config(cfg), [], t)
            for lang in LANGS:
                r = build_cfg(cfg, lang)
                self.assertTrue(r.ok, (t, lang, r.errors))
                self.assertLessEqual(r.compressed_bytes, BUDGET - 300, (t, lang))
                self.assertLessEqual(r.raw_bytes, 32768)
                sizes[f"{t}/{lang}"] = r.compressed_bytes
        self.assertEqual(len(sizes), 15)

    def test_each_preset_builds_for_every_type(self):
        for preset in builder.PRESET_IDS:
            for t in builder.TYPES:
                for lang in ("en", "ru"):
                    r = build_cfg(cfg_of(t, preset), lang)
                    self.assertTrue(r.ok, (preset, t, lang, r.errors))
                    self.assertLessEqual(r.compressed_bytes, BUDGET)
        css = builder.generate(cfg_of("message", "soft"), "en")
        self.assertIn("border-radius:22px", css)
        self.assertIn("@keyframes fa", css)  # soft is lively
        self.assertNotIn("@keyframes", builder.generate(cfg_of("message", "telegram"), "en"))

    def test_custom_style_per_theme_and_shared_colours(self):
        cfg = cfg_of("product")
        cfg["style"] = {"preset": None, "custom": {"block": {"fill": True, "radius": 6}, "animation": "calm"},
                        "palette": "per-theme",
                        "colors": {"light": {"bg": "#ffffff", "button": "#112233"}, "dark": {"bg": "#000000", "text": None}}}
        src = builder.generate(cfg, "en")
        self.assertIn("--c-bg:light-dark(#ffffff,#000000)", src)
        self.assertIn("--c-button:light-dark(#112233,var(--k-btn))", src)  # dark slot null = Telegram theme
        self.assertIn("--c-text:var(--k-tx)", src)
        self.assertIn("border-radius:6px", src)
        self.assertTrue(build_cfg(cfg).ok)
        cfg["style"]["palette"] = "shared"
        self.assertIn("--c-bg:light-dark(#ffffff,#ffffff)", builder.generate(cfg, "en"))
        cfg["style"]["preset"] = "telegram"  # a preset wins; custom is kept, colours come from the preset
        self.assertIn("--c-bg:transparent", builder.generate(cfg, "en"))
        self.assertEqual(cfg["style"]["custom"]["block"]["radius"], 6)
        contrast = builder.generate(cfg_of("message", "contrast"), "en")
        self.assertIn("--c-text:light-dark(#000000,#ffffff)", contrast)
        bad = copy.deepcopy(cfg)
        bad["style"]["colors"] = {"light": {"bg": "red", "digits": "#fff"}}
        self.assertEqual(codes(builder.validate_config(bad)), {("/style/colors/light/bg", "COLOR_INVALID"),
                                                              ("/style/colors/light/digits", "COLOR_SLOT_UNKNOWN")})

    def test_empty_optional_blocks_and_hidden_blocks_are_not_emitted(self):
        msg = builder.generate(cfg_of("message"), "en")
        self.assertNotIn('id="ft"', msg)  # empty footnote
        self.assertNotIn('class="im"', msg)  # no picture
        self.assertNotIn('".f{', msg)
        promo = cfg_of("promo")
        promo["content"]["button"]["label"] = {"en": "", "ru": ""}
        self.assertNotIn('id="go"', builder.generate(promo, "en"))
        prod = cfg_of("product")
        prod["content"]["show"]["footnote"] = False
        prod["content"]["show"]["discount"] = False
        prod["content"]["footnote"]["en"] = "x" * 900  # hidden: kept, not checked, not emitted
        src = builder.generate(prod, "en")
        self.assertNotIn('id="ft"', src)
        self.assertNotIn("<s>", src)
        self.assertEqual(prod["content"]["footnote"]["en"], "x" * 900)
        self.assertEqual(builder.validate_config(prod), [])
        self.assertTrue(build_cfg(prod).ok)

    def test_limits_give_diagnostics_with_pointers(self):
        cfg = cfg_of("message", title={"en": "t" * 81, "ru": "ok"})
        cfg["content"]["button"]["action"]["data"] = "d" * 65
        self.assertEqual(codes(builder.validate_config(cfg)), {("/content/title/en", "TOO_LONG"),
                                                              ("/content/button/action/data", "DATA_TOO_LONG")})
        cfg = cfg_of("countdown")
        cfg["content"]["button"]["action"] = {"kind": "link", "url": "http://example.com/sale"}
        self.assertEqual(codes(builder.validate_config(cfg)), {("/content/button/action/url", "URL_INVALID")})
        cfg["content"]["button"]["label"] = {}  # no button: its action is not checked
        self.assertEqual(builder.validate_config(cfg), [])
        prod = cfg_of("product", quantityMax=99)
        prod["content"]["button"]["action"]["data"] = "add:" + "x" * 59 + ":{n}"
        self.assertIn(("/content/button/action/data", "DATA_TOO_LONG"), codes(builder.validate_config(prod)))
        quiz = cfg_of("quiz")
        quiz["content"]["questions"][0]["answers"][0]["id"] = "a" * 16
        quiz["content"]["button"]["action"]["data"] = "q" * 45
        self.assertIn(("/content/button/action/data", "DATA_TOO_LONG"), codes(builder.validate_config(quiz)))
        quiz["content"]["questions"][1]["answers"][0]["id"] = "a2"
        self.assertIn(("/content/questions/1/answers/0/id", "ID_DUPLICATE"), codes(builder.validate_config(quiz)))
        self.assertIn(("/type", "TYPE_UNKNOWN"), codes(builder.validate_config({"type": "poll"})))
        text = cfg_of("message", text={"en": "Forgot your password?"})
        self.assertIn(("/content/text/en", "TEXT_REFUSED"), codes(builder.validate_config(text)))

    def test_product_discount_strikes_the_old_price(self):
        src = builder.generate(cfg_of("product"), "en")
        self.assertIn('<p class="pr"><b>€14.90</b><s>€18.50</s></p>', src)
        self.assertIn('<b>€18.50</b>', builder.generate(cfg_of("product", price=""), "en"))  # no new price: not struck

    def test_promo_on_tap_code_is_not_in_the_html(self):
        cfg = cfg_of("promo")
        for lang in LANGS:
            r = build_cfg(cfg, lang)
            self.assertTrue(r.ok)
            self.assertNotIn("SPRING20", r.html)
        cfg["content"]["reveal"] = "now"
        self.assertIn("SPRING20", build_cfg(cfg).html)

    def test_quiz_ids_are_stable_when_questions_move(self):
        cfg = cfg_of("quiz")
        src = builder.generate(cfg, "en")
        self.assertIn('var Q=[["a1","a2","a3"],["a4","a5","a6"],["a7","a8","a9"]]', src)
        cfg["content"]["questions"].reverse()
        self.assertIn('var Q=[["a7","a8","a9"],["a4","a5","a6"],["a1","a2","a3"]]', builder.generate(cfg, "en"))
        self.assertEqual(builder.validate_config(cfg), [])

    def test_mock_answers_shape(self):
        prod = builder.mock_answers(cfg_of("product"))
        self.assertEqual(set(prod), {"default", "tapped"})
        self.assertEqual(sorted(prod["default"], key=lambda d: int(d.split(":")[1])), [f"add:{n}" for n in range(1, 11)])
        ans = prod["default"]["add:3"]
        self.assertEqual(json.loads(ans["result"]), {"ok": True, "s": {"n": 3, "r": 2}})
        self.assertEqual(ans["pushes"], [{"field": "chatData", "text": '{"n":3,"r":2}'}])
        promo = builder.mock_answers(cfg_of("promo"))
        self.assertEqual(set(promo), {"closed", "revealed", "copied"})
        self.assertEqual(json.loads(promo["closed"]["promo"]["result"])["c"], "SPRING20")
        quiz = builder.mock_answers(cfg_of("quiz"))
        self.assertEqual(set(quiz), {"q1", "q2", "q3", "result"})
        self.assertEqual(len(quiz["q1"]), 27)
        self.assertIn("quiz:a1.a5.a9", quiz["result"])
        msg = builder.mock_answers(cfg_of("message"))
        self.assertEqual(msg["default"]["tour"], {"pushes": [], "result": '{"ok":true}'})
        self.assertEqual(builder.mock_answers(cfg_of("countdown")), {"running": {}, "finished": {}})

    def test_schema_shape(self):
        s = builder.schema(["en", "ru"])
        self.assertEqual(list(s["types"]), list(builder.TYPES))
        for t, d in s["types"].items():
            self.assertTrue(d["sections"] and d["states"] and d["defaults"] and d["icon"], t)
        self.assertEqual([p["id"] for p in s["style"]["presets"]], ["telegram", "card", "soft", "contrast"])
        self.assertTrue(all(set(p["values"]["colors"]) == {"light", "dark"} for p in s["style"]["presets"]))
        self.assertEqual(set(s["types"]["product"]["defaults"]["name"]), {"en", "ru"})
        self.assertIn("quiz", s["style"]["colorSlots"])


@unittest.skipUnless(NODE, "node is not installed")
class Behaviour(unittest.TestCase):
    def test_product_quantity_substitutes_n_in_data_and_done_text(self):
        html = build_cfg(cfg_of("product")).html
        out = run(html, [["click", "pl"], ["click", "pl"], ["click", "go"]], answers={"add:3": {"ok": True, "s": {"n": 3, "r": 2}}})
        self.assertEqual(out["log"]["requests"], ["add:3"])
        self.assertEqual(out["final"]["st"]["text"], "Added 3 to the cart")
        self.assertEqual(str(out["steps"][0]["q"]["text"]), "2")
        self.assertEqual(out["final"]["nm"]["text"], "Coffee beans, 250 g")
        ru = run(build_cfg(cfg_of("product"), "ru").html, [["click", "go"]], lang="ru")
        self.assertEqual(ru["final"]["st"]["text"], "В корзине: 1 шт.")
        outside = run(html, telegram=False)  # outside Telegram: drawn, nothing asks
        self.assertTrue(outside["final"]["go"]["disabled"])

    def test_promo_reveals_from_the_answer_then_copies(self):
        html = build_cfg(cfg_of("promo")).html
        out = run(html, [["click", "cp"], ["click", "cp"]],
                  answers={"promo": {"ok": True, "s": {"c": "SPRING20", "r": 2}, "c": "SPRING20"}})
        self.assertEqual(out["steps"][0]["cp"]["text"], "SPRING20")
        self.assertEqual(out["log"]["requests"], ["promo"])
        self.assertEqual(out["log"]["copies"], ["SPRING20"])
        self.assertEqual(out["final"]["st"]["text"], "Copied")
        closed = run(html)
        self.assertEqual(closed["final"]["cp"]["text"], "Tap to reveal")
        run(html, [["click", "go"]])  # the link button opens its page
        self.assertEqual(run(html, [["click", "go"]])["log"]["links"], ["https://example.com/shop"])

    def test_countdown_running_then_finished(self):
        cfg = cfg_of("countdown")
        deadline = cfg["content"]["deadline"]
        html = build_cfg(cfg).html
        out = run(html, [["time", deadline + 5]], now=deadline - (86400 + 3600 + 61))
        first = out["steps"][0]  # snapshot after the deadline passed
        running = run(html, now=deadline - (86400 + 3600 + 61))["final"]
        self.assertEqual([running[f"v{i}"]["text"] for i in range(4)], ["01", "01", "01", "01"])
        self.assertEqual((running["cd"]["display"], running["fn"]["display"], running["go"]["display"]), ("", "none", ""))
        self.assertEqual((first["cd"]["display"], first["fn"]["display"], first["go"]["display"]), ("none", "", "none"))
        self.assertEqual(first["fn"]["text"], "The sale is over. See you at the next one!")
        # The preview "finished" state works whatever the author's deadline is.
        fin = build_cfg(cfg, state="finished").html
        self.assertEqual(run(fin, now=deadline - 86400)["final"]["fn"]["display"], "")

    def test_quiz_one_question_per_screen_then_sends_answer_ids_and_plays_again(self):
        html = build_cfg(cfg_of("quiz")).html
        steps = [["child", "an", 0], ["child", "an", 1], ["child", "an", 2], ["click", "go"], ["click", "ag"]]
        out = run(html, steps, answers={"quiz:a1.a5.a9": {"ok": True, "s": {"a": "a1.a5.a9", "r": 2}}})
        self.assertEqual(out["steps"][0]["qn"]["text"], "Question 2 of 3")
        self.assertEqual(out["steps"][0]["an"]["kids"], ["Morning", "After lunch", "Late at night"])
        self.assertEqual(out["steps"][2]["qz"]["display"], "none")
        self.assertEqual(out["steps"][2]["rs"]["display"], "")
        self.assertEqual(out["log"]["requests"], ["quiz:a1.a5.a9"])
        self.assertEqual(out["steps"][3]["st"]["text"], "Sent! Your match is in the chat.")
        self.assertEqual((out["final"]["qz"]["display"], out["final"]["qn"]["text"]), ("", "Question 1 of 3"))
        q2 = run(build_cfg(cfg_of("quiz"), state="q2").html, [["child", "an", 0], ["child", "an", 0], ["click", "go"]])
        self.assertEqual(q2["steps"][0]["qn"]["text"], "Question 3 of 3")
        self.assertEqual(q2["log"]["requests"], ["quiz:a1.a4.a7"])

    def test_message_request_and_copy_action(self):
        html = build_cfg(cfg_of("message")).html
        out = run(html, [["click", "go"]])
        self.assertEqual((out["log"]["requests"], out["final"]["st"]["text"]), (["tour"], "Sent, check the chat"))
        cfg = cfg_of("message")
        cfg["content"]["button"]["action"] = {"kind": "copy", "text": {"en": "WELCOME"}}
        self.assertEqual(run(build_cfg(cfg).html, [["click", "go"]])["log"]["copies"], ["WELCOME"])


class Studio(ProjectCase):
    def create(self, wid: str, template: str):
        return write_patch(self.root, widgets.creation_patch(open_snapshot(self.root), wid, template))

    def test_templates_list_builder_types_right_after_blank(self):
        t = widgets.templates()
        self.assertEqual([x["id"] for x in t[:6]], ["blank"] + [f"builder:{k}" for k in builder.TYPES])
        self.assertTrue(all(x["source"] == "builder" and x["icon"] and x["title"] and x["summary"] for x in t[1:6]))
        self.assertTrue(widgets.template_preview(open_snapshot(self.root), "builder:quiz", "ru")["ok"])

    def test_creation_and_build_round_trip(self):
        for t in builder.TYPES:
            res = self.create(f"b-{t}", f"builder:{t}")
            self.assertEqual(sorted(res.changed_files), [f"widgets/b-{t}/index.html", f"widgets/b-{t}/widget.json"])
            snap = open_snapshot(self.root)
            meta = snap.widgets[f"b-{t}"]
            self.assertEqual(meta["languages"], ["en", "ru", "uk"])
            self.assertEqual(list(meta["states"]), builder.state_ids(meta["builder"]))
            for lang in meta["languages"]:
                b = widgets.build(snap, f"b-{t}", lang=lang)
                self.assertTrue(b["ok"], (t, lang, b["errors"]))
                self.assertLessEqual(b["compressedBytes"], BUDGET)
                p = widgets.payload(snap, f"b-{t}", b)
                self.assertEqual(p["params"].get("allow_queries", False), builder.needs_queries(meta["builder"]))
            self.assertEqual(widgets.mock_answers(snap, f"b-{t}"), builder.mock_answers(meta["builder"]))
        from bot_ui.validate import validate
        self.assertFalse([d for d in validate(open_snapshot(self.root)) if d.severity == "error"])

    def test_source_hash_follows_the_config_and_the_preview_state(self):
        self.create("promo", "builder:promo")
        snap = open_snapshot(self.root)
        old = widgets.build(snap, "promo", lang="en")
        preview = widgets.build(snap, "promo", lang="en", state="revealed")
        self.assertNotEqual(preview["sourceHash"], old["sourceHash"])
        self.assertIn("SPRING20", preview["html"])
        self.assertNotIn("SPRING20", old["html"])
        with self.assertRaises(widgets.WidgetError):
            widgets.export(snap, "promo", preview, preview["sourceHash"])
        same = widgets.build(snap, "promo", lang="en", state="closed")  # the first state is production
        self.assertEqual(same["sourceHash"], old["sourceHash"])
        self.assertEqual(widgets.export(snap, "promo", old, old["sourceHash"])["sourceHash"], old["sourceHash"])
        meta = self.read("widgets/promo/widget.json")
        meta["builder"]["content"]["title"]["en"] = "−25% today"
        self.write_raw("widgets/promo/widget.json", json.dumps(meta, ensure_ascii=False).encode())
        snap2 = open_snapshot(self.root)
        new = widgets.build(snap2, "promo", lang="en")
        self.assertNotEqual(new["sourceHash"], old["sourceHash"])
        self.assertIn("−25% today", new["html"])
        with self.assertRaises(widgets.WidgetError) as ctx:
            widgets.export(snap2, "promo", old, old["sourceHash"])
        self.assertEqual(ctx.exception.code, "STALE_BUILD")

    def test_eject_writes_files_and_later_builds_from_them(self):
        self.create("sale", "builder:countdown")
        snap = open_snapshot(self.root)
        before = {lang: widgets.build(snap, "sale", lang=lang)["html"] for lang in LANGS}
        write_patch(self.root, builder.eject_patch(snap, "sale"))
        snap = open_snapshot(self.root)
        meta = snap.widgets["sale"]
        self.assertTrue(meta["builder"]["ejected"])
        self.assertFalse(builder.active(meta))
        for name in ("index.html", "style.css", "widget.js"):
            self.assertIn(f"widgets/sale/{name}", snap.files)
        self.assertIn("/*@lang uk*/", snap.files["widgets/sale/widget.js"].decode())  # every language kept
        for lang in LANGS:
            b = widgets.build(snap, "sale", lang=lang)
            self.assertTrue(b["ok"], b["errors"])
            self.assertEqual(b["html"], before[lang])
        rel = "widgets/sale/style.css"
        self.write_raw(rel, self.raw(rel) + b".cd b{letter-spacing:.02em}\n")  # files are the source now
        self.assertIn("letter-spacing:.02em", widgets.build(open_snapshot(self.root), "sale", lang="en")["html"])
        with self.assertRaises(widgets.WidgetError) as ctx:
            builder.eject_patch(open_snapshot(self.root), "sale")
        self.assertEqual(ctx.exception.code, "ALREADY_EJECTED")

    def test_images_come_from_svg_files_in_the_widget_folder(self):
        self.create("card", "builder:product")
        svg = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 3"><rect width="4" height="3"/></svg>'
        self.write_raw("widgets/card/beans.svg", svg.encode())
        meta = self.read("widgets/card/widget.json")
        meta["builder"]["content"]["image"] = "beans.svg"
        self.write_raw("widgets/card/widget.json", json.dumps(meta, ensure_ascii=False).encode())
        snap = open_snapshot(self.root)
        b = widgets.build(snap, "card", lang="en")
        self.assertTrue(b["ok"], b["errors"])
        self.assertRegex(b["html"], r'<div class="im"><svg viewBox="0 0 4 3"><rect[^>]*></svg><span class="bd" id="bd">')
        self.assertEqual(builder.validate_config(meta["builder"], builder.assets_of(snap, "card")), [])
        meta["builder"]["content"]["image"] = "nope.svg"
        self.assertEqual(codes(builder.validate_config(meta["builder"], builder.assets_of(snap, "card"))),
                         {("/content/image", "IMAGE_MISSING")})

    def test_server_endpoints(self):
        from bot_ui.server import Studio as Server
        self.create("hello", "builder:message")
        srv = Server(self.root, 0)
        status, doc = srv.api("/api/widget/builder-schema", {})
        self.assertEqual((status, doc["version"], list(doc["types"])), (200, 1, list(builder.TYPES)))
        cfg = open_snapshot(self.root).widgets["hello"]["builder"]
        status, doc = srv.api("/api/widget/builder-validate", {"config": cfg, "widget": "hello"})
        self.assertEqual((status, doc["issues"]), (200, []))
        bad = copy.deepcopy(cfg)
        bad["content"]["button"]["action"] = {"kind": "link", "url": "http://x.example"}
        self.assertEqual(srv.api("/api/widget/builder-validate", {"config": bad})[1]["issues"][0]["code"], "URL_INVALID")
        status, doc = srv.api("/api/widget/build", {"widget": "hello", "lang": "ru", "state": "default"})
        self.assertTrue(doc["ok"], doc.get("errors"))
        status, doc = srv.api("/api/widget/eject", {"widget": "hello", "expectedRevision": "sha256:stale"})
        self.assertEqual(status, 409)
        status, doc = srv.api("/api/widget/eject", {"widget": "hello", "expectedRevision": open_snapshot(self.root).revision})
        self.assertEqual(status, 200, doc)
        self.assertEqual(srv.api("/api/widget/eject", {"widget": "hello"})[0], 422)
        self.assertEqual(srv.api("/api/widget/eject", {"widget": "order-status"})[1]["error"]["code"], "NOT_A_BUILDER_WIDGET")

    def test_draft_config_builds_without_saving(self):
        from bot_ui.server import Studio as Server
        self.create("hello", "builder:message")
        snap = open_snapshot(self.root)
        meta = copy.deepcopy(snap.widgets["hello"])
        meta["builder"]["style"]["preset"] = "contrast"
        status, doc = Server(self.root, 0).api("/api/widget/build", {"widget": "hello", "lang": "en",
                                                                    "files": {"widget.json": json.dumps(meta)}})
        self.assertTrue(doc["ok"] and doc["draft"], doc.get("errors"))
        self.assertRegex(doc["html"], r"--c-text:light-dark\(#000000,#ffffff\)")
        self.assertEqual(open_snapshot(self.root).revision, snap.revision)
        self.assertTrue(re.search(r"min-height:46px", doc["html"]))


if __name__ == "__main__":
    unittest.main()
