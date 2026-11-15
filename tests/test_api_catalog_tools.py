"""tg_api_lookup and validate_payload over the committed snapshot (offline)."""
import contextlib
import glob
import io
import json
import os
import unittest

import _paths
import tg_api_lookup as lookup
import validate_payload as vp

API = lookup.Api()
V = vp.Validator(API.cat)

# Payload files with structural mismatches already reported to the maintainers.
# The test tolerates them being fixed; it fails only on NEW mismatches.
KNOWN_PAYLOAD_MISMATCHES = {("r04-shared-card-personal-panel.json", "editEphemeralMessageText")}


class Lookup(unittest.TestCase):
    def test_show_is_case_insensitive(self):
        self.assertEqual(API.get("SENDMESSAGE")["name"], "sendMessage")
        self.assertEqual(API.get("inlinekeyboardbutton")["kind"], "type")

    def test_accepts_parameter_name(self):
        res = API.accepts("rich_message")
        names = {r["symbol"] for r in res["methods"]}
        self.assertTrue({"sendRichMessage", "sendRichMessageDraft", "editMessageText"} <= names)
        bc = {r["symbol"] for r in API.accepts("business_connection_id")["methods"]}
        self.assertTrue({"sendMessage", "deleteBusinessAccountGift", "getBusinessAccountStarBalance"} <= bc)
        thread = {r["symbol"] for r in API.accepts("message_thread_id")["methods"]}
        self.assertTrue({"sendMessage", "sendPhoto", "sendMediaGroup", "sendRichMessage"} <= thread)

    def test_accepts_type_includes_union_members(self):
        names = {r["symbol"] for r in API.accepts("InputMedia")["methods"]}
        self.assertTrue({"editMessageMedia", "sendMediaGroup"} <= names)
        names = {r["symbol"] for r in API.accepts("InputMediaPhoto")["methods"]}
        self.assertIn("editMessageMedia", names)  # via the InputMedia union

    def test_reply_markup_takers(self):
        names = {r["symbol"] for r in API.accepts("reply_markup")["methods"]}
        self.assertTrue({"sendMessage", "editMessageReplyMarkup", "sendInvoice", "copyMessage"} <= names)
        self.assertGreater(len(names), 25)

    def test_search_ranks_exact_name_first(self):
        hits = API.search("refundStarPayment")
        self.assertEqual(hits[0]["name"], "refundStarPayment")
        self.assertTrue(any(h["name"] == "pre_checkout_query" or "pre_checkout_query" in " ".join(h["where"])
                            for h in API.search("pre_checkout")))

    def test_skeleton_has_exactly_required_params(self):
        sk = API.skeleton("sendInvoice")
        self.assertEqual(set(sk["params"]), {"chat_id", "title", "description", "payload", "currency", "prices"})
        self.assertEqual(sk["params"]["prices"], [{"label": "<label>", "amount": 0}])
        rep = V.check_request("sendInvoice", {**sk["params"], "chat_id": 1, "currency": "XTR"})
        self.assertTrue(rep.ok, rep.errors)

    def test_skeleton_unknown_method(self):
        with self.assertRaises(KeyError):
            API.skeleton("sendHologram")

    def test_version_lists_added_symbols(self):
        r = API.version("10.4")
        self.assertEqual(r["date"], "2026-11-09")
        self.assertIn("sendWidget", r["symbols_mentioned_in_added_items"])
        self.assertIsNone(API.version("1.0.0"))
        self.assertEqual(API.releases()[0]["version"], API.cat["meta"]["bot_api_version"])

    def test_cli_runs(self):
        for argv in (["show", "answerPreCheckoutQuery"], ["search", "refund"], ["version", "10.3"],
                     ["accepts", "reply_markup"], ["skeleton", "sendPaidMedia"], ["meta"], ["versions"],
                     ["--json", "show", "Update"], ["diff"]):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(lookup.main(argv), 0, argv)
            self.assertTrue(buf.getvalue().strip(), argv)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lookup.main(["show", "definitelyNotAMethod"]), 1)


class PayloadValidation(unittest.TestCase):
    def ok(self, method, params):
        rep = V.check_request(method, params)
        self.assertTrue(rep.ok, rep.errors)
        return rep

    def bad(self, method, params, needle):
        rep = V.check_request(method, params)
        self.assertFalse(rep.ok)
        self.assertTrue(any(needle in e for e in rep.errors), rep.errors)
        return rep

    def test_minimal_send_message(self):
        self.ok("sendMessage", {"chat_id": 1, "text": "hi"})
        self.ok("sendMessage", {"chat_id": "@channel", "text": "hi"})

    def test_unknown_method_and_field(self):
        self.bad("sendMesage", {}, "unknown method")
        self.bad("sendMessage", {"chat_id": 1, "text": "x", "parse_mod": "HTML"}, "unknown parameter 'parse_mod'")

    def test_missing_required(self):
        self.bad("sendMessage", {"chat_id": 1}, "missing required parameter 'text'")
        self.bad("answerPreCheckoutQuery", {"ok": True}, "pre_checkout_query_id")

    def test_basic_type_mismatches(self):
        self.bad("sendMessage", {"chat_id": 1.5, "text": "x"}, "fits none")
        self.bad("sendMessage", {"chat_id": 1, "text": 5}, "expected String")
        self.bad("sendMessage", {"chat_id": 1, "text": "x", "disable_notification": "yes"}, "expected Boolean")
        self.bad("sendMessage", {"chat_id": True, "text": "x"}, "fits none")
        self.bad("sendMessage", {"chat_id": 1, "text": "x", "reply_markup": None}, "null")

    def test_integer_as_string_is_a_warning(self):
        rep = self.ok("refundStarPayment", {"user_id": "123", "telegram_payment_charge_id": "c"})
        self.assertTrue(rep.warnings)

    def test_nested_objects_and_arrays(self):
        self.ok("sendInvoice", {"chat_id": 1, "title": "t", "description": "d", "payload": "p",
                                "currency": "XTR", "prices": [{"label": "Pro", "amount": 100}]})
        self.bad("sendInvoice", {"chat_id": 1, "title": "t", "description": "d", "payload": "p",
                                 "currency": "XTR", "prices": {"label": "Pro", "amount": 100}}, "expected Array")
        self.bad("sendInvoice", {"chat_id": 1, "title": "t", "description": "d", "payload": "p",
                                 "currency": "XTR", "prices": [{"label": "Pro"}]}, "missing required field 'amount'")

    def test_reply_markup_alternatives(self):
        self.ok("sendMessage", {"chat_id": 1, "text": "x", "reply_markup": {"remove_keyboard": True}})
        self.ok("sendMessage", {"chat_id": 1, "text": "x",
                                "reply_markup": {"inline_keyboard": [[{"text": "a", "callback_data": "a"}]]}})
        self.bad("sendMessage", {"chat_id": 1, "text": "x", "reply_markup": {"inline_keyboard": [{"text": "a"}]}},
                 "fits none")
        rep = V.check_request("sendMessage", {"chat_id": 1, "text": "x", "reply_markup": {"remove_keyboard": True}})
        self.assertTrue(any("validate_keyboard.py" in n for n in rep.notes))

    def test_union_discriminator_selects_exactly_one(self):
        self.ok("setMessageReaction", {"chat_id": 1, "message_id": 2, "reaction": [{"type": "emoji", "emoji": "👍"}]})
        self.bad("setMessageReaction", {"chat_id": 1, "message_id": 2, "reaction": [{"type": "sticker"}]},
                 "is not a ReactionType")
        self.bad("setMessageReaction", {"chat_id": 1, "message_id": 2, "reaction": [{"emoji": "👍"}]},
                 "needs 'type'")
        self.bad("setMessageReaction", {"chat_id": 1, "message_id": 2,
                                        "reaction": [{"type": "custom_emoji", "emoji": "👍"}]},
                 "custom_emoji_id")
        self.ok("setMyCommands", {"commands": [{"command": "start", "description": "Start"}],
                                  "scope": {"type": "all_private_chats"}})

    def test_shared_discriminator_resolved_structurally(self):
        cached = {"type": "photo", "id": "1", "photo_file_id": "AgAD"}
        by_url = {"type": "photo", "id": "2", "photo_url": "https://e.x/p.jpg", "thumbnail_url": "https://e.x/t.jpg"}
        self.ok("answerInlineQuery", {"inline_query_id": "q", "results": [cached, by_url]})
        self.bad("answerInlineQuery", {"inline_query_id": "q", "results": [{"type": "photo", "id": "3"}]},
                 "not any InlineQueryResult member")

    def test_input_media_and_files(self):
        self.ok("sendMediaGroup", {"chat_id": 1, "media": [{"type": "photo", "media": "attach://a"},
                                                           {"type": "photo", "media": "AgAD"}]})
        self.bad("sendPhoto", {"chat_id": 1, "photo": {"path": "a.jpg"}}, "InputFile")

    def test_conditional_note_only_when_no_alternative(self):
        rep = V.check_request("editMessageText", {"chat_id": 1, "message_id": 2, "text": "x"})
        self.assertFalse(any("rich_message" in n for n in rep.notes), rep.notes)

    def test_true_type(self):
        self.bad("sendMessage", {"chat_id": 1, "text": "x", "reply_markup": {"remove_keyboard": False}}, "fits none")

    def test_check_object_update(self):
        upd = {"update_id": 1, "message": {"message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"},
                                           "text": "hi"}}
        self.assertTrue(V.check_object("Update", upd).ok)
        upd["message"]["chat"]["tpye"] = "private"
        self.assertFalse(V.check_object("Update", upd).ok)

    def test_rich_text_accepts_strings_and_arrays(self):
        t = next(f for f in API.cat["types"]["RichBlockParagraph"]["fields"] if f["name"] != "type")
        self.assertEqual(t["types"][0]["name"], "RichText")
        self.assertTrue(V.check_object("RichText", "plain").ok)
        self.assertTrue(V.check_object("RichText", ["a", "b"]).ok)

    def test_repository_payloads(self):
        """Every request in examples/payloads/ is structurally valid, except known reported ones."""
        found = set()
        for path in sorted(glob.glob(os.path.join(_paths.EXAMPLES, "payloads", "*.json"))):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            for method, params in vp.steps_from(doc, None):
                rep = V.check_request(method, params)
                if not rep.ok:
                    found.add((os.path.basename(path), method))
        self.assertLessEqual(found, KNOWN_PAYLOAD_MISMATCHES, found - KNOWN_PAYLOAD_MISMATCHES)

    def test_repository_update_fixtures(self):
        for path in sorted(glob.glob(os.path.join(_paths.EXAMPLES, "fixtures", "*.json"))):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            if "update_id" not in doc:
                continue  # API responses, not updates
            rep = V.check_object("Update", doc)
            self.assertTrue(rep.ok, (os.path.basename(path), rep.errors))

    def test_cli_header_says_structural(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = vp.main([os.path.join(_paths.EXAMPLES, "payloads", "r07-wallet.json")])
        self.assertEqual(code, 0)
        self.assertIn("Not full semantic validation", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
