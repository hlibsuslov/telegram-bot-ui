// Composes the widget preview document the way skills/telegram-bot-ui/scripts/preview_widget.py
// does (default CSS, window.__cfg, the mock runtime, the built widget) for the sandboxed
// /preview-frame.html, which accepts it once from its parent.
import type { Doc } from "@/core/render.ts";

export interface Runtime { mock: string; css: string; themes: Record<string, Doc>; answers: Record<string, Record<string, { pushes?: { field: string; text: string }[]; result?: string | null }>> }

const FS = 15;

/** Shift demo timestamps so "fresh" fields read as relative to now (preview_widget.py fresh()). */
export function freshen(state: Doc | undefined, keys: string[] | undefined, base: number | undefined): Doc | undefined {
  if (!state) return state;
  const s = structuredClone(state);
  const now = Math.floor(Date.now() / 1000);
  for (const k of keys ?? []) if (typeof s[k] === "number" && base) s[k] = now - (base - s[k]);
  return s;
}

export function composeDoc(rt: Runtime, html: string, o: { session: string; theme: string; lang: string; meta: Doc; state: string; offline: boolean }): string {
  const th = rt.themes[o.theme] ?? rt.themes.light ?? {};
  let vars = `--tg-color-scheme:${th._scheme};--tg-text-font-size:${FS}px;--tg-text-line-height:1.35;--tg-text-padding:8px 12px;` +
    `--tg-button-bg:${th.button_color};--tg-button-text:${th.button_text_color};--tg-button-radius:8px;--tg-button-font:500 ${FS}px system-ui;` +
    `--tg-button-padding:8px 12px;--tg-button-height:36px;--tg-button-pressed-opacity:.7;--tg-button-disabled-opacity:.5;`;
  for (const [k, v] of Object.entries(th)) if (!k.startsWith("_")) vars += `--tg-theme-${k.replace(/_/g, "-")}:${v};`;
  vars += "--tg-content-safe-area-inset-bottom:0px;--tg-content-safe-area-inset-top:0px;--tg-content-safe-area-inset-left:0px;--tg-content-safe-area-inset-right:0px;" +
    "--tg-content-safe-area-corner-right:0px;--tg-content-safe-area-corner-left:0px;";
  const st: Doc = o.meta.states?.[o.state] ?? {};
  const txt = (v: any) => (v == null ? null : JSON.stringify(v));
  const theme = Object.fromEntries(Object.entries(th).filter(([k]) => !k.startsWith("_")));
  const cfg = {
    f: o.session, scheme: th._scheme, theme, lang: o.lang, dir: "ltr", place: "private", shared: !!o.meta.send?.is_shared,
    bot: o.offline ? "offline" : "answer", band: 0, corner: 0,
    chatData: txt(freshen(st.chatData, o.meta.fresh, o.meta.now)), publicData: txt(freshen(st.publicData, o.meta.fresh, o.meta.now)),
  };
  const cfgJson = JSON.stringify(cfg).replace(/</g, "\\u003c");
  const mock = rt.mock.replace(/<\/script/gi, "<\\/script");
  return `<!doctype html><html dir="ltr" style="${vars.replace(/"/g, "&quot;")}"><head><meta charset="utf-8"><style>${rt.css}</style>` +
    `<script>window.__cfg=${cfgJson};${mock}</script></head><body>${html}</body></html>`;
}
