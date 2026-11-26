"""Tab bar, opening mode and back navigation: the kit, the examples, icons.json and lint MA45-MA47 agree."""
import glob
import os
import re
import tempfile
import unittest

import _paths
import miniapp_lint as lint

REF = os.path.join(_paths.ROOT, "references", "mini-apps")
EX = os.path.join(_paths.ROOT, "examples", "mini-apps")
APPS = ("vanilla", "catalog", "portfolio", "rework", "gallery")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def lint_files(files):
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in files.items():
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            paths.append(p)
        return [(f.rule, f.msg) for f in lint.lint_files(paths, d).findings]


def rules(files, rule):
    return [m for r, m in lint_files(files) if r == rule]


def tab(label, icon="", selected=False, sprite="icons.svg"):
    svg = f'<svg class="tma-icon" aria-hidden="true"><use href="{sprite}#i-{icon}"/></svg>' if icon else ""
    return f'<button type="button" role="tab" aria-selected="{str(selected).lower()}">{svg}<span>{label}</span></button>'


def bar(*tabs):
    return '<nav class="tma-tabbar tma-glass" role="tablist" aria-label="Sections">' + "".join(tabs) + "</nav>"


class TabBarLint(unittest.TestCase):
    def test_a_clean_bar_passes(self):
        html = bar(tab("Books", "book", True), tab("Trainers", "people"), tab("Workouts", "dumbbell"))
        self.assertEqual(rules({"index.html": html}, "MA45"), [])

    def test_an_icon_that_means_something_else(self):
        found = rules({"index.html": bar(tab("Books", "document", True), tab("Workouts", "play"))}, "MA45")
        self.assertEqual(len(found), 2, found)
        self.assertIn("i-dumbbell", found[1])
        found = rules({"index.html": bar(tab("Профиль", "settings", True), tab("Настройки", "settings"))}, "MA45")
        self.assertEqual(len(found), 1, found)  # Russian labels are matched too

    def test_tabs_without_icons_count_and_selection(self):
        self.assertTrue(rules({"index.html": bar(tab("Menu", selected=True), tab("Order"))}, "MA45"))
        six = bar(*[tab(f"T{i}", "home", i == 0) for i in range(6)])
        self.assertTrue(any("6 tab(s)" in m for m in rules({"index.html": six}, "MA45")))
        self.assertTrue(any("aria-selected" in m for m in rules({"index.html": bar(tab("Home", "home"), tab("Search", "search"))}, "MA45")))

    def test_mixed_sets_and_custom_emoji(self):
        mixed = bar(tab("Home", "home", True), tab("Search", "search", sprite="lucide.svg"))
        self.assertTrue(any("2 sets" in m for m in rules({"index.html": mixed}, "MA45")))
        emoji = bar(tab("Home", "home", True), '<button role="tab" aria-selected="false"><img src="e.webm" alt=""><span>Bonus</span></button>')
        self.assertTrue(any("animated or custom emoji" in m for m in rules({"index.html": emoji}, "MA45")))

    def test_jsx_tabs_need_icons(self):
        jsx = ('<nav className="tma-tabbar tma-glass" role="tablist">{TABS.map((t) => (<button key={t} role="tab" '
               'aria-selected={tab === t}>{t}</button>))}</nav>')
        self.assertTrue(rules({"App.tsx": jsx}, "MA45"))


class LaunchAndBackLint(unittest.TestCase):
    APP = "import { createTma } from './tma.ts';\nconst tma = createTma();\n"

    def test_launch_mode_must_be_decided(self):
        self.assertTrue(rules({"app.ts": self.APP + "tma.ready();\n"}, "MA46"))
        for decided in ("tma.start();", "tma.start({ fullscreen: 'never' });",
                        "tg.onEvent('fullscreenFailed', stay); tg.requestFullscreen();", "viewport.requestFullscreen().catch(() => {});"):
            self.assertEqual(rules({"app.ts": self.APP + decided + "\ntma.ready();\n"}, "MA46"), [], decided)

    def test_dead_ends(self):
        hidden = self.APP + "tma.start();\n$('tabbar').hidden = true;\ntma.ready();\n"
        self.assertTrue(rules({"app.ts": hidden}, "MA47"))
        never_popped = self.APP + "tma.start();\ntma.nav.push({ id: 'x', kind: 'screen' });\ntma.ready();\n"
        self.assertTrue(rules({"app.ts": never_popped}, "MA47"))
        ok = never_popped + "function close() { tma.nav.pop('x'); }\n"
        self.assertEqual(rules({"app.ts": ok}, "MA47"), [])


class Examples(unittest.TestCase):
    def test_every_example_opens_fullscreen_on_phones_and_has_a_back_stand_in(self):
        for app in APPS:
            with self.subTest(app=app):
                self.assertIn("tma.start()", read(EX, app, "app.ts"))
                self.assertIn('data-tma-fallback="back-button"', read(EX, app, "index.html"))
        main = read(EX, "react", "src", "main.tsx")
        self.assertIn("viewport.requestFullscreen", main)
        self.assertIn("viewport.expand", main)

    def test_every_tab_bar_has_icons_and_labels(self):
        for path in glob.glob(os.path.join(EX, "*", "index.html")) + [os.path.join(EX, "react", "src", "App.tsx")]:
            text = read(path)
            for nav in re.finditer(r"<nav\b[^>]*tma-tabbar.*?</nav>", text, re.S):
                for b in re.finditer(r"<button\b.*?</button>", nav.group(0), re.S):
                    with self.subTest(file=os.path.relpath(path, EX)):
                        self.assertRegex(b.group(0), r"<svg class(?:Name)?=\"tma-icon\"")
                        self.assertRegex(b.group(0), r"<span>")

    def test_tab_switches_keep_scroll(self):
        for app in ("vanilla", "catalog", "portfolio", "rework"):
            with self.subTest(app=app):
                code = read(EX, app, "app.ts")
                self.assertIn("tma.scrollMemory()", code)
                self.assertIn("tabScroll.top()", code)

    def test_examples_lint_clean(self):
        rep = lint.lint_files(*lint.collect([EX]))
        self.assertEqual([f.text() for f in rep.findings if f.rule in ("MA45", "MA46", "MA47")], [])


class BotSide(unittest.TestCase):
    def test_order_card_is_a_rich_message_with_its_buttons_in_the_document(self):
        import sys
        sys.path.insert(0, os.path.join(EX, "bot"))
        sys.path.insert(0, os.path.join(_paths.ROOT, "scripts"))
        from bot_side import MiniAppBot
        from bot_ui import rich

        sent = []
        transport = type("T", (), {"call": lambda self, m, p: sent.append((m, p))})()
        bot = MiniAppBot(transport, bot_username="demo_bot", app_url="https://app.example.com")
        bot.send_order_card(7, "4821", [("Flat white <M>", "€4.20")], "€4.20", "/orders/4821")
        method, params = sent[0]
        self.assertEqual(method, "sendRichMessage")
        self.assertNotIn("reply_markup", params)  # nothing navigates: the actions live in the document
        html = params["rich_message"]["html"]
        self.assertEqual([c for c, sev, _ in rich.check(html) if sev == "error"], [])
        self.assertIn("&lt;M&gt;", html)
        self.assertRegex(html, r"<tg-button-row><tg-button type=\"web_app\"[^>]*>Open order</tg-button>")
        with self.assertRaises(ValueError):
            bot.send_order_card(7, "48<21", [], "€0")
        with self.assertRaises(ValueError):  # a path must not be able to change the host
            bot.send_order_card(7, "4821", [], "€0", "@evil.example/x")
        self.assertEqual(bot.app_url_for("?tab=orders"), "https://app.example.com?tab=orders")


class Data(unittest.TestCase):
    def test_tab_meanings_name_real_icons(self):
        icons = _paths.load("data", "mini-apps", "icons.json")
        sprite = set(re.findall(r'<symbol id="i-([a-z0-9-]+)"', read(EX, "_kit", "icons.svg")))
        tb = icons["tab_bar"]
        self.assertEqual((tb["min"], tb["max"]), (2, 5))
        seen = set()
        for row in tb["meanings"]:
            self.assertTrue(set(row["icons"]) <= sprite, row)
            words = {w.lower() for w in row["words"]}
            self.assertFalse(words & seen, f"a word in two rows: {sorted(words & seen)}")
            seen |= words

    def test_docs_name_the_rules_and_the_kit_calls(self):
        self.assertRegex(read(REF, "launch-and-lifecycle.md"), r"\n## 9\. Opening mode")
        self.assertIn("Back navigation contract", read(REF, "telegram-design-guidelines.md"))
        table = read(REF, "anti-slop.md")
        for rule in ("MA45 tab-bar", "MA46 launch-mode", "MA47 dead-end"):
            self.assertIn(rule, table)
        kit = read(EX, "_kit", "tma.ts")
        for name in ("function start(", "function scrollMemory(", "function verticalSwipes(", "back(): void"):
            self.assertIn(name, kit)


if __name__ == "__main__":
    unittest.main()
