"""Rich messages as JSON blocks: tgkit.rich builders against the catalog, and validate_rich on blocks."""
import inspect
import unittest

import _paths
import validate_payload as vp
import validate_rich as vr
from tgkit import rich

CAT = _paths.load("data", "bot-api", "catalog.json")
TYPES = CAT["types"]
V = vp.Validator(CAT)

# A valid value for each catalog field type the builders take (and per field name where the
# catalog limits the value in prose).
SAMPLES = {
    "String": "x", "Integer": 1, "True": True, "RichText": "Text",
    "Array of InputRichBlock": [{"type": "paragraph", "text": "inner"}],
    "Array of InputRichBlockListItem": [{"blocks": [{"type": "paragraph", "text": "item"}]}],
    "Array of Array of RichBlockTableCell": [[{"text": "c", "align": "left", "valign": "middle"}]],
    "Array of RichMessageButton": [{"text": "Open", "url": "https://t.me/example"}],
    "RichMessageButton": {"text": "Open", "url": "https://t.me/example"},
    "RichBlockCaption": {"text": "Caption", "credit": "Credit"},
    "Location": {"latitude": 59.91, "longitude": 10.75},
    "User": {"id": 1001, "is_bot": False, "first_name": "Ann"},
    "WebAppInfo": {"url": "https://example.com/app"},
    "LoginUrl": {"url": "https://example.com/login"},
    "SwitchInlineQueryChosenChat": {"query": "x", "allow_user_chats": True},
    "CopyTextButton": {"text": "x"},
    "DisabledButton": {},
}
BY_NAME = {"align": "left", "valign": "middle", "style": "primary", "type": "1", "size": 2, "zoom": 12,
           "width": 600, "height": 300, "callback_data": "x", "url": "https://t.me/example"}
MEDIA = {"InputMediaPhoto": "photo", "InputMediaVideo": "video", "InputMediaAnimation": "animation",
         "InputMediaAudio": "audio", "InputMediaDocument": "document", "InputMediaVoiceNote": "voice_note"}
BUTTON_ACTIONS = ("url", "callback_data", "web_app", "login_url", "switch_inline_query",
                  "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", "copy_text", "disabled")


def catalog_fields(name):
    """Field name -> required, without the constant `type` discriminator."""
    return {f["name"]: f["required"] for f in TYPES[name]["fields"] if not f.get("const")}


def builder_fields(fn):
    """Parameter name -> required (no default) of a builder."""
    return {p.name: p.default is inspect.Parameter.empty for p in inspect.signature(fn).parameters.values()}


def type_const(name):
    return next((f["const"] for f in TYPES[name]["fields"] if f["name"] == "type" and f.get("const")), None)


def sample(field):
    if field["name"] in BY_NAME and field["type"] in ("String", "Integer"):
        return BY_NAME[field["name"]]
    if field["type"] in MEDIA:
        return "BQACAgIAAxkBAAEBfile"   # a file_id; the builder wraps it into InputMedia*
    return SAMPLES[field["type"]]


def build(name, fn, *, optional):
    kwargs = {f["name"]: sample(f) for f in TYPES[name]["fields"]
              if not f.get("const") and (f["required"] or optional)}
    if name in ("InputRichBlockCollage", "InputRichBlockSlideshow"):
        kwargs["blocks"] = [{"type": "photo", "photo": {"type": "photo", "media": "AgACAgIAAxkBAAEBphoto"}}]
    if name == "RichMessageButton":  # exactly one action, so never "required fields only"
        kwargs = {k: v for k, v in kwargs.items() if k not in BUTTON_ACTIONS}
        kwargs["url"] = BY_NAME["url"]
    return fn(**kwargs)


def object_types_used_by_input_blocks():
    """Rich-messages object types (not unions) reachable from InputRichBlock members' fields."""
    seen, todo = set(), list(TYPES["InputRichBlock"]["subtypes"])
    while todo:
        for f in TYPES[todo.pop()]["fields"]:
            for t in f["types"]:
                sym = TYPES.get(t["name"])
                if sym and sym["section"] == "Rich messages" and not sym["subtypes"] and t["name"] not in seen:
                    seen.add(t["name"])
                    todo.append(t["name"])
    return seen


ALL = {**rich.BLOCKS, **rich.TEXTS, **rich.PARTS}


class BuildersMirrorTheCatalog(unittest.TestCase):
    def test_every_input_block_has_a_builder(self):
        self.assertEqual(sorted(rich.BLOCKS), sorted(TYPES["InputRichBlock"]["subtypes"]))

    def test_every_rich_text_has_a_builder(self):
        # RichText is shared by sent and received messages: the catalog has no InputRichText.
        self.assertNotIn("InputRichText", TYPES)
        self.assertEqual(sorted(rich.TEXTS), sorted(TYPES["RichText"]["subtypes"]))

    def test_every_object_an_input_block_holds_has_a_builder(self):
        self.assertEqual(sorted(rich.PARTS), sorted(object_types_used_by_input_blocks() - set(rich.BLOCKS)))

    def test_builder_parameters_are_the_catalog_fields(self):
        for name, fn in ALL.items():
            with self.subTest(name):
                self.assertEqual(builder_fields(fn), catalog_fields(name))

    def test_builders_write_the_type_constant_and_pass_the_payload_validator(self):
        for name, fn in ALL.items():
            for optional in (False, True):
                with self.subTest(name, optional=optional):
                    out = build(name, fn, optional=optional)
                    self.assertIsInstance(out, dict)
                    self.assertEqual(out.get("type") if type_const(name) else None, type_const(name))
                    rep = V.check_object(name, out)
                    self.assertEqual(rep.errors, [])

    def test_every_button_action_builds_a_valid_button(self):
        fields = {f["name"]: f for f in TYPES["RichMessageButton"]["fields"]}
        for action in BUTTON_ACTIONS:
            with self.subTest(action):
                value = sample(fields[action])
                btn = rich.message_button("Open", **{action: value})
                self.assertEqual(V.check_object("RichMessageButton", btn).errors, [])
                self.assertEqual(len(set(btn) & set(BUTTON_ACTIONS)), 1)
        with self.assertRaises(ValueError):
            rich.message_button("Open", url="https://t.me/example", callback_data="x")
        with self.assertRaises(ValueError):
            rich.message_button("Open")

    def test_media_builders_take_a_file_reference_or_an_input_media_object(self):
        photo = rich.photo_block("AgACAgIAAxkBAAEBphoto", "Bridge at dawn")
        self.assertEqual(photo, {"type": "photo", "photo": {"type": "photo", "media": "AgACAgIAAxkBAAEBphoto"},
                                 "caption": {"text": "Bridge at dawn"}})
        spoiler = {"type": "photo", "media": "AgACAgIAAxkBAAEBphoto", "has_spoiler": True}
        self.assertIs(rich.photo_block(spoiler)["photo"], spoiler)
        credited = rich.block_caption("Bridge at dawn", credit="City archive")
        self.assertIs(rich.photo_block("AgAC", credited)["caption"], credited)

    def test_false_and_none_flags_are_left_out(self):
        self.assertEqual(rich.details_block("More", [rich.paragraph_block("x")], is_open=False),
                         {"type": "details", "summary": "More", "blocks": [{"type": "paragraph", "text": "x"}]})
        self.assertEqual(rich.map_block({"latitude": 0.0, "longitude": 0.0}, zoom=0)["zoom"], 0)

    def test_a_message_from_every_block_builder_is_valid(self):
        blocks = [build(name, fn, optional=True) for name, fn in rich.BLOCKS.items()
                  if name != "InputRichBlockThinking"]
        params = {"chat_id": 1001, "rich_message": {"blocks": blocks}}
        self.assertEqual(V.check_request("sendRichMessage", params).errors, [])
        self.assertEqual(vr.validate(params)[0], [])
        draft = {"chat_id": 1001, "draft_id": 7, "rich_message": {"blocks": [
            rich.thinking_block("Reading the report"), rich.paragraph_block("Partial answer")]}}
        self.assertEqual(V.check_request("sendRichMessageDraft", draft).errors, [])
        self.assertEqual(vr.validate(draft, draft=True)[0], [])

    def test_convenience_helpers_keep_their_output(self):
        self.assertEqual(rich.cell("Total", header=True, align="right"),
                         {"text": "Total", "align": "right", "valign": "middle", "is_header": True})
        self.assertEqual(rich.button_row([rich.rich_button("Pay", callback_data="pay", style="success")]),
                         {"type": "buttons", "buttons": [{"text": "Pay", "callback_data": "pay", "style": "success"}],
                          "align": "left"})
        self.assertEqual(rich.expandable_quote("Long", "Ann"),
                         {"type": "expandable_blockquote", "blocks": [{"type": "paragraph", "text": "Long"}],
                          "credit": "Ann"})


if __name__ == "__main__":
    unittest.main()
