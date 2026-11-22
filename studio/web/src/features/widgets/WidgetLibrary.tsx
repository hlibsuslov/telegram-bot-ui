// Widget library: every template (blank, skill gallery, recipes) as a card with a live thumbnail.
// Thumbnails reuse the sandboxed /preview-frame.html protocol, load lazily (IntersectionObserver)
// and at most three template builds run at a time.
import { ArrowLeft, BookOpen, FileQuestion, Languages, Library, Loader2, Package, Plus, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { href } from "@/lib/route";
import { cn } from "@/lib/utils";
import { Segmented } from "../inspector/fields";
import { composeDoc, frameScheme, type Runtime } from "./frame";

export interface Template { id: string; title: string; summary: string }
interface PreviewDoc { ok: boolean; html: string; chatData?: Doc; publicData?: Doc; now?: number; languages?: string[]; rawBytes?: number; compressedBytes?: number }

// One shared runtime and a small queue for template builds.
let runtimePromise: Promise<Runtime | null> | null = null;
const getRuntime = () => (runtimePromise ??= api<Runtime>("/api/widget/runtime", { widget: "" }).then((r) => (r.ok ? r.data : null)));
const previewCache = new Map<string, Promise<PreviewDoc | null>>();
let running = 0;
const waiting: (() => void)[] = [];
async function limited<T>(fn: () => Promise<T>): Promise<T> {
  if (running >= 3) await new Promise<void>((r) => waiting.push(r));
  running++;
  try { return await fn(); } finally { running--; waiting.shift()?.(); }
}
function loadPreview(id: string): Promise<PreviewDoc | null> {
  if (!previewCache.has(id)) previewCache.set(id, limited(() => api<PreviewDoc>("/api/widget/template-preview", { template: id }).then((r) => (r.ok && r.data.ok ? r.data : null))));
  return previewCache.get(id)!;
}

export const sourceOf = (id: string) => (id === "blank" ? "blank" : id.split(":")[0]);

function LiveThumb({ t, onInfo }: { t: Template; onInfo: (d: PreviewDoc) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const [visible, setVisible] = useState(false);
  const [doc, setDoc] = useState<string | null>(null);
  const [state, setState] = useState<"wait" | "ready" | "failed">("wait");
  const [h, setH] = useState(220);
  const session = useMemo(() => `t${Math.random().toString(36).slice(2, 8)}`, []);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { setVisible(true); io.disconnect(); } }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let live = true;
    Promise.all([getRuntime(), loadPreview(t.id)]).then(([rt, p]) => {
      if (!live) return;
      if (!rt || !p) return setState("failed");
      onInfo(p);
      const meta = { states: { default: { chatData: p.chatData, publicData: p.publicData } }, now: p.now, fresh: [] };
      setDoc(composeDoc(rt, p.html, { session, theme: "light", lang: p.languages?.[0] ?? "en", meta, state: "default", offline: false }));
    });
    return () => { live = false; };
    // onInfo is not a dependency: one load per card is enough.
  }, [visible, t.id, session]);

  useEffect(() => {
    if (!doc) return;
    const timer = setTimeout(() => setState((s) => (s === "wait" ? "failed" : s)), 6000);
    const on = (e: MessageEvent) => {
      const win = frame.current?.contentWindow;
      if (!win || e.source !== win || !e.data || typeof e.data !== "object") return;
      const m = e.data;
      if (m.k === "frame-ready") { win.postMessage({ k: "load", doc }, "*"); return; }
      if (m.f !== session) return;
      if ((m.k === "size" || m.k === "ready") && typeof m.h === "number" && Number.isFinite(m.h)) { setH(Math.max(60, Math.min(600, m.h))); setState("ready"); }
    };
    addEventListener("message", on);
    return () => { clearTimeout(timer); removeEventListener("message", on); };
  }, [doc, session]);

  const scale = 0.62;
  return (
    <div ref={box} className="relative flex h-48 items-start justify-center overflow-hidden rounded-xl bg-[#c2d6a9] pt-3" aria-hidden={state !== "failed"}>
      {doc && state !== "failed" && (
        <div className="origin-top overflow-hidden rounded-xl bg-white shadow-sm" style={{ width: 320, height: h, transform: `scale(${scale})`, colorScheme: frameScheme({ _scheme: "light" }) }}>
          <iframe ref={frame} title={`${t.title} preview`} src="/preview-frame.html" scrolling="no" tabIndex={-1}
            className="pointer-events-none block w-full border-0" style={{ height: h, colorScheme: "light" }} />
        </div>
      )}
      {(state === "wait") && <Loader2 className="absolute top-1/2 left-1/2 size-5 -translate-x-1/2 -translate-y-1/2 animate-spin text-black/40" aria-label="Loading the preview" />}
      {state === "failed" && (
        <div className="absolute inset-3 flex flex-col items-center justify-center gap-1.5 rounded-lg bg-white/80 p-3 text-center text-xs text-muted-foreground">
          <FileQuestion className="size-5" aria-hidden />
          <span>No live preview here.</span>
          <span className="line-clamp-2">{t.summary}</span>
        </div>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-[#c2d6a9] to-transparent" />
    </div>
  );
}

export function WidgetLibrary({ onUse, hasWidgets }: { onUse: (t: Template) => void; hasWidgets: boolean }) {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [q, setQ] = useState("");
  const [source, setSource] = useState("all");
  const [info, setInfo] = useState<Record<string, PreviewDoc>>({});
  useEffect(() => { api<{ templates: Template[] }>("/api/widget/templates", {}).then((r) => setTemplates(r.ok ? r.data.templates ?? [] : [])); }, []);
  const list = (templates ?? [])
    .filter((t) => source === "all" || sourceOf(t.id) === source || t.id === "blank")
    .filter((t) => `${t.id} ${t.title} ${t.summary}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (a.id === "blank" ? -1 : b.id === "blank" ? 1 : 0));
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          {hasWidgets && <a href={href("widgets")} className="mb-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="size-3.5" /> Back to your widgets</a>}
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight"><Library className="size-5" /> Widget library</h2>
          <p className="text-sm text-muted-foreground">Pick a ready widget or start blank. Previews use example data; nothing is created until you press “Use this”.</p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search widgets" aria-label="Search widgets" className="pl-8" />
        </div>
        <Segmented label="Source" value={source} onChange={setSource}
          options={[{ value: "all", label: "All" }, { value: "gallery", label: "Gallery" }, { value: "recipe", label: "Recipes" }]} />
      </div>
      {templates === null && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading the library…</p>}
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-4" aria-label="Widget templates">
        {list.map((t) => {
          const p = info[t.id];
          const src = sourceOf(t.id);
          return (
            <li key={t.id} className="flex flex-col overflow-hidden rounded-2xl bg-card ring-1 ring-border">
              <LiveThumb t={t} onInfo={(d) => setInfo((m) => (m[t.id] ? m : { ...m, [t.id]: d }))} />
              <div className="flex flex-1 flex-col gap-2 p-3">
                <div>
                  <h3 className="text-sm font-semibold">{t.title}</h3>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{t.summary}</p>
                </div>
                <div className="flex flex-wrap gap-1 text-[10.5px]">
                  <span className={cn("inline-flex items-center gap-1 rounded-full px-1.5 py-0.5", src === "recipe" ? "bg-violet-100 text-violet-900" : src === "gallery" ? "bg-sky-100 text-sky-900" : "bg-muted text-muted-foreground")}>
                    {src === "recipe" ? <BookOpen className="size-3" aria-hidden /> : src === "gallery" ? <Sparkles className="size-3" aria-hidden /> : <Plus className="size-3" aria-hidden />}{src}
                  </span>
                  {p?.languages?.length ? <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground"><Languages className="size-3" aria-hidden />{p.languages.join(", ")}</span> : null}
                  {p?.compressedBytes ? <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground"><Package className="size-3" aria-hidden />{(p.compressedBytes / 1024).toFixed(1)} KB</span> : null}
                </div>
                <Button className="mt-auto w-full" onClick={() => onUse(t)}>Use this</Button>
              </div>
            </li>
          );
        })}
      </ul>
      {templates && !list.length && <p className="text-sm text-muted-foreground">No widget matches “{q}”.</p>}
    </div>
  );
}
