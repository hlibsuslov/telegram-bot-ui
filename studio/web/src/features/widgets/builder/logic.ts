// Pure rules of the visual builder (no DOM, node-testable): dot paths, field applicability
// (`when` and block `toggle`), preset/custom merge, palettes, type switching with a kept copy,
// and the local form checks used until /api/widget/builder-validate answers.
import type { BField, BSchema } from "./schema.ts";

type Doc = Record<string, any>;
export interface Issue { pointer: string; code: string; message: string }

export const clone = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

export function getAt(obj: any, path: string): any {
  let cur = obj;
  for (const k of path.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[k];
  }
  return cur;
}

/** A copy of obj with path set (undefined removes the key). */
export function setAt<T extends Doc>(obj: T, path: string, value: any): T {
  const out: any = clone(obj ?? {});
  const keys = path.split(".");
  let cur = out;
  for (const k of keys.slice(0, -1)) {
    if (cur[k] == null || typeof cur[k] !== "object") cur[k] = {};
    cur = cur[k];
  }
  const last = keys[keys.length - 1];
  if (value === undefined) delete cur[last]; else cur[last] = value;
  return out;
}

/** `when` decides whether a field applies at all in the current content. */
export function applies(field: BField, content: Doc): boolean {
  if (!field.when) return true;
  const v = getAt(content, field.when.key);
  if ("eq" in field.when) return v === field.when.eq || (field.when.eq === false && v === undefined);
  if (field.when.in) return field.when.in.includes(v);
  return !!v;
}

/** A block `toggle` hides the rendered block but keeps its values; missing means on. */
export function blockOn(field: BField, content: Doc): boolean {
  return !field.toggle || getAt(content, field.toggle) !== false;
}

export function applicableFields(fields: BField[], content: Doc): BField[] {
  return fields.filter((f) => applies(f, content));
}

// ------------------------------------------------------------------ style
export interface Style { preset: string | null; custom: Doc; palette: "per-theme" | "shared"; colors: { light: Doc; dark: Doc } }

export function presetValues(schema: BSchema, id: string | null): Doc | null {
  return id ? schema.style.presets.find((p) => p.id === id)?.values ?? null : null;
}

/** What the widget looks like now: the preset's values while one is active, else `custom`. */
const BASE_PRESET = "telegram";
const STYLE_SECTIONS = ["block", "text", "button", "image"];

/** What the widget looks like now, like builder.effective_style: an active preset wins; else the
 * author's `custom` over the Telegram preset, section by section (null values keep the base). */
export function effectiveCustom(style: Style, schema: BSchema): Doc {
  const p = presetValues(schema, style.preset);
  if (p) {
    const { colors: _c, ...rest } = p;
    return clone(rest);
  }
  const { colors: _b, ...base } = clone(presetValues(schema, BASE_PRESET) ?? schema.style.presets[0]?.values ?? {});
  const custom = style.custom ?? {};
  for (const sec of STYLE_SECTIONS) {
    if (custom[sec] && typeof custom[sec] === "object") {
      base[sec] = { ...(base[sec] ?? {}), ...Object.fromEntries(Object.entries(custom[sec]).filter(([, v]) => v !== null && v !== undefined)) };
    }
  }
  if (custom.animation != null) base.animation = custom.animation;
  return base;
}

/** Colours shown for a theme: the preset's while one is active, else the user's (shared uses light). */
export function effectiveColors(style: Style, schema: BSchema, theme: "light" | "dark"): Doc {
  const p = presetValues(schema, style.preset);
  if (p?.colors) return p.colors[theme] ?? {};
  const src = style.palette === "shared" ? style.colors?.light : style.colors?.[theme];
  return src ?? {};
}

/** Leaving a preset by editing: copy its values (and colours) into the user's design first. */
function detach(style: Style, schema: BSchema): Style {
  const p = presetValues(schema, style.preset);
  if (!p) return style;
  const { colors, ...rest } = p;
  return {
    ...style, preset: null, custom: clone(rest),
    colors: colors ? { light: { ...clone(colors.light ?? {}) }, dark: { ...clone(colors.dark ?? {}) } } : style.colors,
  };
}

export function changeStyle(style: Style, schema: BSchema, path: string, value: any): Style {
  const s = detach(style, schema);
  return { ...s, custom: setAt(s.custom ?? {}, path, value) };
}

export function setColor(style: Style, schema: BSchema, theme: "light" | "dark", slot: string, value: string | null): Style {
  const s = detach(style, schema);
  const t = s.palette === "shared" ? "light" : theme;
  return { ...s, colors: { ...s.colors, [t]: { ...(s.colors?.[t] ?? {}), [slot]: value } } };
}

export function resetColors(style: Style, schema: BSchema, theme: "light" | "dark" | "all"): Style {
  const s = detach(style, schema);
  if (theme === "all") return { ...s, colors: { light: {}, dark: {} } };
  const t = s.palette === "shared" ? "light" : theme;
  return { ...s, colors: { ...s.colors, [t]: {} } };
}

/** Choosing a preset never touches `custom`, so restoring my design is just `preset: null`. */
export const choosePreset = (style: Style, id: string): Style => ({ ...style, preset: id });
export const restoreMyDesign = (style: Style): Style => ({ ...style, preset: null });

export function defaultStyle(schema: BSchema): Style {
  const id = presetValues(schema, BASE_PRESET) ? BASE_PRESET : schema.style.presets[0]?.id ?? null;
  const { colors: _c, ...custom } = clone(presetValues(schema, id) ?? {});
  return { preset: id, custom, palette: "per-theme", colors: { light: {}, dark: {} } };
}

/** Quiz preview states follow the number of questions (the schema lists q1-q5). */
export function previewStates(states: { id: string; title: string }[], builder: Doc): { id: string; title: string }[] {
  if (builder?.type !== "quiz") return states;
  const n = Array.isArray(builder.content?.questions) ? builder.content.questions.length : 0;
  return states.filter((st) => !/^q\d+$/.test(st.id) || Number(st.id.slice(1)) <= n);
}

/** The next short id ("a7") not used anywhere in the list tree: request data must fit 64 bytes. */
export function shortId(prefix: string, root: any): string {
  const used = new Set<string>();
  const walk = (v: any) => {
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") { if (typeof v.id === "string") used.add(v.id); Object.values(v).forEach(walk); }
  };
  walk(root);
  for (let i = 1; ; i++) if (!used.has(`${prefix}${i}`)) return `${prefix}${i}`;
}

// ------------------------------------------------------------------ type switching
/** Switch type; the old type's content is kept in `stash` and comes back when switching back. */
export function switchType(builder: Doc, type: string, schema: BSchema): Doc {
  if (builder.type === type) return builder;
  const stash = { ...(builder.stash ?? {}), [builder.type]: clone(builder.content ?? {}) };
  const content = clone(stash[type] ?? schema.types[type]?.defaults ?? {});
  delete stash[type];
  return { ...builder, type, content, stash };
}

// ------------------------------------------------------------------ local checks
export const utf8Len = (s: string) => new TextEncoder().encode(s).length;
export const charLen = (s: string) => [...s].length;

function checkField(f: BField, v: any, ptr: string, out: Issue[]) {
  if (f.type === "text" && f.max) {
    const vals: [string, any][] = f.localized && v && typeof v === "object" ? Object.entries(v) : [["", v]];
    for (const [loc, t] of vals) {
      if (typeof t === "string" && charLen(t) > f.max) out.push({ pointer: loc ? `${ptr}/${loc}` : ptr, code: "TOO_LONG", message: `${charLen(t)} characters; at most ${f.max}` });
    }
  }
  if (f.type === "number" && typeof v === "number") {
    if (f.min !== undefined && v < f.min) out.push({ pointer: ptr, code: "TOO_SMALL", message: `at least ${f.min}` });
    if (f.max !== undefined && v > f.max) out.push({ pointer: ptr, code: "TOO_BIG", message: `at most ${f.max}` });
  }
  if (f.type === "action" && v && typeof v === "object") {
    if (v.kind === "request" && typeof v.data === "string" && utf8Len(v.data) > 64) out.push({ pointer: `${ptr}/data`, code: "DATA_TOO_LONG", message: `${utf8Len(v.data)} bytes; the bot accepts at most 64` });
    const dones: [string, any][] = v.done && typeof v.done === "object" ? Object.entries(v.done) : [["", v.done]];
    for (const [loc, d] of dones) if (v.kind === "request" && typeof d === "string" && charLen(d) > 64) out.push({ pointer: loc ? `${ptr}/done/${loc}` : `${ptr}/done`, code: "TOO_LONG", message: "at most 64 characters" });
    if (v.kind === "link" && v.url && (!/^https:\/\//.test(v.url) || v.url.length > 256)) out.push({ pointer: `${ptr}/url`, code: "URL_INVALID", message: "an https:// link of up to 256 characters" });
    if (v.kind === "copy" && typeof v.text === "string" && charLen(v.text) > 256) out.push({ pointer: `${ptr}/text`, code: "TOO_LONG", message: "at most 256 characters" });
  }
  if (f.type === "list" && Array.isArray(v)) {
    if (f.minItems && v.length < f.minItems) out.push({ pointer: ptr, code: "TOO_FEW", message: `at least ${f.minItems}` });
    if (f.maxItems && v.length > f.maxItems) out.push({ pointer: ptr, code: "TOO_MANY", message: `at most ${f.maxItems}` });
    v.forEach((item, i) => (f.item?.fields ?? []).forEach((sf) => checkField(sf, getAt(item, sf.key), `${ptr}/${i}/${sf.key.replace(/\./g, "/")}`, out)));
  }
}

/** Pointers are /content/<path with / between keys>, like the server's. */
export function localIssues(builder: Doc, schema: BSchema): Issue[] {
  const t = schema.types[builder.type];
  if (!t) return [{ pointer: "/type", code: "TYPE_UNKNOWN", message: `unknown type ${builder.type}` }];
  const out: Issue[] = [];
  const content = builder.content ?? {};
  for (const s of t.sections) for (const f of applicableFields(s.fields, content)) checkField(f, getAt(content, f.key), `/content/${f.key.replace(/\./g, "/")}`, out);
  return out;
}

/** The field key (dot path) a validation pointer points into, for "go to field". */
export function keyOfPointer(pointer: string): string {
  return pointer.replace(/^\/builder/, "").replace(/^\/content\/?/, "").split("/").filter(Boolean).join(".");
}

