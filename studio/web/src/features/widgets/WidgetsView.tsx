// Widget page: one top-to-bottom flow of numbered steps (Widget, Look, What the bot sends, Message,
// Check) beside a sticky live preview with its own toolbar. Builds come from /api/widget/build
// (debounced, late answers dropped); the frame is the sandboxed /preview-frame.html.
import {
  ArrowDownLeft, ArrowUpRight, Check, ChevronDown, ChevronRight, Copy, Download, Expand, ImageUp, Plus, RefreshCw, RotateCcw, Save, Search, WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { type Doc } from "@/core/render.ts";
import { CodeArea } from "@/components/code-area";
import { CodeBlock, CodeView } from "@/components/code-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useIsMobile } from "@/hooks/use-mobile";
import { api, errorText } from "@/lib/api";
import { copyText, defaultLocale, download, exampleValues, fnv1a, locales, sha256Text, utf8Bytes } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, Segmented } from "../inspector/fields";
import { DraftBadge } from "../inspector/ScreenInspector";
import { ScreenPreview } from "../preview/Telegram";
import { renderScreen } from "@/core/render.ts";
import { composeDoc, frameScheme, type Runtime } from "./frame";
import { insertMarker, marker, PhotoToSvg } from "./PhotoToSvg";
import { DataSection, MessageSection, SendSection } from "./WidgetForms";

interface Build {
  ok: boolean; html: string; rawBytes: number; compressedBytes: number; limits: { rawBytes: number; compressedBytes: number; dataBytes: number };
  errors: string[]; warnings: string[]; caption?: string | null; sourceHash: string; payload?: Doc; lang: string; draft?: boolean;
}
type BuildState = { status: "idle" | "updating" | "ok" | "error"; current: Build | null; message?: string };
type Ev = { n: number; at: number; dir: "out" | "in" | "sys"; kind: string; text: string; json?: unknown };

const ORDER = ["index.html", "style.css", "widget.js", "widget.json"];
const WIDTHS = [240, 320, 400, 600];
const WIDGET_ID_RE = /^[a-z0-9][a-z0-9_-]*$/;

function Meter({ label, value, limit }: { label: string; value: number; limit: number }) {
  const pct = Math.min(100, Math.round((value / limit) * 100));
  const over = value > limit;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span className="text-muted-foreground">{label}</span><span className={cn("font-mono tabular-nums", over && "font-semibold text-destructive")}>{value.toLocaleString()} / {limit.toLocaleString()} B</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={limit} aria-valuenow={value}>
        <div className={cn("h-full rounded-full transition-[width]", over ? "bg-destructive" : pct > 85 ? "bg-amber-500" : "bg-emerald-600")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const KIND_STYLE: Record<string, string> = {
  req: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100",
  ans: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
  push: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-100",
  reject: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-100",
  error: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-100",
};

function Timeline({ events, onClear }: { events: Ev[]; onClear: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const t0 = events[0]?.at ?? 0;
  return (
    <div className="rounded-xl ring-1 ring-border" aria-label="Requests and state">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <span className="text-xs font-semibold">Requests from the widget</span>
        <span className="text-[11px] text-muted-foreground">{events.length} events</span>
        {events.length > 0 && <Button size="sm" variant="ghost" className="ml-auto h-6 px-2 text-[11px]" onClick={onClear}>Clear</Button>}
      </div>
      <ol className="max-h-72 overflow-y-auto">
        {events.length === 0 && <li className="px-3 py-4 text-center text-xs text-muted-foreground">Tap something in the preview. Requests are answered from demo answers; nothing leaves the page.</li>}
        {events.map((e) => {
          const Icon = e.dir === "out" ? ArrowUpRight : e.dir === "in" ? ArrowDownLeft : ChevronRight;
          const expanded = open === e.n;
          return (
            <li key={e.n} className="border-b last:border-b-0">
              <button type="button" className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted/50" aria-expanded={e.json !== undefined ? expanded : undefined}
                onClick={() => e.json !== undefined && setOpen(expanded ? null : e.n)}>
                <Icon className={cn("size-3.5 shrink-0", e.dir === "out" ? "text-sky-600" : e.dir === "in" ? "text-emerald-600" : "text-muted-foreground")} aria-label={e.dir === "out" ? "from the widget" : e.dir === "in" ? "to the widget" : "info"} />
                <span className={cn("w-14 shrink-0 rounded-full px-1.5 py-0.5 text-center text-[10px] font-medium", KIND_STYLE[e.kind] ?? "bg-muted text-muted-foreground")}>{e.kind}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11.5px]">{e.text}</span>
                <span className="shrink-0 font-mono text-[10.5px] text-muted-foreground tabular-nums">+{((e.at - t0) / 1000).toFixed(2)}s</span>
                {e.json !== undefined && <ChevronRight className={cn("size-3.5 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-90")} aria-hidden />}
              </button>
              {expanded && <div className="px-3 pb-2"><CodeBlock code={JSON.stringify(e.json, null, 2)} lang="json" maxHeight="16rem" wrap /></div>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

const parseMaybe = (s: unknown) => { if (typeof s !== "string") return s; try { return JSON.parse(s); } catch { return s; } };

/** One numbered, collapsible step of the flow. */
function Step({ n, title, hint, open, onToggle, children, right }: { n: number; title: string; hint: string; open: boolean; onToggle: () => void; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="rounded-2xl bg-card ring-1 ring-border" aria-labelledby={`wstep-${n}`}>
      <div className="flex items-start gap-3 p-4">
        <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={`wstep-${n}-body`} className="flex min-w-0 flex-1 items-start gap-3 text-left">
          <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold", open ? "bg-foreground text-background" : "bg-muted text-muted-foreground")}>{n}</span>
          <span className="min-w-0 flex-1">
            <span id={`wstep-${n}`} className="block text-[15px] font-semibold tracking-tight">{title}</span>
            <span className="block text-xs text-muted-foreground">{hint}</span>
          </span>
          <ChevronDown className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
        </button>
        {right}
      </div>
      {open && <div id={`wstep-${n}-body`} className="space-y-4 px-4 pb-5 sm:pl-14">{children}</div>}
    </section>
  );
}

function WidgetSwitcher({ current, onNew }: { current: string | null; onNew: () => void }) {
  const { loaded } = useStudio();
  const [open, setOpen] = useState(false);
  const ids = Object.keys(loaded.widgets).sort();
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-9 max-w-full justify-between gap-2 px-3" aria-label={`Widget: ${current ?? "none"}. Switch or create`}>
          <span className="truncate font-mono text-[13px]">{current ?? "No widget"}</span>
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(92vw,22rem)] p-1">
        <div role="listbox" aria-label="Widgets">
          {ids.map((w) => (
            <button key={w} type="button" role="option" aria-selected={w === current} onClick={() => { setOpen(false); go("widgets", w); }}
              className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left hover:bg-muted aria-selected:bg-muted">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[13px]">{w}</span>
                {loaded.widgets[w].meta.title && <span className="block truncate text-xs text-muted-foreground">{loaded.widgets[w].meta.title}</span>}
              </span>
              {w === current && <Check className="size-4" />}
            </button>
          ))}
        </div>
        <div className="mt-1 border-t pt-1">
          <button type="button" onClick={() => { setOpen(false); onNew(); }} className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm hover:bg-muted">
            <Plus className="size-4" /> New widget
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

interface Template { id: string; title: string; summary: string }

function NewWidgetDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { loaded, store, reload, replaceLoaded, refreshGit, notify } = useStudio();
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [id, setId] = useState("");
  const [title, setTitle] = useState("");
  const [template, setTemplate] = useState("blank");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!open || templates) return;
    api<{ templates: Template[] }>("/api/widget/templates", {}).then((r) => setTemplates(r.ok ? r.data.templates ?? [] : []));
  }, [open, templates]);
  const problem = !id ? "" : id.length > 64 ? "At most 64 characters." : !WIDGET_ID_RE.test(id) ? "One segment: lowercase letters, digits, _ and -." : loaded.widgets[id] ? "A widget with this ID exists." : "";
  const shown = (templates ?? []).filter((t) => `${t.id} ${t.title} ${t.summary}`.toLowerCase().includes(q.toLowerCase()));
  const create = async () => {
    if (!id || problem) return;
    setBusy(true);
    setErr("");
    try {
      const res = await api("/api/widget/create", { widgetId: id, template, title: title || undefined, expectedRevision: store.saved.revision });
      if (!res.ok) {
        if (res.status === 409) {
          const next = await reload();
          if (next) replaceLoaded(next);
          setErr("The project changed in the meantime; it is reloaded. Press Create again.");
        } else setErr(errorText(res.data));
        return;
      }
      const next = await reload();
      if (next) replaceLoaded(next);
      void refreshGit();
      notify(`Created widgets/${id}/ (saved to files, not committed)`, "success");
      onOpenChange(false);
      setId(""); setTitle(""); setTemplate("blank");
      go("widgets", id);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <form onSubmit={(e) => { e.preventDefault(); void create(); }} className="space-y-4">
          <DialogHeader>
            <DialogTitle>New widget</DialogTitle>
            <DialogDescription>Creates widgets/&lt;id&gt;/ in your project (saved to files, not committed). Start empty or from a ready example.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Widget ID" htmlFor="new-widget-id" hint={problem || "Lowercase letters, digits, _ and -; it never changes later."}>
              <Input id="new-widget-id" autoFocus value={id} onChange={(e) => setId(e.target.value.trim())} placeholder="order-card" className="font-mono"
                aria-invalid={!!problem || undefined} />
            </Field>
            <Field label="Title (optional)" htmlFor="new-widget-title">
              <Input id="new-widget-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Order card" />
            </Field>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Start from</span>
              <div className="relative ml-auto w-56">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search examples" aria-label="Search templates" className="h-8 pl-8 text-xs" />
              </div>
            </div>
            <div role="radiogroup" aria-label="Template" className="grid max-h-[46svh] gap-2 overflow-y-auto p-0.5 sm:grid-cols-2">
              {templates === null && <p className="text-xs text-muted-foreground">Loading templates…</p>}
              {shown.map((t) => (
                <button key={t.id} type="button" role="radio" aria-checked={template === t.id} onClick={() => setTemplate(t.id)}
                  className="rounded-xl p-3 text-left ring-1 ring-border hover:bg-muted/50 aria-checked:bg-muted aria-checked:ring-2 aria-checked:ring-foreground">
                  <span className="flex items-center gap-2 text-sm font-medium">{t.title}{t.id === "blank" && <span className="rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">empty</span>}</span>
                  <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{t.summary}</span>
                </button>
              ))}
              {templates && !shown.length && <p className="text-xs text-muted-foreground">No example matches “{q}”.</p>}
            </div>
          </div>
          {err && <p role="alert" className="text-sm text-destructive">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!id || !!problem || busy}>{busy ? "Creating…" : "Create widget"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PreviewToolbar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl bg-card px-3 py-2 ring-1 ring-border">{children}</div>;
}

function Workbench({ wid, onNew }: { wid: string; onNew: () => void }) {
  const { store, loaded, notify, reload, replaceLoaded, refreshGit, saving: savingRef } = useStudio();
  const isMobile = useIsMobile();
  const files = store.widgetFiles(wid);
  const draft = !!store.data.widgets[wid];
  const names = useMemo(() => [...Object.keys(files)].sort((a, b) => {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  }), [files]);
  const [tab, setTab] = useState(names[0] ?? "index.html");
  const meta: Doc = useMemo(() => {
    try { return files["widget.json"] ? JSON.parse(files["widget.json"]) : loaded.widgets[wid]?.meta ?? {}; } catch { return loaded.widgets[wid]?.meta ?? {}; }
  }, [files, loaded, wid]);
  const metaError = useMemo(() => { try { if (files["widget.json"]) JSON.parse(files["widget.json"]); return ""; } catch (e) { return (e as Error).message; } }, [files]);
  const langs: string[] = meta.languages?.length ? meta.languages : [defaultLocale(loaded.project)];
  const states = Object.keys(meta.states ?? { default: {} });
  const [lang, setLang] = useState(langs[0]);
  const [state, setState] = useState(states.includes("default") ? "default" : states[0]);
  const [theme, setTheme] = useState("light");
  const [width, setWidth] = useState(320);
  const [offline, setOffline] = useState(false);
  const [reset, setReset] = useState(0);
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [build, setBuild] = useState<BuildState>({ status: "idle", current: null });
  const [lastGood, setLastGood] = useState<Build | null>(null);
  const [height, setHeight] = useState(120);
  const [events, setEvents] = useState<Ev[]>([]);
  const [exported, setExported] = useState<Doc | null>(null);
  const [exportErr, setExportErr] = useState("");
  const [wide, setWide] = useState(false);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState<Set<number>>(() => new Set(isMobile ? [3] : [1, 3, 4, 5]));
  const seq = useRef(0);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const toggle = (n: number) => setOpen((o) => {
    const next = new Set(isMobile ? [] : o);
    if (o.has(n)) next.delete(n); else next.add(n);
    return next;
  });
  // Narrow screens: one step open at a time.
  useEffect(() => { if (isMobile) setOpen((o) => (o.size > 1 ? new Set([3]) : o)); }, [isMobile]);
  useEffect(() => { if (!langs.includes(lang)) setLang(langs[0]); }, [langs, lang]);
  useEffect(() => { if (!states.includes(state)) setState(states[0]); }, [states, state]);

  useEffect(() => {
    let live = true;
    api("/api/widget/runtime", { widget: wid }).then((res) => { if (!live) return; if (res.ok) setRuntime(res.data); else notify(`Widget runtime: ${errorText(res.data)}`, "error"); });
    return () => { live = false; };
  }, [wid, loaded.revision, notify]);

  // Debounced build; an answer is used only if it belongs to the latest request.
  const filesJson = JSON.stringify(files);
  const key = fnv1a(`${filesJson}\u0000${lang}\u0000${state}`);
  useEffect(() => {
    const mine = ++seq.current;
    setBuild((b) => ({ ...b, status: "updating" }));
    const t = setTimeout(async () => {
      const res = await api<Build>("/api/widget/build", { widget: wid, lang, state, ...(draft ? { files: JSON.parse(filesJson) } : {}) });
      if (mine !== seq.current) return;
      if (!res.ok) return setBuild({ status: "error", current: null, message: errorText(res.data) });
      const b = res.data;
      setBuild({ status: b.ok ? "ok" : "error", current: b, message: b.ok ? undefined : b.errors?.[0] });
      if (b.ok) setLastGood(b);
    }, 400);
    return () => clearTimeout(t);
  }, [key, wid, lang, state, filesJson, draft]);

  const shown = build.status === "ok" ? build.current : lastGood;
  const isPrevious = !!shown && shown !== build.current;
  const session = `s${fnv1a(`${shown?.sourceHash ?? ""}|${shown?.html.length ?? 0}|${state}|${theme}|${lang}|${offline}|${reset}|${width}`)}${reset}`;
  const doc = shown && runtime ? composeDoc(runtime, shown.html, { session, theme, lang, meta, state, offline }) : null;
  const live = useRef({ session, doc, state, offline, runtime });
  live.current = { session, doc, state, offline, runtime };

  useEffect(() => { setHeight(120); }, [session]);

  useEffect(() => {
    let n = 0;
    const add = (dir: Ev["dir"], kind: string, text: string, json?: unknown) =>
      setEvents((l) => [...l.slice(-80), { n: ++n + Date.now(), at: performance.now(), dir, kind, text: text.slice(0, 300), json }]);
    const onMsg = (e: MessageEvent) => {
      const win = frameRef.current?.contentWindow;
      if (!win || e.source !== win) return;
      const m = e.data;
      if (!m || typeof m !== "object" || typeof m.k !== "string") return;
      const cur = live.current;
      if (m.k === "frame-ready") { if (cur.doc) win.postMessage({ k: "load", doc: cur.doc }, "*"); return; }
      if (m.f !== cur.session) return;
      if (m.k === "size" || m.k === "ready") {
        if (typeof m.h === "number" && Number.isFinite(m.h)) setHeight(Math.max(50, Math.min(600, Math.round(m.h))));
        if (m.k === "ready") add("sys", "ready", "widget called ready()");
        return;
      }
      if (m.k === "log") { if (typeof m.t === "string" && typeof m.m === "string") add(m.t === "error" ? "sys" : "out", m.t.slice(0, 16), m.m); return; }
      if (m.k !== "req") return;
      if (typeof m.id !== "string" || m.id.length > 40 || typeof m.data !== "string" || utf8Bytes(m.data) > 64) return;
      const sess = cur.session;
      add("out", "req", `request("${m.data}") · ${m.tap ? "tap" : "background"}`, { data: m.data, tap: !!m.tap });
      const post = (msg: Doc) => { if (live.current.session === sess) frameRef.current?.contentWindow?.postMessage(msg, "*"); };
      if (cur.offline) {
        setTimeout(() => { add("in", "reject", `${m.data} → TIMEOUT (15 s in Telegram, 2 s here)`, { code: "TIMEOUT" }); post({ k: "ans", id: m.id, code: "TIMEOUT" }); }, 2000);
        return;
      }
      const pre = cur.runtime?.answers?.[cur.state]?.[m.data];
      setTimeout(() => {
        for (const p of pre?.pushes ?? []) {
          if ((p.field === "chatData" || p.field === "publicData") && typeof p.text === "string" && utf8Bytes(p.text) <= 4096) {
            add("in", "push", `${p.field} updated`, parseMaybe(p.text));
            post({ k: "push", field: p.field, text: p.text });
          }
        }
        const result = pre?.result ?? JSON.stringify({ ok: false, err: "bad_request", msg: "(mock) no precomputed answer for this query" });
        add("in", "ans", `answer to "${m.data}"`, parseMaybe(result));
        post({ k: "ans", id: m.id, result });
      }, 250);
    };
    addEventListener("message", onMsg);
    return () => removeEventListener("message", onMsg);
  }, []);

  const doExport = async () => {
    setExportErr("");
    const b = build.current;
    if (!b?.ok) return setExportErr("Fix the build errors first (step 5).");
    const res = await api("/api/widget/export", { widget: wid, lang, sourceHash: b.sourceHash });
    if (!res.ok) {
      const code = res.data?.error?.code;
      return setExportErr(code === "STALE_BUILD" ? "Save first: export uses the saved files, and this build is of your unsaved draft." : errorText(res.data));
    }
    setExported(res.data);
  };

  // widget.json edits from the forms: 2-space JSON, key order kept, trailing newline as before.
  const updateMeta = (fn: (m: Doc) => void) => {
    const src = files["widget.json"];
    if (src === undefined || metaError) return;
    const m = JSON.parse(src);
    fn(m);
    store.setWidgetFile(wid, "widget.json", JSON.stringify(m, null, 2) + (src.endsWith("\n") ? "\n" : ""));
  };

  const addAsset = async (name: string, svg: string, place: "top" | "end" | "none") => {
    const entry = meta.entry ?? "index.html";
    const index = files[entry] ?? "";
    const nextIndex = place === "none" ? index : insertMarker(index, name, place);
    const baseIndex = loaded.widgets[wid]?.files[entry];
    const changes: Doc[] = [{ widgetId: wid, file: name, content: svg }];
    if (nextIndex !== baseIndex) changes.push({ widgetId: wid, file: entry, content: nextIndex, ...(baseIndex !== undefined ? { fromHash: await sha256Text(baseIndex) } : {}) });
    setSaving(true);
    savingRef.current = true;
    try {
      const res = await api("/api/save", { patch: { format: "bot-ui-patch/v1", projectId: loaded.projectId, baseRevision: store.saved.revision, changes } });
      if (!res.ok) { notify(`Image not saved: ${errorText(res.data)}`, "error"); return; }
      const next = await reload();
      if (next) { store.afterSave(next, {}, { [wid]: { [entry]: nextIndex } }); replaceLoaded(next); }
      void refreshGit();
      if (place === "none" && await copyText(marker(name))) notify(`Saved widgets/${wid}/${name}; the marker ${marker(name)} is copied`, "success");
      else notify(`Saved widgets/${wid}/${name} and its marker in ${entry} (not committed, not live)`, "success");
    } finally {
      setSaving(false);
      savingRef.current = false;
    }
  };

  const st: Doc = meta.states?.[state] ?? {};
  const dataBytes = Math.max(st.chatData ? utf8Bytes(JSON.stringify(st.chatData)) : 0, st.publicData ? utf8Bytes(JSON.stringify(st.publicData)) : 0);
  const limits = shown?.limits ?? build.current?.limits ?? { rawBytes: 32768, compressedBytes: 4096, dataBytes: 1024 };
  const over = shown && (shown.rawBytes > limits.rawBytes || shown.compressedBytes > limits.compressedBytes || dataBytes > limits.dataBytes);
  const near = shown && !over && (shown.compressedBytes > limits.compressedBytes * 0.85 || shown.rawBytes > limits.rawBytes * 0.85);
  const th = runtime?.themes?.[theme] ?? {};
  const scheme = frameScheme(th);
  const codeTabs = names.filter((n) => !n.endsWith(".svg"));
  const svgs = names.filter((n) => n.endsWith(".svg"));
  const projectLocales = locales(loaded.project);
  const statusText = !shown ? "No build yet" : over ? "Over a limit: Telegram refuses it" : near ? "Close to a limit" : "Within limits";

  const codeEditor = (big: boolean) => (
    <div className={cn("flex min-h-0 flex-col", big && "h-full")}>
      <div role="tablist" aria-label="Widget files" className="mb-2 flex flex-wrap gap-1 rounded-lg bg-muted p-0.5"
        onKeyDown={(e) => {
          const all = [...codeTabs, "built"];
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          const i = all.indexOf(tab), j = (i + (e.key === "ArrowRight" ? 1 : all.length - 1)) % all.length;
          setTab(all[j]);
          requestAnimationFrame(() => document.getElementById(`wtab-${big ? "w" : "n"}-${all[j]}`)?.focus());
        }}>
        {[...codeTabs, "built"].map((n) => (
          <button key={n} id={`wtab-${big ? "w" : "n"}-${n}`} role="tab" type="button" aria-selected={tab === n} tabIndex={tab === n ? 0 : -1} onClick={() => setTab(n)}
            className="rounded-md px-2.5 py-1 font-mono text-[11.5px] text-muted-foreground aria-selected:bg-background aria-selected:text-foreground aria-selected:shadow-sm">
            {n === "built" ? "built result" : n}{store.data.widgets[wid]?.[n] !== undefined ? " •" : ""}
          </button>
        ))}
      </div>
      {tab === "built" ? (
        shown ? <CodeView className={cn(big && "min-h-0 flex-1")} maxHeight={big ? "calc(90svh - 9rem)" : "26rem"} tabs={[{ id: "b", label: `Built for ${shown.lang}${isPrevious ? " (previous)" : ""}`, code: shown.html, lang: "html", filename: `${wid}.${shown.lang}.html`, mime: "text/html" }]} />
          : <p className="p-4 text-sm text-muted-foreground">No successful build yet.</p>
      ) : (
        <CodeArea id={`wf-${big ? "w" : "n"}-${tab}`} label={tab} value={files[tab] ?? ""} onChange={(v) => store.setWidgetFile(wid, tab, v)} className={big ? "min-h-0 flex-1" : "h-[26rem]"} />
      )}
    </div>
  );

  const preview = (
    <div className="space-y-3">
      <PreviewToolbar>
        <Segmented size="xs" label="Chat theme" value={theme} onChange={setTheme} options={Object.keys(runtime?.themes ?? { light: 1, dark: 1 }).filter((t) => t !== "outgoing").map((t) => ({ value: t, label: t === "light" ? "Light" : t === "dark" ? "Dark" : t }))} />
        <Segmented size="xs" label="Bubble width" value={String(width)} onChange={(v) => setWidth(Number(v))} options={WIDTHS.map((w) => ({ value: String(w), label: String(w) }))} />
        {langs.length > 1 && <Segmented size="xs" label="Widget language" value={lang} onChange={setLang} options={langs.map((l) => ({ value: l, label: l.toUpperCase() }))} />}
        <div className="w-32"><EnumSelect size="sm" label="Test state" value={state} onChange={setState} options={states.map((s) => ({ value: s, label: s }))} /></div>
        <span className="ml-auto flex items-center gap-1">
          <Button size="icon" variant={offline ? "default" : "ghost"} className="size-8" aria-pressed={offline} onClick={() => setOffline(!offline)} title="Bot offline: requests time out" aria-label="Bot offline"><WifiOff className="size-4" /></Button>
          <Button size="icon" variant="ghost" className="size-8" onClick={() => setReset((r) => r + 1)} title="Restart the widget" aria-label="Restart the widget"><RefreshCw className="size-4" /></Button>
        </span>
      </PreviewToolbar>
      <figure className="overflow-hidden rounded-2xl ring-1 ring-border">
        <div className="flex justify-center px-3 py-6" style={{ background: th._chat ?? "#b9cea0" }}>
          <div className="max-w-full overflow-hidden rounded-2xl rounded-bl-md shadow-sm" style={{ width, background: th.bg_color ?? "#fff", color: th.text_color ?? "#000", colorScheme: scheme }}>
            {doc ? (
              <iframe key={session} ref={frameRef} title={`Widget ${wid} preview`} sandbox="allow-scripts" src="/preview-frame.html" scrolling="no"
                className="block w-full border-0" style={{ height, colorScheme: scheme }} />
            ) : (
              <div className="p-4 text-sm opacity-70">{build.status === "updating" || !runtime ? "Building…" : "No successful build yet."}</div>
            )}
            <div className="flex items-end gap-2 px-3 pt-1 pb-1.5 text-[14px]">
              <span className="min-w-0 flex-1">{shown?.caption}</span>
              <span className="shrink-0 text-[11px] opacity-60">10:00</span>
            </div>
          </div>
        </div>
        <figcaption className="flex flex-wrap items-center gap-2 border-t bg-background px-3 py-1.5 text-[11px] text-muted-foreground">
          <span aria-live="polite" className={cn("rounded-full px-2 py-0.5 font-medium", build.status === "updating" ? "bg-muted" : build.status === "error" ? "bg-red-100 text-red-900" : "bg-emerald-100 text-emerald-900")}>
            {build.status === "updating" ? "building…" : build.status === "error" ? "build failed" : build.status === "ok" ? "up to date" : "waiting"}
          </span>
          {isPrevious && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">showing the previous build</span>}
          <span>{statusText}</span>
          <span className="ml-auto">Browser approximation; Telegram runs widgets in QuickJS</span>
        </figcaption>
      </figure>
    </div>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="sticky top-14 z-20 flex flex-wrap items-center gap-2 border-b bg-background/95 px-4 py-2.5 backdrop-blur">
        <WidgetSwitcher current={wid} onNew={onNew} />
        <DraftBadge draft={draft} />
        {meta.title && <span className="hidden truncate text-sm text-muted-foreground sm:inline">{meta.title}</span>}
        <span className="ml-auto flex items-center gap-2">
          {draft && <Button size="sm" variant="ghost" onClick={() => store.resetWidget(wid)}><RotateCcw className="size-3.5" /> Reset</Button>}
          <Button asChild size="sm" variant="outline" className={cn(!draft && "pointer-events-none opacity-50")} aria-disabled={!draft || undefined}>
            <a href={href("changes")} tabIndex={draft ? undefined : -1}><Save className="size-3.5" /> Save</a>
          </Button>
          <Button size="sm" onClick={doExport} disabled={!build.current?.ok}><Download className="size-3.5" /> Export</Button>
        </span>
        {exportErr && <p role="alert" className="w-full text-right text-xs text-destructive">{exportErr}</p>}
      </div>

      <div className="grid flex-1 grid-cols-1 gap-5 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.85fr)]">
        <div className="lg:order-2">
          <div className="lg:sticky lg:top-[7.75rem]">{preview}</div>
        </div>

        <div className="min-w-0 space-y-3 lg:order-1">
          {metaError && <Alert variant="destructive"><AlertTitle>widget.json is not valid JSON</AlertTitle><AlertDescription>{metaError}. Fix it in step 2; the forms are paused.</AlertDescription></Alert>}

          <Step n={1} title="Widget" hint="Which widget, its name and the languages it is built in." open={open.has(1)} onToggle={() => toggle(1)}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Widget">
                <div className="flex items-center gap-2"><WidgetSwitcher current={wid} onNew={onNew} /><Button size="sm" variant="outline" onClick={onNew}><Plus className="size-3.5" /> New</Button></div>
              </Field>
              <Field label="Title (for you; not shown to users)" htmlFor={`${wid}-title`}>
                <Input id={`${wid}-title`} value={meta.title ?? ""} disabled={!!metaError} onChange={(e) => updateMeta((m) => { m.title = e.target.value; })} />
              </Field>
            </div>
            <Field label="Languages it is built in">
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Languages">
                {projectLocales.map((l) => {
                  const on = langs.includes(l);
                  return (
                    <button key={l} type="button" aria-pressed={on} disabled={!!metaError || (on && langs.length === 1)}
                      onClick={() => updateMeta((m) => { const cur: string[] = m.languages?.length ? m.languages : [defaultLocale(loaded.project)]; m.languages = on ? cur.filter((x) => x !== l) : projectLocales.filter((x) => x === l || cur.includes(x)); })}
                      className="rounded-full px-3 py-1 font-mono text-xs uppercase ring-1 ring-border aria-pressed:bg-foreground aria-pressed:text-background aria-pressed:ring-foreground disabled:opacity-50">{l}</button>
                  );
                })}
              </div>
            </Field>
          </Step>

          <Step n={2} title="Look" hint="The HTML, CSS and JS that draw it, and its images. Most of the time you can leave this closed." open={open.has(2)} onToggle={() => toggle(2)}
            right={<Button size="sm" variant="ghost" className="h-8" onClick={() => setWide(true)}><Expand className="size-3.5" /> Open wide</Button>}>
            {codeEditor(false)}
            <details className="rounded-xl bg-muted/40 p-3">
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium"><ImageUp className="size-4" /> Images (SVG){svgs.length > 0 && <span className="text-xs text-muted-foreground">· {svgs.length}</span>}</summary>
              <div className="mt-3 space-y-3">
                <p className="text-xs text-muted-foreground">A <code className="font-mono">&lt;!--@file name.svg--&gt;</code> marker in the HTML puts the image there. Turn a photo or logo into a small SVG below.</p>
                {svgs.length > 0 && (
                  <ul className="space-y-1">
                    {svgs.map((n) => (
                      <li key={n} className="flex items-center gap-2 rounded-lg bg-background px-2 py-1.5 text-xs">
                        <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(files[n])}`} alt="" className="size-6 object-contain" />
                        <span className="min-w-0 flex-1 truncate font-mono">{n}</span>
                        <span className="font-mono text-muted-foreground">{utf8Bytes(files[n]).toLocaleString()} B</span>
                        <button type="button" className="rounded p-1 text-muted-foreground hover:text-foreground" aria-label={`Copy the marker for ${n}`}
                          onClick={async () => { if (await copyText(marker(n))) notify(`Copied ${marker(n)}`, "success"); }}><Copy className="size-3.5" /></button>
                      </li>
                    ))}
                  </ul>
                )}
                <PhotoToSvg existing={svgs} onAdd={addAsset} busy={saving} />
              </div>
            </details>
          </Step>

          <Step n={3} title="What the bot sends (chat_data) and test states" open={open.has(3)} onToggle={() => toggle(3)}
            hint="chat_data is the small per-message data your bot writes for the widget; states are only test examples for this preview.">
            <div className={cn(metaError && "pointer-events-none opacity-50")}>
              <DataSection bare wid={wid} meta={meta} update={updateMeta} state={state} setState={setState} limit={limits.dataBytes} />
            </div>
          </Step>

          <Step n={4} title="Message" hint="The caption under the widget, how it is sent, and the screen used where widgets are unavailable." open={open.has(4)} onToggle={() => toggle(4)}>
            <div className={cn("space-y-5", metaError && "pointer-events-none opacity-50")}>
              <MessageSection bare wid={wid} meta={meta} update={updateMeta} lang={lang} />
              <div className="border-t pt-4"><p className="mb-2 text-xs font-semibold">How it is sent (sendWidget)</p><SendSection bare meta={meta} update={updateMeta} /></div>
            </div>
          </Step>

          <Step n={5} title="Check" hint="Build status, Telegram's size limits and the requests the widget made in the preview." open={open.has(5)} onToggle={() => toggle(5)}>
            <div className="space-y-2.5">
              <Meter label="HTML" value={shown?.rawBytes ?? 0} limit={limits.rawBytes} />
              <Meter label="Compressed (zlib-9)" value={shown?.compressedBytes ?? 0} limit={limits.compressedBytes} />
              <Meter label={`chat_data · ${state}`} value={dataBytes} limit={limits.dataBytes} />
              <p className={cn("rounded-lg px-2.5 py-1.5 text-xs font-medium", !shown ? "bg-muted text-muted-foreground" : over ? "bg-red-100 text-red-900" : near ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900")} aria-live="polite">
                {statusText}{shown && !over ? " · ready to export" : ""}
              </p>
            </div>
            {build.status === "error" && (
              <Alert variant="destructive"><AlertTitle className="text-xs">Build errors</AlertTitle>
                <AlertDescription><ul className="list-disc pl-4 font-mono text-[11px]">{(build.current?.errors?.length ? build.current.errors : [build.message]).map((e, i) => <li key={i}>{e}</li>)}</ul></AlertDescription>
              </Alert>
            )}
            {(build.current?.warnings?.length ?? 0) > 0 && (
              <Alert><AlertTitle className="text-xs">Warnings</AlertTitle><AlertDescription><ul className="list-disc pl-4 font-mono text-[11px]">{build.current!.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></AlertDescription></Alert>
            )}
            <Timeline events={events} onClear={() => setEvents([])} />
          </Step>
        </div>
      </div>

      <Dialog open={wide} onOpenChange={setWide}>
        <DialogContent className="flex h-[90svh] flex-col sm:max-w-[min(96vw,1400px)]">
          <DialogHeader>
            <DialogTitle>Look · {wid}</DialogTitle>
            <DialogDescription>Edits are drafts; the preview behind updates as you type.</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1">{codeEditor(true)}</div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!exported} onOpenChange={(o) => { if (!o) setExported(null); }}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Export {wid} ({lang})</DialogTitle>
            <DialogDescription>Built from the saved files (source hash <span className="font-mono">{String(exported?.sourceHash ?? "").slice(7, 19)}</span>). Your bot sends the payload with sendWidget.</DialogDescription>
          </DialogHeader>
          {exported && (
            <>
              <CodeView maxHeight="50svh" tabs={[
                { id: "html", label: "HTML", code: exported.html, lang: "html", filename: `${wid}.${lang}.html`, mime: "text/html" },
                { id: "payload", label: "sendWidget payload", code: JSON.stringify(exported.payload, null, 2), lang: "json", filename: `${wid}.${lang}.sendWidget.json` },
              ]} />
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={() => download(`${wid}.${lang}.sendWidget.json`, JSON.stringify(exported.payload, null, 2))}><Download className="size-4" /> Payload</Button>
                <Button onClick={() => download(`${wid}.${lang}.html`, exported.html, "text/html")}><Download className="size-4" /> HTML</Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function WidgetsView({ id }: { id: string | null }) {
  const { loaded, caps, working } = useStudio();
  const [creating, setCreating] = useState(false);
  const ids = Object.keys(loaded.widgets).sort();
  if (!caps.widgets) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 p-4">
        <Alert>
          <AlertTitle>Widgets are not in the artifact</AlertTitle>
          <AlertDescription>This file carries no widget sources. Open the project with <code className="font-mono">bot-ui studio</code> to create, edit, build and preview widgets.</AlertDescription>
        </Alert>
        <ul className="space-y-4">
          {ids.map((wid) => {
            const fbId = loaded.widgets[wid].meta.fallbackScreen;
            const fb = fbId && working.screens[fbId];
            return (
              <li key={wid} className="space-y-1.5">
                <p className="text-sm"><span className="font-mono">{wid}</span> {loaded.widgets[wid].meta.title} · fallback <span className="font-mono">{fbId ?? "none"}</span></p>
                {fb && <div className="max-w-md"><ScreenPreview logical={renderScreen(loaded.project, fb, { values: exampleValues(loaded.project) })} theme="light" contextLabel="fallback message" hideWidget /></div>}
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
  const wid = id && ids.includes(id) ? id : ids[0];
  return (
    <>
      {wid ? <Workbench key={wid} wid={wid} onNew={() => setCreating(true)} /> : (
        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <ImageUp className="size-8 text-muted-foreground" aria-hidden />
          <h2 className="text-lg font-semibold">No widgets yet</h2>
          <p className="text-sm text-muted-foreground">A widget is a small interactive card your bot sends in a private chat. Start empty or from one of the ready examples.</p>
          <Button onClick={() => setCreating(true)}><Plus className="size-4" /> New widget</Button>
        </div>
      )}
      <NewWidgetDialog open={creating} onOpenChange={setCreating} />
    </>
  );
}
