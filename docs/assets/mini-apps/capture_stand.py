"""The README picture of the preview stand itself (light and dark, 2x), framed like compose_showcase.py.

Start the stand first (from skills/telegram-bot-ui):
  py -3 scripts/preview_miniapp.py examples/mini-apps/paywall --serve 8813 --api examples/mini-apps/paywall/mock-api.json
Then: py -3 capture_stand.py [OUT_DIR]   (needs Python Playwright and Pillow; raw captures go to OUT_DIR)
Writes stand-light.png and stand-dark.png next to this file.
"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8813/?platform=ios&width=390&height=800&mode=fullscreen"
VIEWPORT = {"width": 1440, "height": 900}
SCALE = 2
# The showcase's backgrounds and shadow strength, so the two pictures sit together in the README.
THEMES = {"light": ((201, 217, 184), 0.16), "dark": ((14, 22, 33), 0.45)}
MARGIN, RADIUS, SHADOW_Y, SHADOW_BLUR = 72, 28, 14, 34


def capture(out: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in THEMES:
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE, color_scheme=scheme)
            page = ctx.new_page()
            page.goto(f"{URL}&scheme={scheme}")
            page.wait_for_timeout(3000)
            # The Layout audit of the screen on show fills the bottom panel's third tab; Events stays in front.
            page.click("#tab-layout")
            page.click("#audit-run")
            page.wait_for_timeout(1500)
            page.click("#tab-events")
            page.wait_for_timeout(400)
            page.screenshot(path=str(out / f"stand-{scheme}-raw.png"), animations="disabled")
            ctx.close()
        browser.close()


def frame(raw: Path, theme: str) -> None:
    background, opacity = THEMES[theme]
    with Image.open(raw) as shot:
        window = shot.convert("RGBA")
    m, r = MARGIN * SCALE, RADIUS * SCALE
    mask = Image.new("L", (window.width * 2, window.height * 2))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, window.width * 2 - 1, window.height * 2 - 1), radius=r * 2, fill=255)
    window.putalpha(mask.resize(window.size, Image.Resampling.BOX))

    size = (window.width + 2 * m, window.height + 2 * m)
    canvas = Image.new("RGB", size, background)
    shadow = Image.new("L", size)
    shadow.paste(window.getchannel("A"), (m, m + SHADOW_Y * SCALE))
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR * SCALE))
    canvas.paste((0, 0, 0), (0, 0, *size), shadow.point([round(v * opacity) for v in range(256)]))
    canvas.paste(window, (m, m), window.getchannel("A"))
    # A hairline edge: on the dark background the shadow alone doesn't separate the window.
    edge = (255, 255, 255, 30) if theme == "dark" else (0, 0, 0, 22)
    overlay = Image.new("RGBA", size)
    ImageDraw.Draw(overlay).rounded_rectangle((m, m, m + window.width - 1, m + window.height - 1),
                                              radius=r, outline=edge, width=SCALE)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    # README width is about 900 px; 2560 wide keeps text sharp on 2x screens and matches the showcase.
    target = 2560
    canvas = canvas.resize((target, round(canvas.height * target / canvas.width)), Image.Resampling.LANCZOS)
    output = Path(__file__).with_name(f"stand-{theme}.png")
    canvas.save(output, optimize=True)
    print(f"{output.name}: {canvas.width}x{canvas.height}, {output.stat().st_size:,} bytes")


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    os.makedirs(out, exist_ok=True)
    capture(out)
    for theme in THEMES:
        frame(out / f"stand-{theme}-raw.png", theme)


if __name__ == "__main__":
    main()
