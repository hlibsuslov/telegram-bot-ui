"""bot-ui Emoji page: the emoji library's catalog filtered by style, colour, theme fit and motion, and a pack
picked for the slots the project's screens use. Online answers are saved (no network); the offline export is
tests/fixtures/emoji_library/emoji-library.ndjson.gz."""
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
from unittest import mock

from _bot_ui import CLI, ROOT, ProjectCase
from bot_ui import emoji, emoji_catalog
from bot_ui.artifact import snapshot_document
from bot_ui.project import open_snapshot
from bot_ui.server import serve

import emoji_packs  # noqa: E402  (on sys.path through bot_ui.skill)

FIX = os.path.join(ROOT, "tests", "fixtures", "emoji_library")
EXPORT = os.path.join(FIX, "emoji-library.ndjson.gz")
TEMPLATE_SLOTS = ["back", "product", "pending", "warning", "done", "cart", "notifications", "store"]


def facets() -> dict:
    with open(os.path.join(FIX, "facets.json"), encoding="utf-8") as fh:
        return json.load(fh)


def saved_client() -> emoji_packs.LibraryClient:
    """An online client with canned answers: CenterOfEmoji98095669 has back, cart and done; IOS27icons8 has back."""
    def entry(eid, fallback):
        return {"id": eid, "fallback": fallback, "format": "static", "adaptive": True}
    center = {"title": "Center of emoji", "emoji": [entry("11", "⬅️"), entry("12", "🛒"), entry("13", "✅")]}
    ios = {"title": "iOS icons", "emoji": [entry("21", "⬅️")]}
    search = {"⬅️": {"emoji": [{"pack": "CenterOfEmoji98095669", **entry("11", "⬅️")}, {"pack": "IOS27icons8", **entry("21", "⬅️")}]},
              "🛒": {"emoji": [{"pack": "CenterOfEmoji98095669", **entry("12", "🛒")}]},
              "✅": {"emoji": [{"pack": "CenterOfEmoji98095669", **entry("13", "✅")}]}}
    return emoji_packs.LibraryClient({"search": search, "packs": {"CenterOfEmoji98095669": center, "IOS27icons8": ios},
                                      "facets": facets()})


def no_network(*_a, **_k):
    raise AssertionError("no network expected")


class SlotsBrief(ProjectCase):
    def test_slot_groups_become_the_interface_roles_the_pack_should_cover(self):
        vocab = emoji_packs.load_vocabulary(None)
        brief = emoji_packs.slots_brief(["back", "home", "cart", "done", "settings"], vocab)
        self.assertEqual(brief["topic"], ["interface"])
        self.assertEqual(brief["role"][0], "navigation")          # back and home: the most frequent role first
        self.assertEqual(set(brief["role"]), {"navigation", "commerce", "status", "settings"})
        self.assertEqual(emoji_packs.slots_brief([], vocab), {"topic": ["interface"]})

    def test_the_screens_slots_are_their_ordinary_emoji_and_the_placed_icons(self):
        snap = open_snapshot(self.root)
        self.assertEqual(emoji_catalog.screen_slots(snap, emoji.load_library(self.root)), TEMPLATE_SLOTS)
        lib = {**emoji.empty_library(), "icons": {"home": {"id": "5", "set": "p", "fallback": "🏠", "animated": False, "adaptive": True}}}
        screen = snap.screens[next(iter(snap.screens))]
        screen.setdefault("actions", {})["go_home"] = {"label": {"en": "Home"}, "icon": {"customEmojiId": "5"}}
        self.assertEqual(emoji_catalog.screen_slots(snap, lib), TEMPLATE_SLOTS + ["home"])


class View(ProjectCase):
    def test_the_view_has_the_four_filter_facets_and_each_packs_tags_above_the_threshold(self):
        view = emoji_catalog.catalog_view({**facets(), "source": "online"})
        self.assertEqual(list(view["facets"]), ["style", "color", "fit", "motion"])
        self.assertEqual(view["facets"]["fit"]["label"], "Theme fit")
        self.assertIn({"id": "adaptive", "label": "Adaptive (repainted in the text colour)"}, view["facets"]["fit"]["values"])
        self.assertEqual((view["threshold"], view["source"], view["taxonomy"], len(view["packs"])), (0.3, "online", 2, 7))
        abc = next(p for p in view["packs"] if p["name"] == "ABCEmoji")
        self.assertEqual(set(abc["tags"]), {"style", "color", "fit", "motion"})
        self.assertEqual(abc["tags"]["style"], [["lettering", 1], ["gradient", 0.75]])
        self.assertTrue(abc["description"]["what"].startswith("56 animated"))
        self.assertNotIn("look", abc)

    def test_labels_and_descriptions_follow_the_language(self):
        view = emoji_catalog.catalog_view(facets(), lang="ru")
        self.assertEqual(view["facets"]["style"]["label"], "Стиль")
        abc = next(p for p in view["packs"] if p["name"] == "ABCEmoji")
        self.assertRegex(abc["description"]["for"], "[А-я]")

    def test_tags_outside_the_taxonomy_and_bad_pack_names_are_dropped(self):
        doc = facets()
        doc["packs"][0]["facets"]["style"].append(["watercolour", 0.9])
        doc["packs"].append({**doc["packs"][1], "name": "../evil"})
        view = emoji_catalog.catalog_view(doc)
        self.assertNotIn("watercolour", json.dumps(view))
        self.assertNotIn("../evil", [p["name"] for p in view["packs"]])


class Pick(ProjectCase):
    def test_online_the_pick_ranks_by_coverage_of_the_screens_slots(self):
        snap = open_snapshot(self.root)
        res = emoji_catalog.pick_for_screens(snap, emoji.load_library(self.root), facets(), client=saved_client())
        self.assertEqual((res["mode"], res["slots"]), ("coverage", TEMPLATE_SLOTS))
        top = res["packs"][0]
        self.assertEqual((top["name"], top["coverage"]), ("CenterOfEmoji98095669", round(3 / 8, 3)))
        self.assertIn("cart", [s for s in TEMPLATE_SLOTS if s not in top["missing"]])
        self.assertTrue(top["why"].startswith("CenterOfEmoji98095669: covers 3/8 slots"))
        self.assertTrue(top["description"]["what"])
        self.assertEqual(top["link"], "https://t.me/addemoji/CenterOfEmoji98095669")

    def test_offline_the_pick_ranks_the_catalog_by_the_slots_roles(self):
        snap = open_snapshot(self.root)
        client = emoji_packs.LibraryClient(export=EXPORT)
        res = emoji_catalog.pick_for_screens(snap, emoji.load_library(self.root), client.facets(), client=client)
        vocab = emoji_packs.load_vocabulary(None)
        same = emoji_packs.pick_by_profile(client.facets(), emoji_packs.slots_brief(TEMPLATE_SLOTS, vocab), [], top=10)
        self.assertEqual(res["mode"], "tags")
        self.assertEqual([r["name"] for r in res["packs"]], [r["name"] for r in same["packs"]])
        self.assertTrue(all(r["why"] and r["coverage"] is None and r["missing"] is None for r in res["packs"]))
        self.assertTrue(any("fallback emoji" in n for n in res["notes"]))


class Cache(ProjectCase):
    def test_loading_the_library_caches_the_catalog_for_the_page_and_the_snapshot(self):
        self.assertIsNone(emoji_catalog.load_catalog(self.root))
        emoji_catalog.fetch_catalog(self.root, library_file=EXPORT)
        self.assertEqual(emoji_catalog.load_catalog(self.root)["source"], "export")
        doc = emoji.client_document(self.root, open_snapshot(self.root))
        self.assertEqual((len(doc["catalog"]["packs"]), doc["screenSlots"], doc["pick"]), (7, TEMPLATE_SLOTS, None))
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".bot-ui", "emoji", "catalog.json")))

    def test_without_the_resolver_and_without_an_export_the_library_is_off(self):
        with mock.patch.dict(os.environ, {"BOT_UI_EMOJI_RESOLVER": "off"}):
            with self.assertRaises(emoji.EmojiError) as cm:
                emoji_catalog.fetch_catalog(self.root)
        self.assertEqual(cm.exception.code, "LIBRARY_OFF")

    def test_a_broken_cache_is_ignored(self):
        os.makedirs(os.path.join(self.root, ".bot-ui", "emoji"), exist_ok=True)
        self.write_raw(".bot-ui/emoji/catalog.json", b"{not json")
        self.assertIsNone(emoji_catalog.load_catalog(self.root))
        self.assertIsNone(emoji.client_document(self.root, open_snapshot(self.root))["catalog"])


class Snapshot(ProjectCase):
    def test_the_snapshot_carries_the_catalog_and_a_pick_without_any_network(self):
        emoji_catalog.fetch_catalog(self.root, library_file=EXPORT)
        with mock.patch.object(emoji._OPENER, "open", side_effect=no_network):
            block = snapshot_document(open_snapshot(self.root))["emoji"]
        self.assertEqual(len(block["catalog"]["packs"]), 7)
        self.assertEqual((block["pick"]["mode"], block["pick"]["slots"]), ("tags", TEMPLATE_SLOTS))
        self.assertEqual(block["library"]["packs"], {}, "no emoji/library.json: an empty library, the catalog still ships")

    def test_an_online_pick_for_the_same_screens_is_kept_a_stale_one_is_redone_offline(self):
        snap = open_snapshot(self.root)
        emoji_catalog.fetch_catalog(self.root, client=saved_client())
        emoji_catalog.pick(self.root, snap, client=saved_client())
        block = snapshot_document(open_snapshot(self.root))["emoji"]
        self.assertEqual(block["pick"]["mode"], "coverage")
        cached = json.loads(self.raw(".bot-ui/emoji/pick.json"))
        cached["slots"] = ["home"]
        self.write_raw(".bot-ui/emoji/pick.json", json.dumps(cached).encode())
        block = snapshot_document(open_snapshot(self.root))["emoji"]
        self.assertEqual((block["pick"]["mode"], block["pick"]["slots"]), ("tags", TEMPLATE_SLOTS))

    def test_the_export_file_can_be_embedded_directly(self):
        block = snapshot_document(open_snapshot(self.root), emoji_library_file=EXPORT)["emoji"]
        self.assertEqual((block["catalog"]["source"], len(block["catalog"]["packs"])), ("export", 7))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".bot-ui", "emoji", "catalog.json")), "no cache side effect")

    def test_no_library_and_no_catalog_means_no_emoji_block(self):
        self.assertNotIn("emoji", snapshot_document(open_snapshot(self.root)))

    def test_export_snapshot_takes_the_export_and_a_bad_file_is_one_error(self):
        out = os.path.join(self._tmp, "snap.json")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, CLI, "export-snapshot", "--project", self.root, "--format", "json",
                            "--output", out, "--emoji-library-file", EXPORT], capture_output=True, text=True,
                           encoding="utf-8", env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["emoji"]["pick"]["mode"], "tags")
        bad = os.path.join(self._tmp, "bad.ndjson")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        p = subprocess.run([sys.executable, CLI, "export-snapshot", "--project", self.root, "--format", "json",
                            "--output", out, "--emoji-library-file", bad, "--json"], capture_output=True, text=True,
                           encoding="utf-8", env=env)
        self.assertEqual(p.returncode, 4)
        self.assertIn("CONTRACT", p.stdout + p.stderr)

    def test_map_snapshot_embeds_the_export(self):
        import bot_ui_mcp
        out = os.path.join(tempfile.gettempdir(), f"bot-ui-catalog-{os.getpid()}.html")
        try:
            with mock.patch("bot_ui.artifact.build_artifact") as build:
                bot_ui_mcp.map_snapshot({"project": self.root, "output": out, "library_file": EXPORT})
            self.assertEqual(build.call_args.kwargs["emoji_library_file"], EXPORT)
        finally:
            if os.path.exists(out):
                os.remove(out)


class Server(ProjectCase):
    def setUp(self):
        super().setUp()
        ready, self.holder = threading.Event(), {}
        self.thread = threading.Thread(target=serve, args=(self.root,), daemon=True,
                                       kwargs={"port": 0, "ready": ready, "holder": self.holder, "quiet": True,
                                               "emoji_library_file": EXPORT})
        self.thread.start()
        ready.wait(10)
        self.port = self.holder["studio"].port

    def tearDown(self):
        self.holder["server"].shutdown()
        self.thread.join(5)
        super().tearDown()

    def post(self, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("POST", path, body=json.dumps(body).encode(), headers={
            "Host": f"127.0.0.1:{self.port}", "Origin": f"http://127.0.0.1:{self.port}",
            "X-Bot-UI-Token": self.holder["studio"].token, "Content-Type": "application/json"})
        r = conn.getresponse()
        doc = json.loads(r.read())
        conn.close()
        return r.status, doc

    def test_load_the_library_then_pick_for_the_screens(self):
        status, doc = self.post("/api/emoji", {})
        self.assertEqual((status, doc["catalog"], doc["libraryFile"], doc["screenSlots"]), (200, None, True, TEMPLATE_SLOTS))
        status, doc = self.post("/api/emoji/pick", {})
        self.assertEqual((status, doc["pick"]["mode"], len(doc["catalog"]["packs"])), (200, "tags", 7))
        self.assertTrue(all(r["why"] for r in doc["pick"]["packs"]))
        status, doc = self.post("/api/emoji/library", {})
        self.assertEqual((status, doc["catalog"]["source"], doc["pick"]["mode"]), (200, "export", "tags"))
