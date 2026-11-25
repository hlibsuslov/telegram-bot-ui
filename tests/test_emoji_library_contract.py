"""emoji_packs.LibraryClient against the emoji library contract: vendored schemas, taxonomy version,
the offline export, and picking a pack from the style profile's brand colour. No network: the
online client gets a fake fetch that serves saved answers of a real site build
(tests/fixtures/emoji_library: the OpenAPI examples, /api/emoji-facets trimmed to seven packs,
and the same seven lines of /emoji-library.ndjson.gz with three emoji each)."""
from __future__ import annotations

import copy
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _paths

SCRIPTS = os.path.join(_paths.ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import emoji_contract  # noqa: E402
import emoji_packs  # noqa: E402
from bot_ui.emoji import EmojiError  # noqa: E402

FIX = os.path.join(_paths.REPO, "tests", "fixtures", "emoji_library")
EXPORT = os.path.join(FIX, "emoji-library.ndjson.gz")
SCRIPT = os.path.join(SCRIPTS, "emoji_packs.py")
PROFILE = {"bot": {"archetype": "monitoring", "primary_locale": "ru"},
           "brand": {"traits": ["calm", "precise"], "accent": "#2F6FEB", "icon_style": "outline"}}


def saved(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def export_lines():
    with gzip.open(EXPORT, "rt", encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def fake_fetch(answers):
    """fetch(path) for LibraryClient: path without the query -> (status, JSON doc)."""
    seen = []

    def fetch(path):
        seen.append(path)
        status, doc = answers.get(path.split("?")[0], (404, {"ok": False, "error": {"code": "PACK_NOT_FOUND", "message": "no"}}))
        return status, json.dumps(doc, ensure_ascii=False).encode("utf-8")
    fetch.seen = seen
    return fetch


def online(**override):
    answers = {"/api/emoji-facets": (200, saved("facets.json")), "/api/emoji-search": (200, saved("search.json")),
               "/api/emoji-pack/by-id": (200, saved("by-id.json")),
               f"/api/emoji-pack/{saved('pack.json')['name']}": (200, saved("pack.json"))}
    answers.update(override)
    return emoji_packs.LibraryClient(fetch=fake_fetch(answers))


class Contract(unittest.TestCase):
    def test_the_vendored_contract_names_its_source_date_and_taxonomy(self):
        doc = emoji_contract.load_contract()
        self.assertTrue(doc["source"].startswith("https://") and doc["source"].endswith("/api/emoji-openapi.json"))
        self.assertRegex(doc["vendored"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(doc["openapi"], "3.1.0")
        self.assertIn(doc["taxonomy"]["version"], doc["taxonomy"]["understood"])
        for name in ("SearchResponse", "PackResponse", "ByIdResponse", "FacetsResponse", "CatalogLine"):
            self.assertIn(name, doc["schemas"])

    def test_saved_answers_of_a_real_build_conform(self):
        for file, schema in (("search.json", "SearchResponse"), ("pack.json", "PackResponse"),
                             ("by-id.json", "ByIdResponse"), ("facets.json", "FacetsResponse")):
            self.assertEqual(emoji_contract.problems(saved(file), emoji_contract.load_contract()["schemas"][schema],
                                                     emoji_contract.load_contract()["schemas"]), [], file)
        for line in export_lines():
            emoji_contract.check_answer(line, "CatalogLine", line["name"])

    def test_the_client_reads_every_endpoint_through_the_contract(self):
        client = online()
        self.assertEqual(client.search("checkmark")["query"], "checkmark")
        name = saved("pack.json")["name"]
        self.assertEqual(client.pack(name)["name"], name)
        self.assertEqual(len(client.facets()["packs"]), 7)
        self.assertEqual(client.calls, 3)

    def test_a_wrong_shape_fails_and_names_the_field(self):
        bad = saved("pack.json")
        bad["emoji"][0]["id"] = 5381          # a number: ids must stay strings
        del bad["telegramUrl"]
        client = online(**{f"/api/emoji-pack/{bad['name']}": (200, bad)})
        with self.assertRaises(emoji_contract.ContractError) as ctx:
            client.pack(bad["name"])
        self.assertEqual(ctx.exception.code, "CONTRACT_MISMATCH")
        self.assertIn("$.emoji[0].id: expected string", ctx.exception.message)
        self.assertIn("missing telegramUrl", ctx.exception.message)
        self.assertIn("PackResponse", ctx.exception.message)

    def test_an_unknown_facet_or_tag_shape_fails(self):
        bad = saved("facets.json")
        bad["packs"][0]["facets"]["weather"] = [["rain", 0.9]]
        bad["packs"][1]["facets"]["style"] = [["outline"]]
        with self.assertRaises(emoji_contract.ContractError) as ctx:
            online(**{"/api/emoji-facets": (200, bad)}).facets()
        self.assertIn("key 'weather'", ctx.exception.message)
        self.assertIn("$.packs[1].facets.style[0]: 1 items, at least 2 expected", ctx.exception.message)

    def test_an_unknown_taxonomy_major_version_fails_clearly(self):
        future = saved("search.json")
        future["taxonomy"] = 3
        with self.assertRaises(emoji_contract.ContractError) as ctx:
            online(**{"/api/emoji-search": (200, future)}).search("checkmark")
        self.assertEqual(ctx.exception.code, "TAXONOMY_UNSUPPORTED")
        self.assertIn("taxonomy 3", ctx.exception.message)
        self.assertIn("understands taxonomy 2", ctx.exception.message)
        facets = saved("facets.json")
        facets["taxonomy"]["version"] = 3
        with self.assertRaises(emoji_contract.ContractError):
            online(**{"/api/emoji-facets": (200, facets)}).facets()

    def test_error_answers_keep_their_code(self):
        with self.assertRaises(EmojiError) as ctx:
            online().pack("NoSuchPack")
        self.assertEqual(ctx.exception.code, "PACK_NOT_FOUND")
        with self.assertRaises(EmojiError) as ctx:
            online().pack("../etc")
        self.assertEqual(ctx.exception.code, "PACK_NAME")

    def test_an_older_deployment_without_tags_means_no_facets(self):
        client = emoji_packs.LibraryClient(fetch=lambda path: (404, b"<html>not found</html>"))
        self.assertIsNone(client.facets())

    def test_refreshing_from_the_same_documents_gives_the_same_contract(self):
        old = emoji_contract.load_contract()
        api = {"openapi": old["openapi"], "info": {"version": old["apiVersion"], "x-catalog-version": old["catalog"]},
               "components": {"schemas": old["schemas"]}}
        self.assertEqual(emoji_contract.vendor(api, saved("facets.json"), old["vendored"]), old)

    def test_the_validator_refuses_keywords_it_does_not_check(self):
        tmp = tempfile.mkdtemp()
        try:
            doc = copy.deepcopy(emoji_contract.load_contract())
            doc["schemas"]["PackName"]["maxLength"] = 64
            path = os.path.join(tmp, "contract.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            with self.assertRaises(emoji_contract.ContractError) as ctx:
                emoji_contract.load_contract(path)
            self.assertIn("maxLength", ctx.exception.message)
        finally:
            shutil.rmtree(tmp)


class Export(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, lines, gz=True):
        path = os.path.join(self.tmp, "lib.ndjson.gz" if gz else "lib.ndjson")
        data = ("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n").encode("utf-8")
        with open(path, "wb") as fh:
            fh.write(gzip.compress(data) if gz else data)
        return path

    def test_the_export_stands_for_the_facets_answer(self):
        catalog = emoji_packs.LibraryClient(export=EXPORT).facets()
        live = saved("facets.json")
        self.assertEqual(sorted(catalog["packs"], key=lambda p: p["name"]), sorted(live["packs"], key=lambda p: p["name"]))
        self.assertEqual(catalog["taxonomy"], live["taxonomy"])
        self.assertEqual(catalog["thresholds"], live["thresholds"])

    def test_plain_ndjson_works_too_and_a_bad_line_is_named(self):
        lines = export_lines()
        self.assertEqual(len(emoji_packs.read_export(self.write(lines, gz=False))["lines"]), 7)
        lines[2]["emoji"][0]["codes"] = "not codes"
        with self.assertRaises(emoji_contract.ContractError) as ctx:
            emoji_packs.read_export(self.write(lines))
        self.assertIn("line 3", ctx.exception.message)
        self.assertIn("$.emoji[0].codes", ctx.exception.message)

    def test_a_future_taxonomy_in_the_export_fails(self):
        lines = export_lines()
        for x in lines:
            x["taxonomy"] = 3
        with self.assertRaises(emoji_contract.ContractError) as ctx:
            emoji_packs.read_export(self.write(lines))
        self.assertEqual(ctx.exception.code, "TAXONOMY_UNSUPPORTED")

    def test_offline_has_no_search(self):
        with self.assertRaises(EmojiError) as ctx:
            emoji_packs.LibraryClient(export=EXPORT).search("home")
        self.assertEqual(ctx.exception.code, "OFFLINE_NO_SEARCH")


class ProfilePick(unittest.TestCase):
    def pick(self, client, profile=PROFILE, **kw):
        brief, accents = emoji_packs.profile_request(profile)
        return emoji_packs.pick_by_profile(client.facets(), brief, accents, lang=emoji_packs.profile_lang(profile), **kw)

    def test_offline_gives_the_same_result_as_online(self):
        on, off = self.pick(online()), self.pick(emoji_packs.LibraryClient(export=EXPORT))
        self.assertEqual(on, off)
        self.assertEqual(self.pick(online(), require=["motion:static"], theme="dark"),
                         self.pick(emoji_packs.LibraryClient(export=EXPORT), require=["motion:static"], theme="dark"))

    def test_the_brand_colour_is_compared_with_the_pack_colours(self):
        out = self.pick(online())
        self.assertEqual(out["accents"], ["#2F6FEB"])
        self.assertNotIn("color", out["brief"])            # the accent is compared, not matched as a tag
        top = out["packs"][0]
        self.assertEqual(top["name"], "CenterOfEmoji98095669")   # outline, blue, static, utility
        self.assertEqual(top["colour"]["family"], "blue")
        self.assertEqual(top["colour"]["best"][0], "blue")
        red = self.pick(online(), profile={**PROFILE, "brand": {**PROFILE["brand"], "accent": "#E53935"}})
        nutrok = next(p for p in red["packs"] if p["name"] == "EmojiNutrokStore")
        blue_nutrok = next(p for p in out["packs"] if p["name"] == "EmojiNutrokStore")
        self.assertGreater(nutrok["colour"]["score"], blue_nutrok["colour"]["score"])

    def test_an_adaptive_pack_suits_any_accent(self):
        ios = next(p for p in self.pick(online())["packs"] if p["name"] == "IOS27icons8")
        self.assertTrue(ios["colour"]["adaptive"])
        self.assertIn("text colour", ios["why"])

    def test_every_pack_is_explained_in_one_line_with_its_description(self):
        out = self.pick(online())
        for row in out["packs"]:
            line = row["why"]
            self.assertNotIn("\n", line)
            for part in ("emoji", "style", "topic", "colour"):
                self.assertIn(part, line, line)
            self.assertTrue(line.startswith(row["name"] + ":"))
        top = out["packs"][0]
        self.assertEqual(set(top["description"]), {"what", "for", "not_for"})
        self.assertRegex(top["description"]["what"], "[а-яА-Я]")   # the profile's primary locale (ru)

    def test_an_explicit_colour_flag_replaces_the_accent(self):
        brief, accents = emoji_packs.profile_request(PROFILE, {"color": ["red"]})
        self.assertEqual((brief["color"], accents), (["red"], []))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.profile = os.path.join(self.tmp, "profile.json")
        with open(self.profile, "w", encoding="utf-8") as fh:
            json.dump(PROFILE, fh)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_pick_with_a_profile_prints_one_line_per_pack(self):
        out = os.path.join(self.tmp, "out.json")
        r = self.run_cli("library", "pick", "--profile", self.profile, "--library-file", EXPORT, "--top", "3", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(len(doc["packs"]), 3)
        lines = [x for x in r.stderr.splitlines() if x.strip()]
        self.assertEqual(lines[:3], [p["why"] for p in doc["packs"]])
        self.assertTrue(lines[0].startswith("CenterOfEmoji98095669:"))

    def test_slot_picking_needs_the_online_library(self):
        r = self.run_cli("library", "pick", "--needs", "home,back", "--library-file", EXPORT)
        self.assertEqual(r.returncode, 2)
        self.assertIn("fallback emoji", r.stderr)

    def test_a_contract_error_is_one_clear_line_and_exit_1(self):
        lines = export_lines()
        lines[0]["taxonomy"] = lines[1]["taxonomy"] = 9
        path = os.path.join(self.tmp, "future.ndjson")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines))
        r = self.run_cli("library", "facets", "--library-file", path)
        self.assertEqual(r.returncode, 1)
        self.assertIn("TAXONOMY_UNSUPPORTED", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_contract_shows_the_vendored_source(self):
        r = self.run_cli("library", "contract")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("/api/emoji-openapi.json", r.stdout)


if __name__ == "__main__":
    unittest.main()
