// Client-side checks of the surfaces the Studio and the artifact edit (texts, labels, targets,
// rules, keyboard references). A subset of studio/bot_ui/validate.py with the same codes and
// pointers; the CLI and the Studio server run the full validator before any write.
import { type Doc, keyboardRows, placeholders } from "./render.ts";
import type { Snapshot } from "./engine.ts";

export interface Diag { code: string; severity: "error" | "warning" | "info"; file: string; pointer: string; message: string; screenId?: string }

const RULE_SOURCES = new Set(["context", "state"]);
const ALLOWED_TAGS = new Set(["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre", "blockquote", "tg-emoji", "tg-time"]);

function typeOk(fd: Doc, v: any): boolean {
  if (fd.type === "enum") return (fd.values ?? []).includes(v);
  if (fd.type === "string") return typeof v === "string";
  if (fd.type === "number") return typeof v === "number";
  if (fd.type === "boolean") return typeof v === "boolean";
  return false;
}

export function lintScreen(snap: Snapshot, sid: string): Diag[] {
  const p = snap.project;
  const s = snap.screens[sid];
  const file = `screens/${sid}.json`;
  const out: Diag[] = [];
  const add = (code: string, severity: Diag["severity"], pointer: string, message: string) => out.push({ code, severity, file, pointer, message, screenId: sid });
  if (!s) return out;
  const def = p.defaultLocale;
  const fields = p.fields ?? {};
  const audience = s.audience ?? "private";
  const text = (value: any, pointer: string, fmt: string) => {
    if (typeof value === "string") value = { [def]: value };
    if (!value || typeof value[def] !== "string" || !value[def]) {
      add("DEFAULT_LOCALE_TEXT_MISSING", "error", `${pointer}/${def}`, `text in the default locale '${def}' is required`);
      return;
    }
    for (const loc of p.locales ?? []) if (loc !== def && typeof value[loc] !== "string") add("LOCALE_TEXT_MISSING", "warning", `${pointer}/${loc}`, `no '${loc}' text: users with this language see '${def}'`);
    for (const [loc, t] of Object.entries(value)) {
      if (typeof t !== "string") continue;
      for (const name of placeholders(t)) if (!(name in fields)) add("PLACEHOLDER_UNDECLARED", "error", `${pointer}/${loc}`, `{${name}} is not a declared field in project.json fields`);
      if (fmt === "regular.html") {
        const stack: string[] = [];
        for (const m of t.matchAll(/<(\/?)([a-zA-Z-]+)[^>]*>/g)) {
          const tag = m[2].toLowerCase();
          if (!ALLOWED_TAGS.has(tag)) add("HTML_TAG_UNSUPPORTED", "error", `${pointer}/${loc}`, `<${tag}> is not a Telegram regular-HTML tag`);
          else if (m[1]) { if (stack.pop() !== tag) add("HTML_UNBALANCED", "error", `${pointer}/${loc}`, `unbalanced </${tag}>`); }
          else stack.push(tag);
        }
        if (stack.length) add("HTML_UNBALANCED", "error", `${pointer}/${loc}`, `unclosed <${stack[stack.length - 1]}>`);
      }
    }
  };
  const target = (to: any, pointer: string) => {
    if (typeof to !== "string" || !to) return add("TARGET_EMPTY", "error", pointer, "choose a target screen");
    if (!snap.screens[to]) return add("TARGET_MISSING", "error", pointer, `screen '${to}' does not exist`);
    const ta = snap.screens[to].audience ?? "private";
    if (ta !== audience && ta !== "any" && audience !== "any") add("AUDIENCE_MISMATCH", "error", pointer, `${sid} (${audience}) leads to ${to} (${ta}); a transition keeps one audience`);
  };
  const fmt = s.message?.format ?? "regular.plain";
  if (fmt === "regular.plain" || fmt === "regular.html") {
    text(s.message?.text, "/message/text", fmt);
    for (const [st, v] of Object.entries<any>(s.message?.states ?? {})) if (v && "text" in v) text(v.text, `/message/states/${st}/text`, fmt);
  }
  const actions = s.actions ?? {};
  const placed = new Set<string>();
  keyboardRows(s).forEach((row, r) => row.forEach((aid, c) => {
    if (!(aid in actions)) add("KEYBOARD_ACTION_MISSING", "error", `/keyboard/rows/${r}/${c}`, `action '${aid}' is not defined in actions`);
    else if (placed.has(aid)) add("KEYBOARD_ACTION_DUPLICATE", "error", `/keyboard/rows/${r}/${c}`, `'${aid}' is already on the keyboard`);
    placed.add(aid);
  }));
  for (const [aid, a] of Object.entries<any>(actions)) {
    const ptr = `/actions/${aid}`;
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(aid)) add("ACTION_ID_INVALID", "error", ptr, "action IDs: lowercase letters, digits, _ and -");
    text(a.label, `${ptr}/label`, "regular.plain");
    if (a.type === "navigate") {
      const hasTo = "to" in a, rule = a.rule;
      if (hasTo === (rule !== undefined && rule !== null)) add("NAVIGATE_TARGET", "error", ptr, "navigate has exactly one of 'to' or 'rule'");
      if (hasTo) target(a.to, `${ptr}/to`);
      if (rule) {
        const fd = fields[rule.when?.field];
        if (!fd) add("RULE_FIELD_UNDECLARED", "error", `${ptr}/rule/when/field`, `field '${rule.when?.field}' is not declared in project.json`);
        else if (!RULE_SOURCES.has(fd.source)) add("RULE_FIELD_UNTRUSTED", "error", `${ptr}/rule/when/field`, `${rule.when.field} comes from '${fd.source}'; rules read only context or state fields`);
        else if (!("eq" in rule.when) || !typeOk(fd, rule.when.eq)) add("RULE_VALUE_TYPE", "error", `${ptr}/rule/when/eq`, `value must be a ${fd.type}` + (fd.values ? ` of ${JSON.stringify(fd.values)}` : ""));
        target(rule.match, `${ptr}/rule/match`);
        target(rule.otherwise, `${ptr}/rule/otherwise`);
        if (rule.match && rule.match === rule.otherwise) add("RULE_SAME_TARGETS", "warning", `${ptr}/rule`, "both branches lead to the same screen");
      }
    } else if (a.type === "handler") {
      for (const [k, to] of Object.entries(a.outcomes ?? {})) target(to, `${ptr}/outcomes/${k}`);
    } else if (a.type === "back" && a.fallback != null) target(a.fallback, `${ptr}/fallback`);
  }
  return out;
}

export function lintAll(snap: Snapshot): Diag[] {
  return Object.keys(snap.screens).flatMap((sid) => lintScreen(snap, sid));
}

/** Directed edges of the map: one per action target (rules give two), plus input. */
export function edges(snap: Snapshot): { id: string; from: string; to: string; actionId: string | null; via: string }[] {
  const out: { id: string; from: string; to: string; actionId: string | null; via: string }[] = [];
  for (const [sid, s] of Object.entries<any>(snap.screens)) {
    for (const [aid, a] of Object.entries<any>(s.actions ?? {})) {
      const push = (via: string, to: any) => { if (typeof to === "string" && to) out.push({ id: `${sid}/${aid}/${via}`, from: sid, to, actionId: aid, via }); };
      if (a.type === "navigate") {
        if (a.rule) { push("match", a.rule.match); push("otherwise", a.rule.otherwise); } else push("to", a.to);
      } else if (a.type === "handler") for (const [k, to] of Object.entries(a.outcomes ?? {})) push(`outcome:${k}`, to);
      else if (a.type === "back") push("back-fallback", a.fallback);
    }
    if (s.input?.to) out.push({ id: `${sid}/input`, from: sid, to: s.input.to, actionId: null, via: "input" });
  }
  return out;
}
