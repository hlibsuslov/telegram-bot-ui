"""Rich messages as JSON blocks: tgkit.rich builders against the catalog, one document as Rich HTML and
as blocks, and validate_rich on blocks."""
import inspect
import re
import unittest
from html.parser import HTMLParser

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

    def test_document_block_keeps_the_file_ref_keyword(self):
        """Before the catalog-mirrored builders, document_block took file_ref=; callers keep working."""
        self.assertEqual(rich.document_block(file_ref="BQACdemo", caption="Spec"),
                         rich.document_block("BQACdemo", caption="Spec"))
        with self.assertRaises(TypeError):
            rich.document_block("BQACdemo", file_ref="BQACother")
        self.assertNotIn("file_ref", builder_fields(rich.document_block))   # the catalog field stays the name


# ---- parity: one document as Rich HTML and as blocks ---------------------------------------------
#
# "Equivalent" means equal outlines. An outline is the list of blocks in document order; each block is
# (type constant, properties, content):
#   * type constant: the InputRichBlock `type` (HTML tag -> type from the catalog's "corresponding to the
#     HTML tag" text, checked below);
#   * properties: what both forms state - heading size, pre language, list item checkbox / value / label
#     type, table flags and caption, cell header / align / valign / spans, quote credit, details summary
#     and open state, media file (a tg://photo?id= link resolved through InputRichMessage.media) with its
#     caption and credit, button row align and each button's label, action field, value and style;
#   * content: text runs, or the nested block outlines of a container.
# A text run is (text, styles): styles is the set of enclosing RichText types (a link adds ("url", href)).
# Runs are compared after collapsing whitespace, merging neighbours with equal styles and trimming the ends.
# Inline content directly inside a block container (an <li>) is one paragraph: list items hold blocks.
# HTML tag and attribute names: core.telegram.org/bots/api#rich-html-style (Official, checked 2026-11-25).

INLINE_TAGS = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline", "ins": "underline",
               "s": "strikethrough", "strike": "strikethrough", "del": "strikethrough", "tg-spoiler": "spoiler",
               "mark": "marked", "sub": "subscript", "sup": "superscript", "code": "code"}
TAG_TO_BLOCK = {"p": "paragraph", **{f"h{n}": "heading" for n in range(1, 7)}, "pre": "pre", "footer": "footer",
                "hr": "divider", "ul": "list", "ol": "list", "blockquote": "blockquote", "aside": "pullquote",
                "table": "table", "details": "details", "img": "photo", "video": "video", "audio": "audio",
                "tg-document": "document", "tg-button-row": "buttons", "tg-math-block": "mathematical_expression",
                "tg-map": "map", "tg-collage": "collage", "tg-slideshow": "slideshow", "tg-thinking": "thinking"}
MEDIA_TAGS = {"img", "video", "audio", "tg-document"}
VOID_TAGS = {"hr", "br", "img", "input"}
BUTTON_FIELDS = {"callback_data": "data", "url": "url", "copy_text": "text"}  # tg-button type -> attribute


class _Dom(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": None, "attrs": {}, "kids": []}
        self.stack = [self.root]
        self.feed(html)
        self.close()
        assert len(self.stack) == 1, f"<{self.stack[-1]['tag']}> is not closed"

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "kids": []}
        self.stack[-1]["kids"].append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1]["kids"].append({"tag": tag, "attrs": dict(attrs), "kids": []})

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        assert self.stack[-1]["tag"] == tag, f"</{tag}> closes <{self.stack[-1]['tag']}>"
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1]["kids"].append(data)


def _tidy(runs):
    merged = []
    for s, styles in runs:
        s = re.sub(r"\s+", " ", s)
        if merged and merged[-1][1] == styles:
            merged[-1] = (merged[-1][0] + s, styles)
        elif s:
            merged.append((s, styles))
    if merged:
        merged[0] = (merged[0][0].lstrip(), merged[0][1])
        merged[-1] = (merged[-1][0].rstrip(), merged[-1][1])
    return [r for r in merged if r[0]]


def _styled(styles, extra):
    return tuple(sorted(set(styles) | {extra}, key=str))


def _html_runs(kids, styles=()):
    out = []
    for n in kids:
        if isinstance(n, str):
            out.append((n, styles))
        elif n["tag"] in INLINE_TAGS:
            out += _html_runs(n["kids"], _styled(styles, INLINE_TAGS[n["tag"]]))
        elif n["tag"] == "a" and "href" in n["attrs"]:
            out += _html_runs(n["kids"], _styled(styles, ("url", n["attrs"]["href"])))
        else:
            raise AssertionError(f"<{n['tag']}> is not inline text")
    return out


def _is_inline(n):
    return isinstance(n, str) or n["tag"] in INLINE_TAGS or (n["tag"] == "a" and "href" in n["attrs"])


def _split(kids, tag):
    """(the children named `tag`, the rest)."""
    hit = [k for k in kids if isinstance(k, dict) and k["tag"] == tag]
    return hit, [k for k in kids if not (isinstance(k, dict) and k["tag"] == tag)]


def _html_blocks(kids, media):
    out, inline = [], []

    def flush():
        runs = _tidy(_html_runs(inline))
        if runs:
            out.append(("paragraph", {}, runs))
        inline.clear()
    for n in kids:
        if _is_inline(n):
            inline.append(n)
            continue
        flush()
        out.append(_html_block(n, media))
    flush()
    return out


def _runs_of(nodes):
    return _tidy(_html_runs(nodes[0]["kids"])) if nodes else []


def _html_media(n, media, caption=None):
    src = n["attrs"].get("src", "")
    m = re.match(r"tg://\w+\?id=(.+)$", src)
    ref = media[m.group(1)]["media"]["media"] if m else src
    cite, text = _split(caption["kids"], "cite") if caption else ([], [])
    return (TAG_TO_BLOCK[n["tag"]], {"media": ref, "caption": _tidy(_html_runs(text)), "credit": _runs_of(cite)}, [])


def _html_cell(n):
    a = n["attrs"]
    return {"is_header": n["tag"] == "th", "align": a.get("align"), "valign": a.get("valign"),
            "colspan": int(a.get("colspan", 1)), "rowspan": int(a.get("rowspan", 1)),
            "text": _tidy(_html_runs(n["kids"]))}


def _html_block(n, media):
    tag, a, kids = n["tag"], n["attrs"], n["kids"]
    if tag not in TAG_TO_BLOCK and tag != "figure":
        raise AssertionError(f"<{tag}> has no block in this outline")
    kind = TAG_TO_BLOCK.get(tag)
    if kind == "heading":
        return kind, {"size": int(tag[1])}, _tidy(_html_runs(kids))
    if kind in ("paragraph", "footer"):
        return kind, {}, _tidy(_html_runs(kids))
    if kind == "pre":
        (code,), _ = _split(kids, "code")
        return kind, {"language": code["attrs"].get("class", "").removeprefix("language-") or None}, \
            _tidy(_html_runs(code["kids"]))
    if kind == "divider":
        return kind, {}, []
    if kind == "list":
        items = []
        for li in _split(kids, "li")[0]:
            boxes, rest = _split(li["kids"], "input")
            props = {"has_checkbox": bool(boxes), "is_checked": bool(boxes) and "checked" in boxes[0]["attrs"],
                     "value": int(li["attrs"]["value"]) if "value" in li["attrs"] else None,
                     "type": li["attrs"].get("type")}
            items.append((props, _html_blocks(rest, media)))
        return kind, {}, items
    if kind == "blockquote":
        cite, rest = _split(kids, "cite")
        return ("expandable_blockquote" if "expandable" in a else kind), {"credit": _runs_of(cite)}, \
            _html_blocks(rest, media)
    if kind == "details":
        summary, rest = _split(kids, "summary")
        return kind, {"is_open": "open" in a, "summary": _runs_of(summary)}, _html_blocks(rest, media)
    if kind == "table":
        caption, rest = _split(kids, "caption")
        rows = [[_html_cell(c) for c in tr["kids"] if isinstance(c, dict)] for tr in _split(rest, "tr")[0]]
        flags = {f: f[3:] in a for f in ("is_bordered", "is_striped", "is_compact")}
        return kind, {**flags, "caption": _runs_of(caption)}, rows
    if tag == "figure":
        caption, rest = _split(kids, "figcaption")
        (item,) = [k for k in rest if isinstance(k, dict)]
        return _html_media(item, media, caption[0] if caption else None)
    if tag in MEDIA_TAGS:
        return _html_media(n, media)
    if kind == "buttons":
        row = []
        for b in _split(kids, "tg-button")[0]:
            field = b["attrs"]["type"]
            row.append(("".join(s for s, _ in _tidy(_html_runs(b["kids"]))), field,
                        b["attrs"][BUTTON_FIELDS[field]], b["attrs"].get("style")))
        return kind, {"align": a.get("align")}, row
    raise AssertionError(f"<{tag}> is not in the parity document's outline yet")


def html_outline(html, media=()):
    by_id = {m["id"]: m for m in media}
    return _html_blocks(_Dom(html).root["kids"], by_id)


def _rt_runs(rt, styles=()):
    if rt is None:
        return []
    if isinstance(rt, str):
        return [(rt, styles)]
    if isinstance(rt, list):
        return [r for x in rt for r in _rt_runs(x, styles)]
    style = ("url", rt["url"]) if rt["type"] == "url" else rt["type"]
    return _rt_runs(rt.get("text"), _styled(styles, style))


def _runs(rt):
    return _tidy(_rt_runs(rt))


def _block_outline(b):
    t = b["type"]
    if t == "heading":
        return t, {"size": b["size"]}, _runs(b["text"])
    if t in ("paragraph", "footer"):
        return t, {}, _runs(b["text"])
    if t == "pre":
        return t, {"language": b.get("language")}, _runs(b["text"])
    if t == "divider":
        return t, {}, []
    if t == "list":
        return t, {}, [({"has_checkbox": bool(i.get("has_checkbox")), "is_checked": bool(i.get("is_checked")),
                         "value": i.get("value"), "type": i.get("type")}, blocks_outline(i["blocks"]))
                       for i in b["items"]]
    if t in ("blockquote", "expandable_blockquote"):
        return t, {"credit": _runs(b.get("credit"))}, blocks_outline(b["blocks"])
    if t == "details":
        return t, {"is_open": bool(b.get("is_open")), "summary": _runs(b["summary"])}, blocks_outline(b["blocks"])
    if t == "table":
        flags = {f: bool(b.get(f)) for f in ("is_bordered", "is_striped", "is_compact")}
        rows = [[{"is_header": bool(c.get("is_header")), "align": c["align"], "valign": c["valign"],
                  "colspan": c.get("colspan", 1), "rowspan": c.get("rowspan", 1), "text": _runs(c.get("text"))}
                 for c in row] for row in b["cells"]]
        return t, {**flags, "caption": _runs(b.get("caption"))}, rows
    if t in ("photo", "video", "audio", "document", "animation", "voice_note"):
        cap = b.get("caption") or {}
        return t, {"media": b[t]["media"], "caption": _runs(cap.get("text")), "credit": _runs(cap.get("credit"))}, []
    if t == "buttons":
        row = []
        for btn in b["buttons"]:
            (field,) = [k for k in BUTTON_FIELDS if k in btn]
            value = btn[field]["text"] if field == "copy_text" else btn[field]
            row.append(("".join(s for s, _ in _runs(btn["text"])), field, value, btn.get("style")))
        return t, {"align": b.get("align")}, row
    raise AssertionError(f"{t!r} is not in the parity document's outline yet")


def blocks_outline(blocks):
    return [_block_outline(b) for b in blocks]


CHART = "AgACAgIAAxkBAAEBchart"
CHANGELOG = "https://example.com/changelog"
DOC_HTML = (
    "<h1>Release 2.4</h1>"
    "<p>Payments are <b>faster</b>, refunds <i>arrive in <b>minutes</b></i>, and the "
    f'<a href="{CHANGELOG}">changelog</a> lists <code>refund_id</code>. <u>Old links</u> <s>expire</s> keep '
    "working; <mark>check the limits</mark> before the <tg-spoiler>launch date</tg-spoiler>.</p>"
    "<h2>Checklist</h2>"
    '<ul><li><input type="checkbox" checked>Migrate the webhook</li>'
    '<li><input type="checkbox">Rotate the signing key</li></ul>'
    '<ol><li value="1" type="1">Back up the database</li><li value="2" type="1">Deploy</li></ol>'
    "<table bordered compact><caption>Median refund time</caption>"
    '<tr><th align="left" valign="middle">Method</th><th align="right" valign="middle">Minutes</th></tr>'
    '<tr><td align="left" valign="middle">Card</td><td align="right" valign="middle">4</td></tr>'
    '<tr><td align="left" valign="middle">Stars</td><td align="right" valign="middle">1</td></tr></table>'
    "<blockquote><p>Refunds no longer need a support ticket.</p><cite>Payments team</cite></blockquote>"
    "<details><summary>What changed for <b>admins</b></summary>"
    "<p>Refunds over 100 USD still need a second approval.</p></details>"
    '<figure><img src="tg://photo?id=chart"><figcaption>Refund time by week<cite>Internal metrics</cite>'
    "</figcaption></figure>"
    "<hr/>"
    '<tg-button-row align="center"><tg-button type="callback_data" data="release:ack" style="primary">Got it'
    f'</tg-button><tg-button type="url" url="{CHANGELOG}">Full changelog</tg-button></tg-button-row>'
    "<footer>Questions: reply to this message.</footer>"
)
DOC_MEDIA = [{"id": "chart", "media": {"type": "photo", "media": CHART}}]


def doc_blocks():
    r = rich
    return [
        r.heading_block("Release 2.4", 1),
        r.paragraph_block(["Payments are ", r.bold("faster"), ", refunds ", r.italic(["arrive in ", r.bold("minutes")]),
                           ", and the ", r.url("changelog", CHANGELOG), " lists ", r.code("refund_id"), ". ",
                           r.underline("Old links"), " ", r.strikethrough("expire"), " keep working; ",
                           r.marked("check the limits"), " before the ", r.spoiler("launch date"), "."]),
        r.heading_block("Checklist", 2),
        r.list_block([r.list_item([r.paragraph_block("Migrate the webhook")], has_checkbox=True, is_checked=True),
                      r.list_item([r.paragraph_block("Rotate the signing key")], has_checkbox=True)]),
        r.list_block([r.list_item([r.paragraph_block("Back up the database")], value=1, type="1"),
                      r.list_item([r.paragraph_block("Deploy")], value=2, type="1")]),
        r.table(["Method", "Minutes"], [["Card", "4"], ["Stars", "1"]], compact=True, numeric_cols=frozenset({1}),
                caption="Median refund time"),
        r.blockquote_block([r.paragraph_block("Refunds no longer need a support ticket.")], credit="Payments team"),
        r.details_block(["What changed for ", r.bold("admins")],
                        [r.paragraph_block("Refunds over 100 USD still need a second approval.")]),
        r.photo_block(CHART, r.block_caption("Refund time by week", credit="Internal metrics")),
        r.divider_block(),
        r.buttons_block([r.message_button("Got it", callback_data="release:ack", style="primary"),
                         r.message_button("Full changelog", url=CHANGELOG)], align="center"),
        r.footer_block("Questions: reply to this message."),
    ]


class HtmlAndBlocksParity(unittest.TestCase):
    def test_the_tag_map_is_the_catalog_text(self):
        consts = {type_const(n): n for n in TYPES["InputRichBlock"]["subtypes"]}
        for tag, kind in TAG_TO_BLOCK.items():
            with self.subTest(tag):
                self.assertIn(f"<{tag}", TYPES[consts[kind]]["description"])
        self.assertIn("expandable", TYPES[consts["expandable_blockquote"]]["description"])

    def test_one_document_as_html_and_as_blocks_has_the_same_outline(self):
        html, blocks = html_outline(DOC_HTML, DOC_MEDIA), blocks_outline(doc_blocks())
        self.assertEqual([b[0] for b in html], ["heading", "paragraph", "heading", "list", "list", "table",
                                                "blockquote", "details", "photo", "divider", "buttons", "footer"])
        for i, (h, b) in enumerate(zip(html, blocks)):
            with self.subTest(i, block=h[0]):
                self.assertEqual(h, b)
        self.assertEqual(len(html), len(blocks))

    def test_both_forms_are_valid(self):
        self.assertEqual(vr.validate({"html": DOC_HTML, "media": DOC_MEDIA})[0], [])
        self.assertEqual(vr.validate({"blocks": doc_blocks()})[0], [])
        params = {"chat_id": 1001, "rich_message": {"blocks": doc_blocks()}}
        self.assertEqual(V.check_request("sendRichMessage", params).errors, [])

    def test_the_outline_sees_a_difference(self):
        changed = doc_blocks()
        changed[1]["text"][1] = rich.italic("faster")          # bold -> italic
        self.assertNotEqual(html_outline(DOC_HTML, DOC_MEDIA)[1], blocks_outline(changed)[1])
        with self.assertRaises(AssertionError):
            html_outline("<blink>x</blink>")


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

    def test_malformed_values_are_errors_with_field_paths(self):
        self.assertFlags(vr.validate({"blocks": 5})[0], "blocks: an array of InputRichBlock")
        self.assertFlags(errors([{"type": "details", "summary": "S", "blocks": "abc"}]),
                         "blocks[0].blocks: an array of InputRichBlock")
        self.assertFlags(errors([{"type": "photo", "photo": {"type": "photo"}}]),
                         "blocks[0].photo: InputMediaPhoto is missing required field 'media'")
        self.assertFlags(errors([{"type": "paragraph", "text": None}]), "blocks[0].text: null")
        self.assertFlags(errors([{"type": ["paragraph"], "text": "x"}]),
                         "blocks[0]: ['paragraph'] is not an InputRichBlock type")
        self.assertFlags(errors([rich.paragraph_block({"type": ["bold"], "text": "x"})]),
                         "blocks[0].text: ['bold'] is not a RichText type")

    def test_junk_in_any_field_never_crashes(self):
        junk = (None, 5, True, "x", [], [1], [["x"]], {}, {"type": []}, [{"type": ["x"]}])
        for const, name in sorted(vr._spec()[1].items()):
            for field in TYPES[name]["fields"]:
                if field["name"] == "type":
                    continue
                for value in junk:
                    block = {"type": const, field["name"]: value}
                    kind = field["type"]
                    wrong = value is None or (kind.startswith("Array of") and not isinstance(value, list))                         or (kind == "RichText" and isinstance(value, (int, bool)))
                    with self.subTest(block=block):
                        for draft in (False, True):
                            found, _, _ = vr.validate({"blocks": [block]}, draft=draft)
                            if wrong:
                                self.assertFlags(found, f"blocks[0].{field['name']}")


class ValidateRichMovingEmoji(unittest.TestCase):
    """--emoji-library: a button's animated or video custom emoji is an error, in blocks, HTML and the keyboard."""
    MOVING = {"2222222222": "animated", "3333333333": "video"}

    def check(self, payload, **kw):
        return [e for e in vr.validate(payload, moving_emoji=self.MOVING, **kw)[0] if "BUTTON_EMOJI_ANIMATED" in e]

    def test_blocks_html_and_markdown(self):
        film = rich.message_button([rich.custom_emoji("3333333333", "🎬"), " Film"], callback_data="m")
        home = rich.message_button([rich.custom_emoji("1111111111", "🏠"), " Home"], callback_data="h")
        self.assertEqual(len(self.check({"blocks": [rich.buttons_block([film, home])]})), 1)
        self.assertEqual(self.check({"blocks": [rich.buttons_block([home])]}), [])
        html = ('<p><tg-emoji emoji-id="2222222222">🔥</tg-emoji></p>'
                '<tg-button type="callback_data" data="g"><tg-emoji emoji-id="2222222222">🔥</tg-emoji> Go</tg-button>')
        self.assertEqual(len(self.check({"html": html})), 1, "only the emoji inside the button counts")
        self.assertEqual(len(self.check({"rich_message": {"markdown": html}})), 1)
        self.assertEqual([e for e in vr.validate({"html": html})[0] if "BUTTON_EMOJI_ANIMATED" in e], [], "no library")

    def test_a_reply_markup_icon_is_checked_too(self):
        payload = {"html": "<p>x</p>", "reply_markup": {"inline_keyboard": [[
            {"text": "Fire", "callback_data": "f", "icon_custom_emoji_id": "2222222222"}]]}}
        self.assertEqual(len(self.check(payload)), 1)

    def test_the_cli_takes_the_project_library(self):
        import json
        import os
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            lib, doc = os.path.join(tmp, "library.json"), os.path.join(tmp, "message.json")
            with open(lib, "w", encoding="utf-8") as fh:
                json.dump({"format": "bot-ui-emoji/v1", "packs": {"demo": {"emoji": [
                    {"id": "2222222222", "fallback": "🔥", "format": "animated"}]}}, "icons": {}}, fh)
            with open(doc, "w", encoding="utf-8") as fh:
                json.dump({"html": '<tg-button type="callback_data" data="g"><tg-emoji emoji-id="2222222222">🔥</tg-emoji> Go</tg-button>'}, fh)
            script = os.path.join(_paths.ROOT, "scripts", "validate_rich.py")
            run = lambda *a: subprocess.run([sys.executable, script, doc, *a], capture_output=True, text=True, encoding="utf-8")  # noqa: E731
            self.assertEqual(run().returncode, 0)
            bad = run("--emoji-library", lib)
            self.assertEqual(bad.returncode, 1, bad.stdout)
            self.assertIn("BUTTON_EMOJI_ANIMATED", bad.stdout)
            self.assertEqual(run("--emoji-library", os.path.join(tmp, "nope.json")).returncode, 1)


if __name__ == "__main__":
    unittest.main()
