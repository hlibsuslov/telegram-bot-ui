import type { Doc } from "@/core/render.ts";
import type { Diag } from "@/core/lint.ts";

export type Mode = "studio" | "artifact";

export interface WidgetDoc { meta: Doc; files: Record<string, string> }

/** One shape for both sources: the Studio API project document and the artifact snapshot. */
export interface Loaded {
  mode: Mode;
  projectId: string;
  title: string;
  revision: string;
  project: Doc;
  screens: Record<string, Doc>;
  screenFiles: Record<string, string>;
  scenarios: Record<string, Doc>;
  widgets: Record<string, WidgetDoc>;
  diagnostics: Diag[];
  rootKey: string;
  rootLabel?: string;
  cliProject?: string;
  readOnly: boolean;
  features: Record<string, boolean>;
  apply?: string;
}

export const SNAPSHOT_FORMAT = "bot-ui-snapshot/v1";
export const STUDIO_FEATURES = {
  map: true, simulate: true, editText: true, editRule: true, exportPatch: false,
  save: true, widgets: true, createScreen: true, editStructure: true,
};

export function fromProjectDocument(doc: Doc): Loaded {
  const project = doc.project ?? {};
  return {
    mode: "studio",
    projectId: project.projectId ?? "project",
    title: project.title ?? project.projectId ?? doc.rootLabel ?? "bot-ui project",
    revision: doc.revision,
    project,
    screens: doc.screens ?? {},
    screenFiles: doc.screenFiles ?? {},
    scenarios: doc.scenarios ?? {},
    widgets: doc.widgets ?? {},
    diagnostics: doc.diagnostics ?? [],
    rootKey: doc.rootKey ?? "local",
    rootLabel: doc.rootLabel,
    cliProject: doc.cliProject,
    readOnly: !!doc.readOnly,
    features: STUDIO_FEATURES,
  };
}

export function fromSnapshot(doc: Doc): Loaded {
  if (!doc || doc.format !== SNAPSHOT_FORMAT) throw new Error(`not a ${SNAPSHOT_FORMAT} document`);
  if (typeof doc.baseRevision !== "string" || !doc.screens || typeof doc.screens !== "object") {
    throw new Error("the snapshot has no baseRevision or screens");
  }
  const project = doc.project ?? {};
  const widgets: Record<string, WidgetDoc> = {};
  for (const [wid, w] of Object.entries<Doc>(doc.widgets ?? {})) widgets[wid] = { meta: { ...w }, files: {} };
  return {
    mode: "artifact",
    projectId: doc.projectId ?? project.projectId ?? "project",
    title: project.title ?? doc.projectId ?? "bot-ui snapshot",
    revision: doc.baseRevision,
    project,
    screens: doc.screens,
    screenFiles: {},
    scenarios: doc.scenarios ?? {},
    widgets,
    diagnostics: doc.diagnostics ?? [],
    rootKey: "artifact",
    readOnly: false,
    features: { editStructure: false, ...(doc.features ?? {}) },
    apply: doc.apply,
  };
}

/** The embedded artifact snapshot, when this page is the single-file artifact. */
export function embeddedSnapshot(): Doc | null {
  const el = document.getElementById("bot-ui-snapshot");
  if (!el || el.getAttribute("type") !== "application/json") return null;
  try {
    const doc = JSON.parse(el.textContent ?? "");
    return doc && typeof doc === "object" ? doc : null;
  } catch {
    return null;
  }
}

export function screenFile(l: Loaded, sid: string): string {
  return l.screenFiles[sid] ?? `screens/${sid}.json`;
}

export const shortRev = (rev: string | undefined) => (rev ?? "").replace(/^sha256:/, "").slice(0, 8);

// Screen IDs: the contract regex (studio/bot_ui/project.py ID_RE) plus length and reserved names.
const ID_RE = /^[a-z0-9][a-z0-9_-]*(\.[a-z0-9][a-z0-9_-]*)*$/;
const RESERVED = new Set(["con", "prn", "aux", "nul", ...Array.from({ length: 9 }, (_, i) => `com${i + 1}`), ...Array.from({ length: 9 }, (_, i) => `lpt${i + 1}`)]);
export const ACTION_ID_RE = /^[a-z0-9][a-z0-9_-]*$/;

export function idProblem(id: string): string | null {
  if (!id) return "Enter an ID.";
  if (id.length > 64) return "At most 64 characters.";
  if (!ID_RE.test(id)) return "Lowercase letters, digits, _ and -, with . between segments (e.g. checkout.payment.confirm).";
  if (id.split(".").some((s) => RESERVED.has(s))) return "A segment is a reserved Windows name (con, nul, com1…).";
  return null;
}

export const KINDS = ["entry", "menu", "form", "confirmation", "result", "error", "empty", "loading", "notification", "status"];
export const KEYBOARD_TYPES = ["inline", "reply", "force_reply", "remove", "none"];
export const ACTION_TYPES = ["navigate", "back", "url", "answer", "handler", "disabled"];
export const STYLES = ["", "primary", "success", "danger"];
/** What Telegram clients paint for each Bot API button style. */
export const STYLE_LABELS: Record<string, string> = {
  "": "default (theme colour)", primary: "primary (blue)", success: "success (green)", danger: "danger (red)",
};

// ------------------------------------------------------------------ JSON helpers
export const clone = <T,>(v: T): T => (v === undefined ? v : structuredClone(v));

export function deepEqual(a: any, b: any): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  if (a && b && typeof a === "object" && typeof b === "object" && !Array.isArray(a) && !Array.isArray(b)) {
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => k in b && deepEqual(a[k], b[k]));
  }
  return false;
}

const tokens = (pointer: string) => pointer.split("/").slice(1).map((t) => t.replace(/~1/g, "/").replace(/~0/g, "~"));

export function getPointer(doc: any, pointer: string): any {
  let cur = doc;
  for (const t of tokens(pointer)) {
    if (cur === null || typeof cur !== "object" || !(t in cur)) return undefined;
    cur = cur[t];
  }
  return cur;
}

/** Apply bot-ui-patch ops (set/remove by JSON pointer) to a document copy. */
export function applyOps(doc: Doc, ops: Doc[]): Doc {
  const out = clone(doc);
  for (const op of ops) {
    const ts = tokens(op.path);
    let cur: any = out;
    for (const t of ts.slice(0, -1)) {
      if (cur[t] === null || typeof cur[t] !== "object") cur[t] = {};
      cur = cur[t];
    }
    const last = ts[ts.length - 1];
    if (op.op === "remove") delete cur[last];
    else cur[last] = clone(op.value);
  }
  return out;
}

export function fieldDomId(sid: string, pointer: string): string {
  return `f-${sid}-${pointer}`.replace(/[^a-zA-Z0-9_-]/g, "_");
}

/** Example values for placeholders in previews: field examples, the first enum value. */
export function exampleValues(project: Doc): Doc {
  const out: Doc = {};
  for (const [name, fd] of Object.entries<Doc>(project.fields ?? {})) {
    if (fd.example !== undefined) out[name] = fd.example;
    else if (fd.type === "enum" && fd.values?.length) out[name] = fd.values[0];
  }
  return out;
}

export const defaultLocale = (project: Doc): string => project.defaultLocale ?? "en";
export const locales = (project: Doc): string[] => {
  const def = defaultLocale(project);
  const ls: string[] = project.locales?.length ? project.locales : [def];
  return ls.includes(def) ? [def, ...ls.filter((l) => l !== def)] : [def, ...ls];
};

export function utf8Bytes(s: string): number {
  return new TextEncoder().encode(s).length;
}

export async function sha256Text(text: string): Promise<string> {
  const data = new TextEncoder().encode(text.replace(/\r\n/g, "\n"));
  const digest = await crypto.subtle.digest("SHA-256", data);
  return "sha256:" + [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Cheap stable hash for request de-duplication (not security). */
export function fnv1a(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

export function download(name: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

/** Scroll an element into view inside its own panel (data-scroll-root), below any sticky header
 * of that panel, without scrolling the page or the map. */
export function scrollWithin(el: HTMLElement, align: "start" | "center" = "start") {
  const root = el.closest<HTMLElement>("[data-scroll-root]");
  if (!root) return;
  const sticky = root.querySelector<HTMLElement>("[data-scroll-sticky]");
  const offset = sticky ? sticky.offsetHeight : 0;
  const top = el.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
  const room = root.clientHeight - offset;
  root.scrollTo({ top: align === "center" ? top - offset - Math.max(0, (room - el.offsetHeight) / 2) : top - offset - 12, behavior: "smooth" });
}
