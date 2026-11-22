// Drafts live apart from the repository: in localStorage under projectId + rootKey, with the
// revision they were made on and the saved documents they started from (for a rebase).
// Undo/Redo is session-only.
import { useSyncExternalStore } from "react";
import type { Doc } from "@/core/render.ts";
import { diffOps } from "@/core/patch.ts";
import { applyOps, clone, deepEqual, type Loaded } from "./model";

export interface DraftData {
  baseRevision: string;
  screens: Record<string, Doc>;
  bases: Record<string, Doc | null>;
  widgets: Record<string, Record<string, string>>;
  widgetBases: Record<string, Record<string, string | null>>;
}

const HISTORY = 200;
const COALESCE_MS = 900;

const empty = (rev: string): DraftData => ({ baseRevision: rev, screens: {}, bases: {}, widgets: {}, widgetBases: {} });

function readStorage(key: string): DraftData | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (!d || typeof d.baseRevision !== "string" || typeof d.screens !== "object") return null;
    return { ...empty(d.baseRevision), ...d };
  } catch {
    return null;
  }
}

export class DraftStore {
  saved: Loaded;
  data: DraftData;
  past: DraftData[] = [];
  future: DraftData[] = [];
  version = 0;
  readonly key: string;
  storageOk = true;
  private lastKey = "";
  private lastAt = 0;
  private listeners = new Set<() => void>();

  constructor(saved: Loaded) {
    this.saved = saved;
    this.key = `bot-ui-studio:draft:${saved.projectId}:${saved.rootKey}`;
    this.data = readStorage(this.key) ?? empty(saved.revision);
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getVersion = () => this.version;
  private emit() {
    this.version++;
    this.listeners.forEach((fn) => fn());
  }
  private persist() {
    try {
      if (this.count() === 0) localStorage.removeItem(this.key);
      else localStorage.setItem(this.key, JSON.stringify(this.data));
      this.storageOk = true;
    } catch {
      this.storageOk = false;
    }
  }
  private commit(next: DraftData, coalesce?: string) {
    const now = Date.now();
    const merge = !!coalesce && coalesce === this.lastKey && now - this.lastAt < COALESCE_MS;
    if (!merge) {
      this.past.push(this.data);
      if (this.past.length > HISTORY) this.past.shift();
    }
    this.lastKey = coalesce ?? "";
    this.lastAt = now;
    this.future = [];
    this.data = next;
    this.persist();
    this.emit();
  }

  /** True when the drafts were made on another revision than the one now saved. */
  get stale() {
    return this.count() > 0 && this.data.baseRevision !== this.saved.revision;
  }
  count() {
    return Object.keys(this.data.screens).length + Object.values(this.data.widgets).reduce((n, f) => n + Object.keys(f).length, 0);
  }
  isDraft(sid: string) {
    return sid in this.data.screens;
  }
  screen(sid: string): Doc | undefined {
    return this.data.screens[sid] ?? this.saved.screens[sid];
  }
  screens(): Record<string, Doc> {
    return { ...this.saved.screens, ...this.data.screens };
  }
  widgetFiles(wid: string): Record<string, string> {
    return { ...(this.saved.widgets[wid]?.files ?? {}), ...(this.data.widgets[wid] ?? {}) };
  }

  updateScreen(sid: string, fn: (doc: Doc) => Doc | void, coalesce?: string) {
    const cur = this.screen(sid);
    if (!cur) return;
    const doc = clone(cur);
    const out = fn(doc) ?? doc;
    const next: DraftData = { ...this.data, screens: { ...this.data.screens }, bases: { ...this.data.bases } };
    const saved = this.saved.screens[sid];
    if (saved && deepEqual(out, saved)) {
      delete next.screens[sid];
      delete next.bases[sid];
    } else {
      next.screens[sid] = out;
      if (!(sid in next.bases)) next.bases[sid] = saved ? clone(saved) : null;
    }
    if (Object.keys(this.data.screens).length === 0 && Object.keys(this.data.widgets).length === 0) next.baseRevision = this.saved.revision;
    this.commit(next, coalesce ? `${sid}:${coalesce}` : undefined);
  }

  createScreen(doc: Doc) {
    const next: DraftData = { ...this.data, screens: { ...this.data.screens, [doc.id]: doc }, bases: { ...this.data.bases, [doc.id]: null } };
    if (this.count() === 0) next.baseRevision = this.saved.revision;
    this.commit(next);
  }

  setWidgetFile(wid: string, file: string, content: string) {
    const saved = this.saved.widgets[wid]?.files[file];
    const files = { ...(this.data.widgets[wid] ?? {}) };
    const bases = { ...(this.data.widgetBases[wid] ?? {}) };
    if (saved !== undefined && saved === content) {
      delete files[file];
      delete bases[file];
    } else {
      files[file] = content;
      if (!(file in bases)) bases[file] = saved ?? null;
    }
    const widgets = { ...this.data.widgets, [wid]: files };
    const widgetBases = { ...this.data.widgetBases, [wid]: bases };
    if (!Object.keys(files).length) { delete widgets[wid]; delete widgetBases[wid]; }
    const next = { ...this.data, widgets, widgetBases };
    if (this.count() === 0) next.baseRevision = this.saved.revision;
    this.commit(next, `w:${wid}:${file}`);
  }

  resetScreen(sid: string) {
    if (!this.isDraft(sid)) return;
    const screens = { ...this.data.screens }, bases = { ...this.data.bases };
    delete screens[sid];
    delete bases[sid];
    this.commit({ ...this.data, screens, bases });
  }
  resetWidget(wid: string) {
    if (!this.data.widgets[wid]) return;
    const widgets = { ...this.data.widgets }, widgetBases = { ...this.data.widgetBases };
    delete widgets[wid];
    delete widgetBases[wid];
    this.commit({ ...this.data, widgets, widgetBases });
  }
  resetAll() {
    this.commit(empty(this.saved.revision));
  }

  undo() {
    const prev = this.past.pop();
    if (!prev) return;
    this.future.push(this.data);
    this.data = prev;
    this.lastKey = "";
    this.persist();
    this.emit();
  }
  redo() {
    const nxt = this.future.pop();
    if (!nxt) return;
    this.past.push(this.data);
    this.data = nxt;
    this.lastKey = "";
    this.persist();
    this.emit();
  }

  /** New saved data with drafts on the same revision (after a reload with no external change). */
  setSaved(saved: Loaded) {
    this.saved = saved;
    if (this.count() === 0) this.data = empty(saved.revision);
    this.emit();
  }

  /** After a successful save: drop drafts that went out unchanged, rebase the rest. */
  afterSave(saved: Loaded, sentScreens: Record<string, Doc>, sentWidgets: Record<string, Record<string, string>>) {
    const screens = { ...this.data.screens }, bases = { ...this.data.bases };
    for (const [sid, doc] of Object.entries(sentScreens)) if (deepEqual(screens[sid], doc)) { delete screens[sid]; delete bases[sid]; }
    const widgets = clone(this.data.widgets), widgetBases = clone(this.data.widgetBases);
    for (const [wid, files] of Object.entries(sentWidgets)) {
      for (const [f, c] of Object.entries(files)) if (widgets[wid]?.[f] === c) { delete widgets[wid][f]; delete widgetBases[wid]?.[f]; }
      if (widgets[wid] && !Object.keys(widgets[wid]).length) { delete widgets[wid]; delete widgetBases[wid]; }
    }
    this.data = { baseRevision: this.data.baseRevision, screens, bases, widgets, widgetBases };
    this.past = [];
    this.future = [];
    this.rebase(saved, false);
  }

  /** "Reload saved and keep my draft": replay my changes (base -> draft) onto the newer saved docs. */
  rebase(saved: Loaded, record = true) {
    const screens: Record<string, Doc> = {}, bases: Record<string, Doc | null> = {};
    for (const [sid, draft] of Object.entries(this.data.screens)) {
      const base = this.data.bases[sid];
      const now = saved.screens[sid];
      const rebased = base && now ? applyOps(now, diffOps(base, draft)) : draft;
      if (now && deepEqual(rebased, now)) continue;
      screens[sid] = rebased;
      bases[sid] = now ? clone(now) : null;
    }
    const widgets: DraftData["widgets"] = {}, widgetBases: DraftData["widgetBases"] = {};
    for (const [wid, files] of Object.entries(this.data.widgets)) {
      for (const [f, c] of Object.entries(files)) {
        const now = saved.widgets[wid]?.files[f];
        if (now === c) continue;
        (widgets[wid] ??= {})[f] = c;
        (widgetBases[wid] ??= {})[f] = now ?? null;
      }
    }
    this.saved = saved;
    const next = { baseRevision: saved.revision, screens, bases, widgets, widgetBases };
    if (record) this.commit(next);
    else {
      this.data = next;
      this.persist();
      this.emit();
    }
  }
}

export function useDraftVersion(store: DraftStore): number {
  return useSyncExternalStore(store.subscribe, store.getVersion);
}
