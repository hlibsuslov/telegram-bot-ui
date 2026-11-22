#!/usr/bin/env python3
"""Demo bot for a bot-ui project on aiogram 3.31.0 (or the raw tgkit adapter).

  py -3 studio/adapters/demo_bot.py --project <bot-ui> --replay studio/fixtures/updates/checkout.json [--raw] [--json]

--replay feeds synthetic updates through aiogram's Dispatcher with a recording session
(no network, no token) and prints every Bot API request, each checked against the skill's
Bot API catalog (structural check). Exit 1 when a request does not pass.

Live run (NOT done by tests; needs a separate, explicitly approved task and a test bot):
  set BOT_TOKEN in the environment outside the repository, then
  py -3 studio/adapters/demo_bot.py --project <bot-ui> --live
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from bot_ui.skill import load  # noqa: E402


def demo_runtime_kw(fixture: dict) -> dict:
    queues = {k: list(v) for k, v in (fixture.get("outcomes") or {}).items()}

    async def confirm(ctx: dict) -> str:
        # A real handler charges on the server and checks the payment; the demo is scripted.
        q = queues.get("checkout.confirm") or ["ok"]
        return q.pop(0) if len(q) > 1 else q[0]

    return {"handlers": {"checkout.confirm": confirm},
            "context": lambda upd: dict(fixture.get("context") or {}),
            "data": lambda upd: dict(fixture.get("data") or {})}


async def replay_aiogram(root: str, fixture: dict) -> list[tuple[str, dict]]:
    from aiogram import Bot, Dispatcher
    from aiogram.types import Update
    from aiogram_adapter import RecordingSession, bot_ui_router
    session = RecordingSession()
    bot = Bot("123456:TEST-TOKEN-NOT-REAL", session=session)
    dp = Dispatcher()
    dp.include_router(bot_ui_router(root, **demo_runtime_kw(fixture)))
    for upd in fixture["updates"]:
        await dp.feed_update(bot, Update.model_validate(upd, context={"bot": bot}))
    return session.calls


async def replay_raw(root: str, fixture: dict) -> list[tuple[str, dict]]:
    from raw_adapter import RawBot
    bot = RawBot(root, **demo_runtime_kw(fixture))
    for upd in fixture["updates"]:
        await bot.handle(upd)
    return bot.transport.calls


def check(calls: list[tuple[str, dict]]) -> list[dict]:
    vp = load("validate_payload")
    v = vp.Validator(vp.load_catalog(vp.DATA_DIR))
    out = []
    for method, params in calls:
        rep = v.check_request(method, params)
        out.append({"method": method, "params": params, "ok": rep.ok, "errors": rep.errors})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--replay")
    ap.add_argument("--raw", action="store_true", help="use the raw tgkit adapter instead of aiogram")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.live:
        return live(a.project)
    with open(a.replay, encoding="utf-8") as fh:
        fixture = json.load(fh)
    calls = asyncio.run((replay_raw if a.raw else replay_aiogram)(os.path.abspath(a.project), fixture))
    checked = check(calls)
    if a.json:
        print(json.dumps(checked, ensure_ascii=False, indent=2))
    else:
        for c in checked:
            p = c["params"]
            what = p.get("text") or p.get("caption") or p.get("callback_query_id") or ""
            print(f"{'ok ' if c['ok'] else 'BAD'} {c['method']:20} {str(what)[:70]!r}")
            for e in c["errors"]:
                print(f"      ! {e}")
        print(f"{len(checked)} request(s), structural check against the skill's Bot API catalog (simulated, not live)")
    return 0 if all(c["ok"] for c in checked) else 1


def live(root: str) -> int:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("BOT_TOKEN is not set; the live run is a separate, approved task", file=sys.stderr)
        return 2
    from aiogram import Bot, Dispatcher
    from aiogram_adapter import bot_ui_router
    dp = Dispatcher()
    dp.include_router(bot_ui_router(root, **demo_runtime_kw({})))
    asyncio.run(dp.start_polling(Bot(token)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
