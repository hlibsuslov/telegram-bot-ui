"""Premium emoji in channel posts: eligibility, density, links, fallback text."""
import unittest

import _paths  # noqa: F401
from tgkit.icons import (DENSITY, Eligibility, IconSystem, SendContext, decorate_post, density_warnings,
                         load_vocabulary, strip_html)

VOCAB = load_vocabulary()
ICONS = {s: {"id": f"03000000000001{n:02d}", "fallback": VOCAB[s]["unicode"][0]}
         for n, s in enumerate(["headline", "section", "bullet", "cta", "check_item", "cross_item"])}
POST = {"headline": "Release <2.4>", "lead": "Notes & fixes",
        "sections": [{"title": "New", "bullets": ["A", "B"]}, {"title": "Fixed", "status": "done", "bullets": ["C"]},
                     {"title": "Gone", "status": "fail"}],
        "cta": {"text": "Read more", "url": "https://example.com/?a=1&b=2"}}


class Posts(unittest.TestCase):
    def test_channel_needs_fragment(self):
        prem = IconSystem(ICONS, eligibility=Eligibility(owner_premium=True)).for_context(SendContext.channel())
        frag = IconSystem(ICONS, eligibility=Eligibility(fragment_usernames=True)).for_context(SendContext.channel())
        self.assertNotIn("tg-emoji", decorate_post(POST, prem)["text"])
        self.assertIn("tg-emoji", decorate_post(POST, frag)["text"])

    def test_fallback_post_equals_stripped_post(self):
        on, off = IconSystem(ICONS), IconSystem(ICONS, enabled=False)
        self.assertEqual(strip_html(decorate_post(POST, on)["text"]), decorate_post(POST, off)["text"])

    def test_density_and_structure(self):
        p = decorate_post(POST, IconSystem(ICONS))
        text = p["text"]
        self.assertEqual(density_warnings(p, post=True), [])
        self.assertLessEqual(text.count("<tg-emoji"), DENSITY["post_text"])
        self.assertTrue(text.startswith("<b><tg-emoji"))
        self.assertIn("&lt;2.4&gt;", text)
        self.assertIn('href="https://example.com/?a=1&amp;b=2"', text)
        link_line = next(line for line in text.split("\n") if "<a href" in line)
        self.assertNotIn("tg-emoji", link_line.split("<a href")[1])     # never inside the link
        self.assertIn("• C", text)                                       # bullets accented in the first list only
        self.assertIn(f'emoji-id="{ICONS["check_item"]["id"]}"', text)
        self.assertIn(f'emoji-id="{ICONS["cross_item"]["id"]}"', text)

    def test_budget_caps_accents(self):
        p = decorate_post(POST, IconSystem(ICONS), max_accents=2)
        self.assertEqual(p["text"].count("<tg-emoji"), 2)

    def test_density_warning_triggers(self):
        line = '<tg-emoji emoji-id="1">✅</tg-emoji> <tg-emoji emoji-id="2">✅</tg-emoji>'
        self.assertTrue(any("one line" in w for w in density_warnings({"text": line}, post=True)))
        many = "\n".join(['<tg-emoji emoji-id="1">✅</tg-emoji>'] * 9)
        self.assertTrue(any("post text" in w for w in density_warnings({"text": many}, post=True)))


if __name__ == "__main__":
    unittest.main()
