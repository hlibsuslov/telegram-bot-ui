"""bot-ui widget workbench backend: assembly, builds bound to sources, export, import split."""
from __future__ import annotations

import os
import re
import unittest

from _bot_ui import ROOT, ProjectCase
from bot_ui import widgets
from bot_ui.project import open_snapshot
from bot_ui.skill import load

GALLERY_SRC = os.path.join(ROOT, "skills", "telegram-bot-ui", "examples", "widgets", "src", "order-tracker.html")
VALUES = {"order.no": "4821", "order.status_text": "в пути 🛵"}


class Widgets(ProjectCase):
    def test_build_every_language_within_limits_and_payload_passes_the_catalog(self):
        snap = open_snapshot(self.root)
        vp = load("validate_payload")
        v = vp.Validator(vp.load_catalog(vp.DATA_DIR))
        for lang in ("ru", "en"):
            b = widgets.build(snap, "order-status", lang=lang, values=VALUES)
            self.assertTrue(b["ok"], b["errors"])
            self.assertLessEqual(b["rawBytes"], 32768)
            self.assertLessEqual(b["compressedBytes"], 4096)
            self.assertEqual(b["caption"], "Заказ #4821 · в пути 🛵" if lang == "ru" else "Order #4821 · в пути 🛵")
            p = widgets.payload(snap, "order-status", b)
            self.assertEqual(p["method"], "sendWidget")
            self.assertTrue(v.check_request(p["method"], p["params"]).ok)
            self.assertLessEqual(len(p["params"]["chat_data"].encode()), 1024)

    def test_split_sources_assemble_to_the_gallery_source(self):
        snap = open_snapshot(self.root)
        with open(GALLERY_SRC, encoding="utf-8") as fh:
            original = fh.read()
        assembled = widgets.assemble(snap, "order-status")
        self.assertEqual(re.sub(r"^<!--[^\n]*\n", "", assembled), re.sub(r"^<!--[^\n]*\n", "", original))

    def test_import_split_round_trip(self):
        with open(GALLERY_SRC, encoding="utf-8") as fh:
            original = fh.read()
        files = widgets.split_html(original)
        self.assertEqual(sorted(files), ["index.html", "style.css", "widget.js"])
        snap = open_snapshot(self.root)
        files_bytes = dict(snap.files)
        for name, text in files.items():
            files_bytes[f"widgets/order-status/{name}"] = text.encode("utf-8")
        from bot_ui.project import parse_files
        self.assertEqual(widgets.assemble(parse_files(self.root, files_bytes), "order-status"), original)

    def test_stale_build_cannot_be_exported_even_when_results_arrive_late(self):
        snap1 = open_snapshot(self.root)
        old = widgets.build(snap1, "order-status", lang="ru", values=VALUES)
        rel = "widgets/order-status/style.css"
        self.write_raw(rel, self.raw(rel) + b".tl{margin:10px 0}\n")
        snap2 = open_snapshot(self.root)
        new = widgets.build(snap2, "order-status", lang="ru", values=VALUES)
        self.assertNotEqual(old["sourceHash"], new["sourceHash"])
        with self.assertRaises(widgets.WidgetError) as ctx:
            widgets.export(snap2, "order-status", old, old["sourceHash"])  # the older build "arrived last"
        self.assertEqual(ctx.exception.code, "STALE_BUILD")
        out = widgets.export(snap2, "order-status", new, new["sourceHash"])
        self.assertEqual(out["sourceHash"], new["sourceHash"])
        self.assertIn(".tl{margin:10px 0}", out["html"])

    def test_language_is_part_of_the_build_identity(self):
        snap = open_snapshot(self.root)
        ru = widgets.build(snap, "order-status", lang="ru", values=VALUES)
        en = widgets.build(snap, "order-status", lang="en", values=VALUES)
        self.assertNotEqual(ru["sourceHash"], en["sourceHash"])

    def test_network_access_fails_the_build(self):
        rel = "widgets/order-status/widget.js"
        self.write_raw(rel, self.raw(rel) + b'fetch("http://127.0.0.1:8790/api/project");\n')
        b = widgets.build(open_snapshot(self.root), "order-status", lang="ru", values=VALUES)
        self.assertFalse(b["ok"])
        self.assertTrue(any("fetch" in e or "network" in e.lower() for e in b["errors"]), b["errors"])

    def test_oversized_widget_reports_both_budgets(self):
        rel = "widgets/order-status/widget.js"
        noise = "".join(f"var v{i}='{os.urandom(24).hex()}';\n" for i in range(700))
        self.write_raw(rel, self.raw(rel) + noise.encode())
        b = widgets.build(open_snapshot(self.root), "order-status", lang="ru", values=VALUES)
        self.assertFalse(b["ok"])
        self.assertGreater(b["rawBytes"], 32768)
        self.assertTrue(any("32768" in e or "4096" in e for e in b["errors"]), b["errors"][:3])

    def test_missing_inlined_file_is_a_build_error(self):
        os.remove(os.path.join(self.root, "widgets", "order-status", "style.css"))
        b = widgets.build(open_snapshot(self.root), "order-status", lang="ru")
        self.assertFalse(b["ok"])
        self.assertIn("WIDGET_FILE_MISSING", b["errors"][0])

    def test_svg_asset_is_inlined_and_out_of_profile_svg_fails(self):
        svg = ('<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
               '<path fill="#2481cc" d="M0 0h8v8H0z"/></svg>\n')
        self.write_raw("widgets/order-status/logo.svg", svg.encode())
        rel = "widgets/order-status/index.html"
        self.write_raw(rel, self.raw(rel).replace(b'<div class="k">', b'<div class="k"><!--@file logo.svg-->'))
        snap = open_snapshot(self.root)
        self.assertIn('<div class="k"><svg viewBox="0 0 8 8"><path', widgets.assemble(snap, "order-status"))
        self.assertTrue(widgets.build(snap, "order-status", lang="en", values=VALUES)["ok"])
        self.write_raw("widgets/order-status/logo.svg", b'<svg viewBox="0 0 8 8"><image href="data:image/png;base64,AA=="/></svg>')
        bad = widgets.build(open_snapshot(self.root), "order-status", lang="en", values=VALUES)
        self.assertFalse(bad["ok"])

    def test_new_widget_from_blank_and_from_the_gallery(self):
        from bot_ui.store import write_patch
        names = [t["id"] for t in widgets.templates()]
        self.assertEqual(names[0], "blank")
        self.assertIn("gallery:quiz", names)
        for wid, template in (("promo", "blank"), ("quiz-card", "gallery:quiz")):
            res = write_patch(self.root, widgets.creation_patch(open_snapshot(self.root), wid, template))
            self.assertEqual(len(res.changed_files), 4)
            snap = open_snapshot(self.root)
            for lang in snap.widgets[wid]["languages"]:
                self.assertTrue(widgets.build(snap, wid, lang=lang)["ok"], (wid, lang))
        for bad, code in (("promo", "WIDGET_EXISTS"), ("Bad.ID", "WIDGET_ID_INVALID")):
            with self.assertRaises(widgets.WidgetError) as ctx:
                widgets.creation_patch(open_snapshot(self.root), bad, "blank")
            self.assertEqual(ctx.exception.code, code)
        with self.assertRaises(widgets.WidgetError):
            widgets.creation_patch(open_snapshot(self.root), "x", "gallery:../../etc")

    def test_every_library_template_previews_without_writing(self):
        snap = open_snapshot(self.root)
        for t in widgets.templates():
            r = widgets.template_preview(snap, t["id"], "en")
            self.assertTrue(r["ok"], (t["id"], r["errors"]))
            self.assertLessEqual(r["compressedBytes"], 4096)
        self.assertEqual(open_snapshot(self.root).revision, snap.revision)
        fields = snap.widgets["order-status"]["dataFields"]["chatData"]
        self.assertEqual(set(fields) - set(snap.widgets["order-status"]["states"]["default"]["chatData"]), {"t4"})

    def test_mock_answers_come_from_the_gallery_handler(self):
        answers = widgets.mock_answers(open_snapshot(self.root), "order-status")
        self.assertIn("call", answers["default"])
        self.assertIn("help", answers["cancelled"])


if __name__ == "__main__":
    unittest.main()
