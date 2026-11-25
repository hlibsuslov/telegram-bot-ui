"""aiogram 3.31.0 adapter for a bot-ui project (the first adapter).

    from aiogram import Bot, Dispatcher
    from aiogram_adapter import bot_ui_router

    dp = Dispatcher()
    dp.include_router(bot_ui_router("bot-ui", handlers={"checkout.confirm": charge},
                                    context=lambda upd: {"delivery.method": order_delivery(upd)}))
    await dp.start_polling(Bot(token))          # live: a separate, explicitly approved run

Every request goes through aiogram's own method classes and the bot's session, so the SDK
serialises it (RecordingSession below captures exactly that in tests). sendWidget is Bot API
10.4, newer than aiogram 3.31.0 (Bot API 10.3): the skill's SendWidget method class is used
(skills/telegram-bot-ui/examples/python/sdk_aiogram/adapter.py).

The project is re-read when its revision changes (a Studio save reaches the next update).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable

from aiogram import Bot, Router
from aiogram.client.session.base import BaseSession
from aiogram.methods import (AnswerCallbackQuery, EditMessageMedia, EditMessageText, SendAnimation, SendAudio,
                             SendMessage, SendPhoto, SendSticker, SendVideo, SendVideoNote, SendVoice)
from aiogram.types import CallbackQuery, Message

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "skills", "telegram-bot-ui", "scripts"))
if __package__:  # imported as studio.adapters.<name>
    from .runtime import Runtime  # noqa: E402
else:            # run or imported from studio/adapters (demo_bot.py, replays)
    from runtime import Runtime  # noqa: E402
from bot_ui.skill import load  # noqa: E402

SendWidget = load("sdk_aiogram.adapter").SendWidget
METHODS = {"sendMessage": SendMessage, "editMessageText": EditMessageText, "editMessageMedia": EditMessageMedia,
           "answerCallbackQuery": AnswerCallbackQuery, "sendWidget": SendWidget,
           "sendPhoto": SendPhoto, "sendVideo": SendVideo, "sendAnimation": SendAnimation, "sendAudio": SendAudio,
           "sendVoice": SendVoice, "sendVideoNote": SendVideoNote, "sendSticker": SendSticker}


def _dump(obj) -> dict:
    return obj.model_dump(mode="json", exclude_none=True, by_alias=True)


def make_execute(bot: Bot) -> Callable[[str, dict], Any]:
    async def execute(method: str, params: dict) -> Any:
        cls = METHODS.get(method)
        if cls is None:
            raise RuntimeError(f"bot-ui adapter: no aiogram method for {method}")
        return await bot(cls(**params))
    return execute


def bot_ui_router(root: str, **runtime_kw) -> Router:
    runtime = Runtime(root, **runtime_kw)
    router = Router(name="bot-ui")
    router.bot_ui_runtime = runtime  # type: ignore[attr-defined]

    @router.message()
    async def on_message(message: Message, bot: Bot) -> None:
        if message.text is None:
            return
        await runtime.handle({"message": _dump(message)}, make_execute(bot))

    @router.callback_query()
    async def on_callback(query: CallbackQuery, bot: Bot) -> None:
        await runtime.handle({"callback_query": _dump(query)}, make_execute(bot))

    return router


class RecordingSession(BaseSession):
    """Test transport: records each request as aiogram would put it on the wire and returns
    plausible results. No network."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self._mid = 1000

    async def make_request(self, bot: Bot, method, timeout: int | None = None):
        files: dict = {}
        wire = {}
        for key, original in method.model_dump(warnings=False).items():
            value = self.prepare_value(original, bot=bot, files=files)
            if not value:
                continue  # exactly what build_form_data skips
            # Form fields are strings; decode back only what aiogram itself JSON-encoded.
            if isinstance(original, (dict, list)) or hasattr(original, "model_dump"):
                value = json.loads(value)
            elif isinstance(original, bool):
                value = value == "true"
            elif isinstance(original, int):
                value = int(value)
            wire[key] = value
        for k in ("chat_id", "message_id"):
            if isinstance(wire.get(k), str) and wire[k].lstrip("-").isdigit():
                wire[k] = int(wire[k])
        name = method.__api_method__
        self.calls.append((name, wire))
        if name.startswith("send"):
            self._mid += 1
            return Message.model_validate({"message_id": self._mid, "date": 1794736800,
                                           "chat": {"id": int(wire["chat_id"]), "type": "private"},
                                           "text": wire.get("text", "")}, context={"bot": bot})
        if name in ("editMessageText", "editMessageMedia"):
            return Message.model_validate({"message_id": int(wire.get("message_id", 0)), "date": 1794736800,
                                           "chat": {"id": int(wire.get("chat_id", 0) or 0), "type": "private"},
                                           "text": wire.get("text", "")}, context={"bot": bot})
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError
        yield b""
