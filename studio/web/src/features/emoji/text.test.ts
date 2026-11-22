import assert from "node:assert/strict";
import { test } from "node:test";
import { dropLeadingEmoji, insertEmoji, plainToHtml } from "./text.ts";

const TAG = '<tg-emoji emoji-id="5368324170671202286">☕</tg-emoji>';

test("insert at the start, the cursor and the end, with spaces only where needed", () => {
  const text = "<b>Coffee</b> is ready";
  assert.equal(insertEmoji(text, { start: 5, end: 5 }, "start", "5368324170671202286", "☕").text, `${TAG} <b>Coffee</b> is ready`);
  assert.equal(insertEmoji(text, { start: 0, end: 0 }, "end", "5368324170671202286", "☕").text, `<b>Coffee</b> is ready ${TAG}`);
  const mid = insertEmoji(text, { start: 13, end: 14 }, "cursor", "5368324170671202286", "☕"); // replaces the selected space
  assert.equal(mid.text, `<b>Coffee</b> ${TAG} is ready`);
  assert.equal(mid.caret, `<b>Coffee</b> ${TAG} `.length);
  assert.equal(insertEmoji("", { start: 0, end: 0 }, "end", "1", "").text, '<tg-emoji emoji-id="1">⭐</tg-emoji>');
});

test("plain text is escaped around the emoji and the message becomes HTML", () => {
  const r = insertEmoji("Fish & chips <hot>", { start: 0, end: 0 }, "end", "5368324170671202286", "☕", true);
  assert.equal(r.text, `Fish &amp; chips &lt;hot&gt; ${TAG}`);
  const message: Record<string, any> = { format: "regular.plain", text: { en: "A & B", ru: "А < Б" }, states: { loading: { text: { en: "1 > 0" } } } };
  plainToHtml(message);
  assert.deepEqual(message, { format: "regular.html", text: { en: "A &amp; B", ru: "А &lt; Б" }, states: { loading: { text: { en: "1 &gt; 0" } } } });
});

test("a label that gets an icon loses the emoji it started with", () => {
  assert.equal(dropLeadingEmoji("🛒 Cart"), "Cart");
  assert.equal(dropLeadingEmoji("⚙️ Settings"), "Settings");
  assert.equal(dropLeadingEmoji("👍🏽 Thanks"), "Thanks");
  assert.equal(dropLeadingEmoji("Cart 🛒"), "Cart 🛒");
  assert.equal(dropLeadingEmoji("12 items"), "12 items");
});
