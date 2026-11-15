"""Product invariants, real callback paths, payload drift and intent discovery."""
import copy
from datetime import datetime, timedelta, timezone
import unittest

import _paths
import example_library as library
import r80_87_product_journeys as demos
from sync_bot_api import load_catalog
from tgkit.flows import IllegalTransition, payload_text
from tgkit.journeys import Event, FileJob, Lead, Loyalty, Moderation, Refused, Reminder, ServiceQueue, Survey
from validate_keyboard import validate as validate_keyboard
from validate_payload import Validator


class ProductJourneys(unittest.TestCase):
    def test_lead_consent_snapshot_and_owner(self):
        lead = Lead(1)
        with self.assertRaisesRegex(Refused, "consent_required"):
            lead.submit(1)
        with self.assertRaisesRegex(Refused, "invalid"):
            lead.give_consent(1)
        lead.edit(1, "<consultation>", "contact")
        with self.assertRaisesRegex(Refused, "not_yours"):
            lead.give_consent(2)
        lead.give_consent(1)
        lead.edit(1, "changed", "contact")
        self.assertFalse(lead.consent)
        lead.give_consent(1)
        result = lead.submit(1)
        result["topic"] = "tampered"
        self.assertEqual(lead.submit(1)["topic"], "changed")
        with self.assertRaisesRegex(Refused, "not_yours"):
            lead.submit(2)
        with self.assertRaisesRegex(Refused, "closed"):
            lead.edit(1, "new", "contact")
        draft = Lead(1)
        draft.edit(1, "topic", "contact")
        draft.cancel(1)
        self.assertFalse(draft.answers)
        with self.assertRaisesRegex(Refused, "closed"):
            draft.submit(1)
        with self.assertRaisesRegex(Refused, "closed"):
            draft.give_consent(1)

    def test_event_capacity_promotion_and_checkin(self):
        event = Event(1)
        self.assertEqual(event.join(1), "confirmed")
        self.assertEqual(event.join(2), "waitlisted")
        event.join(2)
        event.join(3)
        self.assertEqual(event.waitlist, [2, 3])
        with self.assertRaisesRegex(Refused, "not_confirmed"):
            event.check_in(9, 2, {9})
        self.assertEqual(event.cancel(1), 2)
        self.assertEqual(event.attendees, [2])
        with self.assertRaisesRegex(Refused, "forbidden"):
            event.check_in(2, 2, {9})
        self.assertTrue(event.check_in(9, 2, {9}))
        self.assertFalse(event.check_in(9, 2, {9}))
        with self.assertRaisesRegex(Refused, "closed"):
            event.cancel(2)
        event.cancel(3)
        self.assertFalse(event.waitlist)

    def test_reminder_timezone_cancel_and_lease(self):
        now = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)
        reminder = Reminder(1, "r:1")
        with self.assertRaisesRegex(Refused, "timezone_required"):
            reminder.schedule(1, now.replace(tzinfo=None), now)
        with self.assertRaisesRegex(Refused, "past"):
            reminder.schedule(1, now, now)
        reminder.schedule(1, now + timedelta(hours=1), now)
        self.assertEqual(reminder.scheduler.due(now.timestamp()), [])
        leased = reminder.scheduler.due((now + timedelta(hours=1)).timestamp())[0]
        reminder.cancel(1)
        self.assertFalse(reminder.claim(leased.payload["generation"]))
        reminder.schedule(1, now + timedelta(hours=2), now)
        self.assertTrue(reminder.claim(reminder.generation))
        self.assertFalse(reminder.claim(reminder.generation))
        self.assertEqual(reminder.status, "claimed")
        with self.assertRaisesRegex(Refused, "not_yours"):
            reminder.cancel(2)
        for late_change in (lambda: reminder.cancel(1), lambda: reminder.schedule(1, now + timedelta(hours=3), now)):
            with self.assertRaisesRegex(Refused, "closed"):
                late_change()

    def test_reminder_old_lease_after_reschedule(self):
        now = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)
        reminder = Reminder(1, "r:1")
        reminder.schedule(1, now + timedelta(hours=1), now)
        old = reminder.scheduler.due((now + timedelta(hours=1)).timestamp())[0].payload["generation"]
        reminder.schedule(1, now + timedelta(hours=2), now)
        self.assertEqual(reminder.status, "scheduled")
        self.assertFalse(reminder.claim(old))
        self.assertEqual(reminder.due, now + timedelta(hours=2))

    def test_file_job_late_completion_and_failure(self):
        job = FileJob(1)
        for size, mime in [(0, "application/pdf"), (5_000_001, "application/pdf"), (100, "text/html")]:
            with self.assertRaisesRegex(Refused, "invalid_file"):
                job.upload(1, "file", size, mime)
        job.upload(1, "file", 100, "application/pdf")
        generation = job.start()
        job.cancel(1)
        self.assertFalse(job.finish(generation, "late"))
        self.assertIsNone(job.result)
        self.assertIsNone(job.file_id)
        for terminal in ("finish", "fail"):
            other = FileJob(1)
            other.upload(1, "file", 100, "application/pdf")
            gen = other.start()
            self.assertFalse(other.finish(gen + 1, "wrong attempt"))
            self.assertTrue(other.finish(gen, "summary") if terminal == "finish" else other.fail(gen))
            self.assertFalse(other.finish(gen, "again"))
        with self.assertRaises(IllegalTransition):
            FileJob(1).start()
        # Repeated uploads and cancels in the wrong state are refusals, not crashes.
        with self.assertRaisesRegex(Refused, "closed"):
            FileJob(1).cancel(1)
        queued = FileJob(1)
        queued.upload(1, "file", 100, "application/pdf")
        with self.assertRaisesRegex(Refused, "closed"):
            queued.upload(1, "file2", 100, "application/pdf")

    def test_moderation_scope_and_revision(self):
        case = Moderation(-10, 50)
        for actor, chat in [(2, -10), (9, -11)]:
            with self.assertRaisesRegex(Refused, "forbidden"):
                case.decide(actor, {9}, chat, 0, "remove")
        with self.assertRaisesRegex(Refused, "invalid"):
            case.decide(9, {9}, -10, 0, "ban_everyone")
        seen = case.revision
        case.add_report()
        with self.assertRaisesRegex(Refused, "stale"):
            case.decide(9, {9}, -10, seen, "remove")
        self.assertEqual(case.status, "pending")
        plan = case.decide(9, {9}, -10, case.revision, "remove")
        self.assertEqual(plan["message_id"], 50)
        self.assertEqual(case.status, "planned")
        with self.assertRaisesRegex(Refused, "stale"):
            case.decide(10, {9, 10}, -10, case.revision, "dismiss")
        with self.assertRaisesRegex(Refused, "closed"):
            case.add_report()

    def test_survey_optional_comment_and_withdrawal(self):
        survey = Survey(1)
        with self.assertRaisesRegex(Refused, "incomplete"):
            survey.submit(1)
        with self.assertRaisesRegex(Refused, "invalid"):
            survey.answer(1, "rating", "6")
        survey.answer(1, "rating", "4")
        self.assertEqual(survey.submit(1), {"rating": "4"})
        self.assertEqual(survey.submit(1), {"rating": "4"})
        with self.assertRaisesRegex(Refused, "not_yours"):
            survey.withdraw(2)
        survey.withdraw(1)
        self.assertEqual(survey.answers, {})
        with self.assertRaisesRegex(Refused, "closed"):
            survey.submit(1)

    def test_loyalty_replay_conflict_and_balance(self):
        ledger = Loyalty(1)
        self.assertTrue(ledger.credit("order1", 100))
        self.assertFalse(ledger.credit("order1", 100))
        with self.assertRaisesRegex(Refused, "conflict"):
            ledger.credit("order1", 200)
        with self.assertRaisesRegex(Refused, "not_yours"):
            ledger.redeem(2, "r1", 80)
        self.assertTrue(ledger.redeem(1, "r1", 80))
        self.assertFalse(ledger.redeem(1, "r1", 80))
        with self.assertRaisesRegex(Refused, "conflict"):
            ledger.redeem(1, "r1", 10)
        with self.assertRaisesRegex(Refused, "insufficient"):
            ledger.redeem(1, "r2", 80)
        self.assertEqual(ledger.balance, 20)
        with self.assertRaisesRegex(Refused, "invalid"):
            ledger.redeem(1, "r3", -1)

    def test_queue_identity_and_staff_advancement(self):
        queue = ServiceQueue()
        self.assertEqual(queue.join(1), 1)
        self.assertEqual(queue.join(2), 2)
        self.assertEqual(queue.join(1), 1)
        with self.assertRaisesRegex(Refused, "forbidden"):
            queue.call_next(1, {9})
        self.assertEqual(queue.call_next(9, {9}), 1)
        self.assertEqual(queue.call_next(9, {9}), 1)
        with self.assertRaisesRegex(Refused, "already_called"):
            queue.cancel(1)
        queue.complete(9, {9}, 1)
        self.assertEqual(queue.call_next(9, {9}), 2)
        with self.assertRaisesRegex(Refused, "stale"):
            queue.complete(9, {9}, 1)
        self.assertEqual(queue.active, 2)
        queue.closed = True
        with self.assertRaisesRegex(Refused, "closed"):
            queue.join(3)

    def test_all_demos_locales_payloads_and_ack_order(self):
        validator = Validator(load_catalog())
        for number in range(80, 88):
            for lang in ("en", "ru"):
                with self.subTest(number=number, lang=lang):
                    doc = demos.run(f"R{number}", lang)
                    if lang == "en":
                        self.assertEqual(payload_text(doc), _paths.read("examples", "payloads", f"r{number}-journey.json"))
                    queries = []
                    for step in doc["steps"]:
                        report = validator.check_request(step["method"], step["params"])
                        self.assertFalse(report.errors, report.errors)
                        if "reply_markup" in step["params"]:
                            report = validate_keyboard(step["params"]["reply_markup"], context="private")
                            self.assertFalse(report.errors, report.errors)
                        if step["method"] == "answerCallbackQuery":
                            queries.append(step["params"]["callback_query_id"])
                    self.assertEqual(len(queries), len(set(queries)))
                    self.assertEqual(sum(s["method"] == "sendMessage" for s in doc["steps"]), 1)
                    for i, step in enumerate(doc["steps"]):
                        if step["method"] == "answerCallbackQuery" and step["params"]["callback_query_id"].startswith("tap-"):
                            self.assertEqual(doc["steps"][i + 1]["method"], "editMessageText")

    def test_forged_callback_and_unavailable_action_do_not_mutate(self):
        model, panel, transport, _ = demos.build("R86")
        forged = panel.flow.cb(panel.session, "redeem", "1")
        demos.tap(panel, "redeem", "forged", data=forged)
        self.assertEqual(model.balance, 100)
        demos.tap(panel, "redeem", "real")
        self.assertEqual(model.balance, 20)

    def test_refusal_notice_is_shown_once(self):
        model, panel, transport, _ = demos.build("R80")
        demos.tap(panel, "submit", "early")
        self.assertIn("consent", transport.calls[-1][1]["text"])
        demos.tap(panel, "status", "status")
        self.assertNotIn("could not be completed", transport.calls[-1][1]["text"])

    def test_product_body_is_escaped(self):
        from tgkit.journey_panel import JourneyPanel
        from tgkit.transport import FakeTransport
        transport = FakeTransport()
        panel = JourneyPanel(transport, "test", 1, ("<title>", "<заголовок>"), lambda lang: "<script>&", {})
        panel.open()
        self.assertIn("&lt;script&gt;&amp;", transport.calls[0][1]["text"])


class ExampleDiscovery(unittest.TestCase):
    def test_catalog_is_valid(self):
        self.assertEqual(library.validate(library.load(), library.recipes()), [])

    def test_english_russian_and_context_search(self):
        cat, man = library.load(), library.recipes()
        for query, expected in [("waitlist", "events"), ("лист ожидания", "events"), ("CRM заявки", "lead-intake"),
                                ("расшифровка", "file-jobs"), ("очередь талон", "service-queue")]:
            self.assertEqual(library.search(cat, man, query)[0]["id"], expected)
        self.assertEqual(library.search(cat, man, "waitlist", "channel"), [])
        self.assertEqual(library.search(cat, man, "nonexistentxyz"), [])
        for query in ("remind me tomorrow", "напомни мне завтра"):
            self.assertEqual(library.search(cat, man, query)[0]["id"], "reminders")
        self.assertEqual(library.search(cat, man, "a"), [])

    def test_bad_catalog_entries_fail(self):
        catalog, manifest = library.load(), library.recipes()
        broken = copy.deepcopy(catalog)
        broken["use_cases"].append(copy.deepcopy(broken["use_cases"][0]))
        broken["use_cases"][0]["recipes"] = ["R999"]
        broken["use_cases"][0]["sources"] = ["invented"]
        broken["use_cases"][0]["coverage"] = "production-ready"
        broken["use_cases"][0]["contexts"] = ["unverified-surface"]
        errors = library.validate(broken, manifest)
        self.assertTrue(any("duplicate" in e for e in errors))
        self.assertTrue(any("unknown recipe" in e for e in errors))
        self.assertTrue(any("unknown source" in e for e in errors))
        self.assertTrue(any("unknown coverage" in e for e in errors))
        self.assertTrue(any("unknown context" in e for e in errors))
        broken["use_cases"][1]["intent"] = "not a list"
        self.assertTrue(any("list of strings" in e for e in library.validate(broken, manifest)))


if __name__ == "__main__":
    unittest.main()
