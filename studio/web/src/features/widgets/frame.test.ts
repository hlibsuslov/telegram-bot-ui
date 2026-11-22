// node --test: the preview frame follows the chat theme's colour scheme, never the OS one.
import assert from "node:assert/strict";
import { test } from "node:test";
import { composeDoc, frameScheme, type Runtime } from "./frame.ts";

const rt: Runtime = {
  mock: "/*mock*/", css: ":where(html){color-scheme:var(--tg-color-scheme)}", answers: {},
  themes: {
    light: { bg_color: "#ffffff", text_color: "#000000", button_color: "#2481cc", button_text_color: "#ffffff", _scheme: "light", _chat: "#c9d9b8" },
    dark: { bg_color: "#212d3b", text_color: "#ffffff", button_color: "#50a8eb", button_text_color: "#ffffff", _scheme: "dark", _chat: "#0e1621" },
  },
};
const widget = "<style>:root{color-scheme:light dark;--x:light-dark(#000,#fff)}</style><div class=k>hi</div>";

for (const theme of ["light", "dark"] as const) {
  test(`${theme} chat theme forces color-scheme ${theme} and a transparent canvas`, () => {
    const doc = composeDoc(rt, widget, { session: "s1", theme, lang: "en", meta: {}, state: "default", offline: false });
    assert.equal(frameScheme(rt.themes[theme]), theme);
    assert.ok(doc.includes(`<meta name="color-scheme" content="${theme}">`));
    assert.ok(doc.includes(`:root{color-scheme:${theme} !important}`));
    assert.ok(doc.includes("background:transparent !important"));
    assert.ok(doc.includes(`--tg-theme-text-color:${rt.themes[theme].text_color}`));
    assert.ok(doc.indexOf("!important}") < doc.indexOf("<body>"), "the override sits in the head");
  });
}

test("outgoing or unknown themes fall back to light", () => {
  assert.equal(frameScheme({ _scheme: "light" }), "light");
  assert.equal(frameScheme(undefined), "light");
});
