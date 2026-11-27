"""The welcome spec check (references/welcome-message.md section 10): the example is clean, every rule fires."""
import contextlib
import io
import json
import os
import tempfile
import unittest

import _paths
import tgui
import validate_welcome as vw

EXAMPLE = os.path.join(_paths.ROOT, "examples", "welcome", "coffee-shop.json")
KB = {"inline_keyboard": [[{"text": "Order", "callback_data": "v1:order", "style": "primary"}],
                          [{"text": "Help", "callback_data": "v1:help"}]]}
PHOTO = {"method": "sendPhoto", "params": {"chat_id": 1, "photo": "<file_id>", "caption": "<b>Shop</b>\nCoffee in 10 minutes.",
                                           "parse_mode": "HTML", "reply_markup": KB}}
HOME = {"method": "sendMessage", "params": {"chat_id": 1, "text": "<b>Shop</b>\nOrder #7 is ready.", "parse_mode": "HTML",
                                            "reply_markup": KB}}


def spec(*scenarios, languages=("en",)):
    return {"kind": "welcome-spec", "languages": list(languages), "scenarios": list(scenarios)}


def new(*steps, **extra):
    return {"id": extra.pop("id", "new"), "entry": "/start", "user": "new", "steps": list(steps), **extra}


def returning(*steps):
    return {"id": "returning", "entry": "/start", "user": "returning", "steps": list(steps)}


def codes(doc) -> dict:
    checker = vw.Checker()
    checker.spec(doc)
    out: dict = {}
    for f in checker.found:
        out.setdefault(f["code"], set()).add(f["level"])
    return out


class Example(unittest.TestCase):
    def test_example_spec_is_clean(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            self.assertEqual(codes(json.load(fh)), {})

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(vw.main([EXAMPLE]), 0)
            bad = os.path.join(tmp, "welcome.json")
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(spec(new(PHOTO, HOME)), fh)
            self.assertEqual(vw.main([bad, "--json"]), 1)
        self.assertIn('"WELCOME_SPLIT"', out.getvalue())

    def test_check_changed_routes_a_spec_to_check_welcome(self):
        name, code, _ = tgui.check_file(EXAMPLE)
        self.assertEqual((name, code), ("check welcome", 0))


class Rules(unittest.TestCase):
    def test_a_clean_minimal_spec(self):
        self.assertEqual(codes(spec(new(PHOTO), returning(HOME))), {})

    def test_three_messages_filler_and_a_phone_request(self):
        filler = {"method": "sendMessage", "params": {"chat_id": 1, "text": "Choose an option below 👇", "reply_markup": KB}}
        phone = {"method": "sendMessage", "params": {"chat_id": 1, "text": "Share your phone", "reply_markup": {
            "keyboard": [[{"text": "Share", "request_contact": True}]], "one_time_keyboard": True}}}
        found = codes(spec(new(PHOTO, filler, phone), languages=("en", "uk")))
        self.assertEqual(found["WELCOME_SPLIT"], {"error"})
        self.assertEqual(found["WELCOME_ASKS_DATA"], {"error"})
        self.assertEqual(found["WELCOME_FILLER"], {"warning"})
        self.assertIn("WELCOME_NO_RETURNING", found)
        self.assertIn("WELCOME_LANGUAGE_UNCOVERED", found)

    def test_caption_limit_counts_what_the_reader_sees(self):
        long = dict(PHOTO, params=dict(PHOTO["params"], caption="<b>" + "x" * 1025 + "</b>"))
        self.assertIn("CAPTION_TOO_LONG", codes(spec(new(long), returning(HOME))))
        tags_only = dict(PHOTO, params=dict(PHOTO["params"], caption="<b>" * 300 + "Shop"))
        self.assertNotIn("CAPTION_TOO_LONG", codes(spec(new(tags_only), returning(HOME))))

    def test_editing_a_photo_welcome_as_text_fails(self):
        edit = {"on": "tap v1:order", "method": "editMessageText",
                "params": {"chat_id": 1, "message_id": 2, "text": "Catalog", "reply_markup": KB}}
        self.assertEqual(codes(spec(new(PHOTO, edit), returning(HOME)))["EDIT_TEXT_ON_MEDIA"], {"error"})
        caption = {"on": "tap", "method": "editMessageCaption", "params": {"chat_id": 1, "message_id": 2, "caption": "x"}}
        self.assertIn("EDIT_CAPTION_ON_TEXT", codes(spec(new(HOME, caption), returning(HOME))))

    def test_album_cannot_carry_buttons(self):
        album = {"method": "sendMediaGroup", "params": {"chat_id": 1, "media": [
            {"type": "photo", "media": "<a>"}, {"type": "photo", "media": "<b>"}]}}
        self.assertEqual(codes(spec(new(album), returning(HOME)))["WELCOME_ALBUM"], {"error"})

    def test_language_picker_is_replaced_not_followed(self):
        picker = {"method": "sendMessage", "params": {"chat_id": 1, "text": "Choose a language", "reply_markup": {
            "inline_keyboard": [[{"text": "English", "callback_data": "lang:en"},
                                 {"text": "Українська", "callback_data": "lang:uk"}]]}}}
        stacked = dict(PHOTO, on="tap lang:en")
        found = codes(spec(new(PHOTO), new(picker, stacked, id="unknown", language_code=None), returning(HOME),
                           languages=("en", "uk")))
        self.assertIn("WELCOME_PICKER_STACKED", found)
        self.assertNotIn("WELCOME_NO_PRIMARY", found)  # the picker has no main action by design
        self.assertNotIn("WELCOME_SPLIT", found)  # the second message follows a tap

    def test_returning_users_must_not_get_the_welcome_again(self):
        same = returning(dict(PHOTO))
        self.assertIn("RETURNING_REPEATS_WELCOME", codes(spec(new(PHOTO), same)))

    def test_group_entry_and_effects(self):
        reply = {"method": "sendMessage", "params": {"chat_id": -100, "text": "Hi everyone, I'm the shop bot",
                                                     "message_effect_id": "5104841245755180586"}}
        found = codes(spec(new(PHOTO), returning(HOME), {"id": "g", "user": "new", "chat": "group", "steps": [reply]}))
        self.assertIn("GROUP_ONBOARDING", found)
        self.assertEqual(found["EFFECT_NOT_PRIVATE"], {"error"})

    def test_setup_calls_menu_dumps_and_stray_previews(self):
        setup = {"method": "setMyCommands", "params": {"commands": [{"command": "start", "description": "Main menu"}]}}
        rows = [[{"text": f"Item {i}", "callback_data": f"v1:i{i}"}] for i in range(8)]
        dump = {"method": "sendMessage", "params": {"chat_id": 1, "text": "<b>Shop</b>\nSee https://example.com",
                                                    "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows}}}
        found = codes(spec(new(setup, dump), returning(HOME)))
        self.assertIn("WELCOME_SETUP_CALL", found)
        self.assertIn("WELCOME_MENU_DUMP", found)
        self.assertIn("STRAY_PREVIEW", found)
        self.assertIn("WELCOME_NO_PRIMARY", found)

    def test_a_dead_end_unless_the_text_asks_for_input(self):
        bare = {"method": "sendMessage", "params": {"chat_id": 1, "text": "Shop"}}
        self.assertIn("WELCOME_NO_ACTION", codes(spec(new(bare), returning(HOME))))
        cue = {"method": "sendMessage", "params": {"chat_id": 1, "text": "Надішліть посилання, наприклад youtu.be/…"}}
        self.assertNotIn("WELCOME_NO_ACTION", codes(spec(new(cue), returning(HOME))))

    def test_not_a_spec(self):
        self.assertIn("SPEC", codes({"method": "sendMessage"}))
        self.assertIn("WELCOME_NO_NEW", codes(spec(returning(HOME))))


if __name__ == "__main__":
    unittest.main()
