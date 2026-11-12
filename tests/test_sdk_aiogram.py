"""Check 6 on a real SDK: aiogram 3.31.0 loses widget_query unless adapted.

Skipped when aiogram isn't installed. To run:
  python -m venv .venv && .venv/Scripts/python -m pip install -r examples/python/sdk_aiogram/requirements.txt
  .venv/Scripts/python -m unittest discover -s tests
"""
import asyncio
import os
import sys
import unittest
import warnings

import _paths

try:
    import aiogram
    from aiogram import Bot
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Update
except ImportError:  # pragma: no cover
    aiogram = None

sys.path.insert(0, os.path.join(_paths.EXAMPLES, "python"))


@unittest.skipIf(aiogram is None, "aiogram not installed")
class Aiogram(unittest.TestCase):
    def setUp(self):
        from sdk_aiogram.adapter import WidgetAwareDispatcher  # noqa: F401
        self.bot = Bot("123456:" + "A" * 35)     # never used for network here

    def tearDown(self):
        asyncio.run(self.bot.session.close())

    def raw(self, name):
        return Update.model_validate({k: v for k, v in _paths.load("examples", "fixtures", name).items()
                                      if not k.startswith("_")})

    def test_version_under_test(self):
        self.assertEqual(aiogram.__version__, "3.31.0")
        self.assertEqual(aiogram.__api_version__, "10.3")

    def test_10_3_fields_serialize(self):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Sold out", disabled={})]],
                                  force_reply=True)
        dumped = kb.model_dump(exclude_none=True)
        self.assertEqual(dumped["inline_keyboard"][0][0], {"text": "Sold out", "disabled": {}})
        self.assertTrue(dumped["force_reply"])
        upd = self.raw("stopped_message_generation.json")
        self.assertEqual(upd.event_type, "stopped_message_generation")

    def test_plain_dispatcher_drops_widget_query_with_a_warning(self):
        from aiogram import Dispatcher
        dp = Dispatcher()
        upd = self.raw("widget_query_ship.json")
        self.assertIn("widget_query", upd.model_extra)            # kept as extra ...
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asyncio.run(dp.feed_update(self.bot, upd))
        self.assertTrue(any("unknown update type" in str(w.message) for w in caught))   # ... then dropped
        self.assertNotIn("widget_query", dp.resolve_used_update_types())

    def test_adapter_routes_and_subscribes(self):
        from sdk_aiogram.adapter import AnswerWidgetQuery, SendWidget, WidgetAwareDispatcher
        got = []

        async def handler(kind, payload):
            got.append((kind, payload["id"]))

        dp = WidgetAwareDispatcher(widget_handler=handler)
        asyncio.run(dp.feed_update(self.bot, self.raw("widget_query_ship.json")))
        asyncio.run(dp.feed_update(self.bot, self.raw("shared_widget_query_vote.json")))
        self.assertEqual(got, [("widget_query", "8123456789012345678"), ("shared_widget_query", "8123456789012340101")])
        self.assertTrue({"widget_query", "shared_widget_query"} <= set(dp.resolve_used_update_types()))
        m = SendWidget(chat_id=1, html="<p>x</p>", caption="c", allow_queries=True)
        self.assertEqual(m.__api_method__, "sendWidget")
        self.assertEqual(m.model_dump(exclude_none=True), {"chat_id": 1, "html": "<p>x</p>", "caption": "c",
                                                           "allow_queries": True})
        self.assertEqual(AnswerWidgetQuery(widget_query_id="q", data="{}").__api_method__, "answerWidgetQuery")


if __name__ == "__main__":
    unittest.main()
