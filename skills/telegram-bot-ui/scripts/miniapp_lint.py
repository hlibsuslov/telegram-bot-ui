#!/usr/bin/env python3
# run-checks: examples/mini-apps --strict
"""Lint a Telegram Mini App's source for security mistakes, non-native patterns and AI-slop.

  py -3 scripts/miniapp_lint.py examples/mini-apps            # a folder (html, css, js, ts, jsx, tsx, py)
  py -3 scripts/miniapp_lint.py app/index.html app/style.css   # files
  py -3 scripts/miniapp_lint.py examples/mini-apps --json      # machine-readable
  py -3 scripts/miniapp_lint.py examples/mini-apps --strict    # warnings fail too

Pattern-based and offline. A clean report is evidence for the static contract only, never proof that
real Telegram clients render the app as intended. Files under a `server/` or `bot/` folder and `.py`
files count as server code; the rest is client code. `dist/` and `node_modules/` are skipped.

Rules (G = Telegram design guidelines rule, S = security.md, A = anti-slop.md; every rule is explained
in references/mini-apps/anti-slop.md#linter-rules):
  errors
    MA01 bot-token        S   a bot token or BOT_TOKEN in client code
    MA02 unsafe-server    S   initDataUnsafe read in server code: verify initData instead
    MA03 native-dialog    G3  alert() / confirm() / prompt(): use showAlert / showConfirm / showPopup
    MA04 script-order     G8  telegram-web-app.js missing from <head>, or another script runs before it
  warnings
    MA05 raw-color        G1  colour literal outside a var() fallback, light-dark(), a --tma-fb-* palette or a neutral alpha grey
    MA06 vh               G2  100vh / dvh / svh outside a var(--tg-viewport-*) fallback
    MA07 fixed-cta        G3  own fixed bottom button: use the MainButton (mark a browser fallback data-tma-fallback)
    MA08 safe-area        G6  requestFullscreen without --tg-safe-area / --tg-content-safe-area insets in CSS
    MA09 transition-all   G4  transition: all, animate-pulse, animate-ping
    MA10 infinite         G4  an infinite animation on something that is not a loader
    MA11 gradient-text    A   background-clip: text
    MA12 glass-fallback   A   backdrop-filter without a reduced-transparency or @supports fallback
    MA13 emoji-ui         A   Unicode emoji as a label in buttons, navigation, headings or bottom-button text
    MA14 local-storage    S   localStorage / sessionStorage: CloudStorage / DeviceStorage, secrets in SecureStorage
    MA15 version-gate     G3  a Telegram.WebApp member newer than 6.0 used with no isVersionAtLeast in the file
    MA16 web-font         A   @font-face or a web-font CDN for UI text: system font
    MA17 reduced-motion   G4  motion in CSS and no prefers-reduced-motion rule anywhere
    MA18 ready            G8  the app never calls ready()
    MA19 own-back         G3  history.back() or an own back button: BackButton
    MA20 web-login        S   "Login with Telegram" widget inside a Mini App: initData already identifies the user
    MA21 hover-only       G2  content revealed on :hover only
    MA22 small-text       G5  font-size below 11 px
    MA23 viewport-meta    G2  HTML entry without <meta name="viewport">
    MA24 label            G5  <input> without a label or aria-label, <img> without alt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REF = "references/mini-apps/anti-slop.md#linter-rules"
EXTS = (".html", ".htm", ".css", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".py")
SKIP = {"dist", "node_modules", ".git", "__pycache__"}
RULES = {
    "MA01": ("error", "bot-token"), "MA02": ("error", "unsafe-server"), "MA03": ("error", "native-dialog"),
    "MA04": ("error", "script-order"), "MA05": ("warn", "raw-color"), "MA06": ("warn", "vh"),
    "MA07": ("warn", "fixed-cta"), "MA08": ("warn", "safe-area"), "MA09": ("warn", "transition-all"),
    "MA10": ("warn", "infinite"), "MA11": ("warn", "gradient-text"), "MA12": ("warn", "glass-fallback"),
    "MA13": ("warn", "emoji-ui"), "MA14": ("warn", "local-storage"), "MA15": ("warn", "version-gate"),
    "MA16": ("warn", "web-font"), "MA17": ("warn", "reduced-motion"), "MA18": ("warn", "ready"),
    "MA19": ("warn", "own-back"), "MA20": ("warn", "web-login"), "MA21": ("warn", "hover-only"),
    "MA22": ("warn", "small-text"), "MA23": ("warn", "viewport-meta"), "MA24": ("warn", "label"),
}
TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b|\bBOT_TOKEN\b|\bTELEGRAM_BOT_TOKEN\b")
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^)]*\)")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF\u2600-\u27BF\u2B50\u2B55]")
STARS_AMOUNT = re.compile(r"⭐️?\s*(?:\d|\$\{)")  # the Telegram Stars currency sign before an amount is not decoration
TG_SCRIPT = re.compile(r"<script\b[^>]*\bsrc=[\"']https://telegram\.org/js/telegram-web-app\.js", re.I)
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
COMMENT_CSS = re.compile(r"/\*.*?\*/", re.S)
COMMENT_JS = re.compile(r"/\*.*?\*/|(?<![:\"'\\])//[^\n]*", re.S)


@dataclass
class Finding:
    rule: str
    level: str
    name: str
    file: str
    line: int
    msg: str

    def text(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule} {self.name}] {self.msg}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warn"]


def gated_members() -> dict[str, str]:
    """Method and object names of Telegram.WebApp newer than 6.0, from the offline catalog."""
    try:
        import webapp_lookup
        api = webapp_lookup.WebAppApi()
    except (OSError, ImportError, ValueError):
        return {}
    out = {}
    for key, ver in api.gates().items():
        m = api.cat["members"][key]
        if m["owner"] == "WebApp" and m["kind"] in ("method", "object"):
            out[m["name"]] = ver
    out["SecondaryButton"] = "7.10"
    return out


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _strip_allowed_colors(css: str) -> str:
    """Blank out theme-safe colour spots (var() fallbacks, light-dark(), --tma-fb-* / --fb-* values) keeping offsets."""
    chars = list(css)

    def blank(a: int, b: int) -> None:
        for i in range(a, b):
            if chars[i] != "\n":
                chars[i] = " "

    for m in re.finditer(r"\b(var|light-dark)\(", css):
        depth, j = 0, m.end() - 1
        while j < len(css):
            if css[j] == "(":
                depth += 1
            elif css[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if m.group(1) == "var":
            comma = css.find(",", m.end(), j)
            if comma > 0:
                blank(comma, j)
        else:
            blank(m.start(), j)
    for m in re.finditer(r"--(?:tma-fb|fb)-[\w-]+\s*:[^;}]*", css):
        blank(m.start(), m.end())
    return "".join(chars)


def _neutral(color: str) -> bool:
    m = re.match(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)\s*(?:[/,]\s*([\d.]+%?))?\s*\)", color)
    if not m or not m.group(4):
        return False
    alpha = float(m.group(4).rstrip("%")) / (100 if m.group(4).endswith("%") else 1)
    return m.group(1) == m.group(2) == m.group(3) and alpha < 1


def _css_rules(css: str):
    for m in re.finditer(r"([^{}@;]+)\{([^{}]*)\}", css):
        yield m.group(1).strip(), m.group(2), m.start()


def is_server(path: str, root: str | None = None) -> bool:
    """Server code by folder name, judged on the path RELATIVE to the lint root (a project that itself lives
    under C:/work/api/... is not all server code)."""
    rel = os.path.relpath(path, root) if root else os.path.basename(path)
    parts = set(re.split(r"[\\/]", rel.lower())[:-1])
    return path.endswith(".py") or bool(parts & {"server", "bot", "api", "backend"})


def lint_files(paths: list[str], root: str | None = None) -> Report:
    rep = Report()
    files: dict[str, str] = {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            files[p] = fh.read()
    gates = gated_members()

    def add(rule: str, path: str, text: str, pos: int, msg: str) -> None:
        level, name = RULES[rule]
        rel = os.path.relpath(path, root) if root else path
        rep.findings.append(Finding(rule, level, name, rel.replace(os.sep, "/"), _line(text, pos), msg))

    all_css, client_js = [], []
    uses_webapp = False
    calls_ready = False
    for path, text in files.items():
        ext = os.path.splitext(path)[1].lower()
        server = is_server(path, root)
        in_kit = "_kit" in re.split(r"[\\/]", os.path.relpath(path, root) if root else path)
        css_parts: list[tuple[str, int]] = []
        if ext == ".css":
            css_parts.append((text, 0))
        if ext in (".html", ".htm"):
            css_parts += [(m.group(1), m.start(1)) for m in STYLE_BLOCK.finditer(text)]
        js = text if ext in (".js", ".mjs", ".ts", ".tsx", ".jsx") else ""
        if ext in (".html", ".htm"):
            # keep inline script bodies at their offsets so findings report the right line
            keep = [m.span(1) for m in re.finditer(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", text, re.S | re.I)]
            chars = [" " if c != "\n" else c for c in text]
            for a, b in keep:
                chars[a:b] = text[a:b]
            js = "".join(chars) if keep else ""
        code = COMMENT_JS.sub(lambda m: " " * len(m.group(0)), js) if js else ""
        if "Telegram.WebApp" in text or "createTma" in text or "@tma.js" in text:
            uses_webapp = uses_webapp or not server
        # the kit's own tg.ready() wrapper does not count: the app must call it (tma.ready() / WebApp.ready())
        if not in_kit and re.search(r"\.ready\s*\(\s*\)", code):
            calls_ready = True

        # ---- security
        if not server and ext != ".py":
            for m in TOKEN.finditer(text):
                add("MA01", path, text, m.start(), "bot token in client code: it stays on the server, read from the environment")
                break
        if server:
            for m in re.finditer(r"initDataUnsafe", text):
                add("MA02", path, text, m.start(), "server reads initDataUnsafe; verify the raw initData (HMAC or Ed25519) and use that")
                break
        if code and not server:
            for m in re.finditer(r"(?<![\w.])(?:window\.)?(alert|confirm|prompt)\s*\(", code):
                if re.search(r"function\s+$", code[max(0, m.start() - 12):m.start()]):
                    continue  # a declaration (the kit's own confirm wrapper), not the browser dialog
                add("MA03", path, text, m.start(), f"{m.group(1)}() blocks the WebView; use showAlert / showConfirm / showPopup")
            for m in re.finditer(r"\b(localStorage|sessionStorage)\b", code):
                add("MA14", path, text, m.start(), f"{m.group(1)}: user data in CloudStorage / DeviceStorage, tokens in SecureStorage or memory")
                break
            for m in re.finditer(r"history\.back\s*\(", code):
                add("MA19", path, text, m.start(), "history.back(): drive Telegram's BackButton from one navigation stack")
            client_js.append((path, code))
        if not server and re.search(r"telegram-widget\.js|oauth\.telegram\.org|Login with Telegram", text, re.I):
            m = re.search(r"telegram-widget\.js|oauth\.telegram\.org|Login with Telegram", text, re.I)
            add("MA20", path, text, m.start(), "web login inside a Mini App: initData already identifies the user")

        # ---- HTML structure
        if ext in (".html", ".htm") and not server:
            head = text.split("</head>", 1)[0]
            uses = "Telegram.WebApp" in text or "./dist/" in text or re.search(r"<script\b[^>]*type=[\"']module", text)
            m = TG_SCRIPT.search(head)
            if uses and not m:
                add("MA04", path, text, 0, "telegram-web-app.js is not in <head>")
            elif m and re.search(r"<script\b", head[:m.start()], re.I):
                add("MA04", path, text, m.start(), "another <script> runs before telegram-web-app.js")
            if "<html" in text.lower() and not re.search(r'name=["\']viewport["\']', head, re.I):
                add("MA23", path, text, 0, "no <meta name=\"viewport\">")
            for m in re.finditer(r"<(button|nav|h[1-6]|a)\b[^>]*>(.*?)</\1>", text, re.S | re.I):
                inner = re.sub(r"<[^>]+>", "", m.group(2))
                if EMOJI.search(STARS_AMOUNT.sub("", inner)):
                    add("MA13", path, text, m.start(), f"emoji in <{m.group(1)}> {inner.strip()[:30]!r}: a line icon or text")
            own_back = re.search(r"history\.back\s*\(|<(?:button|a)[^>]*(?:class|id)=[\"'][^\"']*(?:back-btn|btn-back|back-button|nav-back)", text, re.I)
            if own_back:
                add("MA19", path, text, own_back.start(), "own back control: Telegram's BackButton, driven by one navigation stack")
            labels = set(re.findall(r"<label\b[^>]*\bfor=[\"']([^\"']+)", text, re.I))
            for m in re.finditer(r"<input\b([^>]*)>", text, re.I):
                attrs = m.group(1)
                if re.search(r"type=[\"'](hidden|submit|button)", attrs, re.I):
                    continue
                idm = re.search(r"\bid=[\"']([^\"']+)", attrs)
                wrapped = text.rfind("<label", 0, m.start()) > text.rfind("</label>", 0, m.start())
                if not (re.search(r"aria-label(ledby)?=", attrs) or (idm and idm.group(1) in labels) or wrapped):
                    add("MA24", path, text, m.start(), "<input> without a label, aria-label or aria-labelledby")
            for m in re.finditer(r"<img\b(?![^>]*\balt=)[^>]*>", text, re.I):
                add("MA24", path, text, m.start(), "<img> without alt (alt=\"\" for decoration)")
            if re.search(r"fonts\.googleapis\.com|fonts\.gstatic\.com|use\.typekit", text):
                m = re.search(r"fonts\.googleapis\.com|fonts\.gstatic\.com|use\.typekit", text)
                add("MA16", path, text, m.start(), "web font for UI text: Telegram's system font loads instantly and matches the client")

        # ---- bottom-button labels with emoji (JS)
        if code:
            for m in re.finditer(r"(?:setText\s*\(|\btext\s*:)\s*[`'\"]([^`'\"]*)", code):
                if EMOJI.search(STARS_AMOUNT.sub("", m.group(1))):
                    add("MA13", path, text, m.start(), f"emoji in a button label {m.group(1)[:30]!r}: use iconCustomEmojiId (9.5) or plain text")

        # ---- CSS
        for css, offset in css_parts:
            clean = COMMENT_CSS.sub(lambda m: " " * len(m.group(0)), css)
            all_css.append(clean)
            # selectors are not colours (#add, #face): blank them, keep offsets
            no_selectors = re.sub(r"[^{}]*\{", lambda m: " " * (len(m.group(0)) - 1) + "{", clean)
            allowed = _strip_allowed_colors(no_selectors)
            for m in COLOR.finditer(allowed):
                if not _neutral(m.group(0)):
                    add("MA05", path, text, offset + m.start(), f"hard-coded colour {m.group(0)}: a --tg-theme-* role or a derived color-mix()")
            stripped_vh = re.sub(r"var\([^()]*(?:\([^()]*\)[^()]*)*\)", lambda m: m.group(0) if "100" not in m.group(0) else " " * len(m.group(0)), clean)
            for m in re.finditer(r"\b100[dsl]?vh\b", stripped_vh):
                add("MA06", path, text, offset + m.start(), "100vh jumps with Telegram's sheet: var(--tg-viewport-stable-height)")
            for sel, body, pos in _css_rules(clean):
                if re.search(r"position\s*:\s*fixed", body) and re.search(r"\bbottom\s*:", body) \
                        and re.search(r"btn|button|cta|checkout|submit|buy|pay", sel, re.I) and "data-tma-fallback" not in sel:
                    add("MA07", path, text, offset + pos, f"fixed bottom button {sel[:40]!r}: MainButton / SecondaryButton")
                if re.search(r"\binfinite\b", body) and not re.search(r"skeleton|spinner|shimmer|loading|loader|progress|spin", sel, re.I):
                    add("MA10", path, text, offset + pos, f"infinite animation on {sel[:40]!r}: animate only live or loading things")
                if ":hover" in sel and re.search(r"(display\s*:\s*(block|flex|grid)|visibility\s*:\s*visible|opacity\s*:\s*1\b)", body):
                    add("MA21", path, text, offset + pos, f"{sel[:40]!r} reveals content on hover only; touch has no hover")
            for m in re.finditer(r"transition\s*:\s*all\b|transition-all\b|animate-(pulse|ping)\b", clean):
                add("MA09", path, text, offset + m.start(), f"{m.group(0)}: name the properties (transform, opacity, colour)")
            for m in re.finditer(r"background-clip\s*:\s*text", clean):
                add("MA11", path, text, offset + m.start(), "gradient text: emphasis by weight and size")
            if re.search(r"backdrop-filter", clean) and not re.search(r"prefers-reduced-transparency|@supports\s+not", clean):
                m = re.search(r"backdrop-filter", clean)
                add("MA12", path, text, offset + m.start(), "glass without a solid fallback for reduced transparency, Android LOW and no-blur WebViews")
            for m in re.finditer(r"@font-face", clean):
                add("MA16", path, text, offset + m.start(), "@font-face for UI text: system font (a brand face only on one moment)")
            for m in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", clean):
                if float(m.group(1)) < 11:
                    add("MA22", path, text, offset + m.start(), f"font-size {m.group(1)}px: nothing below 11 px")

    # ---- project-level checks
    css_all = "\n".join(all_css)
    js_all = "\n".join(c for _, c in client_js)
    if re.search(r"@keyframes|transition\s*:|animation\s*:", css_all) and "prefers-reduced-motion" not in css_all:
        path = next((p for p in files if p.endswith(".css")), next(iter(files), ""))
        if path:
            add("MA17", path, files[path], 0, "motion without a prefers-reduced-motion rule")
    if re.search(r"requestFullscreen\s*\(", js_all) and not re.search(r"--tg-(content-)?safe-area-inset|--tma-safe", css_all):
        path = next(p for p, c in client_js if "requestFullscreen" in c)
        add("MA08", path, files[path], files[path].find("requestFullscreen"), "fullscreen without safe-area and content-safe-area padding")
    if uses_webapp and not calls_ready:
        path = next((p for p, _ in client_js), next(iter(files), ""))
        if path:
            add("MA18", path, files[path], 0, "ready() is never called: Telegram shows its loading screen until the page fully loads")
    for path, code in client_js:
        # Gates: Telegram.WebApp.isVersionAtLeast, the kit's has('x.y'), @tma.js/sdk's isAvailable()/ifAvailable()
        if not gates or re.search(r"isVersionAtLeast|versionAtLeast|\bhas\(\s*['\"]\d|\.isAvailable\(\)|\.ifAvailable\(", code):
            continue
        used = sorted({m.group(1) for m in re.finditer(r"\.(" + "|".join(map(re.escape, gates)) + r")\b", code)})
        if used:
            add("MA15", path, files[path], files[path].find(used[0]),
                "ungated: " + ", ".join(f"{u} ({gates[u]})" for u in used[:6]) + " - older clients throw or ignore it")
    return rep


def collect(targets: list[str]) -> tuple[list[str], str | None]:
    files = []
    root = None
    for t in targets:
        if os.path.isdir(t):
            root = root or os.path.abspath(t)
            for dirpath, dirs, names in os.walk(t):
                dirs[:] = sorted(d for d in dirs if d not in SKIP)
                files += [os.path.join(dirpath, n) for n in sorted(names) if n.lower().endswith(EXTS)]
        elif os.path.isfile(t):
            files.append(t)
    return files, root


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Mini App lint (offline, pattern-based)")
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    args = ap.parse_args(argv)
    targets = []
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for t in args.targets:  # run_checks passes skill-relative paths
        targets.append(t if os.path.exists(t) else os.path.join(skill, t))
    files, root = collect(targets)
    if not files:
        print("no Mini App files found")
        return 2
    rep = lint_files(files, root)
    if args.json:
        print(json.dumps({"files": len(files), "errors": [f.__dict__ for f in rep.errors],
                          "warnings": [f.__dict__ for f in rep.warnings], "reference": REF}, indent=1))
    else:
        for f in rep.findings:
            print(("ERROR " if f.level == "error" else "WARN  ") + f.text())
        print(f"{len(files)} file(s): {len(rep.errors)} error(s), {len(rep.warnings)} warning(s). Rules: {REF}")
    if rep.errors or (args.strict and rep.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
