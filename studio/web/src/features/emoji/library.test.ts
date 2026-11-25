import assert from "node:assert/strict";
import { test } from "node:test";
import { facetOptions, filterPacks, filterPick, hasTag, isFiltered, pickIsStale, toggleFilter, type Catalog, type Pick } from "./library.ts";

const CATALOG: Catalog = {
  generated: "2026-11-25", taxonomy: 2, source: "export", threshold: 0.3,
  facets: {
    style: { label: "Style", values: [{ id: "outline", label: "Outline" }, { id: "glyph", label: "Solid glyph" }, { id: "3d", label: "3D" }] },
    color: { label: "Colour", values: [{ id: "blue", label: "Blue" }, { id: "red", label: "Red" }] },
    fit: { label: "Theme fit", values: [{ id: "adaptive", label: "Adaptive" }, { id: "both", label: "Light and dark themes" }, { id: "light", label: "Light theme only" }] },
    motion: { label: "Motion", values: [{ id: "static", label: "Static" }, { id: "animated", label: "Animated" }] },
  },
  packs: [
    { name: "lines", tags: { style: [["outline", 0.9]], color: [["blue", 0.8]], fit: [["adaptive", 1]], motion: [["static", 1]] } },
    { name: "solid", tags: { style: [["glyph", 1]], color: [["red", 0.7]], fit: [["both", 0.9]], motion: [["static", 1]] } },
    { name: "toons", tags: { style: [["3d", 0.9], ["outline", 0.2]], fit: [["light", 0.6]], motion: [["animated", 1]] } },
    { name: "mixed", tags: { style: [["outline", 0.6], ["glyph", 0.5]], color: [["blue", 0.4]], motion: [["animated", 1]] } },
  ],
};

const names = (list: { name: string }[]) => list.map((p) => p.name);

test("a tag counts at or above the library's pack threshold only", () => {
  assert.equal(hasTag(CATALOG.packs[2], "style", "3d", 0.3), true);
  assert.equal(hasTag(CATALOG.packs[2], "style", "outline", 0.3), false, "0.2 is below the threshold");
  assert.equal(hasTag(CATALOG.packs[0], "color", "red", 0.3), false);
});

test("values of one facet add up, facets narrow down", () => {
  assert.deepEqual(names(filterPacks(CATALOG, {})), ["lines", "solid", "toons", "mixed"]);
  assert.deepEqual(names(filterPacks(CATALOG, { style: ["outline"] })), ["lines", "mixed"]);
  assert.deepEqual(names(filterPacks(CATALOG, { style: ["outline", "glyph"] })), ["lines", "solid", "mixed"]);
  assert.deepEqual(names(filterPacks(CATALOG, { style: ["outline", "glyph"], motion: ["static"] })), ["lines", "solid"]);
  assert.deepEqual(names(filterPacks(CATALOG, { color: ["blue"], fit: ["adaptive"] })), ["lines"]);
  assert.deepEqual(names(filterPacks(CATALOG, { fit: ["light"], color: ["blue"] })), []);
});

test("toggling a value adds it, removes it, and drops an empty facet", () => {
  let f = toggleFilter({}, "style", "outline");
  assert.deepEqual(f, { style: ["outline"] });
  f = toggleFilter(f, "style", "glyph");
  assert.deepEqual(f, { style: ["outline", "glyph"] });
  f = toggleFilter(toggleFilter(f, "style", "outline"), "style", "glyph");
  assert.deepEqual(f, {});
  assert.equal(isFiltered(f), false);
  assert.equal(isFiltered({ motion: ["static"] }), true);
});

test("each value shows how many packs it would leave, counting the other facets' filters only", () => {
  const opts = facetOptions(CATALOG, { style: ["outline"] });
  assert.deepEqual(opts.map((o) => o.facet), ["style", "color", "fit", "motion"]);
  const style = opts.find((o) => o.facet === "style");
  assert.deepEqual(style?.values.map((v) => [v.id, v.count, v.active]), [["outline", 2, true], ["glyph", 2, false], ["3d", 1, false]]);
  const motion = opts.find((o) => o.facet === "motion");
  assert.deepEqual(motion?.values.map((v) => [v.id, v.count]), [["static", 1], ["animated", 1]]);
  const fit = opts.find((o) => o.facet === "fit");
  assert.deepEqual(fit?.values.map((v) => [v.id, v.count]), [["adaptive", 1], ["both", 0], ["light", 0]]);
});

const PICK: Pick = {
  mode: "coverage", slots: ["back", "cart", "done"], generated: "2026-11-25", source: "online", notes: [],
  packs: [
    { name: "mixed", link: "https://t.me/addemoji/mixed", score: 1.2, why: "mixed: covers 3/3 slots", coverage: 1, missing: [] },
    { name: "lines", link: "https://t.me/addemoji/lines", score: 1.1, why: "lines: covers 3/3 slots", coverage: 1, missing: [] },
    { name: "gone", link: "https://t.me/addemoji/gone", score: 0.9, why: "gone: covers 2/3 slots", coverage: 0.667, missing: ["done"] },
    { name: "solid", link: "https://t.me/addemoji/solid", score: 0.5, why: "solid: covers 1/3 slots", coverage: 0.333, missing: ["back", "cart"] },
  ],
};

test("the pick keeps its order and is narrowed by the same filters", () => {
  assert.deepEqual(names(filterPick(PICK, CATALOG, {}).rows), ["mixed", "lines", "gone", "solid"]);
  const narrowed = filterPick(PICK, CATALOG, { motion: ["static"] });
  assert.deepEqual(names(narrowed.rows), ["lines", "solid"]);
  assert.equal(narrowed.hidden, 2, "mixed is animated; gone is not in the catalog, so its tags are unknown");
});

test("a pick made for other screens or another catalog is stale", () => {
  assert.equal(pickIsStale(PICK, ["back", "cart", "done"], CATALOG), false);
  assert.equal(pickIsStale(PICK, ["back", "cart"], CATALOG), true);
  assert.equal(pickIsStale(PICK, ["back", "cart", "done"], { ...CATALOG, generated: "2026-12-01" }), true);
  assert.equal(pickIsStale(null, ["back"], CATALOG), false);
});
