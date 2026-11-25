"""Bot runtime shared by every SDK adapter: Telegram update in, Bot API requests out.

It lives with the Studio adapters, not in the skill: only they run a bot-ui project as a bot.
The importer puts the skill's scripts/ (the bot_ui core) on sys.path first.

    runtime = Runtime(project_root, handlers={"checkout.confirm": charge}, context=trusted_ctx, data=order_data)
    result = await runtime.handle(update_dict, execute)   # execute(method, params) -> API result

* The project is read from its source files on start and re-read whenever its revision
  changes, so a Studio save reaches the next update without a restart.
* Routing, Back, rules, handlers, stale buttons and fallbacks are the engine's (engine.py);
  this module only maps updates to engine events and effects to requests.
* Context comes from the trusted runtime (the chat type from Telegram plus `context(update)`),
  never from callback_data. Handlers decide on the server (payments, permissions).
* callback_query may carry `message` (possibly inaccessible: date == 0) or, depending on
  setMySettings callback_query_mode (Bot API 10.5), only `inline_message_id`.
* A press on a keyboard the session does not know (bot restarted, session store cleared) is
  adopted: its screen comes from callback_data, then the press is handled normally.
"""
from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from bot_ui import render, widgets
from bot_ui.engine import Engine, new_session
from bot_ui.project import Snapshot, open_snapshot

Execute = Callable[[str, dict], Any]
CHAT_TYPES = {"private": "private", "group": "group", "supergroup": "group", "channel": "channel"}


class MemorySessions:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, session: dict) -> None:
        self.data[key] = session


async def _maybe(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class Runtime:
    def __init__(self, root: str, *, handlers: dict[str, Callable[[dict], Any]] | None = None,
                 context: Callable[[dict], Any] | None = None, data: Callable[[dict], Any] | None = None,
                 sessions: Any = None) -> None:
        self.root = root
        self.handlers = handlers or {}
        self.context = context
        self.data = data
        self.sessions = sessions or MemorySessions()
        self._snap: Snapshot | None = None
        self._widget_cache: dict[str, dict] = {}

    # ------------------------------------------------------------ project
    def snapshot(self) -> Snapshot:
        fresh = open_snapshot(self.root)
        if self._snap is None or fresh.revision != self._snap.revision:
            self._snap = fresh
            self._widget_cache.clear()
        return self._snap

    def callback_map(self, snap: Snapshot) -> dict[str, list[tuple[str, str]]]:
        """callback_data -> every (screenId, actionId) using it (shared values do the same thing)."""
        out: dict[str, list[tuple[str, str]]] = {}
        for sid, s in snap.screens.items():
            for aid, a in (s.get("actions") or {}).items():
                if isinstance(a, dict) and a.get("type") != "url":
                    out.setdefault(render.callback_data(sid, aid, a), []).append((sid, aid))
        return out

    # ------------------------------------------------------------ updates
    async def handle(self, update: dict, execute: Execute) -> dict:
        snap = self.snapshot()
        project = snap.project or {}
        requests: list[tuple[str, dict]] = []

        async def call(method: str, params: dict) -> Any:
            requests.append((method, params))
            return await _maybe(execute(method, params))

        if "callback_query" in update:
            cq = update["callback_query"]
            msg = cq.get("message")
            chat_id = (msg or {}).get("chat", {}).get("id") if msg else cq["from"]["id"]
            chat_type = (msg or {}).get("chat", {}).get("type", "private") if msg else "private"
        elif "message" in update and isinstance(update["message"].get("text"), str):
            cq, msg = None, update["message"]
            chat_id, chat_type = msg["chat"]["id"], msg["chat"].get("type", "private")
        else:
            return {"ignored": True, "requests": requests, "trace": None}

        key = str(chat_id)
        s = self.sessions.get(key) or new_session(project, locale=self._locale(update, project))
        s.setdefault("tg", {})
        s["context"]["chat"] = CHAT_TYPES.get(chat_type, chat_type)
        if self.context:
            s["context"].update(await _maybe(self.context(update)) or {})
        if self.data:
            s["data"].update(await _maybe(self.data(update)) or {})

        outcome: dict[str, str] = {}
        if cq is not None:
            hits = self.callback_map(snap).get(cq.get("data") or "")
            if not hits:
                await call("answerCallbackQuery", {"callback_query_id": cq["id"], "text": Engine(snap)._text("stale", s["locale"])})
                self.sessions.put(key, s)
                return {"ignored": False, "requests": requests,
                        "trace": {"update": {"type": "callback_query", "data": cq.get("data")}, "action": {"type": "stale"},
                                  "transition": None, "effects": [{"type": "answer", "text": "stale"}], "diagnostics": []}}
            sid, aid = self._pick(s, cq, msg, hits)
            instance = self._instance_for(s, cq, msg, sid)
            event = {"press": aid, "message": instance}
            act = snap.screens[sid]["actions"][aid]
            if act.get("type") == "handler" and act.get("handlerId") in self.handlers:
                ctx = {"chatId": chat_id, "userId": cq["from"]["id"], "screenId": sid, "actionId": aid,
                       "state": dict(s["state"]), "input": dict(s["input"]), "context": dict(s["context"])}
                outcome[act["handlerId"]] = await _maybe(self.handlers[act["handlerId"]](ctx))
        else:
            event = {"text": msg["text"]}

        engine = Engine(snap, lambda hid, _c: outcome.get(hid, ""))
        entry = engine.feed(s, event)
        for eff in entry["effects"]:
            await self._effect(snap, s, eff, chat_id, cq, call)
        self.sessions.put(key, s)
        return {"ignored": False, "requests": requests, "trace": entry, "revision": snap.revision}

    async def notify(self, chat_id: int, event_key: str, data: dict, execute: Execute) -> dict:
        """An external event (order status changed) -> its entry point screen as a new message."""
        snap = self.snapshot()
        key = str(chat_id)
        s = self.sessions.get(key) or new_session(snap.project or {})
        s.setdefault("tg", {})
        s["context"].setdefault("chat", "private")
        requests: list[tuple[str, dict]] = []

        async def call(method: str, params: dict) -> Any:
            requests.append((method, params))
            return await _maybe(execute(method, params))

        entry = Engine(snap).feed(s, {"event": event_key, "data": data})
        for eff in entry["effects"]:
            await self._effect(snap, s, eff, chat_id, None, call)
        self.sessions.put(key, s)
        return {"requests": requests, "trace": entry, "revision": snap.revision}

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _locale(update: dict, project: dict) -> str:
        user = (update.get("message") or update.get("callback_query") or {}).get("from") or {}
        code = (user.get("language_code") or "").split("-")[0]
        return code if code in (project.get("locales") or []) else project.get("defaultLocale", "en")

    @staticmethod
    def _pick(s: dict, cq: dict, msg: dict | None, hits: list[tuple[str, str]]) -> tuple[str, str]:
        """The screen the pressed message shows, when the session knows it; else the first."""
        ref = {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"]} if msg else \
            {"inline_message_id": cq.get("inline_message_id")}
        inst = next((int(i) for i, known in s.get("tg", {}).items() if known == ref), None)
        shown = next((m["screen"] for m in s.get("messages", []) if m["instance"] == inst), None)
        return next(((sid, aid) for sid, aid in hits if sid == shown), hits[0])

    @staticmethod
    def _instance_for(s: dict, cq: dict, msg: dict | None, sid: str) -> int:
        if msg is not None:
            ref = {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"]}
        else:
            ref = {"inline_message_id": cq.get("inline_message_id")}
        inaccessible = msg is not None and msg.get("date") == 0
        for inst, known in s["tg"].items():
            if known == ref:
                if inaccessible:
                    for m in s["messages"]:
                        if m["instance"] == int(inst):
                            m["accessible"] = False
                return int(inst)
        inst = s["next"]
        s["next"] += 1
        s["messages"].append({"instance": inst, "screen": sid, "state": None, "kind": "message",
                              "accessible": not inaccessible})
        s["tg"][str(inst)] = ref
        s["active"] = inst
        if s["screen"] is None:
            s["screen"] = sid
        return inst

    async def _effect(self, snap: Snapshot, s: dict, eff: dict, chat_id: int, cq: dict | None, call) -> None:
        t = eff["type"]
        if t == "answer" and cq is not None:
            params = {"callback_query_id": cq["id"]}
            if eff.get("text"):
                params["text"] = eff["text"]
            await call("answerCallbackQuery", params)
        elif t == "send":
            logical = eff["render"]
            if eff.get("kind") == "widget":
                wid = eff["widget"]
                built = self._widget(snap, wid, logical["locale"], s)
                req = {"method": "sendWidget",
                       "params": widgets.payload(snap, wid, built, chat_id=chat_id,
                                                 reply_markup=render.reply_markup(logical))["params"]}
            else:
                req = render.bot_request(logical, chat_id)
            result = await call(req["method"], req["params"])
            mid = result.get("message_id") if isinstance(result, dict) else getattr(result, "message_id", None)
            s["tg"][str(eff["instance"])] = {"chat_id": chat_id, "message_id": mid}
        elif t == "edit":
            ref = s["tg"].get(str(eff["instance"])) or {}
            req = render.bot_request(eff["render"], chat_id, edit_message_id=ref.get("message_id"),
                                     inline_message_id=ref.get("inline_message_id"))
            await call(req["method"], req["params"])

    def _widget(self, snap: Snapshot, wid: str, lang: str, s: dict) -> dict:
        values = {}
        for part in ("data", "context", "state", "input"):
            values.update(s[part])
        key = f"{wid}:{lang}:{sorted(values.items())}"
        if key not in self._widget_cache:
            built = widgets.build(snap, wid, lang=lang, values=values)
            if not built["ok"]:
                raise RuntimeError(f"widget {wid} [{lang}] does not build: {built['errors'][:3]}")
            self._widget_cache[key] = built
        return self._widget_cache[key]


AsyncHandler = Callable[[dict], Awaitable[str]]
