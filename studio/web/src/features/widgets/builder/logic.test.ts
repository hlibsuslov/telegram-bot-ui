// node --test: field applicability and the preset/custom/palette rules of the visual builder,
// on a small schema shaped like the one studio/bot_ui/builder.py serves.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applicableFields, applies, blockOn, changeStyle, choosePreset, defaultStyle, effectiveColors, effectiveCustom, getAt, keyOfPointer, localIssues,
  previewStates, restoreMyDesign, setAt, setColor, shortId, switchType, type Style,
} from "./logic.ts";
import type { BField, BSchema } from "./schema.ts";

const tg = { block: { fill: false, radius: 0, border: 0, padding: 0, gap: 8, align: "start" }, text: { title: "m", body: "normal" },
  button: { look: "native", radius: 8, height: "normal", width: "full", align: "start" }, image: { full: true, aspect: "auto", width: 96, align: "start", radius: 8 }, animation: "none" };
const SCHEMA: BSchema = {
  version: 1,
  types: {
    message: { title: "Message", summary: "", sections: [{ id: "c", title: "", fields: [{ key: "title", label: "Title", type: "text", localized: true, max: 80 },
      { key: "button.action", label: "When pressed", type: "action" }] }], states: [{ id: "default", title: "" }], defaults: { title: { en: "Hi" } } },
    product: { title: "Product", summary: "", sections: [{ id: "c", title: "", fields: [
      { key: "badge", label: "Badge", type: "text", max: 16, toggle: "show.badge" },
      { key: "badgeCorner", label: "Corner", type: "choice", toggle: "show.badge", options: [{ value: "left", label: "L" }, { value: "right", label: "R" }] }] }],
    states: [{ id: "default", title: "" }, { id: "tapped", title: "" }], defaults: { price: "€14.90" } },
    promo: { title: "Promo", summary: "", sections: [{ id: "c", title: "", fields: [
      { key: "reveal", label: "Reveal", type: "choice", options: [{ value: "now", label: "Now" }, { value: "tap", label: "Tap" }] },
      { key: "code", label: "Code", type: "text", max: 24 },
      { key: "closedLabel", label: "Closed", type: "text", max: 24, when: { key: "reveal", eq: "tap" } }] }],
    states: [{ id: "closed", title: "" }, { id: "revealed", title: "" }, { id: "copied", title: "" }], defaults: {} },
    quiz: { title: "Quiz", summary: "", sections: [], states: ["q1", "q2", "q3", "q4", "q5", "result"].map((id) => ({ id, title: id })), defaults: {} },
  },
  style: {
    sections: [],
    presets: [
      { id: "telegram", title: "Telegram", values: { ...tg, colors: { light: {}, dark: {} } } },
      { id: "card", title: "Card", values: { ...tg, block: { ...tg.block, fill: true, radius: 16, border: 1, padding: 14 }, colors: { light: { bg: "#ffffff" }, dark: { bg: "#1c1c1e" } } } },
    ],
    colorSlots: { common: [{ key: "bg", label: "Background" }] },
  },
};

test("`when` hides fields that do not apply, `toggle` keeps them", () => {
  const promo = SCHEMA.types.promo.sections[0].fields;
  const keys = (c: Record<string, unknown>) => applicableFields(promo, c).map((f) => f.key);
  assert.deepEqual(keys({ reveal: "now" }), ["reveal", "code"]);
  assert.deepEqual(keys({ reveal: "tap" }), ["reveal", "code", "closedLabel"], "the code stays: on tap it is what the bot answers");
  const badge = SCHEMA.types.product.sections[0].fields[0] as BField;
  assert.equal(blockOn(badge, { show: { badge: false }, badge: "NEW" }), false);
  assert.equal(blockOn(badge, {}), true);
  assert.equal(applies({ key: "x", label: "x", type: "text", when: { key: "m", in: ["a", "b"] } }, { m: "b" }), true);
  assert.equal(applies({ key: "x", label: "x", type: "text", when: { key: "image.full", eq: false } }, {}), true, "a missing boolean counts as false");
});

test("dot paths read and write without mutating", () => {
  const a = { block: { radius: 4 } };
  const b = setAt(a, "block.padding", 12);
  assert.deepEqual(a, { block: { radius: 4 } });
  assert.equal(getAt(b, "block.padding"), 12);
  assert.deepEqual(setAt(b, "block.radius", undefined), { block: { padding: 12 } });
});

const mine: Style = { preset: null, custom: { block: { radius: 16, padding: 14 } }, palette: "per-theme", colors: { light: { bg: "#ff0000" }, dark: {} } };

test("my design is custom over the Telegram preset, like builder.effective_style", () => {
  const v = effectiveCustom(mine, SCHEMA);
  assert.equal(v.block.radius, 16);
  assert.equal(v.block.gap, 8, "unset values come from the Telegram preset");
  assert.equal(v.button.look, "native");
  assert.equal(effectiveCustom({ ...mine, custom: { block: { radius: null } } }, SCHEMA).block.radius, 0, "null keeps the base");
  assert.equal(defaultStyle(SCHEMA).preset, "telegram");
});

test("choosing a preset keeps my design; restore brings it back", () => {
  const card = choosePreset(mine, "card");
  assert.equal(effectiveCustom(card, SCHEMA).block.radius, 16);
  assert.equal(effectiveCustom(card, SCHEMA).block.fill, true);
  assert.equal(effectiveColors(card, SCHEMA, "dark").bg, "#1c1c1e");
  assert.deepEqual(card.custom, mine.custom);
  const back = restoreMyDesign(card);
  assert.equal(back.preset, null);
  assert.equal(effectiveCustom(back, SCHEMA).block.fill, false);
  assert.equal(effectiveColors(back, SCHEMA, "light").bg, "#ff0000");
});

test("editing while a preset is active copies the preset into my design first", () => {
  const edited = changeStyle(choosePreset(mine, "card"), SCHEMA, "block.padding", 20);
  assert.equal(edited.preset, null);
  assert.equal(edited.custom.block.radius, 16, "the preset's corner is kept");
  assert.equal(edited.custom.block.padding, 20, "the change is applied");
  assert.equal(edited.colors.dark.bg, "#1c1c1e", "the preset's colours are copied too");
});

test("shared palette edits and reads the light slots for both themes", () => {
  const s = setColor({ ...mine, palette: "shared" }, SCHEMA, "dark", "text", "#00ff00");
  assert.equal(s.colors.light.text, "#00ff00");
  assert.equal(effectiveColors(s, SCHEMA, "dark").text, "#00ff00");
  assert.equal(setColor(mine, SCHEMA, "dark", "bg", null).colors.dark.bg, null, "null = inherit Telegram");
});

test("switching type keeps a copy of the previous content", () => {
  const p = switchType({ type: "message", version: 1, content: { title: { en: "Mine" } } }, "product", SCHEMA);
  assert.equal(p.content.price, "€14.90");
  assert.deepEqual(p.stash.message, { title: { en: "Mine" } });
  assert.deepEqual(switchType(p, "message", SCHEMA).content, { title: { en: "Mine" } });
});

test("quiz states follow the number of questions; new ids stay short", () => {
  const two = { type: "quiz", content: { questions: [{ id: "q1", answers: [{ id: "a1" }, { id: "a2" }] }, { id: "q2", answers: [{ id: "a3" }] }] } };
  assert.deepEqual(previewStates(SCHEMA.types.quiz.states, two).map((s) => s.id), ["q1", "q2", "result"]);
  assert.equal(shortId("a", two.content), "a4");
  assert.equal(shortId("q", two.content), "q3");
});

test("local checks give field pointers", () => {
  const issues = localIssues({ type: "message", content: { title: { en: "x".repeat(81) }, button: { action: { kind: "request", data: "я".repeat(40), done: { ru: "д".repeat(70) } } } } }, SCHEMA);
  assert.deepEqual(issues.map((i) => i.pointer).sort(), ["/content/button/action/data", "/content/button/action/done/ru", "/content/title/en"]);
  assert.equal(keyOfPointer("/builder/content/button/action/data"), "button.action.data");
});
