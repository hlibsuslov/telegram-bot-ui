"""Capture the README showcase screens from running preview stands (light and dark, 2x), for compose_showcase.py.

Start the stands first (from skills/telegram-bot-ui):
  py -3 scripts/preview_miniapp.py examples/mini-apps/rework --serve 8801 --api examples/mini-apps/rework/mock-api.json
  py -3 scripts/preview_miniapp.py examples/mini-apps/catalog --serve 8802
  py -3 scripts/preview_miniapp.py examples/mini-apps/portfolio --serve 8803
  py -3 scripts/preview_miniapp.py examples/mini-apps/vanilla --serve 8804
  py -3 scripts/preview_miniapp.py examples/mini-apps/gallery --serve 8805
Then: py -3 capture_showcase.py OUT_DIR && py -3 compose_showcase.py OUT_DIR   (needs Python Playwright)
"""
import os
import sys

from playwright.sync_api import sync_playwright

Q = "width=390&height=800&zoom=100&panels=0"  # 1:1, no panels: .device is the screenshot


def shot(page, path):
    page.locator(".device").first.screenshot(path=path, animations="disabled")


def main(out):
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 1400, "height": 1000}, device_scale_factor=2, color_scheme=scheme)
            page = ctx.new_page()
            go = lambda port, platform="ios": (page.goto(f"http://127.0.0.1:{port}/?platform={platform}&{Q}&scheme={scheme}"), page.wait_for_timeout(2500))
            go(8801); shot(page, os.path.join(out, f"classes-{scheme}.png"))
            go(8802); shot(page, os.path.join(out, f"catalog-{scheme}.png"))
            go(8803); page.get_by_text("Continue", exact=True).first.click(); page.wait_for_timeout(1200)
            shot(page, os.path.join(out, f"wallet-{scheme}.png"))
            go(8805)
            page.frame_locator("iframe").first.locator("body").evaluate(
                "() => { const s = document.querySelector('.tma-gift').closest('section');"
                " (s.querySelector('.tma-section__header') || s).scrollIntoView({block: 'start'}); window.scrollBy(0, -12); }")
            page.wait_for_timeout(900); shot(page, os.path.join(out, f"gifts-{scheme}.png"))
            go(8804, "android"); shot(page, os.path.join(out, f"coffee-{scheme}.png"))
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
