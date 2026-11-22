"""Widget workbench backend: source -> assemble -> build_widget (lint, check, zlib-9) -> payload.

A widget lives in widgets/<id>/: widget.json, an entry HTML file and optional local files.
An optional design.json is a design profile (skill scripts/widget_design.py) applied at build.
`<!--@file style.css-->` in the entry inlines a local file as <style>/<script> in place, so the
split keeps the order of styles and scripts. Kit partials (`<!--@kit runtime.js-->`) come
from widgets/_kit/ in the project (vendored by `bot-ui init`), else from the skill.

Every build is bound to `sourceHash` = sha256 of the widget's source bytes, the kit and the
options (language, caption). Export refuses a build whose hash is not the current one.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from typing import Any

from . import render
from .project import Snapshot, normalize_bytes
from .skill import kit_dir as skill_kit_dir
from .skill import load

FILE_MARK = re.compile(r"<!--\s*@file\s+([\w.-]+)\s*-->")


class WidgetError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def _project_kit(snap: Snapshot) -> dict[str, bytes]:
    return {rel[len("widgets/_kit/"):]: data for rel, data in snap.files.items() if rel.startswith("widgets/_kit/")}


def assemble(snap: Snapshot, wid: str) -> str:
    w = snap.widgets.get(wid)
    if w is None:
        raise WidgetError("WIDGET_NOT_FOUND", f"widget {wid} does not exist")
    base = f"widgets/{wid}/"
    entry = base + w.get("entry", "index.html")
    if entry not in snap.files:
        raise WidgetError("WIDGET_ENTRY_MISSING", f"{entry} does not exist")
    text = normalize_bytes(snap.files[entry]).decode("utf-8")

    def sub(m: re.Match) -> str:
        rel = base + m.group(1)
        if rel not in snap.files:
            raise WidgetError("WIDGET_FILE_MISSING", f"{rel} (from {m.group(0)}) does not exist")
        body = normalize_bytes(snap.files[rel]).decode("utf-8")
        tag = "style" if rel.endswith(".css") else "script" if rel.endswith(".js") else None
        if tag is None:
            raise WidgetError("WIDGET_FILE_TYPE", f"{rel}: only .css and .js files can be inlined")
        return f"<{tag}>\n{body}</{tag}>"

    return FILE_MARK.sub(sub, text)


def source_hash(snap: Snapshot, wid: str, options: dict) -> str:
    h = hashlib.sha256()
    for rel in sorted(r for r in snap.files if r.startswith(f"widgets/{wid}/") or r.startswith("widgets/_kit/")):
        h.update(rel.encode() + b"\0" + normalize_bytes(snap.files[rel]) + b"\0")
    h.update(json.dumps(options, sort_keys=True, ensure_ascii=False).encode())
    return "sha256:" + h.hexdigest()


def caption_for(snap: Snapshot, wid: str, lang: str, values: dict | None = None) -> str | None:
    w = snap.widgets[wid]
    p = snap.project or {}
    raw = render.localized(w.get("caption"), lang, p.get("defaultLocale", "en"))
    if raw is None:
        return None
    text, _ = render.fill(raw, values or {}, "regular.plain")
    return text


def build(snap: Snapshot, wid: str, *, lang: str | None = None, values: dict | None = None,
          strict: bool = True) -> dict[str, Any]:
    bw = load("build_widget")
    p = snap.project or {}
    lang = lang or p.get("defaultLocale", "en")
    caption = caption_for(snap, wid, lang, values)
    options = {"lang": lang, "caption": caption, "strict": strict}
    shash = source_hash(snap, wid, options)
    try:
        src = assemble(snap, wid)
    except WidgetError as err:
        return {"ok": False, "widget": wid, "lang": lang, "sourceHash": shash, "errors": [f"[{err.code}] {err.message}"],
                "warnings": [], "html": "", "rawBytes": 0, "compressedBytes": 0, "limits": _limits(bw)}
    try:
        design = design_of(snap, wid)
    except WidgetError as err:
        return {"ok": False, "widget": wid, "lang": lang, "sourceHash": shash, "errors": [f"[{err.code}] {err.message}"],
                "warnings": [], "html": "", "rawBytes": 0, "compressedBytes": 0, "limits": _limits(bw)}
    kit = _project_kit(snap)
    with tempfile.TemporaryDirectory(prefix="bot-ui-kit-") as tmp:
        kd = skill_kit_dir()
        if kit:
            for name, data in kit.items():
                with open(os.path.join(tmp, name), "wb") as fh:
                    fh.write(normalize_bytes(data))
            kd = tmp
        res = bw.build_text(src, caption=caption or None, strict=strict, kit_dir=kd, langs=(lang,), design=design)
        plain = bw.build_text(src, caption=caption or None, kit_dir=kd, langs=(lang,)) if res.design_css else None
    out = {"ok": res.ok, "widget": wid, "lang": lang, "sourceHash": shash, "caption": caption, "html": res.html,
           "rawBytes": res.raw_bytes, "compressedBytes": res.compressed_bytes, "includes": res.includes,
           "errors": res.errors, "warnings": res.warnings, "limits": _limits(bw), "summary": res.summary() if res.ok else ""}
    if design is not None:
        wd = load("widget_design")
        out["design"] = {"css": res.design_css, "bytes": res.compressed_bytes - plain.compressed_bytes if plain else 0,
                         "contrast": wd.contrast_report(design)}
    return out


def design_of(snap: Snapshot, wid: str) -> dict | None:
    """The widget's design profile (widgets/<id>/design.json), or None when it has none."""
    raw = snap.files.get(f"widgets/{wid}/design.json")
    if raw is None:
        return None
    try:
        design = json.loads(normalize_bytes(raw).decode("utf-8"))
    except ValueError as err:
        raise WidgetError("DESIGN_INVALID", f"widgets/{wid}/design.json is not valid JSON: {err}") from err
    if not isinstance(design, dict):
        raise WidgetError("DESIGN_INVALID", f"widgets/{wid}/design.json must be an object")
    return design


def _limits(bw) -> dict:
    return {"rawBytes": bw.HTML_MAX_BYTES, "compressedBytes": bw.HTML_MAX_COMPRESSED, "dataBytes": bw.DATA_MAX_BYTES}


def payload(snap: Snapshot, wid: str, built: dict, *, chat_id: int | str = 111111111, state: str = "default",
            reply_markup: dict | None = None) -> dict:
    """sendWidget request for a successful build, with the demo state of widget.json."""
    bw = load("build_widget")
    w = snap.widgets[wid]
    st = (w.get("states") or {}).get(state) or {}
    send = w.get("send") or {}
    return bw.payload(built["html"], chat_id=chat_id, caption=built.get("caption"), chat_data=st.get("chatData"),
                      public_data=st.get("publicData"), shared=send.get("is_shared", False),
                      allow_queries=send.get("allow_queries", False), reply_markup=reply_markup,
                      width=send.get("width"), height=send.get("height"))


def export(snap: Snapshot, wid: str, built: dict, expected_hash: str) -> dict:
    """Refuse a stale build: the hash must match the current sources and options."""
    options = {"lang": built["lang"], "caption": built.get("caption"), "strict": True}
    current = source_hash(snap, wid, options)
    if expected_hash != current or built.get("sourceHash") != current:
        raise WidgetError("STALE_BUILD", "the build is not of the current sources; rebuild before export")
    if not built.get("ok"):
        raise WidgetError("BUILD_FAILED", "the build has errors; fix them before export")
    return {"html": built["html"], "payload": payload(snap, wid, built), "sourceHash": current}


def split_html(single: str) -> dict[str, str]:
    """Import a single-file widget as index.html + style.css + widget.js, reversibly: only one
    <style> and one <script> without attributes are split out; anything else stays inline.
    assemble() of the result reproduces `single` byte for byte (checked by the caller)."""
    styles = list(re.finditer(r"<style>\n(.*?)</style>", single, re.S))
    scripts = list(re.finditer(r"<script>\n(.*?)</script>", single, re.S))
    files: dict[str, str] = {}
    out = single
    if len(scripts) == 1:
        m = scripts[0]
        files["widget.js"] = m.group(1)
        out = out[:m.start()] + "<!--@file widget.js-->" + out[m.end():]
    if len(styles) == 1:
        m = re.search(r"<style>\n(.*?)</style>", out, re.S)
        files["style.css"] = m.group(1)
        out = out[:m.start()] + "<!--@file style.css-->" + out[m.end():]
    files["index.html"] = out
    return files


def mock_answers(snap: Snapshot, wid: str) -> dict:
    """Precomputed answers of the gallery handler named in widget.json mock.handler."""
    w = snap.widgets[wid]
    handler = (w.get("mock") or {}).get("handler", "")
    if not handler.startswith("gallery:"):
        return {}
    pw = load("preview_widget")
    demo = {k: w[k] for k in ("states", "queries", "fresh", "now", "caption") if k in w}
    return pw.precomputed_answers(handler.split(":", 1)[1], demo)


def preview_runtime() -> dict:
    """The skill's mock runtime (JS) and default CSS for the sandboxed preview frame, plus the
    design-profile catalogue (slots, options, presets) the Design tab draws its controls from."""
    pw = load("preview_widget")
    return {"mock": pw.MOCK_JS, "css": pw.DEFAULT_CSS, "themes": pw.THEMES, "design": load("widget_design").catalog()}
