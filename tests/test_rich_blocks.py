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


def errors(blocks, **kw):
    return vr.validate({"blocks": blocks}, **kw)[0]


def warnings(blocks, **kw):
    return vr.validate({"blocks": blocks}, **kw)[1]


def nested(depth, leaf="x"):
    """A RichText `depth` formatting levels deep."""
    rt = leaf
    for _ in range(depth):
        rt = rich.bold(rt)
    return rt


PHOTO = "AgACAgIAAxkBAAEBphoto"


class ValidateRichBlocks(unittest.TestCase):
    """validate_rich checks a blocks message as deeply as an HTML one; each rule quotes the catalog."""

    def assertFlags(self, found, *needles):
        for needle in needles:
            self.assertTrue(any(needle in e for e in found), (needle, found))

    def test_the_quoted_rules_are_still_the_catalog_text(self):
        for key, (type_name, field, quote) in vr.QUOTES.items():
            with self.subTest(key):
                sym = TYPES[type_name]
                text = sym["description"] if field is None else \
                    next(f["description"] for f in sym["fields"] if f["name"] == field)
                self.assertIn(quote, text.replace("“", '"').replace("”", '"'))

    def test_block_types_come_from_the_catalog(self):
        self.assertFlags(errors([{"type": "image", "src": "https://example.com/a.png"}]),
                         "'image' is not an InputRichBlock type")
        self.assertEqual(errors([rich.paragraph_block("ok")]), [])

    def test_block_fields_follow_the_catalog(self):
        old_quote = {"type": "expandable_blockquote", "text": "Before 10.5 a quote held text"}
        self.assertFlags(errors([old_quote]), "has no field 'text'", "missing required field 'blocks'")
        self.assertFlags(errors([{"type": "heading", "text": "Title"}]), "missing required field 'size'")

    def test_rich_text_types_and_fields_come_from_the_catalog(self):
        self.assertFlags(errors([rich.paragraph_block({"type": "link", "text": "x"})]),
                         "'link' is not a RichText type")
        self.assertFlags(errors([rich.paragraph_block({"type": "url", "text": "x"})]), "missing required field 'url'")
        self.assertEqual(errors([rich.paragraph_block(["a ", rich.url("link", "https://t.me")])]), [])

    def test_nesting_depth_counts_formatting_and_blocks(self):
        self.assertEqual(errors([rich.paragraph_block(nested(15))]), [])     # block 1 + 15 levels
        self.assertFlags(errors([rich.paragraph_block(nested(16))]), "depth: 17 > 16")
        quote = rich.blockquote_block([rich.paragraph_block(nested(15))])   # one more block level
        self.assertFlags(errors([quote]), "depth: 17 > 16")

    def test_heading_size(self):
        self.assertFlags(errors([rich.heading_block("Title", 7)]), "size 7: 1-6")
        self.assertEqual(errors([rich.heading_block("Title", 6)]), [])

    def test_list_item_label_type(self):
        item = rich.list_item([rich.paragraph_block("x")], type="x")
        self.assertFlags(errors([rich.list_block([item])]), "type 'x'")
        ok = rich.list_item([rich.paragraph_block("x")], value=3, type="i")
        self.assertEqual(errors([rich.list_block([ok])]), [])

    def test_table_cells_and_columns(self):
        bad_align = [[{"text": "x", "align": "middle", "valign": "middle"}]]
        self.assertFlags(errors([rich.table_block(bad_align)]), "align 'middle'")
        self.assertFlags(errors([rich.table_block([[{"text": "x", "align": "left"}]])]),
                         "missing required field 'valign'")
        tall = rich.table_cell("tall", align="left", valign="top", rowspan=2)
        rows = [[tall], [rich.table_cell(str(i), align="left", valign="top") for i in range(20)]]
        self.assertFlags(errors([rich.table_block(rows)]), "21 columns > 20")
        rows[1].pop()
        self.assertEqual(errors([rich.table_block(rows)]), [])

    def test_map_limits(self):
        here = {"latitude": 59.91, "longitude": 10.75}
        self.assertFlags(errors([rich.map_block(here, zoom=25)]), "zoom 25: 0-24")
        self.assertFlags(errors([rich.map_block(here, width=10001, height=1000)]), "width 10001: 0-10000")
        self.assertFlags(errors([rich.map_block(here, width=9000, height=2000)]), "10000 in total")
        self.assertFlags(errors([rich.map_block(here, width=2100, height=100)]), "ratio")
        self.assertEqual(errors([rich.map_block(here, zoom=14, width=600, height=300)]), [])

    def test_media_object_matches_its_block(self):
        wrong = {"type": "photo", "photo": {"type": "video", "media": PHOTO}}
        self.assertFlags(errors([wrong]), "a photo block takes InputMediaPhoto")
        ignored = rich.photo_block({"type": "photo", "media": PHOTO, "caption": "lost"})
        self.assertFlags(warnings([ignored]), "Caption is ignored")

    def test_collage_and_slideshow_hold_photos_and_videos(self):
        self.assertFlags(warnings([rich.collage_block([rich.paragraph_block("x")])]), "photos and videos")
        self.assertEqual(warnings([rich.slideshow_block([rich.photo_block(PHOTO), rich.video_block("BAAC")])]), [])

    def test_media_field_is_for_html_and_markdown(self):
        found = vr.validate({"blocks": [rich.photo_block(PHOTO)],
                             "media": [{"id": "p1", "media": {"type": "photo", "media": PHOTO}}]})[1]
        self.assertFlags(found, "markdown or html")

    def test_text_length_counts_every_text_once(self):
        long = "x" * 32769
        self.assertFlags(errors([rich.details_block(long, [rich.paragraph_block("x")])]), "chars: 32770 > 32768")
        self.assertFlags(errors([rich.paragraph_block(rich.custom_emoji("5368324170671202286", long))]), "chars")
        self.assertFlags(errors([rich.mathematical_expression_block(long)]), "chars")
        self.assertFlags(errors([rich.buttons_block([rich.message_button(long, callback_data="go")])]), "chars")
        caption = "x" * 20000   # counted once, not twice
        self.assertEqual(errors([rich.table(["a"], [], caption=caption)]), [])

    def test_button_rules_match_the_html_checks(self):
        many = rich.buttons_block([rich.message_button(str(i), callback_data=str(i)) for i in range(9)])
        self.assertFlags(errors([many]), "1-8 buttons")
        self.assertFlags(errors([rich.buttons_block([{"text": "Go", "url": "https://t.me", "style": "link"}])]),
                         "'link' is allowed only for callback buttons")
        self.assertFlags(errors([rich.buttons_block([{"text": "Go", "callback_data": "x" * 65}])]), "65 bytes")
        self.assertFlags(errors([rich.buttons_block([{"text": rich.bold("Go"), "callback_data": "go"}])]),
                         "plain text, custom emoji and date-time")
        two = {"text": "Go", "callback_data": "go", "url": "https://t.me"}
        self.assertFlags(errors([rich.paragraph_block(["Pay ", rich.button(two)])]), "EXACTLY one action")
        self.assertFlags(errors([rich.buttons_block([rich.message_button("Go", url="https://t.me")], "middle")]),
                         "align must be left, center or right")


if __name__ == "__main__":
    unittest.main()
