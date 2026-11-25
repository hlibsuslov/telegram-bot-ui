"""Second adapter: no SDK, the skill's tgkit transports (stdlib only).

    from raw_adapter import RawBot
    bot = RawBot("bot-ui", transport=FakeTransport(), handlers={...})
    await bot.handle(update_dict)

FakeTransport (tests) records every call after a JSON round trip; HttpTransport (live, a
separate approved run) comes from tgkit.transport.live_transport_from_env(). Same Runtime as
the aiogram adapter, so routing and payloads are identical; only the wire layer differs.
"""
from __future__ import annotations

import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "skills", "telegram-bot-ui", "scripts"))
if __package__:  # imported as studio.adapters.<name>
    from .runtime import Runtime  # noqa: E402
else:            # run or imported from studio/adapters (demo_bot.py, replays)
    from runtime import Runtime  # noqa: E402
from bot_ui.skill import load  # noqa: E402


class RawBot:
    def __init__(self, root: str, *, transport: Any = None, **runtime_kw) -> None:
        self.transport = transport or load("tgkit.transport").FakeTransport()
        self.runtime = Runtime(root, **runtime_kw)

    def _execute(self, method: str, params: dict) -> Any:
        return self.transport.call(method, params)

    async def handle(self, update: dict) -> dict:
        return await self.runtime.handle(update, self._execute)

    async def notify(self, chat_id: int, event_key: str, data: dict) -> dict:
        return await self.runtime.notify(chat_id, event_key, data, self._execute)
