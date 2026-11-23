"""Data views (tgkit.dataview, scripts/data_view.py): numbers, deltas, progress bars,
leaderboards, and long tables split into self-describing parts within the limits."""
import io
import json
import unittest
from contextlib import redirect_stdout

import _paths  # noqa: F401
import data_view
import validate_rich
from tgkit import dataview as dv
from tgkit.text import utf16_len


class Atoms(unittest.TestCase):
    def test_numbers_and_money_per_locale(self):
        self.assertEqual(dv.number(1234567), "1,234,567")
        self.assertEqual(dv.number(1234567.891, "ru", 2), "1 234 567,89")
        self.assertEqual(dv.number(-1500), "−1,500")
        self.assertEqual(dv.money(1240050, "EUR"), "€12,400.50")
        self.assertEqual(dv.money(1240050, "EUR", "ru"), "12 400,50 €")
        self.assertEqual(dv.money(250, "XTR", digits=0), "250 ⭐")

    def test_delta_never_hides_the_direction(self):
        self.assertEqual(dv.delta(112, 100), "▲ 12%")
        self.assertEqual(dv.delta(96.5, 100), "▼ 3.5%")
        self.assertEqual(dv.delta(100, 100), "= 0%")
        self.assertEqual(dv.delta(5, 0), "▲ new")

    def test_progress_is_honest_at_the_edges(self):
        self.assertEqual(dv.progress(37, 100), "▰▰▰▰▱▱▱▱▱▱ 37%")
        self.assertEqual(dv.progress(996, 1000), "▰▰▰▰▰▰▰▰▰▱ 99%", "never a false 100%")
        self.assertEqual(dv.progress(1, 1000, style="bar"), "█░░░░░░░░░ 1%", "something done is never 0%")
        self.assertEqual(dv.progress(5, 5), "▰▰▰▰▰▰▰▰▰▰ 100%")
        self.assertEqual(dv.progress(0, 0), "▱▱▱▱▱▱▱▱▱▱ 0%")
        self.assertEqual(len(dv.progress(1, 2, width=99, percent=False)), 20)

    def test_sparkline(self):
        self.assertEqual(dv.sparkline([1, 5, 9]), "▁▅█")
        self.assertEqual(dv.sparkline([3, 3]), "▄▄")
        self.assertEqual(dv.sparkline([]), "")

    def test_status_keeps_the_word(self):
        self.assertEqual(dv.status(2, "Refunded"), "🔴 Refunded")


class Leaderboard(unittest.TestCase):
    def test_ties_medals_escaping_and_the_viewer_below_the_top(self):
        text = dv.leaderboard([("Ann", 120), ("Bob", 120), ("Cid", 90), ("Dan", 80), ("Eve <x>", 10)],
                              me="Eve <x>", top=3, unit="pts")
        lines = text.split("\n")
        self.assertEqual(lines[:3], ["🥇 Ann · 120 pts", "🥇 Bob · 120 pts", "🥉 Cid · 90 pts"])
        self.assertEqual(lines[3:], ["⋯", "<b>#5 Eve &lt;x&gt; · 10 pts</b>"])

    def test_viewer_inside_the_top_is_bold_in_place(self):
        text = dv.leaderboard([("Ann", 3), ("Bob", 2)], me="Bob")
        self.assertEqual(text.split("\n"), ["🥇 Ann · 3", "<b>🥈 Bob · 2</b>"])


class Tables(unittest.TestCase):
    rows = [[f"Order {i}", "Paid" if i % 3 else "Refunded", dv.money(1000 + i * 37, "EUR")] for i in range(300)]

    def test_short_table_is_one_part_with_summary_and_footer(self):
        parts = dv.table_parts("Orders", ["Order", "Status", "Sum"], self.rows[:5], summary="5 orders",
                               footer="<i>legend</i>", right=frozenset({2}))
        self.assertEqual(len(parts), 1)
        self.assertTrue(parts[0].startswith("<b>Orders</b>\n5 orders\n<pre>Order"))
        self.assertTrue(parts[0].endswith("</pre>\n<i>legend</i>"))

    def test_long_table_splits_between_rows_with_the_header_on_every_part(self):
        parts = dv.table_parts("Orders", ["Order", "Status", "Sum"], self.rows, summary="300 orders",
                               footer="Legend", right=frozenset({2}), lang="ru")
        self.assertGreater(len(parts), 1)
        n = len(parts)
        for i, p in enumerate(parts):
            self.assertLessEqual(utf16_len(p), 4096)
            self.assertIn(f"({i + 1}/{n})", p)
            self.assertIn("<pre>Order", p, "the header repeats")
            self.assertEqual(p.count("300 orders"), 1 if i == 0 else 0, "the summary only on part 1")
            self.assertEqual(p.endswith("Legend"), i == n - 1, "the footer only on the last part")
        self.assertIn("продолжение", parts[1])
        body = [ln for p in parts for ln in p.split("<pre>")[1].split("</pre>")[0].split("\n")[2:]]
        self.assertEqual(len(body), 300, "no row lost or cut")

    def test_alignment_counts_display_width(self):
        lines = dv.mono_lines(["Name", "Sum"], [["日本", "5"], ["ab", "12345"]], right=frozenset({1}))
        self.assertEqual(dv.width(lines[2]), dv.width(lines[3]))
        self.assertTrue(lines[3].endswith("12345") and lines[2].endswith("    5"))

    def test_a_row_that_cannot_fit_is_refused(self):
        with self.assertRaises(ValueError):
            dv.table_parts("T", ["a"], [["x"]], summary="s" * 5000)

    def test_rich_parts_pass_the_rich_validator(self):
        many = self.rows * 2   # 600 rows: over the 500-block limit of one message
        parts = dv.rich_table_parts("Orders", ["Order", "Status", "Sum"], many, numeric=frozenset({2}),
                                    summary="600 orders", footer="Refunds are not in the total", lang="uk")
        self.assertEqual(len(parts), 2)
        self.assertEqual([b["type"] for b in parts[0]], ["heading", "paragraph", "table"])
        self.assertEqual([b["type"] for b in parts[1]], ["heading", "table", "paragraph"])
        self.assertEqual(parts[1][0]["text"], "Orders (2/2) · продовження")
        for blocks in parts:
            errors = validate_rich.validate({"chat_id": 1, "rich_message": {"blocks": blocks}})[0]
            self.assertEqual(errors, [], errors)
        self.assertEqual(sum(len(b["cells"]) - 1 for p in parts for b in p if b["type"] == "table"), 600)
        with self.assertRaises(ValueError):
            dv.rich_table_parts("Wide", [str(i) for i in range(21)], [])


class Cli(unittest.TestCase):
    def test_json_output(self):
        spec = {"view": "table", "title": "Orders", "header": ["Order", "Sum"], "rows": [["#1", "€5"]], "right": [1],
                "mode": "html"}
        out = io.StringIO()
        with redirect_stdout(out), unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(spec))):
            self.assertEqual(data_view.main(["-", "--json"]), 0)
        doc = json.loads(out.getvalue())
        self.assertEqual(len(doc["parts"]), 1)
        self.assertEqual(doc["lengths"][0], utf16_len(doc["parts"][0]))

    def test_unknown_view_is_a_usage_error(self):
        with unittest.mock.patch("sys.stdin", io.StringIO('{"view": "pie"}')), redirect_stdout(io.StringIO()):
            self.assertEqual(data_view.main(["-"]), 2)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
