// Pure text helpers for premium emoji in screen texts and button labels (tested in text.test.ts).
export const tgEmojiHtml = (id: string, fallback: string) => `<tg-emoji emoji-id="${id}">${fallback || "⭐"}</tg-emoji>`;

export type Placement = "start" | "cursor" | "end";

export const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Insert <tg-emoji> at the start, the cursor (selection replaced) or the end, with a space on
 * each side where the neighbouring text has none. `escape`: the text was plain and becomes HTML. */
export function insertEmoji(current: string, sel: { start: number; end: number }, where: Placement, id: string, fallback: string,
  escape = false): { text: string; caret: number } {
  const at = where === "start" ? 0 : where === "end" ? current.length : sel.start;
  const end = where === "cursor" ? sel.end : at;
  const wrap = escape ? escapeHtml : (s: string) => s;
  const before = wrap(current.slice(0, at));
  const after = wrap(current.slice(end));
  const tag = (before && !/\s$/.test(before) ? " " : "") + tgEmojiHtml(id, fallback) + (after && !/^\s/.test(after) ? " " : "");
  return { text: before + tag + after, caret: before.length + tag.length };
}

type Doc = Record<string, any>;

/** A plain-text message as regular.html: every text and state text escaped, format switched. */
export function plainToHtml(message: Doc): void {
  const esc = (t: any) => (typeof t === "string" ? escapeHtml(t) : t && typeof t === "object"
    ? Object.fromEntries(Object.entries(t).map(([k, v]) => [k, typeof v === "string" ? escapeHtml(v) : v])) : t);
  message.text = esc(message.text);
  for (const st of Object.values<Doc>(message.states ?? {})) if (st && typeof st === "object") st.text = esc(st.text);
  message.format = "regular.html";
}

/** A button label without the emoji it starts with ("🛒 Cart" -> "Cart"): the icon replaces it. */
export const dropLeadingEmoji = (s: string) =>
  s.replace(/^\p{Extended_Pictographic}(?:️|‍\p{Extended_Pictographic}|[\u{1F3FB}-\u{1F3FF}])*\s*/u, "");
