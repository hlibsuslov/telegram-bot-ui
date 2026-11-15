"""Channel publishing (tgkit/publish.py, scripts/tg_post.py, recipes 30-39).

Invariants: payload shape per post type, no double publish after a timeout,
429 backoff without a tight loop, split posts keep buttons on the last part,
hostile text is safe in every format, unchanged edits send nothing, channel
button rules, and the CLI never sends or echoes a token in dry runs.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _paths
from tgkit.errors import RetryPolicy
from tgkit.publish import (LIMITS, FanOut, Ledger, Post, Publisher, check_entities, decide_correction, plan,
                           resolve_kind, to_entities, to_html, to_markdown_v2, to_rich_blocks, validate)
from tgkit.text import utf16_len
from tgkit.transport import FakeTransport, TelegramErrorResponse

CH = -1001500000001
HOSTILE = "<b>&amp; *_[x](y)`|| \\ 👩‍👩‍👧 𝐀"


def text_post(**kw):
    base = dict(kind="text", blocks=[{"type": "heading", "text": "Title"}, {"type": "paragraph", "text": "Body"}],
                buttons=[[{"text": "Open", "url": "https://example.com"}]])
    base.update(kw)
    return Post(**base)


def codes(post, **kw):
    return {i.code for i in validate(post, **kw) if i.level == "error"}


class PayloadShapes(unittest.TestCase):
    def test_text(self):
        (m, p), = plan(text_post(silent=True, protect=True, link_preview={"url": "https://example.com", "above": True}), CH)
        self.assertEqual(m, "sendMessage")
        self.assertEqual(p["text"], "Title\n\nBody")
        self.assertEqual(p["entities"], [{"type": "bold", "offset": 0, "length": 5}])
        self.assertEqual(p["link_preview_options"], {"url": "https://example.com", "show_above_text": True})
        self.assertTrue(p["disable_notification"] and p["protect_content"])
        self.assertNotIn("parse_mode", p)

    def test_rich(self):
        post = Post(blocks=[{"type": "heading", "text": "A"}, {"type": "table", "header": ["k", "v"], "rows": [["1", "2"]]}],
                    buttons=[[{"text": "Go", "callback_data": "go", "style": "link"}]])
        self.assertEqual(resolve_kind(post), "rich")
        (m, p), = plan(post, CH)
        self.assertEqual(m, "sendRichMessage")
        blocks = p["rich_message"]["blocks"]
        self.assertEqual([b["type"] for b in blocks], ["heading", "table", "buttons"])
        self.assertTrue(blocks[1]["is_compact"])
        self.assertNotIn("link_preview_options", p)

    def test_photo_video_document(self):
        for kind, field in (("photo", "photo"), ("video", "video"), ("document", "document")):
            post = text_post(kind=kind, media=[{"type": kind, "ref": "FILEID123", "spoiler": True}], caption_above=True)
            (m, p), = plan(post, CH)
            self.assertEqual(m, "send" + kind.capitalize())
            self.assertEqual(p[field], "FILEID123")
            self.assertIn("reply_markup", p)
            self.assertEqual(kind != "document", p.get("has_spoiler", False))
            self.assertEqual(kind != "document", p.get("show_caption_above_media", False))

    def test_album(self):
        post = text_post(kind="album", media=[{"type": "photo", "ref": "A1"}, {"type": "video", "ref": "V1"}])
        reqs = plan(post, CH)
        self.assertEqual([m for m, _ in reqs], ["sendMediaGroup", "sendMessage"])
        self.assertNotIn("reply_markup", reqs[0][1])
        self.assertIn("caption", reqs[0][1]["media"][0])
        self.assertNotIn("caption", reqs[0][1]["media"][1])
        self.assertIn("reply_markup", reqs[1][1])

    def test_poll_and_paid_media(self):
        poll = Post(poll={"question": "Q?", "options": ["a", "b"], "type": "quiz", "correct_option_ids": [0]})
        (m, p), = plan(poll, CH)
        self.assertEqual((m, p["options"], p["correct_option_ids"]), ("sendPoll", [{"text": "a"}, {"text": "b"}], [0]))
        paid = Post(stars=10, media=[{"type": "photo", "ref": "P1"}], blocks=[{"type": "paragraph", "text": "x"}])
        (m, p), = plan(paid, CH)
        self.assertEqual((m, p["star_count"], p["media"]), ("sendPaidMedia", 10, [{"type": "photo", "media": "P1"}]))

    def test_address_fields_pass_through(self):
        (_, p), = plan(text_post(), -1001500000201, address={"direct_messages_topic_id": 77})
        self.assertEqual(p["direct_messages_topic_id"], 77)


class Idempotency(unittest.TestCase):
    def test_timeout_never_double_posts(self):
        t = FakeTransport().script("sendMessage", "TIMEOUT")
        pub = Publisher(t, sleep=lambda s: None)
        self.assertEqual(pub.publish(text_post(), CH, "k").status, "unknown")
        for _ in range(3):
            self.assertEqual(pub.publish(text_post(), CH, "k").status, "unknown")
        self.assertEqual(len(t.calls), 1)
        self.assertEqual(pub.reconcile("k", found_message_ids=[]).status, "absent")
        self.assertEqual(pub.publish(text_post(), CH, "k").status, "sent")
        self.assertEqual(pub.publish(text_post(), CH, "k").status, "already_sent")
        self.assertEqual(len(t.calls), 2)

    def test_crash_after_write_ahead_is_unknown(self):
        ledger = Ledger()
        ledger.put("k", state="pending", message_ids=[])
        t = FakeTransport()
        self.assertEqual(Publisher(t, ledger).publish(text_post(), CH, "k").status, "unknown")
        self.assertEqual(t.calls, [])

    def test_partial_multi_part_is_not_resent(self):
        long = text_post(blocks=[{"type": "paragraph", "text": ("word " * 900).strip()}] * 3)
        t = FakeTransport().script("sendMessage", {"message_id": 1, "date": 0, "chat": {"id": CH}}, "TIMEOUT")
        pub = Publisher(t, sleep=lambda s: None)
        r = pub.publish(long, CH, "long")
        self.assertEqual((r.status, r.message_ids), ("unknown", [1]))
        self.assertEqual(pub.publish(long, CH, "long").status, "unknown")
        self.assertEqual(pub.reconcile("long", found_message_ids=None).status, "partial")

    def test_file_ledger_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ledger.json")
            t = FakeTransport()
            Publisher(t, Ledger(path)).publish(text_post(), CH, "k")
            again = Publisher(t, Ledger(path)).publish(text_post(), CH, "k")
            self.assertEqual(again.status, "already_sent")
            self.assertEqual(len(t.calls), 1)

    def test_validation_error_sends_nothing_and_failed_can_retry(self):
        t = FakeTransport().script("sendMessage", TelegramErrorResponse(400, "Bad Request: chat not found"))
        pub = Publisher(t)
        self.assertEqual(pub.publish(text_post(), CH, "k").status, "failed")
        self.assertEqual(pub.publish(text_post(), CH, "k").status, "sent")


class RateLimits(unittest.TestCase):
    def test_429_waits_retry_after_and_is_bounded(self):
        sleeps = []
        t = FakeTransport().script("sendMessage", *[TelegramErrorResponse(429, "Too Many Requests", retry_after=5)] * 5)
        pub = Publisher(t, sleep=sleeps.append, policy=RetryPolicy(max_attempts=3))
        r = pub.publish(text_post(), CH, "k")
        self.assertEqual(r.status, "failed")
        self.assertEqual(len(t.calls), 3)
        self.assertEqual(sleeps, [5, 5])

    def test_fanout_throttles_and_defers_long_waits(self):
        now, sleeps = [0.0], []

        def sleep(s):
            sleeps.append(s)
            now[0] += s
        t = FakeTransport()
        jobs = [(str(i), plan(text_post(), i)) for i in range(1, 11)]
        rep = FanOut(t, per_second=5, sleep=sleep, clock=lambda: now[0]).run("c", jobs)
        self.assertEqual(len(rep.sent), 10)
        self.assertGreaterEqual(now[0], 9 * 0.2 - 1e-9)       # 10 calls at 5/s: at least 1.8 s
        t2 = FakeTransport().script("sendMessage", TelegramErrorResponse(429, "Too Many Requests", retry_after=3600))
        rep2 = FanOut(t2, sleep=sleep, clock=lambda: now[0]).run("c", jobs)
        self.assertEqual(rep2.deferred, [str(i) for i in range(1, 11)])
        self.assertEqual(len(t2.calls), 1)

    def test_fanout_one_failure_does_not_stop_the_batch(self):
        t = FakeTransport().script("sendMessage", TelegramErrorResponse(403, "Forbidden: bot was blocked by the user"))
        rep = FanOut(t, sleep=lambda s: None, clock=lambda: 0.0).run("c", [(str(i), plan(text_post(), i)) for i in (1, 2, 3)])
        self.assertEqual((rep.blocked, sorted(rep.sent)), (["1"], ["2", "3"]))


class Splitting(unittest.TestCase):
    def test_long_text_keeps_buttons_on_last_part_and_one_notification(self):
        body = [{"type": "paragraph", "text": f"Paragraph {i}: " + "x" * 900} for i in range(12)]
        post = text_post(blocks=[{"type": "heading", "text": "Title"}] + body, link_preview={"url": "https://example.com"})
        reqs = plan(post, CH)
        self.assertGreater(len(reqs), 2)
        self.assertTrue(all(utf16_len(p["text"]) <= LIMITS["text"] for _, p in reqs))
        self.assertEqual(["reply_markup" in p for _, p in reqs], [False] * (len(reqs) - 1) + [True])
        self.assertTrue(all(p.get("disable_notification") for _, p in reqs[1:]))
        self.assertNotIn("disable_notification", reqs[0][1])
        self.assertEqual(reqs[0][1]["link_preview_options"], {"url": "https://example.com"})
        self.assertTrue(all(p["link_preview_options"] == {"is_disabled": True} for _, p in reqs[1:]))
        self.assertTrue(reqs[0][1]["text"].startswith("Title"))

    def test_auto_prefers_one_rich_message_over_a_split(self):
        body = [{"type": "paragraph", "text": "x" * 900} for _ in range(6)]
        self.assertEqual(resolve_kind(Post(blocks=body)), "rich")

    def test_caption_overflow_moves_buttons_to_the_follow_up(self):
        post = text_post(kind="photo", media=[{"type": "photo", "ref": "P"}],
                         blocks=[{"type": "heading", "text": "Short title"}, {"type": "paragraph", "text": "y" * 2000}])
        reqs = plan(post, CH)
        self.assertEqual([m for m, _ in reqs], ["sendPhoto", "sendMessage"])
        self.assertEqual(reqs[0][1]["caption"], "Short title")
        self.assertNotIn("reply_markup", reqs[0][1])
        self.assertIn("reply_markup", reqs[1][1])

    def test_entities_inside_utf16_bounds_after_split(self):
        blocks = [{"type": "paragraph", "text": [{"bold": "👩‍👩‍👧 " * 300}, " tail"]}] * 4
        for _, p in plan(text_post(blocks=blocks), CH):
            self.assertEqual(check_entities(p["text"], p.get("entities", [])), [])


class Escaping(unittest.TestCase):
    blocks = [{"type": "heading", "text": HOSTILE}, {"type": "paragraph", "text": [{"link": "https://ex.com/?a=1&b=\"2\")", "text": HOSTILE}]},
              {"type": "list", "items": [HOSTILE]}, {"type": "quote", "text": HOSTILE, "expandable": True}]

    def test_entities_keep_raw_text(self):
        text, ents = to_entities(self.blocks)
        self.assertEqual(text.count(HOSTILE), 4)
        self.assertEqual(check_entities(text, ents), [])

    def test_html_escapes_text_and_attributes(self):
        html = to_html(self.blocks)
        self.assertNotIn("<b>&amp;", html.replace("<b>&lt;b&gt;", ""))
        self.assertIn("&lt;b&gt;&amp;amp;", html)
        self.assertIn('href="https://ex.com/?a=1&amp;b=&quot;2&quot;)"', html)

    def test_markdown_v2_escapes_every_special(self):
        md = to_markdown_v2([{"type": "paragraph", "text": HOSTILE}])
        for ch in "_*[]()~`>#+-=|{}.!":
            self.assertNotIn(ch, md.replace("\\" + ch, "").replace("\\\\", ""), ch)
        link = to_markdown_v2([{"type": "paragraph", "text": {"link": "https://ex.com/a)b", "text": "t"}}])
        self.assertIn("(https://ex.com/a\\)b)", link)

    def test_rich_blocks_carry_raw_strings(self):
        blocks = to_rich_blocks(self.blocks)
        self.assertEqual(blocks[0]["text"], HOSTILE)

    def test_dangerous_urls_refused_everywhere(self):
        bad = [{"type": "paragraph", "text": {"link": "javascript:alert(1)", "text": "x"}}]
        for fn in (to_entities, to_html, to_markdown_v2, to_rich_blocks):
            with self.assertRaises(ValueError):
                fn(bad)
        self.assertIn("button_url", codes(text_post(buttons=[[{"text": "x", "url": "javascript:alert(1)"}]])))


class Editing(unittest.TestCase):
    def test_unchanged_edit_sends_nothing(self):
        t = FakeTransport()
        pub = Publisher(t)
        pub.publish(text_post(), CH, "k")
        self.assertEqual(pub.edit("k", text_post()).status, "unchanged")
        self.assertEqual(len(t.calls), 1)

    def test_changed_text_edits_only_changed_parts(self):
        t = FakeTransport()
        pub = Publisher(t)
        pub.publish(text_post(), CH, "k")
        r = pub.edit("k", text_post(blocks=[{"type": "heading", "text": "Title"}, {"type": "paragraph", "text": "Body!"}]))
        self.assertEqual(r.status, "edited")
        (m, p), = t.calls[1:]
        self.assertEqual((m, p["message_id"], p["text"]), ("editMessageText", 1001, "Title\n\nBody!"))
        self.assertIn("reply_markup", p)

    def test_rich_and_caption_edits(self):
        t = FakeTransport()
        pub = Publisher(t)
        rich_post = Post(kind="rich", blocks=[{"type": "paragraph", "text": "a"}])
        pub.publish(rich_post, CH, "r")
        pub.edit("r", rich_post.with_changes(blocks=[{"type": "paragraph", "text": "b"}]))
        self.assertIn("rich_message", t.params_of("editMessageText")[0])
        photo = text_post(kind="photo", media=[{"type": "photo", "ref": "P"}])
        pub.publish(photo, CH, "p")
        pub.edit("p", photo.with_changes(blocks=[{"type": "paragraph", "text": "new caption"}]))
        self.assertEqual(t.params_of("editMessageCaption")[0]["caption"], "new caption")

    def test_layout_change_requires_repost_and_decision(self):
        t = FakeTransport()
        pub = Publisher(t, clock=lambda: 1000.0)
        pub.publish(text_post(), CH, "k")
        photo = text_post(kind="photo", media=[{"type": "photo", "ref": "P"}])
        self.assertEqual(pub.edit("k", photo).status, "repost_required")
        rec = pub.ledger.get("k")
        self.assertEqual(decide_correction(rec, photo, 1000.0 + 60), "repost")
        self.assertEqual(decide_correction(rec, photo, 1000.0 + 7200), "append_note")
        self.assertEqual(decide_correction(rec, text_post(), 1000.0), "unchanged")

    def test_delete_window(self):
        now = [0.0]
        pub = Publisher(FakeTransport(), clock=lambda: now[0])
        pub.publish(text_post(), CH, "k")
        now[0] = LIMITS["delete_window_s"] + 1
        self.assertEqual(pub.delete("k").status, "too_old")


class ChannelRules(unittest.TestCase):
    def test_buttons_not_for_channels(self):
        for action in ({"web_app": {"url": "https://ex.com"}}, {"switch_inline_query_current_chat": ""},
                       {"switch_inline_query": "q"}, {"pay": True}):
            self.assertIn("button_context", codes(text_post(buttons=[[{"text": "x", **action}]])), action)
        self.assertEqual(codes(text_post(buttons=[[{"text": "x", "callback_data": "like"}],
                                                  [{"text": "y", "copy_text": "code"}],
                                                  [{"text": "z", "login_url": {"url": "https://ex.com"}}]])), set())

    def test_one_action_and_callback_bytes(self):
        self.assertIn("button_actions", codes(text_post(buttons=[[{"text": "x", "url": "https://a", "callback_data": "b"}]])))
        self.assertIn("callback_data", codes(text_post(buttons=[[{"text": "x", "callback_data": "я" * 33}]])))

    def test_custom_emoji_icon_needs_fragment_bot_in_channels(self):
        post = text_post(buttons=[[{"text": "x", "url": "https://a", "icon_custom_emoji_id": "5368324170671202286"}]])
        self.assertIn("custom_emoji", codes(post))
        self.assertNotIn("custom_emoji", codes(post, custom_emoji_ok=True))
        self.assertNotIn("custom_emoji", codes(post, context="group"))

    def test_rich_button_rules(self):
        post = Post(kind="rich", blocks=[{"type": "paragraph", "text": "a"}],
                    buttons=[[{"text": "x", "url": "https://a", "style": "link"}]])
        self.assertIn("button_style", codes(post))

    def test_media_refs(self):
        for ref in ("C:\\a.jpg", "/tmp/a.jpg", "../a.jpg", "file:///a.jpg", ""):
            self.assertIn("media_ref", codes(text_post(kind="photo", media=[{"type": "photo", "ref": ref}])), ref)
        self.assertIn("media_ref", codes(text_post(kind="photo", media=[{"type": "photo", "ref": "attach://a"}]), live=True))
        self.assertEqual(codes(text_post(kind="photo", media=[{"type": "photo", "ref": "https://ex.com/a.jpg"}])), set())

    def test_poll_contexts(self):
        p = Post(poll={"question": "Q", "options": ["a"], "members_only": True})
        self.assertEqual(codes(p), set())
        self.assertIn("poll_channel_only", codes(p, context="group"))
        self.assertIn("poll_context", codes(p, context="channel_dm"))

    def test_rich_limits(self):
        many = Post(kind="rich", blocks=[{"type": "paragraph", "text": "a"}] * 501)
        self.assertIn("rich_blocks", codes(many))
        wide = Post(kind="rich", blocks=[{"type": "table", "header": [str(i) for i in range(21)], "rows": []}])
        self.assertIn("rich_table", codes(wide))


class DecorationHook(unittest.TestCase):
    def test_default_is_no_op(self):
        self.assertEqual(plan(text_post(), CH), plan(text_post(), CH, decorate=None))

    def test_decorator_gets_a_copy_and_the_context(self):
        seen = []

        def deco(post, context):
            seen.append(context)
            post.blocks[0]["text"] = "★ " + post.blocks[0]["text"]
            return post
        src = text_post()
        (_, p), = plan(src, CH, context="group", decorate=deco)
        self.assertEqual((seen, p["text"].split("\n")[0], src.blocks[0]["text"]), (["group"], "★ Title", "Title"))

    def test_decorated_output_is_validated_and_source_is_stored(self):
        icon = lambda post, ctx: post.with_changes(  # noqa: E731
            buttons=[[{"text": "Open", "url": "https://example.com", "icon_custom_emoji_id": "5368324170671202286"}]])
        t = FakeTransport()
        from tgkit.publish import PostInvalid
        with self.assertRaises(PostInvalid):
            Publisher(t, decorate=icon).publish(text_post(), CH, "k")      # channel, no Fragment username
        self.assertEqual(t.calls, [])
        pub = Publisher(t, decorate=icon, custom_emoji_ok=True)
        pub.publish(text_post(), CH, "k2")
        self.assertIn("icon_custom_emoji_id", t.calls[0][1]["reply_markup"]["inline_keyboard"][0][0])
        self.assertNotIn("icon_custom_emoji_id", json.dumps(pub.ledger.get("k2")["post"]))
        self.assertEqual(pub.edit("k2", text_post()).status, "unchanged")

    def test_decorator_must_return_a_post(self):
        with self.assertRaises(TypeError):
            plan(text_post(), CH, decorate=lambda post, ctx: None)


class WidgetVariant(unittest.TestCase):
    def widget_post(self, **w):
        return Post(blocks=[{"type": "heading", "text": "BTC price"}, {"type": "paragraph", "text": "Updated every minute."}],
                    widget={"html": "<div id=p>…</div>", "public_data": '{"p": 1}', **w})

    def test_channel_falls_back_to_the_same_blocks(self):
        import tgkit.publish as pubmod
        self.assertFalse(pubmod.CHANNEL_WIDGETS)
        reqs = plan(self.widget_post(), CH)
        self.assertEqual([m for m, _ in reqs], ["sendMessage"])
        self.assertTrue(reqs[0][1]["text"].startswith("BTC price"))
        self.assertIn("widget_fallback", {i.code for i in validate(self.widget_post())})
        self.assertEqual(codes(self.widget_post()), set())

    def test_private_chat_gets_a_widget_with_caption(self):
        (m, p), = plan(self.widget_post(), 111111111, context="private")
        self.assertEqual(m, "sendWidget")
        self.assertEqual(p["caption"], "BTC price\n\nUpdated every minute.")
        self.assertEqual(p["caption_entities"], [{"type": "bold", "offset": 0, "length": 9}])
        self.assertEqual(p["public_data"], '{"p": 1}')
        self.assertNotIn("allow_queries", p)

    def test_groups_only_on_the_test_server(self):
        self.assertEqual(plan(self.widget_post(), -100, context="group")[0][0], "sendMessage")
        self.assertEqual(plan(self.widget_post(), -100, context="group", environment="test")[0][0], "sendWidget")
        self.assertEqual(plan(self.widget_post(), -100, context="channel_dm", environment="test")[0][0], "sendMessage")

    def test_channel_rules_when_the_flag_is_flipped(self):
        import tgkit.publish as pubmod
        old = pubmod.CHANNEL_WIDGETS
        pubmod.CHANNEL_WIDGETS = True
        try:
            self.assertEqual(plan(self.widget_post(), CH)[0][0], "sendWidget")
            self.assertEqual(codes(self.widget_post()), set())
            self.assertIn("widget_channel", codes(self.widget_post(chat_data="per-chat")))
            self.assertIn("widget_channel", codes(self.widget_post(allow_queries=True)))
        finally:
            pubmod.CHANNEL_WIDGETS = old

    def test_widget_needs_blocks_and_size_limits(self):
        bare = Post(widget={"html": "<b>x</b>"})
        self.assertIn("widget_fallback", codes(bare, context="private"))
        big = self.widget_post()
        big.widget["html"] = os.urandom(20000).hex()
        self.assertIn("widget", codes(big, context="private"))

    def test_sent_widget_is_not_edited_in_place(self):
        t = FakeTransport()
        pub = Publisher(t, context="private")
        pub.publish(self.widget_post(), 111111111, "w")
        changed = self.widget_post()
        changed.blocks[1] = {"type": "paragraph", "text": "Updated every 5 minutes."}
        self.assertEqual(pub.edit("w", changed).status, "repost_required")


class RichSources(unittest.TestCase):
    post = Post(kind="rich", blocks=[
        {"type": "heading", "text": "Q3 <report> & #1"},
        {"type": "paragraph", "text": ["1. ", {"bold": "a_b*c"}, " ", {"link": "https://ex.com/a)b?x=\"1\"", "text": "[src]"}]},
        {"type": "table", "header": ["k", "v"], "rows": [["a|b", "1"]], "numeric": [1], "compact": False},
        {"type": "quote", "text": "q", "expandable": True, "credit": "A & B"},
        {"type": "list", "items": [{"text": "done", "done": True}, {"text": "todo", "done": False}]},
        {"type": "document", "ref": "BQACdoc", "caption": "PDF"}],
        buttons=[[{"text": "Go <now>", "url": "https://ex.com/?a=1&b=2", "style": "primary"},
                  {"text": "Copy", "copy_text": 'he said "hi"'}]])

    def test_one_source_field_and_media(self):
        from tgkit.publish import rich_message
        import validate_rich
        for source in ("blocks", "markdown", "html"):
            msg = rich_message(self.post.with_changes(rich_source=source))
            self.assertEqual([k for k in ("blocks", "markdown", "html") if k in msg], [source])
            errors, _, _ = validate_rich.validate({"rich_message": msg})
            self.assertEqual(errors, [], source)
            if source != "blocks":
                self.assertEqual(msg["media"], [{"id": "doc1", "media": {"type": "document", "media": "BQACdoc"}}])

    def test_rich_html_escapes(self):
        from tgkit.publish import to_rich_html
        html, _ = to_rich_html(self.post.blocks, self.post.buttons)
        self.assertIn("<h1>Q3 &lt;report&gt; &amp; #1</h1>", html)
        self.assertIn('href="https://ex.com/a)b?x=&quot;1&quot;"', html)
        self.assertIn('text="he said &quot;hi&quot;"', html)
        self.assertIn('url="https://ex.com/?a=1&amp;b=2"', html)
        self.assertIn("<cite>A &amp; B</cite>", html)
        self.assertIn('<li><input type="checkbox" checked>done</li>', html)
        self.assertIn('<tg-document src="tg://document?id=doc1">', html)

    def test_rich_markdown_escapes_and_html_fallbacks(self):
        from tgkit.publish import to_rich_markdown
        md, _ = to_rich_markdown(self.post.blocks, self.post.buttons)
        lines = md.split("\n")
        self.assertEqual(lines[0], "# Q3 \\<report> \\& #1")
        self.assertIn("1\\. **a\\_b\\*c** [\\[src\\]](https://ex.com/a%29b?x=\"1\")", md)
        self.assertIn("| a\\|b | 1 |", md)
        self.assertIn("|:---|---:|", md)
        self.assertIn("<blockquote expandable>q<cite>A &amp; B</cite></blockquote>", md)
        self.assertIn("- [x] done\n- [ ] todo", md)
        self.assertIn('![](tg://document?id=doc1 "PDF")', md)
        self.assertIn('<tg-button type="url" url="https://ex.com/?a=1&amp;b=2" style="primary">Go &lt;now&gt;</tg-button>', md)

    def test_invalid_source_refused(self):
        self.assertIn("rich_source", codes(self.post.with_changes(rich_source="rtf")))


class RecipesAndCli(unittest.TestCase):
    def test_recipes_run(self):
        import runpy
        folder = os.path.join(_paths.EXAMPLES, "python", "recipes")
        for f in sorted(os.listdir(folder)):
            if f.startswith("r3") and f.endswith(".py"):
                with self.subTest(recipe=f), contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(os.path.join(folder, f), run_name="__main__")

    def test_payload_files_match_the_code(self):
        p = subprocess.run([sys.executable, os.path.join(_paths.EXAMPLES, "python", "export_publishing_payloads.py"),
                            "--check"], capture_output=True, text=True, cwd=_paths.ROOT)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def _cli(self, *args, env=None):
        return subprocess.run([sys.executable, os.path.join(_paths.ROOT, "scripts", "tg_post.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", env={**os.environ, **(env or {})})

    def test_cli_markdown_preview_and_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "post.md")
            with open(md, "w", encoding="utf-8") as fh:
                fh.write("# Title <x> & y\n\nBody with **bold** and [link](https://ex.com).\n\n"
                         "[button: Open](https://ex.com/o)\n")
            p = self._cli("preview", md, "--chat", "-100123")
            self.assertEqual(p.returncode, 0, p.stderr)
            req = json.loads(p.stdout.strip().splitlines()[-1])
            self.assertEqual(req["method"], "sendMessage")
            self.assertTrue(req["params"]["text"].startswith("Title <x> & y"))
            self.assertEqual(req["params"]["reply_markup"]["inline_keyboard"][0][0]["url"], "https://ex.com/o")
            fake = "0000000:" + "Z" * 35
            dry = self._cli("publish", md, "--chat-env", "TGP_CHAT", "--token-env", "TGP_TOKEN",
                            env={"TGP_CHAT": "-100123", "TGP_TOKEN": fake})
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertIn("dry run: nothing sent", dry.stdout)
            self.assertNotIn(fake, dry.stdout + dry.stderr)
            missing = self._cli("publish", md, "--chat-env", "TGP_CHAT", "--token-env", "TGP_NO_SUCH_VAR", "--live",
                                env={"TGP_CHAT": "-100123"})
            self.assertEqual(missing.returncode, 2)
            self.assertIn("TGP_NO_SUCH_VAR is not set", missing.stderr)

    def test_cli_rejects_invalid_json_post(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "post.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"kind": "text", "blocks": [{"type": "paragraph", "text": "x"}],
                           "buttons": [[{"text": "App", "web_app": {"url": "https://ex.com"}}]]}, fh)
            p = self._cli("validate", path)
            self.assertEqual(p.returncode, 1)
            self.assertIn("button_context", p.stdout)


if __name__ == "__main__":
    unittest.main()
