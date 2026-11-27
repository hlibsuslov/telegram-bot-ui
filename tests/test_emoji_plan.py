"""The icon plan (scripts/emoji_plan.py): stages 0-8 for choosing packs and static button icons, on saved library
answers (tests/fixtures/emoji_plan_library.json), and its bot-ui project commands (plan, verdict, apply-plan)."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

from _bot_ui import CLI, ROOT, ProjectCase
from bot_ui import emoji
from bot_ui.project import open_snapshot

SKILL = os.path.join(ROOT, "skills", "telegram-bot-ui")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import emoji_packs  # noqa: E402
import emoji_plan as ep  # noqa: E402
from tgkit.icons import load_vocabulary  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "emoji_plan_library.json")
VOCAB = load_vocabulary()


def saved() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def client(doc: dict | None = None):
    return emoji_packs.LibraryClient(doc or saved())


PLACES = [
    {"where": "menu/home", "kind": "button", "labels": {"en": "Home", "ru": "Главная"}, "keyboard": "menu"},
    {"where": "menu/cart", "kind": "button", "labels": {"en": "Cart", "ru": "Корзина"}, "keyboard": "menu"},
    {"where": "menu/orders", "kind": "button", "labels": {"en": "My orders", "ru": "Мои заказы"}, "keyboard": "menu"},
    {"where": "menu/settings", "kind": "button", "labels": {"en": "Settings"}, "keyboard": "menu"},
    {"where": "menu/back", "kind": "button", "labels": {"en": "← Back"}, "keyboard": "menu"},
    {"where": "chat/support", "kind": "button", "labels": {"en": "Chat with support"}, "keyboard": "chat"},
    {"where": "chat/home", "kind": "button", "labels": {"en": "Home"}, "keyboard": "chat"},
]


def plan(places=PLACES, doc=None, **kw):
    inv = ep.inventory(places, VOCAB)
    return ep.plan_icons(inv, VOCAB, client(doc), gate_info=ep.gate("owner_premium", len(inv["slots"])), **kw)


class Stages0to2(unittest.TestCase):
    def test_gate(self):
        self.assertFalse(ep.gate("none", 8)["ok"])
        self.assertTrue(any("Fragment" in r for r in ep.gate("owner_premium", 8, ["channel"])["reasons"]))
        self.assertTrue(any("too few" in r for r in ep.gate("fragment", 2)["reasons"]))
        self.assertEqual(ep.gate("fragment", 8)["reasons"], [])

    def test_inventory_reads_label_words_in_every_locale(self):
        inv = ep.inventory(PLACES + [
            {"where": "s/x", "kind": "button", "labels": {"en": "Bartender riddle"}, "keyboard": "s"},
            {"where": "orders/title", "kind": "title", "labels": {"en": "Your orders"}, "lead": "🛒"},
        ], VOCAB)
        self.assertEqual(sorted(inv["slots"]), ["back", "cart", "chat", "home", "order", "settings"])
        self.assertEqual(inv["slots"]["order"]["labels"], ["My orders", "Мои заказы"])
        self.assertTrue(inv["slots"]["back"]["control"])
        self.assertEqual(inv["slots"]["cart"]["use"], ["button", "title"])  # a title's emoji is its icon
        self.assertEqual([u["where"] for u in inv["unmatched"]], ["s/x"])
        self.assertEqual([b["slot"] for b in inv["keyboards"]["s"]], [None])

    def test_placeholders_are_data_not_words(self):
        self.assertEqual(ep.label_slot("Pay {order.total}", VOCAB), "pay")
        self.assertEqual(emoji.label_slots("Оплатить {order.total}", VOCAB), {"pay"})

    def test_brief_defaults_to_the_mini_app_kit(self):
        brief, source = ep.brief_for(None)
        self.assertEqual(brief["style"], ["outline"])
        self.assertIn("kit", source)
        brief, _ = ep.brief_for({"style": ["glyph"]})
        self.assertEqual((brief["style"], brief["fit"]), (["glyph"], ["adaptive"]))


class Scoring(unittest.TestCase):
    def test_meaning(self):
        first, _ = ep.meaning_score({"fallback": "🧾"}, "order", VOCAB, {"order"})
        later, _ = ep.meaning_score({"fallback": "📦"}, "order", VOCAB, {"order"})
        none, _ = ep.meaning_score({"fallback": "🍕"}, "order", VOCAB, {"order"})
        self.assertGreater(first, later)
        self.assertEqual(none, 0.0)
        tagged, why = ep.meaning_score({"fallback": "📦", "facets": {"role": [["commerce", 0.8]]}}, "order", VOCAB, {"order"})
        self.assertGreater(tagged, later)
        clash, why = ep.meaning_score({"fallback": "📦"}, "order", VOCAB, {"order", "product"})
        self.assertLess(clash, later)
        self.assertTrue(any("product" in w for w in why))

    def test_legibility_and_theme(self):
        plain, _ = ep.legibility_score({}, {"look": {"line_weight": "medium", "fill": "none"}})
        busy, why = ep.legibility_score({"facets": {"style": [["3d", 0.9]], "topic": [["characters", 0.8]]}},
                                        {"look": {"shadows": "glow", "fill": "gradient"}})
        self.assertEqual(plain, 1.0)
        self.assertLess(busy, ep.LEGIBLE_MIN)
        self.assertTrue(why)
        self.assertEqual(ep.theme_score({"adaptive": True}, "both")[0], 1.0)
        self.assertLess(ep.theme_score({"adaptive": False, "facets": {"fit": [["light", 0.9]]}}, "both")[0], 0.5)


class Assembly(unittest.TestCase):
    def test_one_main_pack_siblings_above_the_floor_animated_never(self):
        p = plan()
        self.assertEqual(p["packs"]["main"], "lines")
        self.assertEqual([f["name"] for f in p["packs"]["family"]], ["lines", "linesplus"])  # gloss is 0.76 < 0.8
        chosen = {s: r["choice"]["id"] for s, r in p["slots"].items() if r["status"] == "chosen"}
        self.assertEqual(chosen, {"home": "101", "cart": "102", "order": "105", "settings": "103"})
        self.assertEqual(len(set(chosen.values())), len(chosen))  # one emoji, one meaning
        self.assertEqual(p["slots"]["chat"]["status"], "label-only")  # only an animated emoji says it
        self.assertEqual(p["slots"]["back"]["status"], "label-only")  # a control: the word
        self.assertIn("201", [a["id"] for a in p["slots"]["order"]["alternatives"]])
        for r in p["slots"].values():
            for c in [r["choice"]] + r["alternatives"]:
                self.assertTrue(c is None or c.get("format") in (None, "static"))

    def test_a_sibling_fills_a_gap_and_the_main_pack_never_says_the_wrong_thing(self):
        doc = saved()
        doc["packs"]["lines"]["emoji"] = [e for e in doc["packs"]["lines"]["emoji"] if e["id"] != "105"]
        p = plan(doc=doc)
        self.assertEqual(p["slots"]["order"]["choice"]["pack"], "linesplus")
        self.assertTrue(any("drawn alike" in r for r in p["slots"]["order"]["reasons"]))

    def test_keyboards_are_all_icons_or_none(self):
        p = plan()
        self.assertEqual(p["keyboards"]["chat"], {"icons": False, "gaps": ["chat/support"]})
        self.assertTrue(p["keyboards"]["menu"]["icons"])  # Back is a control, not a gap
        only_chat = plan(places=[PLACES[5], {**PLACES[0], "keyboard": "chat"}])
        self.assertEqual(only_chat["slots"]["home"]["status"], "label-only")
        self.assertIn("all icons or none", only_chat["slots"]["home"]["reasons"][0])

    def test_controls_locks_and_the_gate(self):
        with_controls = plan(controls=True)
        self.assertEqual(with_controls["slots"]["back"]["choice"]["id"], "104")
        locked = plan(locks={"home": {"id": "202", "by": "user"}})
        self.assertEqual((locked["slots"]["home"]["status"], locked["slots"]["home"]["choice"]["id"]), ("locked", "202"))
        self.assertNotIn("202", [a["id"] for r in locked["slots"].values() for a in r["alternatives"]])

    def test_verdicts_and_the_review_sheet(self):
        p = plan()
        self.assertEqual(ep.accepted(p), {})
        ep.set_verdict(p, "home", ok=True)
        ep.set_verdict(p, "order", alt=1)
        self.assertEqual(p["slots"]["order"]["choice"]["id"], "201")
        self.assertIsNone(p["slots"]["order"]["verdict"])  # look again
        ep.set_verdict(p, "cart", reject="reads as a basket of food")
        self.assertEqual(sorted(ep.accepted(p)), ["home"])
        with self.assertRaises(ValueError):
            ep.set_verdict(p, "back", ok=True)  # label-only: nothing to accept
        p["slots"]["home"]["labels"] = ["<script>x</script>"]
        html = ep.review_html(p, site="https://example.org")
        self.assertIn('src="https://example.org/p/101.webp"', html)
        self.assertNotIn("<script>x", html)
        self.assertEqual(html.count('class="btn d"'), len(p["slots"]))  # every row on a dark tile too

    def test_cli_plan_without_a_project(self):
        out = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "emoji_packs.py"), "library", "plan",
                              "--needs", "home,cart,order,chat", "--library-json", FIXTURE, "--route", "fragment"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual((doc["format"], doc["packs"]["main"], doc["summary"]["chosen"]), (ep.FORMAT, "lines", 3))


class Project(ProjectCase):
    def route(self, value: str) -> None:
        doc = self.read("project.json")
        doc.setdefault("capabilities", {})["customEmoji"] = value
        self.write_raw("project.json", json.dumps(doc, ensure_ascii=False).encode())

    def test_plan_verdict_apply_keeps_a_persons_icon(self):
        self.route("owner_premium")
        emoji.set_icon(self.root, "cart", "202", fallback="🏠", note="the owner's own choice")
        snap = open_snapshot(self.root)
        places = emoji.plan_places(snap)
        self.assertTrue(any(p["where"] == "entry.start/actions/order" for p in places))
        p = emoji.make_plan(self.root, snap, client=client())
        if "cart" in p["slots"]:
            self.assertEqual(p["slots"]["cart"]["status"], "locked")
        emoji.save_plan(self.root, p)
        loaded = emoji.load_plan(self.root)
        chosen = [s for s, r in loaded["slots"].items() if r["status"] == "chosen"]
        self.assertTrue(chosen, loaded["slots"])
        for s in chosen:
            ep.set_verdict(loaded, s, ok=True)
        res = emoji.apply_plan(self.root, loaded)
        lib = emoji.load_library(self.root)
        self.assertEqual(sorted(res["applied"]), sorted(chosen))
        self.assertTrue(all(lib["icons"][s]["by"] == "plan" for s in chosen))
        self.assertEqual(lib["icons"]["cart"]["id"], "202")  # a person's slot is never overwritten
        self.assertNotIn("by", lib["icons"]["cart"])
        self.assertIn("<!doctype html>", emoji.plan_review(self.root, loaded))

    def test_route_none_blocks_apply(self):
        self.route("none")
        p = emoji.make_plan(self.root, open_snapshot(self.root), client=client())
        self.assertFalse(p["gate"]["ok"])
        with self.assertRaises(emoji.EmojiError) as err:
            emoji.apply_plan(self.root, p)
        self.assertEqual(err.exception.code, "NOT_ELIGIBLE")

    def test_cli_commands(self):
        self.route("fragment")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

        def cli(*args):
            return [sys.executable, CLI, "emoji", *args, "--project", self.root]
        sheet = os.path.join(self.root, "icon-plan.html")
        out = subprocess.run(cli("plan", "--library-json", FIXTURE, "--out", sheet), capture_output=True,
                             text=True, encoding="utf-8", env=env)
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        self.assertTrue(os.path.isfile(sheet))
        doc = self.read(emoji.PLAN)
        slot = next(s for s, r in doc["slots"].items() if r["status"] == "chosen")
        out = subprocess.run(cli("verdict", "--slot", slot, "--ok"), capture_output=True, text=True,
                             encoding="utf-8", env=env)
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        out = subprocess.run(cli("apply-plan"), capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        self.assertIn(slot, self.read(emoji.LIBRARY)["icons"])


class Data(unittest.TestCase):
    def test_fixture_untouched_and_mcp_tool_registered(self):
        doc = saved()
        self.assertEqual(copy.deepcopy(doc), saved())
        import bot_ui_mcp
        tool = next(t for t in bot_ui_mcp.TOOLS if t["name"] == "emoji_plan_icons")
        self.assertIn("places", tool["inputSchema"]["properties"])
        self.assertIs(bot_ui_mcp.HANDLERS["emoji_plan_icons"], bot_ui_mcp.emoji_plan_icons)


if __name__ == "__main__":
    unittest.main()
