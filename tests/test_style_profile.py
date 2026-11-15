"""Style probe, profile scaffold and profile check (scripts/style_profile.py)."""
import builtins
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest

import _paths
import style_profile

FIXTURE = os.path.join(_paths.REPO, "tests", "fixtures", "style_project")
EXAMPLE = os.path.join(_paths.ROOT, "examples", "style-profile", "profile.example.json")
CANARY = "STYLE_PROBE_CANARY_VALUE"


def example():
    return copy.deepcopy(_paths.load("examples", "style-profile", "profile.example.json"))


class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.root = os.path.join(cls.tmp, "project")
        shutil.copytree(FIXTURE, cls.root)
        # Secret-like files the probe must skip without opening them.
        for rel in (".env", ".env.local", "deploy/server.key", "config/credentials.json"):
            path = os.path.join(cls.root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"BOT_TOKEN={CANARY}\n")
        node = os.path.join(cls.root, "node_modules", "grammy")
        os.makedirs(node)
        with open(os.path.join(node, "index.js"), "w", encoding="utf-8") as fh:
            fh.write("InlineKeyboard callback_data\n")
        opened = []
        real_open = builtins.open

        def spy(file, *args, **kwargs):
            opened.append(os.path.abspath(str(file)))
            return real_open(file, *args, **kwargs)

        builtins.open = spy
        try:
            cls.res = style_profile.probe(cls.root)
        finally:
            builtins.open = real_open
        cls.opened = opened

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_secret_like_files_are_never_opened(self):
        rels = [os.path.relpath(p, self.root).replace(os.sep, "/") for p in self.opened]
        for bad in (".env", ".env.local", "deploy/server.key", "config/credentials.json"):
            self.assertNotIn(bad, rels)
        self.assertFalse(any(r.startswith("node_modules/") for r in rels))
        self.assertNotIn(CANARY, json.dumps(self.res))
        self.assertEqual(self.res["skipped_secret_like"], 4)

    def test_finds_sdk_design_tokens_and_assets(self):
        self.assertEqual(self.res["sdk"][0]["sdk"], "grammY")
        self.assertEqual(self.res["sdk"][0]["version"], "^1.38.0")
        self.assertIn("DESIGN.md", self.res["design_docs"])
        names = {t["name"]: t["value"] for t in self.res["tokens"]}
        self.assertEqual(names["--color-primary"], "#2F6FEB")
        self.assertIn("web/public/brand/logo.svg", self.res["brand_assets"])
        self.assertTrue(any("Inter" in f["family"] for f in self.res["fonts"]))

    def test_locale_stats_and_address_form(self):
        loc = self.res["locales"]
        self.assertEqual(sorted(loc), ["en", "ru"])
        self.assertEqual(loc["ru"]["longest_button_label"]["key"], "btn_orders")
        self.assertGreater(loc["ru"]["address_counts"]["formal"], 0)
        self.assertEqual(loc["ru"]["address_counts"]["informal"], 0)
        self.assertEqual(loc["en"]["strings"], 4)

    def test_touchpoints_with_locations(self):
        tp = self.res["touchpoints"]
        for key in ("inline_keyboards", "callback_data", "commands", "button_style"):
            self.assertIn(key, tp)
            self.assertTrue(tp[key]["samples"][0].startswith("src/bot.ts:"))

    def test_scaffold_is_valid_and_carries_evidence(self):
        prof = style_profile.scaffold(self.res)
        errors, warnings = style_profile.check(prof)
        self.assertEqual(errors, [])
        self.assertEqual(prof["voice"]["address"], "formal")
        self.assertEqual(prof["brand"]["accent"], "#2F6FEB")
        self.assertEqual(prof["bot"]["locales"][0], "en")
        self.assertIn("bot.sdk", prof["sources"])
        self.assertIn("voice.address", prof["sources"])
        self.assertTrue(any("without a source" in w for w in warnings))


class Check(unittest.TestCase):
    def errors(self, prof):
        return " | ".join(style_profile.check(prof)[0])

    def test_example_profile_is_clean(self):
        self.assertEqual(style_profile.check(example()), ([], []))

    def test_unknown_keys_are_errors(self):
        prof = example()
        prof["keyboard"]["max_button_per_row"] = 1
        prof["colours"] = {}
        text = self.errors(prof)
        self.assertIn("keyboard.max_button_per_row: unknown knob", text)
        self.assertIn("colours: unknown section", text)

    def test_custom_emoji_need_verified_eligibility_and_pack(self):
        prof = example()
        prof["icons"].update(system="custom", eligibility="unverified", pack=None)
        text = self.errors(prof)
        self.assertIn("eligibility must be verified", text)
        self.assertIn("icons.pack: required", text)

    def test_premium_route_does_not_cover_channels(self):
        prof = example()
        prof["bot"]["contexts"] = ["private", "channel"]
        prof["icons"].update(system="custom", eligibility="premium", pack="line-icons")
        self.assertIn("need Fragment usernames", self.errors(prof))
        prof["icons"]["eligibility"] = "fragment"
        self.assertEqual(style_profile.check(prof)[0], [])

    def test_contracts_change_only_under_m4_with_prefix(self):
        prof = example()
        prof["mandate"]["change"] = "M3"
        self.assertIn("needs mandate.change = M4", self.errors(prof))
        prof = example()
        prof["contracts"]["callback_prefix"] = "x" * 17
        self.assertIn("1-16 byte prefix", self.errors(prof))

    def test_api_limits_for_commands_and_profile_texts(self):
        prof = example()
        prof["navigation"]["commands"] = [{"command": "/Start", "description": ""},
                                          {"command": "help", "description": "Help"},
                                          {"command": "help", "description": "Help again"}]
        prof["profile_texts"]["en"]["short_description"] = "x" * 121
        text = self.errors(prof)
        self.assertIn("1-32 chars of a-z", text)
        self.assertIn("description must be 1-256", text)
        self.assertIn("duplicate command 'help'", text)
        self.assertIn("short_description: must be a string of 0-120", text)

    def test_skill_rules_are_errors(self):
        prof = example()
        prof["emphasis"]["primary_per_screen"] = 2
        prof["feedback"]["ack_every_tap"] = False
        prof["navigation"]["entry"] = "menu_button_mini_app"
        text = self.errors(prof)
        self.assertIn("emphasis.primary_per_screen: must be an integer 0-1", text)
        self.assertIn("ack_every_tap: must be true", text)
        self.assertIn("needs menu_button 'web_app'", text)

    def test_taste_is_a_warning_not_an_error(self):
        prof = example()
        prof["keyboard"]["max_buttons_per_row"] = 4
        del prof["sources"]["voice.tone"]
        errors, warnings = style_profile.check(prof)
        self.assertEqual(errors, [])
        self.assertTrue(any("max_buttons_per_row=4" in w for w in warnings))
        self.assertTrue(any("voice.tone" in w for w in warnings))

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(style_profile.main(["check", EXAMPLE]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            prof = example()
            prof["voice"]["tone"] = "loud"
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(prof, fh)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(style_profile.main(["check", bad]), 1)
            self.assertIn("voice.tone: 'loud' is not one of", out.getvalue())


if __name__ == "__main__":
    unittest.main()
