"""emoji_mosaic.py: grids, crops, the UTF-16 message, manifests and ZIPs, publish against a fake Bot API, and
(when ffmpeg is installed) a real cut of a synthetic clip checked against Telegram's video emoji rules."""
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

import _paths
import emoji_mosaic as em

CLI = os.path.join(_paths.ROOT, "scripts", "emoji_mosaic.py")
TGUI = os.path.join(_paths.ROOT, "scripts", "tgui.py")
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def png(w=100, h=100):
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def png_alpha(path):
    """Alpha rows of an 8-bit RGBA PNG, standard library only (enough for the tiles this tool writes)."""
    with open(path, "rb") as fh:
        data = fh.read()
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert (depth, color) == (8, 6), "expected 8-bit RGBA"
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw, stride, rows, prev = zlib.decompress(idat), width * 4, [], bytearray(width * 4)
    for y in range(height):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - 4] if i >= 4 else 0
            b, c = prev[i], prev[i - 4] if i >= 4 else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(list(line[3::4]))
        prev = line
    return rows


def static_mosaic(cols=3, rows=2, size=100):
    tiles = em.tile_names(cols, rows, "png")
    manifest = {"schema": em.SCHEMA, "format": "static", "grid": {"cols": cols, "rows": rows}, "tile": 100,
                "fallback": "⬜", "tiles": tiles}
    return manifest, {t: png(size, size) for t in tiles}


class FakeBot:
    """Scripted Bot API: keeps one set, hands out ids, answers sendMessage with the entities it got."""

    def __init__(self, *, strip=False, lose_create=False):
        self.calls, self.sets, self.strip, self.lose_create = [], {}, strip, lose_create
        self.params = []
        self.n = 0

    def call(self, method, params, files=None):
        self.calls.append(method)
        self.params.append((method, params))
        if method == "setCustomEmojiStickerSetThumbnail":
            return True
        if method == "getMe":
            return {"id": 1, "is_bot": True, "username": "PackMakerBot"}
        if method == "getStickerSet":
            if params["name"] not in self.sets:
                raise em.TelegramError(method, 400, "Bad Request: STICKERSET_INVALID")
            return {"name": params["name"], "sticker_type": "custom_emoji",
                    "stickers": [{"custom_emoji_id": i} for i in self.sets[params["name"]]]}
        if method == "uploadStickerFile":
            assert files and params["sticker_format"] in ("static", "video")
            self.n += 1
            return {"file_id": f"file{self.n}"}
        if method == "createNewStickerSet":
            assert len(params["stickers"]) <= em.MAX_INITIAL and params["sticker_type"] == "custom_emoji"
            self.sets[params["name"]] = [f"5{len(params['stickers']):02d}{i:06d}" for i in range(len(params["stickers"]))]
            if self.lose_create:
                self.lose_create = False
                raise em.OutcomeUnknown("createNewStickerSet: timeout")
            return True
        if method == "addStickerToSet":
            ids = self.sets[params["name"]]
            ids.append(f"6{len(ids):08d}")
            return True
        if method == "sendMessage":
            return {"message_id": 7, "entities": [] if self.strip else params["entities"]}
        raise AssertionError(method)


class Grid(unittest.TestCase):
    def test_auto_grid_keeps_shape_and_safe_columns(self):
        self.assertEqual(em.auto_grid(1280, 720), (7, 4))
        cols, rows = em.auto_grid(1000, 1000)
        self.assertEqual(cols, rows)
        self.assertLessEqual(cols, em.SAFE_COLUMNS)
        for w, h in ((1920, 1080), (1080, 1920), (3000, 1000), (500, 500)):
            c, r = em.auto_grid(w, h)
            self.assertLessEqual(c * r, em.DEFAULT_MAX_EMOJI)

    def test_options_are_sorted_and_labelled(self):
        options = em.grid_options(1280, 720)
        crops = [round(o["crop"], 2) for o in options]
        self.assertEqual(crops, sorted(crops))
        self.assertEqual(em.column_fit(8), "safe")
        self.assertEqual(em.column_fit(12), "check-narrow-phone")
        self.assertEqual(em.column_fit(13), "likely-wraps")

    def test_parse_grid_limits(self):
        self.assertEqual(em.parse_grid("8x4"), (8, 4))
        self.assertEqual(em.parse_grid("10×10"), (10, 10))
        for bad in ("11x10", "0x4", "eight"):
            with self.assertRaises(em.MosaicError):
                em.parse_grid(bad)


class Defaults(unittest.TestCase):
    def test_auto_grid_prefers_fewer_larger_tiles(self):
        self.assertEqual(em.auto_grid(720, 1280), (4, 7))
        self.assertEqual(em.auto_grid(1000, 1000), (6, 6))
        for w, h in ((1920, 1080), (1080, 1920), (500, 500), (3000, 1000)):
            c, r = em.auto_grid(w, h)
            self.assertLessEqual(c * r, em.TARGET_EMOJI)

    def test_emoji_rules(self):
        for ok in ("⬜", "🌅", "👍🏽", "1️⃣", "🇳🇴", "👨‍👩‍👧", "🖼️"):
            self.assertTrue(em.looks_like_emoji(ok), ok)
        for bad in ("abc", "", "<b>", "🌅 x", "1", 5, "🌅" * 9):
            self.assertFalse(em.looks_like_emoji(bad), bad)


class Crop(unittest.TestCase):
    def test_crop_and_corners_agree(self):
        self.assertEqual(em.parse_box("10,20,300,200", None, 640, 480), (10, 20, 300, 200))
        self.assertEqual(em.parse_box(None, "310,220,10,20", 640, 480), (10, 20, 300, 200))
        self.assertEqual(em.parse_box(None, None, 640, 480), (0, 0, 640, 480))

    def test_crop_outside_or_both_refused(self):
        with self.assertRaises(em.MosaicError):
            em.parse_box("600,0,100,100", None, 640, 480)
        with self.assertRaises(em.MosaicError):
            em.parse_box("0,0,10,10", "0,0,10,10", 640, 480)

    def test_filters(self):
        self.assertIn("crop=300:200:10:20", em.fit_filter((10, 20, 300, 200), 8, 4, "cover", "transparent"))
        self.assertIn("pad=800:400", em.fit_filter((0, 0, 640, 480), 8, 4, "contain", "#FFFFFF"))
        self.assertIn("geq", em.round_filter(40, 8, 4))
        self.assertEqual(em.max_radius(8, 4), 200)


class Message(unittest.TestCase):
    def test_offsets_are_utf16(self):
        ids = [str(5000000000000000000 + i) for i in range(6)]
        body = em.mosaic_message(ids, 3, "🟦")    # U+1F7E6 is two UTF-16 units
        self.assertEqual(body["text"], "🟦🟦🟦\n🟦🟦🟦")
        self.assertEqual([e["offset"] for e in body["entities"]], [0, 2, 4, 7, 9, 11])
        self.assertTrue(all(e["length"] == 2 and e["type"] == "custom_emoji" for e in body["entities"]))
        bmp = em.mosaic_message(ids[:2], 1, "⬜")
        self.assertEqual([e["offset"] for e in bmp["entities"]], [0, 2])

    def test_rejects_invented_or_repeated_ids(self):
        for ids in ([], ["1", "1"], ["abc"]):
            with self.assertRaises(em.MosaicError):
                em.mosaic_message(ids, 2)

    def test_per_tile_emoji_from_the_website(self):
        manifest, _ = static_mosaic(2, 1)
        manifest["emoji"] = ["🌅", "🌿"]
        em._check_manifest(manifest)
        self.assertEqual(em.tile_emoji(manifest), ["🌅", "🌿"])
        self.assertEqual(em.mosaic_message(["1", "2"], 2, em.tile_emoji(manifest))["text"], "🌅🌿")
        with self.assertRaises(em.MosaicError):
            em._check_manifest({**manifest, "emoji": ["🌅"]})

    def test_html(self):
        self.assertEqual(em.mosaic_html(["1", "2", "3", "4"], 2), '<tg-emoji emoji-id="1">⬜</tg-emoji>'
                         '<tg-emoji emoji-id="2">⬜</tg-emoji>\n<tg-emoji emoji-id="3">⬜</tg-emoji>'
                         '<tg-emoji emoji-id="4">⬜</tg-emoji>')


class Files(unittest.TestCase):
    def test_zip_from_the_website_loads_and_checks(self):
        manifest, blobs = static_mosaic()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("emoji-mosaic/mosaic.json", json.dumps(manifest))
            for name, data in blobs.items():
                zf.writestr(f"emoji-mosaic/{name}", data)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.zip")
            with open(path, "wb") as fh:
                fh.write(buf.getvalue())
            mosaic = em.load_mosaic(path)
        self.assertEqual((mosaic.cols, mosaic.rows), (3, 2))
        self.assertEqual(em.check(mosaic), [])

    def test_manifest_types_are_checked(self):
        manifest, _ = static_mosaic()
        for bad in ({**manifest, "grid": "8x4"}, {**manifest, "grid": {"cols": -1, "rows": -1}},
                    {**manifest, "fallback": "abc"}, {**manifest, "emoji": ["x"] * 6}, ["not", "a", "dict"]):
            with self.assertRaises(em.MosaicError):
                em._check_manifest(bad)

    def test_bad_manifest_and_sizes(self):
        manifest, blobs = static_mosaic()
        with self.assertRaises(em.MosaicError):
            em._check_manifest({**manifest, "tiles": manifest["tiles"][:-1]})
        with self.assertRaises(em.MosaicError):
            em._check_manifest({**manifest, "tiles": ["../evil.png"] + manifest["tiles"][1:]})
        manifest, blobs = static_mosaic(size=120)
        self.assertEqual({p["code"] for p in em.check(em.Mosaic(manifest, blobs))}, {"NOT_100X100"})

    def test_image_size(self):
        self.assertEqual(em.image_size(png(100, 100)), ("png", 100, 100))
        self.assertIsNone(em.image_size(b"nope"))


class Publish(unittest.TestCase):
    def test_creates_reads_back_and_sends(self):
        manifest, blobs = static_mosaic(10, 6)       # 60 tiles: 50 at creation, 10 added
        bot = FakeBot()
        result = em.publish(bot, em.Mosaic(manifest, blobs), owner=42, log=lambda _: None)
        self.assertTrue(result["delivered"])
        self.assertEqual(len(result["ids"]), 60)
        self.assertTrue(result["set"].endswith("_by_packmakerbot"))
        self.assertEqual(bot.calls.count("createNewStickerSet"), 1)
        self.assertEqual(bot.calls.count("addStickerToSet"), 10)
        # same tiles, second run: the set is complete, nothing is created or added again
        again = em.publish(bot, em.Mosaic(manifest, blobs), owner=42, log=lambda _: None)
        self.assertEqual(again["set"], result["set"])
        self.assertEqual(bot.calls.count("createNewStickerSet"), 1)

    def test_lost_create_answer_is_read_back(self):
        manifest, blobs = static_mosaic(2, 2)
        bot = FakeBot(lose_create=True)
        result = em.publish(bot, em.Mosaic(manifest, blobs), owner=42, log=lambda _: None)
        self.assertTrue(result["delivered"])
        self.assertEqual(bot.calls.count("createNewStickerSet"), 1)

    def test_stripped_entities_are_not_done(self):
        manifest, blobs = static_mosaic(2, 1)
        result = em.publish(FakeBot(strip=True), em.Mosaic(manifest, blobs), owner=42, log=lambda _: None)
        self.assertFalse(result["delivered"])

    def test_icon_is_the_centre_tile_and_send_is_optional(self):
        manifest, blobs = static_mosaic(3, 3)
        bot = FakeBot()
        result = em.publish(bot, em.Mosaic(manifest, blobs), owner=42, send=False, log=lambda _: None)
        self.assertNotIn("sendMessage", bot.calls)
        self.assertIsNone(result["delivered"])
        thumb = [p for m, p in bot.params if m == "setCustomEmojiStickerSetThumbnail"][0]
        self.assertEqual(thumb["custom_emoji_id"], result["ids"][4])

    def test_publish_refuses_more_than_a_message_holds(self):
        manifest, blobs = static_mosaic(10, 11)
        with self.assertRaises(em.MosaicError):
            em.publish(FakeBot(), em.Mosaic(manifest, blobs), owner=42, log=lambda _: None)

    def test_dry_run_plan(self):
        manifest, blobs = static_mosaic(10, 6)
        plan = em.plan_publish(em.Mosaic(manifest, blobs), bot_username="PackBot", existing=0, owner=42)
        self.assertEqual((plan["uploads"], plan["create_with"], plan["add_one_by_one"]), (60, 50, 10))
        self.assertTrue(plan["set"].endswith("_by_packbot"))
        self.assertEqual(plan["send_to"], 42)

    def test_owner_ids_from_updates(self):
        updates = [{"update_id": 1, "message": {"from": {"id": 7, "is_bot": False, "first_name": "Ada", "is_premium": True}}},
                   {"update_id": 2, "message": {"from": {"id": 7, "is_bot": False, "first_name": "Ada"}}},
                   {"update_id": 3, "callback_query": {"from": {"id": 9, "is_bot": False, "username": "eve"}}}]
        self.assertEqual([p["id"] for p in em.owners_from_updates(updates)], [7, 9])

    def test_set_name_rules(self):
        self.assertEqual(em.set_name("ab12" * 4, "My_Bot"), "mosaic_ab12ab12ab_by_my_bot")
        with self.assertRaises(em.MosaicError):
            em.set_name("ab12" * 4, "x" * 60)

    def test_token_is_hidden_and_live_needs_a_flag(self):
        self.assertNotIn("123:secret", repr(em.Bot("123:secret")))
        with tempfile.TemporaryDirectory() as tmp:
            manifest, blobs = static_mosaic()
            os.makedirs(os.path.join(tmp, "tiles"))
            with open(os.path.join(tmp, "mosaic.json"), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            for name, data in blobs.items():
                with open(os.path.join(tmp, *name.split("/")), "wb") as fh:
                    fh.write(data)
            env = {k: v for k, v in os.environ.items() if not k.startswith("TELEGRAM_")}
            p = subprocess.run([sys.executable, CLI, "publish", tmp, "--owner", "1"], capture_output=True,
                               text=True, encoding="utf-8", env=env)
            self.assertEqual(p.returncode, 4)

    def test_multipart_body(self):
        body = em._multipart({"user_id": 5, "sticker_format": "video"}, {"sticker": ("a.webm", b"\x1aE", "video/webm")}, "B")
        self.assertIn(b'name="sticker"; filename="a.webm"', body)
        self.assertTrue(body.endswith(b"--B--\r\n"))


class Cli(unittest.TestCase):
    def test_plan_through_tgui(self):
        p = subprocess.run([sys.executable, TGUI, "mosaic", "plan", "--size", "1280x720", "--json"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["default"], "7x4")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg is not installed")
class RealCut(unittest.TestCase):
    def test_video_tiles_meet_telegram_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = os.path.join(tmp, "clip.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                            "-t", "4", clip], check=True)
            out = os.path.join(tmp, "m")
            manifest = em.make(clip, out, grid="4x2", corners="0,0,640,320", radius=40, start=0.5)
            self.assertTrue(manifest["alpha"])
            mosaic = em.load_mosaic(out)
            self.assertEqual(em.check(mosaic), [])
            self.assertTrue(os.path.isfile(os.path.join(out, "preview.html")))
            self.assertLessEqual(manifest["source"]["duration"], em.MAX_SECONDS)

    def test_rounded_corners_keep_the_edges_opaque(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "flat.png")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=400x200",
                            "-frames:v", "1", src], check=True)
            out = os.path.join(tmp, "m")
            em.make(src, out, grid="4x2", radius=40)
            top_middle = png_alpha(os.path.join(out, "tiles", "r01c02.png"))
            self.assertEqual(min(top_middle[0]), 255)            # the top edge row is fully opaque
            corner = png_alpha(os.path.join(out, "tiles", "r01c01.png"))
            self.assertEqual(corner[0][0], 0)                    # the outer corner is cut away
            self.assertEqual(corner[99][99], 255)

    def test_pingpong_does_not_repeat_turn_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = os.path.join(tmp, "clip.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=200x100:rate=20",
                            "-t", "2", clip], check=True)
            out = os.path.join(tmp, "m")
            manifest = em.make(clip, out, grid="2x1", duration=1.0, pingpong=True)
            frames = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                     "stream=nb_read_frames", "-of", "csv=p=0",
                                     os.path.join(out, "tiles", "r01c01.webm")], capture_output=True, text=True).stdout
            self.assertEqual(int(frames.strip()), 20 + 18)
            self.assertEqual(manifest["source"]["fps"], 20)          # capped by the source, not raised to 30

    def test_opaque_gif_gets_no_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            gif = os.path.join(tmp, "a.gif")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=200x100:rate=10",
                            "-t", "1", gif], check=True)
            self.assertFalse(em.source_info(gif)["alpha"])


if __name__ == "__main__":
    unittest.main()
