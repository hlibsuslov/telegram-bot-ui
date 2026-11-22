// bot-ui-patch/v1 from a saved and a draft screen: the same smallest-ops rule as
// studio/bot_ui/store.py (_diff_ops, ALLOWED_PATHS). Each op carries `from` (the saved
// value) so a newer revision can be checked field by field.
import type { Doc } from "./render.ts";

export const PATCH_FORMAT = "bot-ui-patch/v1";
const SEG = "[a-z0-9][a-z0-9_-]*";
const LOC = "[a-z]{2,3}(?:-[a-z0-9]{2,8})?";
export const ALLOWED_PATHS = [
  "/title", "/kind", "/audience", "/notes",
  "/message/format", `/message/text(/${LOC})?`, `/message/states/${SEG}(/text(/${LOC})?)?`,
  "/message/media", "/message/media/(type|file|spoiler|emoji)",
  "/keyboard", "/keyboard/(type|rows|placeholder|resize|oneTime)", `/keyboard/placeholder/${LOC}`,
  `/actions/${SEG}`,
  `/actions/${SEG}/(label|type|to|rule|presentation|set|handlerId|outcomes|pending|url|text|fallback|style|icon|hidden)`,
  `/actions/${SEG}/(label|text|pending)/${LOC}`,
  `/actions/${SEG}/rule/(when|match|otherwise)`, `/actions/${SEG}/rule/when/(field|eq)`,
  `/actions/${SEG}/outcomes/${SEG}`, `/actions/${SEG}/set/[a-z0-9_.-]+`,
  "/input", "/input/(field|to)", "/widget", "/widget/(ref|caption)",
].map((p) => new RegExp(`^${p}$`));

const PROBES = ["ru", "en", "when", "field", "eq", "text", "match", "otherwise", "rows", "type", "label", "x", "a1"];
const isObj = (v: any) => v !== null && typeof v === "object" && !Array.isArray(v);
const hasChild = (p: string) => ALLOWED_PATHS.some((rx) => PROBES.some((t) => rx.test(`${p}/${t}`)));
export const allowed = (p: string) => ALLOWED_PATHS.some((rx) => rx.test(p));

function same(a: any, b: any): boolean { return JSON.stringify(a) === JSON.stringify(b) || deepEq(a, b); }
function deepEq(a: any, b: any): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => deepEq(x, b[i]));
  if (isObj(a) && isObj(b)) { const ka = Object.keys(a), kb = Object.keys(b); return ka.length === kb.length && ka.every((k) => k in b && deepEq(a[k], b[k])); }
  return false;
}

export function diffOps(oldV: any, newV: any, path = "", ops: Doc[] = []): Doc[] {
  if (same(oldV, newV)) return ops;
  if (path && !(isObj(oldV) && isObj(newV) && hasChild(path))) { ops.push({ op: "set", path, value: newV, from: oldV }); return ops; }
  const keys = [...Object.keys(oldV), ...Object.keys(newV).filter((k) => !(k in oldV))];
  for (const k of keys) {
    const p = `${path}/${k.replace(/~/g, "~0").replace(/\//g, "~1")}`;
    if (!(k in newV)) ops.push({ op: "remove", path: p, from: oldV[k] });
    else if (!(k in oldV)) ops.push({ op: "set", path: p, value: newV[k], from: null });
    else diffOps(oldV[k], newV[k], p, ops);
  }
  return ops;
}

export function makePatch(projectId: string, baseRevision: string, saved: Record<string, Doc>, drafts: Record<string, Doc>): Doc {
  const changes: Doc[] = [];
  for (const [sid, draft] of Object.entries(drafts)) {
    const old = saved[sid];
    if (!old) changes.push({ screenId: sid, create: draft });
    else {
      const ops = diffOps(old, draft);
      if (ops.length) changes.push({ screenId: sid, ops });
    }
  }
  return { format: PATCH_FORMAT, projectId, baseRevision, changes };
}

export function forbiddenOps(patch: Doc): string[] {
  return (patch.changes ?? []).flatMap((c: Doc) => (c.ops ?? []).filter((o: Doc) => !allowed(o.path)).map((o: Doc) => `${c.screenId}${o.path}`));
}
