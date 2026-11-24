"""Build the README Mini Apps showcase: py -3 compose_showcase.py PATH_TO_SHOTS."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


APPS = ("classes", "catalog", "wallet", "gifts", "coffee")
THEMES = {"light": ((201, 217, 184), 0.12), "dark": ((14, 22, 33), 0.35)}
CANVAS_SIZE = (2560, 1080)
SOURCE_SIZE = (780, 1600)
PHONE_WIDTH = 448
SIDE_MARGIN = 70
GAP = 45
ROW_TOP = 74
SHADOW_OFFSET_Y = 12
SHADOW_BLUR = 30


def load_phone(path, app):
    width, height = SOURCE_SIZE
    with Image.open(path) as capture:
        if capture.width != width or capture.height not in (height, height + 2):
            raise ValueError(f"Unexpected capture size for {path}: {capture.size}")
        # The taller captures include two extra pixels of bezel below the display.
        phone = capture.crop((0, 0, width, height)).convert("RGBA")

    # Follow the mock client's 2x display curve and mask the bezel and stand.
    radius = 56 if app == "coffee" else 88
    mask = Image.new("L", (width * 2, height * 2))
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, 2 * width - 1, 2 * height - 1),
        radius=2 * radius,
        fill=255,
    )
    phone.putalpha(mask.resize(phone.size, Image.Resampling.BOX))
    scaled_height = round(height * PHONE_WIDTH / width)
    return phone.resize((PHONE_WIDTH, scaled_height), Image.Resampling.LANCZOS)


def compose(shots, theme):
    background, opacity = THEMES[theme]
    canvas = Image.new("RGB", CANVAS_SIZE, background)
    shadow = Image.new("L", CANVAS_SIZE)
    phones = []
    for index, app in enumerate(APPS):
        phone = load_phone(shots / f"{app}-{theme}.png", app)
        x = SIDE_MARGIN + index * (PHONE_WIDTH + GAP)
        alpha = phone.getchannel("A")
        shadow.paste(alpha, (x, ROW_TOP + SHADOW_OFFSET_Y))
        phones.append((phone, x, alpha))

    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    shadow = shadow.point([round(value * opacity) for value in range(256)])
    canvas.paste((0, 0, 0), (0, 0, *CANVAS_SIZE), shadow)
    for phone, x, alpha in phones:
        canvas.paste(phone, (x, ROW_TOP), alpha)

    output = Path(__file__).with_name(f"showcase-{theme}.png")
    canvas.save(output, optimize=True)
    print(f"{output.name}: {canvas.width}x{canvas.height}, {output.stat().st_size:,} bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shots", type=Path, help="Directory containing the ten source PNGs")
    args = parser.parse_args()
    for theme in THEMES:
        compose(args.shots, theme)


if __name__ == "__main__":
    main()
