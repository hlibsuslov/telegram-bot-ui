// Port of skills/telegram-bot-ui/scripts/bot_ui/render.py. Keep both in step: tests/test_bot_ui_parity.py runs the
// same scenario fixtures through both engines and compares the results byte for byte.
export type Json = null | boolean | number | string | Json[] | { [k: string]: Json };
export type Doc = Record<string, any>;

export const FORMATS: Record<string, string | null> = {
  "regular.plain": null,
  "regular.html": "HTML",
  "regular.markdownv2": "MarkdownV2",
};
export const EDITABLE_FORMATS = new Set(["regular.plain", "regular.html"]);
export const CALLBACK_MAX = 64;
export const CAPTION_MAX = 1024;
export const MEDIA_TYPES: Record<string, string> = {
  photo: "sendPhoto", video: "sendVideo", animation: "sendAnimation", audio: "sendAudio",
  voice: "sendVoice", video_note: "sendVideoNote", sticker: "sendSticker",
};
export const CAPTION_MEDIA = new Set(["photo", "video", "animation", "audio", "voice"]);
export const EDITABLE_MEDIA = new Set(["photo", "video", "animation", "audio"]);
export const SPOILER_MEDIA = new Set(["photo", "video", "animation"]);
const PLACEHOLDER = /\{\{|\}\}|\{([a-z0-9_.-]+)\}/g;
const MD2 = /([_*\[\]()~`>#+\-=|{}.!\\])/g;

export function localized(value: any, locale: string, def: string): string | null {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return null;
  if (typeof value[locale] === "string") return value[locale];
  return typeof value[def] === "string" ? value[def] : null;
}

export function escape(value: string, fmt: string): string {
  if (fmt === "regular.html") return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (fmt === "regular.markdownv2") return value.replace(MD2, "\\$1");
  return value;
}

export function fill(text: string, values: Record<string, any>, fmt: string): [string, string[]] {
  const missing: string[] = [];
  const out = text.replace(PLACEHOLDER, (m, name) => {
    if (m === "{{") return "{";
    if (m === "}}") return "}";
    if (!(name in values) || values[name] === null || values[name] === undefined) {
      missing.push(name);
      return m;
    }
    return escape(String(values[name]), fmt);
  });
  return [out, missing];
}

export function placeholders(text: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(PLACEHOLDER)) if (m[1]) out.push(m[1]);
  return out;
}

export function utf8Len(s: string): number {
  return new TextEncoder().encode(s).length;
}

export function callbackData(screenId: string, actionId: string, action?: Doc): string {
  if (action && typeof action.callbackData === "string") return action.callbackData;
  const plain = `${screenId}:${actionId}`;
  if (utf8Len(plain) <= CALLBACK_MAX) return plain;
  return "h:" + plain; // hashed form is computed by the Python core; the client never needs it for display
}

export function mediaOf(screen: Doc): Doc | null {
  const m = screen?.message?.media;
  return m && typeof m === "object" && m.type in MEDIA_TYPES ? m : null;
}

export function resolveFile(media: Doc, values: Doc): [string | null, string] {
  const f = media.file ?? {};
  if (typeof f.fileId === "string") return [f.fileId, "fileId"];
  if (typeof f.url === "string") return [f.url, "url"];
  if (typeof f.field === "string") {
    const v = values[f.field];
    return [v === undefined || v === null || v === "" ? null : String(v), "field"];
  }
  return [null, "missing"];
}

export function keyboardRows(screen: Doc): string[][] {
  const rows = screen?.keyboard?.rows ?? [];
  return rows.filter((r: any) => Array.isArray(r)).map((r: any[]) => r.filter((a) => typeof a === "string"));
}

export interface Button { actionId: string; text: string; type: string; url?: string; callbackData?: string; style?: string; icon?: string }
export interface Media { type: string; file: string | null; source: string; spoiler: boolean; emoji: string | null }
export interface Logical {
  screenId: string; messageId: string; locale: string; state: string | null; format: string; text: string;
  parseMode: string | null; keyboard: { type: string; rows: Button[][]; placeholder: string | null };
  media: Media | null; widget: string | null; diagnostics: Doc[];
}

export function renderScreen(project: Doc, screen: Doc, opts: { locale?: string | null; state?: string | null; values?: Doc } = {}): Logical {
  const def = project.defaultLocale ?? "en";
  const locale = opts.locale || def;
  const values = opts.values ?? {};
  const state = opts.state ?? null;
  const msg = screen.message ?? {};
  const fmt = msg.format ?? "regular.plain";
  let source = msg.text;
  if (state && msg.states && typeof msg.states[state] === "object" && msg.states[state]) {
    source = "text" in msg.states[state] ? msg.states[state].text : source;
  }
  const raw = localized(source, locale, def) ?? "";
  const [text, missing] = fill(raw, values, fmt);
  const diagnostics: Doc[] = missing.map((name) => ({
    code: "PLACEHOLDER_VALUE_MISSING", severity: "warning", pointer: "/message/text", message: `no value for {${name}} in this run`,
  }));
  if (!(fmt in FORMATS)) {
    diagnostics.push({ code: "FORMAT_NOT_RENDERED", severity: "warning", pointer: "/message/format",
      message: `${fmt} is kept as is but not rendered by this version; the fallback text is used` });
  }
  let media: Media | null = null;
  const m = mediaOf(screen);
  if (m) {
    const [value, kind] = resolveFile(m, values);
    if (value === null) diagnostics.push({ code: "MEDIA_VALUE_MISSING", severity: "warning", pointer: "/message/media/file", message: `no ${m.type} file for this run (${kind})` });
    media = { type: m.type, file: value, source: kind, spoiler: !!m.spoiler && SPOILER_MEDIA.has(m.type), emoji: typeof m.emoji === "string" ? m.emoji : null };
  }
  const kb = screen.keyboard ?? {};
  const ktype = screen.keyboard ? (kb.type ?? "none") : "none";
  const actions = screen.actions ?? {};
  const rows: Button[][] = [];
  for (const row of keyboardRows(screen)) {
    const outRow: Button[] = [];
    for (const aid of row) {
      const act = actions[aid];
      if (!act || typeof act !== "object" || act.hidden) continue;
      const [label] = fill(localized(act.label, locale, def) ?? aid, values, "regular.plain");
      const btn: Button = { actionId: aid, text: label, type: act.type };
      if (ktype === "inline") {
        if (act.type === "url") btn.url = act.url;
        else btn.callbackData = callbackData(screen.id, aid, act);
        if (["primary", "success", "danger"].includes(act.style)) btn.style = act.style;
      }
      const icon = act.icon && typeof act.icon === "object" ? act.icon.customEmojiId : null;
      if (typeof icon === "string" && (ktype === "inline" || ktype === "reply")) btn.icon = icon;
      outRow.push(btn);
    }
    if (outRow.length) rows.push(outRow);
  }
  return {
    screenId: screen.id, messageId: msg.id ?? "main", locale, state, format: fmt, text,
    parseMode: FORMATS[fmt] ?? null,
    keyboard: { type: ktype, rows, placeholder: localized(kb.placeholder, locale, def) },
    media, widget: screen.widget?.ref ?? null, diagnostics,
  };
}

/** Telegram regular HTML for the preview: only the allowed tags survive, everything else is text. */
export function telegramHtmlToSafe(text: string, fmt: string): { tag: string; text?: string; children?: any[]; href?: string; emojiId?: string }[] {
  // Produces a tiny tree instead of an HTML string, so the Studio never injects bot text as page markup.
  if (fmt !== "regular.html") return [{ tag: "#text", text }];
  const allowed = new Set(["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre", "blockquote", "tg-emoji", "tg-time"]);
  const root: any = { tag: "root", children: [] };
  const stack: any[] = [root];
  const re = /<(\/?)([a-zA-Z-]+)([^>]*)>|([^<]+)|(<)/g;
  for (const m of text.matchAll(re)) {
    const top = stack[stack.length - 1];
    if (m[4] !== undefined || m[5] !== undefined) {
      top.children.push({ tag: "#text", text: decode(m[4] ?? "<") });
      continue;
    }
    const tag = m[2].toLowerCase();
    if (!allowed.has(tag)) { top.children.push({ tag: "#text", text: m[0] }); continue; }
    if (m[1]) {
      const idx = stack.map((n) => n.tag).lastIndexOf(tag);
      if (idx > 0) stack.length = idx;
      continue;
    }
    const node: any = { tag, children: [] };
    const href = /href="([^"]*)"/.exec(m[3]);
    if (tag === "a" && href) node.href = decode(href[1]);
    const eid = tag === "tg-emoji" ? /emoji-id="(\d{1,20})"/.exec(m[3]) : null;
    if (eid) node.emojiId = eid[1];
    if (tag === "span" && !/tg-spoiler/.test(m[3])) node.tag = "span";
    else if (tag === "span") node.tag = "tg-spoiler";
    top.children.push(node);
    stack.push(node);
  }
  return root.children;
}

function decode(s: string): string {
  return s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d)).replace(/&amp;/g, "&");
}
