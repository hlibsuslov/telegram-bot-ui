"""bot-ui writes: one write path, revisions, conflicts, transactions (skills/telegram-bot-ui/scripts/bot_ui/store.py)."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import shutil
import tempfile
import unittest

from _bot_ui import CLI, ROOT, ProjectCase
from bot_ui.project import open_snapshot
from bot_ui.store import StoreError, screen_patch, write_patch

SHORT_RU = "<b>Подтвердите заказ #{order.no}</b>\nК оплате {order.total}. Комментарий: {order.note}."


def text_patch(rev, value=SHORT_RU, frm=None, path="/message/text/ru", sid="checkout.payment.confirm"):
    op = {"op": "set", "path": path, "value": value}
    if frm is not None:
        op["from"] = frm
    return {"format": "bot-ui-patch/v1", "projectId": "demo-shop", "baseRevision": rev,
            "changes": [{"screenId": sid, "ops": [op]}]}


class Writes(ProjectCase):
    def rev(self):
        return open_snapshot(self.root).revision

    def test_small_diff_touches_one_file(self):
        before = {rel: data for rel, data in open_snapshot(self.root).files.items()}
        res = write_patch(self.root, text_patch(self.rev()))
        self.assertEqual(res.changed_files, ["screens/checkout.payment.confirm.json"])
        after = open_snapshot(self.root).files
        changed = sorted(rel for rel in after if after[rel] != before.get(rel))
        self.assertEqual(changed, ["screens/checkout.payment.confirm.json"])
        self.assertEqual(sum(1 for ln in res.diff.splitlines() if ln.startswith(("+ ", "- ", "+\t", '+  "', '-  "'))), 2)
        self.assertEqual(self.read("screens/checkout.payment.confirm.json")["message"]["text"]["ru"], SHORT_RU)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".bot-ui", "journal.json")))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".bot-ui", "write.lock")))

    def test_dry_run_writes_nothing_but_reports_the_same_diff(self):
        rev = self.rev()
        dry = write_patch(self.root, text_patch(rev), dry_run=True)
        self.assertEqual(self.rev(), rev)
        real = write_patch(self.root, text_patch(rev))
        self.assertEqual(dry.diff, real.diff)
        self.assertEqual(dry.revision, real.revision)

    def test_same_patch_on_current_revision_is_idempotent(self):
        first = write_patch(self.root, text_patch(self.rev()))
        again = write_patch(self.root, text_patch(first.revision))
        self.assertEqual(again.changed_files, [])
        self.assertEqual(again.diff, "")
        self.assertEqual(again.revision, first.revision)

    def test_stale_revision_conflicts_and_keeps_the_newer_file(self):
        rev = self.rev()
        write_patch(self.root, text_patch(rev, "Studio wins {order.no} {order.total} {order.note}"))
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, text_patch(rev, "Agent text {order.no} {order.total} {order.note}",
                                              frm=open_snapshot(self.root).screens and None))
        err = ctx.exception
        self.assertEqual(err.code, "REVISION_CONFLICT")
        self.assertEqual(err.extra["expectedRevision"], rev)
        self.assertEqual(err.extra["currentRevision"], self.rev())
        self.assertIn("Studio wins", self.read("screens/checkout.payment.confirm.json")["message"]["text"]["ru"])

    def test_field_conflict_and_rebase(self):
        snap = open_snapshot(self.root)
        old_ru = snap.screens["checkout.payment.confirm"]["message"]["text"]["ru"]
        old_en = snap.screens["checkout.payment.confirm"]["message"]["text"]["en"]
        write_patch(self.root, text_patch(snap.revision, SHORT_RU, frm=old_ru))  # Studio saves ru first
        # The agent changed the same field from the old base: a field conflict, nothing written.
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, text_patch(snap.revision, "Agent " + SHORT_RU, frm=old_ru), rebase=True)
        self.assertEqual(ctx.exception.extra["fieldConflicts"][0]["path"], "/message/text/ru")
        # A different field from the old base can be rebased on the new revision.
        res = write_patch(self.root, text_patch(snap.revision, "<b>Confirm #{order.no}</b> {order.total} {order.note}",
                                                frm=old_en, path="/message/text/en"), rebase=True)
        doc = self.read("screens/checkout.payment.confirm.json")
        self.assertEqual(doc["message"]["text"]["ru"], SHORT_RU)
        self.assertTrue(doc["message"]["text"]["en"].startswith("<b>Confirm #"))
        self.assertEqual(res.changed_files, ["screens/checkout.payment.confirm.json"])

    def test_external_edit_changes_the_revision(self):
        rev = self.rev()
        rel = "screens/orders.pickup.json"
        doc = self.read(rel)
        doc["title"] = "Edited by hand"
        self.write_raw(rel, json.dumps(doc, ensure_ascii=False, indent=2).encode())
        self.assertNotEqual(self.rev(), rev)
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, text_patch(rev))
        self.assertEqual(ctx.exception.code, "REVISION_CONFLICT")

    def test_interrupted_transaction_is_rolled_back(self):
        snap = open_snapshot(self.root)
        before = dict(snap.files)
        patch = {"format": "bot-ui-patch/v1", "baseRevision": snap.revision, "changes": [
            {"screenId": "checkout.payment.confirm", "ops": [{"op": "set", "path": "/message/text/ru", "value": SHORT_RU}]},
            {"screenId": "orders.pickup", "ops": [{"op": "set", "path": "/title", "value": "Новый"}]}]}
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, patch, _fail_after=1)
        self.assertEqual(ctx.exception.code, "WRITE_FAILED")
        self.assertEqual(open_snapshot(self.root).files, before)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".bot-ui", "journal.json")))

    def test_journal_left_by_a_crash_is_recovered_on_open(self):
        snap = open_snapshot(self.root)
        from bot_ui.store import _commit
        target = "screens/orders.pickup.json"
        try:
            _commit(self.root, {target: b"{broken", "screens/orders.delivery.json": b"{broken"}, fail_after=1)
        except OSError:
            pass
        self.assertTrue(os.path.exists(os.path.join(self.root, ".bot-ui", "journal.json")))
        fresh = open_snapshot(self.root)
        self.assertEqual(fresh.revision, snap.revision)
        self.assertIn("WRITE_RECOVERED", [d.code for d in fresh.load_diagnostics])

    def test_create_screen_then_link_it(self):
        snap = open_snapshot(self.root)
        new = {"id": "orders.help", "title": "Помощь", "kind": "menu", "audience": "private",
               "message": {"id": "main", "format": "regular.plain", "text": {"ru": "Чем помочь?", "en": "How can we help?"}},
               "keyboard": {"type": "inline", "rows": [["back"]]},
               "actions": {"back": {"label": {"ru": "Назад", "en": "Back"}, "type": "back", "fallback": "orders.status"}}}
        r1 = write_patch(self.root, screen_patch(snap, "orders.help", new))
        self.assertEqual(r1.changed_files, ["screens/orders.help.json"])
        snap = open_snapshot(self.root)
        status = json.loads(json.dumps(snap.screens["orders.status"]))
        status["actions"]["help"] = {"label": {"ru": "Помощь", "en": "Help"}, "type": "navigate", "to": "orders.help"}
        status["keyboard"]["rows"].append(["help"])
        patch = screen_patch(snap, "orders.status", status)
        self.assertEqual({op["path"] for op in patch["changes"][0]["ops"]}, {"/actions/help", "/keyboard/rows"})
        r2 = write_patch(self.root, patch)
        self.assertEqual(r2.changed_files, ["screens/orders.status.json"])

    def test_delete_with_incoming_links_is_refused(self):
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": self.rev(),
                                    "changes": [{"screenId": "orders.pickup", "delete": True}]})
        self.assertEqual(ctx.exception.code, "SCREEN_HAS_INCOMING")
        self.assertIn("orders.status/route", ctx.exception.extra["incoming"])

    def test_forbidden_paths_and_project_mismatch(self):
        for path in ("/id", "/actions/pay/callbackData", "/../x", "/message/text/ru/../../id"):
            with self.subTest(path), self.assertRaises(StoreError) as ctx:
                write_patch(self.root, text_patch(self.rev(), path=path))
            self.assertEqual(ctx.exception.code, "PATCH_PATH_FORBIDDEN")
        p = text_patch(self.rev())
        p["projectId"] = "other-bot"
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, p)
        self.assertEqual(ctx.exception.code, "PROJECT_MISMATCH")

    def test_widget_source_write_with_content_hash(self):
        from bot_ui.store import content_hash
        rel = "widgets/order-status/style.css"
        old = self.raw(rel)
        change = {"widgetId": "order-status", "file": "style.css", "content": old.decode() + ".x{color:red}\n",
                  "fromHash": content_hash(old)}
        res = write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": self.rev(), "changes": [change]})
        self.assertEqual(res.changed_files, [rel])
        stale = dict(change, content="/* other */\n")
        with self.assertRaises(StoreError) as ctx:
            write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": "sha256:old", "changes": [stale]},
                        rebase=True)
        self.assertEqual(ctx.exception.extra["fieldConflicts"][0]["path"], "style.css")
        for bad in ("../x.css", "sub/x.css", "x.py"):
            with self.assertRaises(StoreError):
                write_patch(self.root, {"format": "bot-ui-patch/v1", "baseRevision": self.rev(),
                                        "changes": [dict(change, file=bad)]})


class CraftedJournal(ProjectCase):
    """The journal is a file in the project, so a cloned repository can carry a crafted one: recovery
    only restores what the project's own transaction folder holds, and read-only opens never recover."""

    def _plant(self, entries):
        state = os.path.join(self.root, ".bot-ui")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "journal.json"), "w", encoding="utf-8") as fh:
            json.dump({"files": entries}, fh)
        return os.path.join(state, "journal.json")

    def _victim(self, text=b"keep me"):
        path = os.path.join(self._tmp, "victim.txt")
        with open(path, "wb") as fh:
            fh.write(text)
        return path

    def test_a_backup_outside_the_transaction_folder_is_refused(self):
        victim = self._victim()
        screen = os.path.join(self.root, "screens", "orders.pickup.json")
        before = pathlib.Path(screen).read_bytes()
        journal = self._plant([{"path": "screens/orders.pickup.json", "backup": victim}])
        with self.assertRaises(StoreError) as ctx:
            open_snapshot(self.root)
        self.assertEqual(ctx.exception.code, "JOURNAL_INVALID")
        self.assertEqual(pathlib.Path(screen).read_bytes(), before)
        self.assertTrue(os.path.exists(victim))
        self.assertTrue(os.path.exists(journal))

    def test_a_target_outside_the_project_is_refused_before_anything_moves(self):
        victim = self._victim()
        screen = os.path.join(self.root, "screens", "orders.pickup.json")
        txn = os.path.join(self.root, ".bot-ui", "txn")
        os.makedirs(txn)
        with open(os.path.join(txn, "0.bak"), "wb") as fh:
            fh.write(b"{}")
        self._plant([{"path": "screens/orders.pickup.json", "backup": os.path.join(txn, "0.bak")},
                     {"path": "../victim.txt", "backup": None}])
        with self.assertRaises(ValueError):
            open_snapshot(self.root)
        self.assertEqual(pathlib.Path(victim).read_bytes(), b"keep me")
        self.assertNotEqual(pathlib.Path(screen).read_bytes(), b"{}")  # the first entry was not applied either

    def test_a_journal_that_is_not_a_list_of_entries_is_refused(self):
        for bad in ({"path": "x"}, ["screens/a.json"], [{"path": 7}], "x"):
            journal = self._plant(bad)
            with self.assertRaises(StoreError) as ctx:
                open_snapshot(self.root)
            self.assertEqual(ctx.exception.code, "JOURNAL_INVALID", bad)
            os.remove(journal)

    def test_a_journal_that_is_not_json_is_refused(self):
        with open(self._plant([]), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with self.assertRaises(StoreError) as ctx:
            open_snapshot(self.root)
        self.assertEqual(ctx.exception.code, "JOURNAL_INVALID")

    def test_read_only_open_reports_the_journal_and_changes_nothing(self):
        screen = os.path.join(self.root, "screens", "orders.pickup.json")
        before = pathlib.Path(screen).read_bytes()
        journal = self._plant([{"path": "screens/orders.pickup.json", "backup": None}])  # recovery would delete the screen
        snap = open_snapshot(self.root, recover=False)
        self.assertIn("WRITE_PENDING", [d.code for d in snap.load_diagnostics])
        self.assertEqual(pathlib.Path(screen).read_bytes(), before)
        self.assertTrue(os.path.exists(journal))


class TwoProcesses(ProjectCase):
    def test_two_writers_from_one_base_one_wins_one_conflicts(self):
        rev = open_snapshot(self.root).revision
        procs = []
        for who in ("studio", "agent"):
            pf = os.path.join(self._tmp, f"{who}.json")
            with open(pf, "w", encoding="utf-8") as fh:
                json.dump(text_patch(rev, f"{who} {{order.no}} {{order.total}} {{order.note}}"), fh)
            procs.append(subprocess.Popen([sys.executable, CLI, "apply-patch", "--project", self.root,
                                           "--patch-file", pf, "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        results = []
        for p in procs:
            out, _ = p.communicate(timeout=60)
            results.append((p.returncode, json.loads(out.decode("utf-8"))))
        self.assertEqual(sorted(code for code, _ in results), [0, 3])
        winner = next(out for code, out in results if code == 0)
        loser = next(out for code, out in results if code == 3)
        self.assertEqual(loser["error"]["currentRevision"], winner["revision"])
        self.assertEqual(open_snapshot(self.root).revision, winner["revision"])



class PlantedLinks(unittest.TestCase):
    """A cloned project can ship links next to the files bot-ui writes (security audit 2026-11-25, H1)."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="bot-ui-links-")
        self.proj = os.path.join(self.work, "bot-ui")
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "rich_project"), self.proj)
        self.outside = os.path.join(self.work, "outside.txt")
        with open(self.outside, "w") as fh:
            fh.write("ORIGINAL")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _write(self):
        from bot_ui.project import open_snapshot
        from bot_ui.store import screen_patch, write_patch
        snap = open_snapshot(self.proj)
        doc = dict(snap.screens["receipt.paid"])
        doc["title"] = "changed"
        return write_patch(self.proj, screen_patch(snap, "receipt.paid", doc))

    def _untouched(self):
        with open(self.outside) as fh:
            self.assertEqual(fh.read(), "ORIGINAL")

    def test_old_temp_name_link_is_not_written_through(self):
        os.link(self.outside, os.path.join(self.proj, "screens", "receipt.paid.json.bot-ui-tmp"))
        self.assertTrue(self._write().ok)
        self._untouched()

    def test_planted_backup_link_in_txn_is_not_written_through(self):
        txn = os.path.join(self.proj, ".bot-ui", "txn")
        os.makedirs(txn)
        for i in range(3):
            os.link(self.outside, os.path.join(txn, f"{i}.bak"))
        self.assertTrue(self._write().ok)
        self._untouched()

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows feature")
    def test_state_dir_junction_is_refused(self):
        elsewhere = os.path.join(self.work, "elsewhere")
        os.makedirs(elsewhere)
        subprocess.run(["cmd", "/c", "mklink", "/J", os.path.join(self.proj, ".bot-ui"), elsewhere], check=True, capture_output=True)
        from bot_ui.store import StoreError
        with self.assertRaises(StoreError):
            self._write()
        self.assertEqual(os.listdir(elsewhere), [])


if __name__ == "__main__":
    unittest.main()
