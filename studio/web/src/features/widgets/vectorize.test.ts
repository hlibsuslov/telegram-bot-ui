// node --test src/features/widgets/vectorize.test.ts (Node type stripping; no build step)
import assert from "node:assert/strict";
import { test } from "node:test";
import { downscale, pathData, polygonArea, quantize, simplifyLoop, traceMask, vectorize, type RGBAImage } from "./vectorize.ts";

/** 20x20: white background, a red 8x8 square at (4,4) with a 2x2 hole at (7,7), a blue 3x3 square at (15,15). */
function synthetic(): RGBAImage {
  const w = 20, h = 20, data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    let c = [255, 255, 255];
    if (x >= 4 && x < 12 && y >= 4 && y < 12 && !(x >= 7 && x < 9 && y >= 7 && y < 9)) c = [220, 30, 30];
    if (x >= 15 && x < 18 && y >= 15 && y < 18) c = [20, 40, 200];
    data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2]; data[i + 3] = 255;
  }
  return { width: w, height: h, data };
}

test("quantize finds the three colours", () => {
  const { palette, labels } = quantize(synthetic(), 3);
  assert.equal(palette.length, 3);
  assert.ok(labels.every((l) => l >= 0));
  const set = new Set(palette.map((c) => c.join(",")));
  assert.ok(set.has("255,255,255") && set.has("220,30,30") && set.has("20,40,200"));
});

test("traceMask returns an outer square and its hole", () => {
  const w = 20, h = 20, mask = new Uint8Array(w * h);
  for (let y = 4; y < 12; y++) for (let x = 4; x < 12; x++) if (!(x >= 7 && x < 9 && y >= 7 && y < 9)) mask[y * w + x] = 1;
  const loops = traceMask(mask, w, h);
  assert.equal(loops.length, 2);
  const areas = loops.map((l) => polygonArea(l)).sort((a, b) => Math.abs(b) - Math.abs(a));
  assert.equal(Math.abs(areas[0]), 64);
  assert.equal(Math.abs(areas[1]), 4);
  assert.ok(Math.sign(areas[0]) !== Math.sign(areas[1]), "hole runs the other way");
  for (const l of loops) assert.equal(l.length, 4, "a square keeps 4 corners");
});

test("simplifyLoop keeps a square and smooths a staircase", () => {
  const square: [number, number][] = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.deepEqual(simplifyLoop(square, 1), square);
  const stairs: [number, number][] = [];
  for (let i = 0; i < 10; i++) stairs.push([i, i], [i + 1, i]);
  stairs.push([10, 10], [0, 10]);
  assert.ok(simplifyLoop(stairs, 1.2).length < stairs.length / 2);
});

test("vectorize builds a compact, deterministic SVG", () => {
  const a = vectorize(synthetic(), { colors: 3, detail: 1 });
  const b = vectorize(synthetic(), { colors: 3, detail: 1 });
  assert.equal(a.svg, b.svg);
  assert.match(a.svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 20 20">/);
  assert.match(a.svg, /<rect width="20" height="20" fill="#fff"\/>/);
  assert.match(a.svg, /<path fill="#dc1e1e" fill-rule="evenodd" d="M4 4l8 0 0 8-8 0zM7 7l0 2 2 0 0-2z"\/>/);
  assert.equal(a.paths, 3);
  assert.ok(!/image|data:|clipPath|mask|pattern|filter|animate/.test(a.svg));
});

test("transparent pixels stay empty and downscale averages", () => {
  const img = synthetic();
  const t = new Uint8ClampedArray(img.data as Uint8ClampedArray);
  for (let p = 0; p < 400; p++) if (t[p * 4] === 255) t[p * 4 + 3] = 0;
  const r = vectorize({ width: 20, height: 20, data: t }, { colors: 2, detail: 1 });
  assert.ok(!r.svg.includes("<rect"));
  const small = downscale(img, 10);
  assert.equal(small.width, 10);
  assert.equal(pathData([[[0, 0], [2, 0], [2, 2]]]), "M0 0l2 0 0 2z");
});
