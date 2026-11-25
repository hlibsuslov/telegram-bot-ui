// Port of skills/telegram-bot-ui/scripts/bot_ui/rich.py (Rich HTML screens). Keep both in step:
// tests/test_bot_ui_rich.py runs the same screens through both and compares the results.
export type Doc = Record<string, any>;

export const RICH_TEXT_MAX = 32768;
export const RICH_ROW_MAX = 8;
export const RICH_TAGS = new Set([
  "a", "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "mark", "sub", "sup", "tg-spoiler",
  "tg-reference", "tg-emoji", "img", "tg-time", "tg-math", "h1", "h2", "h3", "h4", "h5", "h6", "p", "pre",
  "footer", "hr", "ul", "ol", "li", "input", "blockquote", "cite", "aside", "br", "video", "audio",
  "tg-document", "figure", "figcaption", "tg-map", "tg-collage", "tg-slideshow", "table", "caption", "tr", "th",
  "td", "details", "summary", "tg-math-block", "tg-button", "tg-button-row",
]);
export const BUTTON_STYLES = new Set(["primary", "success", "danger", "link"]);
const ATTRS = String.raw`((?:[^>"']|"[^"]*"|'[^']*')*)`; // attributes; a quoted value may hold ">"
const BUTTON_RE = new RegExp(String.raw`<tg-button(?=[\s>/])` + ATTRS + String.raw`>([\s\S]*?)<\/tg-button\s*>`, "gi");
const TAG_RE = new RegExp(String.raw`<\/?[a-zA-Z][a-zA-Z0-9-]*` + ATTRS + ">", "g");
const ATTR_RE = /([a-zA-Z_][a-zA-Z0-9_-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/g;
const NAMED: Record<string, string> = { lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", amp: "&" };

/** Escaper for a placeholder value in Rich HTML text or a quoted attribute (either quote). */
export function richEscape(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/** The entities both engines decode: the XML five, &nbsp; and valid numeric code points; anything else stays as written. */
function decodeEntities(s: string): string {
  return s.replace(/&(#[xX][0-9a-fA-F]{1,6}|#\d{1,7}|lt|gt|quot|apos|nbsp|amp);/g, (whole: string, e: string) => {
    if (e[0] !== "#") return NAMED[e];
    const cp = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : Number(e.slice(1));
    return cp > 0 && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff) ? String.fromCodePoint(cp) : whole;
  });
}

export function unescapeHtml(s: string): string {
  return decodeEntities(s);
}

export function attrs(raw: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of raw.matchAll(ATTR_RE)) {
    const value = m[2] ?? m[3];
    out[m[1].toLowerCase()] = value !== undefined ? unescapeHtml(value) : "";
  }
  return out;
}

export function richVisibleText(text: string): string {
  return unescapeHtml(text.replace(TAG_RE, ""));
}

export function richActionIds(text: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(BUTTON_RE)) {
    const a = attrs(m[1]);
    if (a.action) out.push(a.action);
  }
  return out;
}

export function screenRichActionIds(screen: Doc): Set<string> {
  const msg = screen?.message ?? {};
  const out = new Set<string>();
  if (msg.format !== "rich.html") return out;
  const sources = [msg.text, ...Object.values<any>(msg.states ?? {}).filter((v) => v && typeof v === "object").map((v) => v.text)];
  for (const src of sources) {
    const texts = typeof src === "string" ? [src] : src && typeof src === "object" ? Object.values(src) : [];
    for (const t of texts) if (typeof t === "string") richActionIds(t).forEach((id) => out.add(id));
  }
  return out;
}

export interface RichButton { actionId: string | null; text: string; type: string; callbackData?: string; url?: string; style?: string }

export function compileRichButtons(text: string, actions: Doc, labelOf: (act: Doc, aid: string) => string,
  callbackOf: (aid: string, act: Doc) => string): [string, RichButton[], Doc[]] {
  const buttons: RichButton[] = [];
  const diags: Doc[] = [];
  const html = text.replace(BUTTON_RE, (whole: string, rawAttrs: string, inner: string) => {
    const a = attrs(rawAttrs);
    const aid = a.action;
    if (!aid) {
      const btn: RichButton = { actionId: null, text: richVisibleText(inner).trim(), type: a.type ?? "" };
      if (a.type === "callback_data") btn.callbackData = a.data ?? "";
      else if ("url" in a) btn.url = a.url;
      if (BUTTON_STYLES.has(a.style)) btn.style = a.style;
      buttons.push(btn);
      return whole;
    }
    const act = actions[aid];
    if (!act || typeof act !== "object" || act.hidden) {
      diags.push({ code: "RICH_BUTTON_ACTION_MISSING", severity: "warning", pointer: "/message/text",
        message: `<tg-button action="${aid}"> has no visible action; it is left out` });
      return "";
    }
    const content = richVisibleText(inner).trim() ? inner : richEscape(labelOf(act, aid));
    const btn: RichButton = { actionId: aid, text: richVisibleText(content).trim(), type: act.type };
    let style: string | null = BUTTON_STYLES.has(act.style) ? act.style : null;
    let tag: string;
    if (act.type === "url") {
      const url: string = act.url ?? "";
      btn.url = url;
      tag = `<tg-button type="url" url="${richEscape(url)}"`;
      if (style === "link") style = null;
    } else {
      btn.callbackData = callbackOf(aid, act);
      tag = `<tg-button type="callback_data" data="${richEscape(btn.callbackData)}"`;
    }
    if (style) {
      btn.style = style;
      tag += ` style="${style}"`;
    }
    buttons.push(btn);
    return `${tag}>${content}</tg-button>`;
  });
  return [html, buttons, diags];
}

export interface RichNode { tag: string; text?: string; attrs?: Record<string, string>; children?: RichNode[] }
const VOID = new Set(["br", "hr", "img", "input", "tg-map"]);
const TOKEN_RE = new RegExp(String.raw`<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^>"'/]|"[^"]*"|'[^']*'|\/(?!>))*)(\/?)>|([^<]+)|(<)`, "g");

/** Rich HTML -> a small tree of allowed tags for the preview; anything else stays text, so bot text
 * never reaches the page as markup. */
export function richHtmlToSafe(text: string): RichNode[] {
  type Parent = RichNode & { children: RichNode[] };
  const root: Parent = { tag: "root", children: [] };
  const stack: Parent[] = [root];
  for (const m of text.matchAll(TOKEN_RE)) {
    const top = stack[stack.length - 1];
    if (m[5] !== undefined || m[6] !== undefined) {
      top.children.push({ tag: "#text", text: unescapeHtml(m[5] ?? "<") });
      continue;
    }
    const tag = m[2].toLowerCase();
    if (!RICH_TAGS.has(tag) && tag !== "tg-thinking") { top.children.push({ tag: "#text", text: m[0] }); continue; }
    if (m[1]) {
      const idx = stack.map((n) => n.tag).lastIndexOf(tag);
      if (idx > 0) stack.length = idx;
      continue;
    }
    const node: Parent = { tag, attrs: attrs(m[3]), children: [] };
    top.children.push(node);
    if (!m[4] && !VOID.has(tag)) stack.push(node);
  }
  return root.children;
}

const BUTTON_TYPES = new Set(["url", "callback_data", "web_app", "login_url", "switch_inline_query",
  "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", "copy_text", "disabled"]);
const ROW_RE = new RegExp(String.raw`<tg-button-row(?=[\s>/])` + ATTRS + String.raw`>([\s\S]*?)<\/tg-button-row\s*>`, "gi");
const NAME_RE = new RegExp(String.raw`<\/?([a-zA-Z][a-zA-Z0-9-]*)` + ATTRS + ">", "g");

/** Port of rich.check(): [code, severity, message] for one Rich HTML text (tests/test_bot_ui_rich.py compares both). */
export type RichSeverity = "error" | "warning";
export function richCheck(text: string, draft = false): [string, RichSeverity, string][] {
  const out: [string, RichSeverity, string][] = [];
  for (const m of text.matchAll(NAME_RE)) {
    const t = m[1].toLowerCase();
    if (!RICH_TAGS.has(t) && !(draft && t === "tg-thinking")) out.push(["RICH_TAG_UNSUPPORTED", "warning", `<${t}> is not in Telegram's Rich HTML tag list`]);
  }
  for (const row of text.matchAll(ROW_RE)) {
    const n = [...row[2].matchAll(BUTTON_RE)].length;
    if (n < 1 || n > RICH_ROW_MAX) out.push(["RICH_BUTTON_ROW_SIZE", "error", `a <tg-button-row> holds 1-${RICH_ROW_MAX} buttons, found ${n}`]);
  }
  for (const m of text.matchAll(BUTTON_RE)) {
    const a = attrs(m[1]);
    if (a.action) continue;
    const t = a.type;
    if (!BUTTON_TYPES.has(t)) out.push(["RICH_BUTTON_TYPE", "error", `<tg-button> needs action="<id>" or a type from ${JSON.stringify([...BUTTON_TYPES].sort())}`]);
    else if (t === "callback_data" && !(new TextEncoder().encode(a.data ?? "").length >= 1 && new TextEncoder().encode(a.data ?? "").length <= 64)) out.push(["RICH_BUTTON_DATA", "error", "callback data must be 1-64 bytes"]);
    else if ((t === "url" || t === "web_app" || t === "login_url") && !a.url) out.push(["RICH_BUTTON_URL", "error", `a ${t} button needs url="..."`]);
    if (a.style && !BUTTON_STYLES.has(a.style)) out.push(["RICH_BUTTON_STYLE", "error", `style must be one of ${JSON.stringify([...BUTTON_STYLES].sort())}`]);
    else if (a.style === "link" && t !== "callback_data") out.push(["RICH_BUTTON_STYLE", "error", 'style "link" is allowed only for callback buttons']);
    if (!richVisibleText(m[2]).trim()) out.push(["RICH_BUTTON_TEXT", "error", "a button needs visible text"]);
  }
  const n = [...richVisibleText(text)].length;
  if (n > RICH_TEXT_MAX) out.push(["TEXT_TOO_LONG", "error", `${n} characters > ${RICH_TEXT_MAX} (Rich Message Limits)`]);
  return out;
}
