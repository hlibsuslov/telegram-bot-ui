import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Snapshot } from "@/core/engine.ts";
import { type Diag, lintAll } from "@/core/lint.ts";
import { api } from "./api";
import { DraftStore, useDraftVersion } from "./drafts";
import { fieldDomId, fromProjectDocument, type Loaded } from "./model";
import { go } from "./route";

export interface Toast { id: number; text: string; tone: "info" | "success" | "error" }
export interface Caps { text: boolean; rule: boolean; structure: boolean; create: boolean; save: boolean; widgets: boolean }

interface Ctx {
  loaded: Loaded;
  store: DraftStore;
  version: number;
  working: Snapshot;
  diags: Diag[];
  validating: boolean;
  caps: Caps;
  /** A newer saved project the drafts were not made on (external change or a stale stored draft). */
  pendingBase: Loaded | null;
  adoptPendingBase: () => void;
  reload: () => Promise<Loaded | null>;
  replaceLoaded: (l: Loaded) => void;
  saving: React.MutableRefObject<boolean>;
  saveDiags: Diag[];
  setSaveDiags: (d: Diag[]) => void;
  notify: (text: string, tone?: Toast["tone"]) => void;
  toasts: Toast[];
  focusField: (sid: string, pointer: string) => void;
}

const StudioContext = createContext<Ctx | null>(null);

export function useStudio(): Ctx {
  const ctx = useContext(StudioContext);
  if (!ctx) throw new Error("useStudio outside StudioProvider");
  return ctx;
}

const dedup = (list: Diag[]) => {
  const seen = new Set<string>();
  return list.filter((d) => {
    const k = `${d.screenId ?? ""}|${d.file}|${d.pointer}|${d.code}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
};

export function StudioProvider({ initial, children }: { initial: Loaded; children: ReactNode }) {
  const [loaded, setLoaded] = useState(initial);
  const storeRef = useRef<DraftStore | null>(null);
  if (!storeRef.current || storeRef.current.key !== `bot-ui-studio:draft:${loaded.projectId}:${loaded.rootKey}`) {
    storeRef.current = new DraftStore(loaded);
  }
  const store = storeRef.current;
  const version = useDraftVersion(store);
  const [serverDiags, setServerDiags] = useState<Diag[]>(initial.diagnostics);
  const [validating, setValidating] = useState(false);
  const [saveDiags, setSaveDiags] = useState<Diag[]>([]);
  const [incoming, setIncoming] = useState<Loaded | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const saving = useRef(false);
  const studio = loaded.mode === "studio";

  const notify = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 9000 : 4500);
  }, []);

  const working = useMemo<Snapshot>(
    () => ({ project: loaded.project, screens: store.screens(), scenarios: loaded.scenarios, revision: loaded.revision }),
    [loaded, version],
  );

  // Server validation of the draft overlay (debounced); the artifact has only the client lint.
  useEffect(() => {
    if (!studio) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setValidating(true);
      try {
        const res = await api("/api/validate", { screens: store.data.screens }, ctrl.signal);
        if (res.ok) setServerDiags(res.data.diagnostics ?? []);
      } catch { /* aborted */ }
      setValidating(false);
    }, 600);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [studio, version, loaded.revision, store]);

  const diags = useMemo(() => {
    const client = lintAll(working);
    const server = studio ? serverDiags : serverDiags.filter((d) => !d.screenId || !store.isDraft(d.screenId));
    return dedup([...client, ...server, ...saveDiags]);
  }, [working, serverDiags, saveDiags, studio]);

  const reload = useCallback(async () => {
    const res = await api("/api/project");
    if (!res.ok) {
      notify(`Could not reload the project: ${res.data?.error?.message ?? res.status}`, "error");
      return null;
    }
    return fromProjectDocument(res.data);
  }, [notify]);

  // External changes: poll the revision every 2 s.
  useEffect(() => {
    if (!studio) return;
    let busy = false;
    const timer = setInterval(async () => {
      if (busy || saving.current || document.hidden) return;
      busy = true;
      try {
        const res = await api("/api/revision");
        const rev = res.ok ? res.data.revision : null;
        if (rev && rev !== store.saved.revision && rev !== incoming?.revision && !saving.current) {
          const next = await reload();
          if (next && !saving.current) {
            if (store.count() === 0) {
              store.setSaved(next);
              setLoaded(next);
              setServerDiags(next.diagnostics);
              notify("The project changed on disk; the Studio reloaded it.", "info");
            } else {
              setIncoming(next);
            }
          }
        }
      } finally {
        busy = false;
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [studio, store, incoming, reload, notify]);

  const pendingBase = incoming ?? (store.stale ? loaded : null);
  const adoptPendingBase = useCallback(() => {
    const base = incoming ?? loaded;
    store.rebase(base);
    setLoaded(base);
    setServerDiags(base.diagnostics);
    setIncoming(null);
    notify("Reloaded the saved project and kept your draft on top of it.", "success");
  }, [incoming, loaded, store, notify]);

  const replaceLoaded = useCallback((l: Loaded) => {
    if (storeRef.current && storeRef.current.key === `bot-ui-studio:draft:${l.projectId}:${l.rootKey}`) storeRef.current.setSaved(l);
    setLoaded(l);
    setServerDiags(l.diagnostics);
    setIncoming(null);
  }, []);

  const focusField = useCallback((sid: string, pointer: string) => {
    go("screens", sid);
    let tries = 0;
    const attempt = () => {
      let p = pointer;
      while (p) {
        const el = document.getElementById(fieldDomId(sid, p));
        if (el) {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
          (el as HTMLElement).focus({ preventScroll: true });
          return;
        }
        p = p.slice(0, p.lastIndexOf("/"));
      }
      if (tries++ < 15) requestAnimationFrame(attempt);
    };
    requestAnimationFrame(attempt);
  }, []);

  const f = loaded.features;
  const ro = loaded.readOnly;
  const caps: Caps = {
    text: !ro && f.editText !== false,
    rule: !ro && f.editRule !== false,
    structure: !ro && f.editStructure !== false,
    create: !ro && f.createScreen !== false,
    save: !!f.save,
    widgets: !!f.widgets,
  };

  const value: Ctx = {
    loaded, store, version, working, diags, validating, caps, pendingBase, adoptPendingBase, reload,
    replaceLoaded, saving, saveDiags, setSaveDiags, notify, toasts, focusField,
  };
  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>;
}
