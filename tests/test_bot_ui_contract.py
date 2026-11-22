"""bot-ui contract: model, IDs, validation, revisions, rendering (studio/bot_ui)."""
from __future__ import annotations

import json
import os
import unittest

from _bot_ui import FIXTURES, TEMPLATE, ProjectCase
from bot_ui import render
from bot_ui.project import PathError, canonical_json, check_id, open_snapshot, resolve_inside, revision_of
from bot_ui.store import StoreError, write_patch
from bot_ui.validate import validate


def codes(snap, severity="error"):
    return sorted({d.code for d in validate(snap) if d.severity == severity})


class TemplateFixture(unittest.TestCase):
    def test_template_is_valid_with_no_warnings(self):
        snap = open_snapshot(TEMPLATE)
        self.assertEqual([d.to_json() for d in validate(snap)], [])

    def test_template_screens_are_canonical(self):
        snap = open_snapshot(TEMPLATE)
        for sid, rel in snap.screen_files.items():
            self.assertEqual(snap.files[rel], canonical_json(snap.screens[sid], "screen"), rel)


class Ids(unittest.TestCase):
    def test_valid_and_invalid_ids(self):
        self.assertIsNone(check_id("checkout.payment.confirm"))
        for bad in ("", "Checkout.pay", "checkout..pay", ".x", "x.", "кнопка", "a" * 65, "orders.con", "a b"):
            self.assertIsNotNone(check_id(bad), bad)


class Paths(ProjectCase):
    def test_paths_outside_the_root_are_refused(self):
        for rel in ("../x.json", "screens/../../x", "/etc/passwd", "C:/Windows/x", "\\\\server\\share\\x",
                    "screens//x.json", "screens/./x.json"):
            with self.assertRaises(PathError, msg=rel):
                resolve_inside(self.root, rel)
        self.assertTrue(resolve_inside(self.root, "screens/entry.start.json").endswith("entry.start.json"))

    def test_symlinked_folder_is_not_followed(self):
        target = os.path.join(self._tmp, "elsewhere")
        os.makedirs(target)
        link = os.path.join(self.root, "linked")
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks need privileges on this host")
        with self.assertRaises(PathError):
            resolve_inside(self.root, "linked/x.json")


class Revision(ProjectCase):
    def test_revision_ignores_crlf_mtime_and_state_dir(self):
        rev = open_snapshot(self.root).revision
        rel = "screens/entry.start.json"
        self.write_raw(rel, self.raw(rel).replace(b"\n", b"\r\n"))
        os.makedirs(os.path.join(self.root, ".bot-ui", "build"), exist_ok=True)
        with open(os.path.join(self.root, ".bot-ui", "build", "x.html"), "w") as fh:
            fh.write("cache")
        with open(os.path.join(self.root, "NOTES.md"), "w") as fh:
            fh.write("not a source")
        self.assertEqual(open_snapshot(self.root).revision, rev)

    def test_revision_changes_with_any_source_byte(self):
        rev = open_snapshot(self.root).revision
        rel = "widgets/order-status/style.css"
        self.write_raw(rel, self.raw(rel) + b"/* x */\n")
        self.assertNotEqual(open_snapshot(self.root).revision, rev)

    def test_revision_is_order_independent(self):
        self.assertEqual(revision_of({"a": b"1", "b": b"2"}), revision_of({"b": b"2", "a": b"1"}))


class Validation(ProjectCase):
    def test_failure_fixtures_are_refused_with_their_code_and_pointer(self):
        with open(os.path.join(FIXTURES, "failures", "cases.json"), encoding="utf-8") as fh:
            cases = json.load(fh)["cases"]
        rev = open_snapshot(self.root).revision
        for case in cases:
            with self.subTest(case["name"]):
                patch = {"format": "bot-ui-patch/v1", "baseRevision": rev,
                         "changes": [{"screenId": case["screenId"], "ops": case["ops"]}]}
                with self.assertRaises(StoreError) as ctx:
                    write_patch(self.root, patch, dry_run=True)
                self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")
                found = {(d["code"], d["pointer"]) for d in ctx.exception.extra["diagnostics"]}
                self.assertIn((case["expect"]["code"], case["expect"]["pointer"]), found)
                files = {d["file"] for d in ctx.exception.extra["diagnostics"]}
                self.assertEqual(files, {f"screens/{case['screenId']}.json"})
        self.assertEqual(open_snapshot(self.root).revision, rev, "a refused patch writes nothing")

    def test_duplicate_id_and_wrong_file_name(self):
        doc = self.read("screens/orders.pickup.json")
        with open(os.path.join(self.root, "screens", "orders.pickup-copy.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        self.assertIn("SCREEN_DUPLICATE", codes(open_snapshot(self.root)))

    def test_callback_collision_and_limit(self):
        doc = self.read("screens/orders.pickup.json")
        doc["actions"]["back"]["callbackData"] = "orders.status:route"  # same value, another effect
        doc["actions"]["extra"] = {"label": {"ru": "x", "en": "x"}, "type": "answer", "text": {"ru": "x", "en": "x"},
                                   "callbackData": "x" * 65}
        doc["keyboard"]["rows"].append(["extra"])
        with open(os.path.join(self.root, "screens", "orders.pickup.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        found = codes(open_snapshot(self.root))
        self.assertIn("CALLBACK_COLLISION", found)
        self.assertIn("CALLBACK_DATA_INVALID", found)

    def test_shared_callback_with_the_same_effect_is_allowed(self):
        doc = self.read("screens/orders.pickup.json")
        doc["actions"]["back"]["callbackData"] = "orders.delivery:back"  # both go back to orders.status
        with open(os.path.join(self.root, "screens", "orders.pickup.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        snap = open_snapshot(self.root)
        self.assertNotIn("CALLBACK_COLLISION", codes(snap))
        self.assertIn("CALLBACK_SHARED", codes(snap, "info"))

    def test_long_ids_get_a_hashed_callback_within_64_bytes(self):
        sid, aid = "a" * 30 + "." + "b" * 30, "confirm_and_continue"
        cb = render.callback_data(sid, aid)
        self.assertTrue(cb.startswith("h:"))
        self.assertLessEqual(len(cb.encode()), 64)
        self.assertEqual(cb, render.callback_data(sid, aid))

    def test_audience_mismatch(self):
        p = self.read("project.json")
        p["contexts"] = ["private", "group"]
        with open(os.path.join(self.root, "project.json"), "w", encoding="utf-8") as fh:
            json.dump(p, fh, ensure_ascii=False)
        doc = self.read("screens/orders.pickup.json")
        doc["audience"] = "group"
        with open(os.path.join(self.root, "screens", "orders.pickup.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        self.assertIn("AUDIENCE_MISMATCH", codes(open_snapshot(self.root)))

    def test_unknown_schema_version_opens_read_only(self):
        p = self.read("project.json")
        p["schemaVersion"] = 2
        with open(os.path.join(self.root, "project.json"), "w", encoding="utf-8") as fh:
            json.dump(p, fh)
        snap = open_snapshot(self.root)
        self.assertTrue(snap.read_only)
        self.assertIn("checkout.payment.confirm", snap.screens)
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": snap.revision, "changes": [
                {"screenId": "entry.start", "ops": [{"op": "set", "path": "/title", "value": "x"}]}]})
        self.assertEqual(ctx.exception.code, "READ_ONLY")

    def test_read_only_format_is_kept(self):
        doc = self.read("screens/orders.pickup.json")
        doc["message"]["format"] = "rich"
        doc["message"]["blocks"] = [{"type": "paragraph", "text": "kept"}]
        with open(os.path.join(self.root, "screens", "orders.pickup.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        snap = open_snapshot(self.root)
        self.assertIn("FORMAT_READ_ONLY", codes(snap, "info"))
        rev = snap.revision
        write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": rev, "changes": [
            {"screenId": "orders.pickup", "ops": [{"op": "set", "path": "/title", "value": "Самовывоз!"}]}]})
        self.assertEqual(self.read("screens/orders.pickup.json")["message"]["blocks"], [{"type": "paragraph", "text": "kept"}])


class Rendering(unittest.TestCase):
    def setUp(self):
        self.snap = open_snapshot(TEMPLATE)
        self.p = self.snap.project

    def test_placeholders_are_escaped_for_html(self):
        r = render.render_screen(self.p, self.snap.screens["checkout.payment.confirm"], locale="en",
                                 values={"order.no": "<1&2>", "order.total": "5 €", "order.note": "🚪 <b>x</b>"})
        self.assertIn("#&lt;1&amp;2&gt;", r["text"])
        self.assertIn("🚪 &lt;b&gt;x&lt;/b&gt;", r["text"])
        self.assertEqual(r["keyboard"]["rows"][0][0]["text"], "Pay 5 €")

    def test_edit_request_keeps_only_inline_markup(self):
        r = render.render_screen(self.p, self.snap.screens["checkout.note"], locale="ru")
        self.assertEqual(render.bot_request(r, 1)["params"]["reply_markup"]["force_reply"], True)
        self.assertNotIn("reply_markup", render.bot_request(r, 1, edit_message_id=5)["params"])

    def test_rendered_requests_pass_the_catalog_check(self):
        from bot_ui.skill import load
        vp = load("validate_payload")
        v = vp.Validator(vp.load_catalog(vp.DATA_DIR))
        for sid, s in self.snap.screens.items():
            for loc in self.p["locales"]:
                req = render.bot_request(render.render_screen(self.p, s, locale=loc), 111)
                rep = v.check_request(req["method"], req["params"])
                self.assertTrue(rep.ok, (sid, loc, rep.errors))


if __name__ == "__main__":
    unittest.main()
