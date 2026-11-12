"""Check 9: Unicode, escaping and splits keep content, links, keyboard and
addressing; rich payloads respect the official limits and draft rules."""
import unittest

import _paths  # noqa: F401
import validate_rich as vr
from tgkit import rich
from tgkit.text import (entity_for, escape_html, escape_markdown_v2, send_long, split_text, utf16_len,
                        utf16_offset)
from tgkit.transport import FakeTransport


def utf16_slice(text, off, length):
    return text.encode("utf-16-le")[2 * off:2 * (off + length)].decode("utf-16-le")


class Escaping(unittest.TestCase):
    def test_per_format_escapers(self):
        self.assertEqual(escape_html("a<b>&c"), "a&lt;b&gt;&amp;c")
        self.assertEqual(escape_markdown_v2("1.5*2_(x)!"), r"1\.5\*2\_\(x\)\!")
        self.assertNotEqual(escape_html("a.b"), escape_markdown_v2("a.b"), "one escaper per format")

    def test_utf16_offsets_with_emoji_and_combining(self):
        text = "👍🏽 café ok — Ελλάδα"
        e = entity_for(text, "ok", "bold")
        self.assertEqual(utf16_slice(text, e["offset"], e["length"]), "ok")
        self.assertGreater(utf16_offset(text, text.index("ok")), text.index("ok"))


class Splitting(unittest.TestCase):
    def make(self):
        para = "Слово 👨‍👩‍👧 é " * 120
        text = para + "\n\n" + "See the guide for details. " * 40 + "\n\nFinal line."
        link = entity_for(text, "the guide", "text_link", url="https://example.com/g")
        return text, [link]

    def test_split_preserves_content_and_entities(self):
        text, ents = self.make()
        parts = split_text(text, ents, limit=1000)
        self.assertGreater(len(parts), 2)
        for chunk, local in parts:
            self.assertLessEqual(utf16_len(chunk), 1000)
            self.assertFalse(chunk and ("\ud800" <= chunk[-1] <= "\udbff"))
            self.assertFalse(chunk.endswith("‍"), "no cut inside a ZWJ sequence")
            for e in local:
                self.assertEqual(utf16_slice(chunk, e["offset"], e["length"]), "the guide")
        joined = "".join(p for p, _ in parts).replace(" ", "").replace("\n", "")
        self.assertEqual(joined, text.replace(" ", "").replace("\n", ""))

    def test_send_long_keeps_address_and_puts_keyboard_last(self):
        text, ents = self.make()
        t = FakeTransport()
        kb = {"inline_keyboard": [[{"text": "Open", "url": "https://example.com"}]]}
        send_long(t, {"chat_id": -100, "message_thread_id": 7}, text, ents, kb, limit=1000)
        sends = t.params_of("sendMessage")
        self.assertTrue(all(s["chat_id"] == -100 and s["message_thread_id"] == 7 for s in sends))
        self.assertEqual([("reply_markup" in s) for s in sends], [False] * (len(sends) - 1) + [True])


class RichPayloads(unittest.TestCase):
    def test_limits(self):
        blocks = [{"type": "paragraph", "text": "x"}] * 501
        errors, _, _ = vr.validate({"blocks": blocks})
        self.assertTrue(any("blocks" in e for e in errors))
        wide = rich.table([f"c{i}" for i in range(21)], [])
        errors, _, _ = vr.validate({"blocks": [wide]})
        self.assertTrue(any("columns" in e for e in errors))

    def test_thinking_and_draft_media_rules(self):
        thinking = {"blocks": [{"type": "thinking", "text": "…"}]}
        self.assertTrue(vr.validate(thinking)[0])
        self.assertFalse(vr.validate(thinking, draft=True)[0])
        upload = {"blocks": [rich.document_block("attach://spec")]}
        self.assertTrue(vr.validate(upload, draft=True)[0])
        self.assertFalse(vr.validate({"blocks": [rich.document_block("BQACdemo")]}, draft=True)[0])

    def test_tg_document_references(self):
        ok = {"markdown": "![](tg://document?id=spec)", "media": [{"id": "spec", "media": {"type": "document", "media": "BQAC"}}]}
        self.assertEqual(vr.validate(ok)[0], [])
        missing = {"markdown": "![](tg://document?id=spec)"}
        self.assertTrue(vr.validate(missing)[0])

    def test_quote_builder_keeps_formatting_and_reader_uses_rich_texts(self):
        para = ["Rotate the ", {"type": "bold", "text": "signing key"}, " every 90 days."]
        self.assertEqual(rich.quote_from_paragraph(para, 4, 15), [["te the ", {"type": "bold", "text": "sign"}]])
        self.assertEqual(rich.quote_text({"text": "", "rich_texts": [para]}), "Rotate the signing key every 90 days.")
        errors, _, _ = vr.validate({"rich_message": {"markdown": "x"},
                                    "reply_parameters": {"message_id": 1, "quote_rich_texts": ["a"] * 33}})
        self.assertTrue(errors)

    def test_rich_button_builder_refuses_invalid_models(self):
        with self.assertRaises(ValueError):
            rich.rich_button("x", url="https://t.me", style="link")
        with self.assertRaises(ValueError):
            rich.rich_button("x", callback_data="a", disabled=True)
        with self.assertRaises(ValueError):
            rich.button_row([rich.rich_button(str(i), callback_data=str(i)) for i in range(9)])


if __name__ == "__main__":
    unittest.main()
