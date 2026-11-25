"""The saved review next to the map: bot-ui/context/ (outside the map revision).

Shared by the Studio server and tgui.py so both write the same request files:
  context/requests/<id>.json   bot-ui-request/v1: {id, sid, text, at, baseRevision, status, result}
Status: queued -> taken -> done | rejected. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os

from .project import ID_RE

REQUEST_SCHEMA = "bot-ui-request/v1"
MAX_TEXT = 2000


class ContextError(ValueError):
    pass


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def add_request(context_dir: str, sid: str | None, text: str, base_revision: str | None) -> dict:
    text = (text or "").strip()
    if not text:
        raise ContextError("a request needs text")
    if len(text) > MAX_TEXT:
        raise ContextError(f"a request is at most {MAX_TEXT} characters")
    if sid is not None and (not isinstance(sid, str) or not ID_RE.match(sid)):
        raise ContextError(f"not a screen id: {sid!r}")
    at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rid = "rq-" + hashlib.sha1(f"{sid}|{text}|{at}|{os.urandom(4).hex()}".encode("utf-8")).hexdigest()[:10]
    doc = {"schema": REQUEST_SCHEMA, "id": rid, "sid": sid, "text": text, "at": at,
           "baseRevision": base_revision, "status": "queued", "result": None}
    _write_json(os.path.join(context_dir, "requests", f"{rid}.json"), doc)
    return doc


def list_requests(context_dir: str) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(context_dir, "requests", "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("schema") == REQUEST_SCHEMA:
            out.append(doc)
    return sorted(out, key=lambda d: d.get("at") or "")
