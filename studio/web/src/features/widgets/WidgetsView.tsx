// Widget constructor: settings and checks on the left, a resizable split of the source editor and
// the live chat preview, a request timeline under the preview. Builds come from /api/widget/build
// (debounced, late answers dropped); the frame is the sandboxed /preview-frame.html.
import { ArrowDownLeft, ArrowUpRight, ChevronRight, Code2, Copy, Download, Maximize2, Minimize2, PanelRightClose, RefreshCw, RotateCcw, Save, Wifi, WifiOff } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { renderScreen, type Doc } from "@/core/render.ts";
import { CodeArea } from "@/components/code-area";
import { CodeBlock, CodeView } from "@/components/code-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { api, errorText } from "@/lib/api";
import { copyText, defaultLocale, download, exampleValues, fnv1a, sha256Text, utf8Bytes } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, Segmented } from "../inspector/fields";
import { DraftBadge } from "../inspector/ScreenInspector";
import { ScreenPreview } from "../preview/Telegram";
import { composeDoc, type Runtime } from "./frame";
import { insertMarker, marker, PhotoToSvg } from "./PhotoToSvg";
import { DataSection, MessageSection, Section, SendSection } from "./WidgetForms";

interface Build {
  ok: boolean; html: string; rawBytes: number; compressedBytes: number; limits: { rawBytes: number; compressedBytes: number; dataBytes: number };
  errors: string[]; warnings: string[]; caption?: string | null; sourceHash: string; payload?: Doc; lang: string; draft?: boolean;
}
type BuildState = { status: "idle" | "updating" | "ok" | "error"; current: Build | null; message?: string };
type Ev = { n: number; at: number; dir: "out" | "in" | "sys"; kind: string; text: string; json?: unknown };

const ORDER = ["index.html", "style.css", "widget.js", "widget.json"];
const CODE_KEY = "bot-ui-studio:widget-code";

function Meter({ label, value, limit }: { label: string; value: number; limit: number }) {
  const pct = Math.min(100, Math.round((value / limit) * 100));
  const over = value > limit;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span className="text-muted-foreground">{label}</span><span className={cn("font-mono tabular-nums", over && "font-semibold text-destructive")}>{value.toLocaleString()} / {limit.toLocaleString()}</span></div>
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
    <section className="rounded-xl ring-1 ring-border" aria-label="Requests and state">
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <h3 className="text-xs font-semibold">Requests and state</h3>
        <span className="text-[11px] text-muted-foreground">{events.length} events · answered from precomputed demo answers, nothing leaves the page</span>
        {events.length > 0 && <Button size="sm" variant="ghost" className="ml-auto h-6 px-2 text-[11px]" onClick={onClear}>Clear</Button>}
      </header>
      <ol className="max-h-72 overflow-y-auto">
        {events.length === 0 && <li className="px-3 py-4 text-center text-xs text-muted-foreground">Tap something in the widget: its requests, answers and pushes appear here.</li>}
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
    </section>
  );
}

const parseMaybe = (s: unknown) => { if (typeof s !== "string") return s; try { return JSON.parse(s); } catch { return s; } };

function Workbench({ wid }: { wid: string }) {
  const { store, loaded, notify, reload, replaceLoaded, refreshGit, saving: savingRef } = useStudio();
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
  const seq = useRef(0);
  const frameRef = useRef<HTMLIFrameElement>(null);

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
    if (!b?.ok) return setExportErr("Build without errors first.");
    const res = await api("/api/widget/export", { widget: wid, lang, sourceHash: b.sourceHash });
    if (!res.ok) {
      const code = res.data?.error?.code;
      return setExportErr(code === "STALE_BUILD" ? "STALE_BUILD: export uses the saved sources, and this build is of your unsaved draft. Save first, then export." : errorText(res.data));
    }
    setExported(res.data);
  };

  const [codeMode, setCodeModeState] = useState<"hidden" | "narrow" | "wide">(() => {
    try { const v = localStorage.getItem(CODE_KEY); return v === "hidden" || v === "wide" ? v : "narrow"; } catch { return "narrow"; }
  });
  const setCodeMode = (m: "hidden" | "narrow" | "wide") => { setCodeModeState(m); try { localStorage.setItem(CODE_KEY, m); } catch { /* storage blocked */ } };
  const [saving, setSaving] = useState(false);

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
      if (!res.ok) { notify(`Asset not saved: ${errorText(res.data)}`, "error"); return; }
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
  const fileTabs = [...names, "built"];
  const svgs = names.filter((n) => n.endsWith(".svg"));
  const codeCols = codeMode === "hidden" ? "lg:grid-cols-[minmax(0,1fr)_400px_44px]" : codeMode === "wide" ? "lg:grid-cols-[minmax(0,0.8fr)_400px_minmax(0,1.4fr)]" : "lg:grid-cols-[minmax(0,1fr)_400px_minmax(0,0.6fr)]";

  return (
    <div className={cn("grid min-h-0 flex-1 grid-cols-1", codeCols)}>
      <div className="@container min-w-0 space-y-4 overflow-y-auto p-4 lg:h-[calc(100svh-3.5rem)]" aria-label="Widget settings">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-mono text-base font-semibold">{wid}</h2>
          <DraftBadge draft={draft} />
          {meta.title && <span className="text-sm text-muted-foreground">{meta.title}</span>}
          <span className="ml-auto flex items-center gap-2">
            {Object.keys(loaded.widgets).length > 1 && (
              <span className="w-44"><EnumSelect label="Widget" size="sm" value={wid} onChange={(v) => go("widgets", v)} options={Object.keys(loaded.widgets).sort().map((w) => ({ value: w, label: w }))} /></span>
            )}
            {draft && <Button size="sm" variant="ghost" className="h-8" onClick={() => store.resetWidget(wid)}><RotateCcw className="size-3.5" /> Reset draft</Button>}
            {draft && <Button asChild size="sm" className="h-8"><a href={href("changes")}><Save className="size-3.5" /> Save to files</a></Button>}
          </span>
        </div>
        {metaError && <Alert variant="destructive"><AlertTitle>widget.json is not valid JSON</AlertTitle><AlertDescription>{metaError}. Fix it in the code panel; the forms below are paused.</AlertDescription></Alert>}
        <div className={cn("grid gap-4 @3xl:grid-cols-2", metaError && "pointer-events-none opacity-50")}>
          <MessageSection wid={wid} meta={meta} update={updateMeta} lang={lang} />
          <Section title="Preview environment" hint="Only for this preview; nothing here is saved.">
            {langs.length > 1 && <Field label="Language"><Segmented label="Widget language" value={lang} onChange={setLang} options={langs.map((l) => ({ value: l, label: l }))} /></Field>}
            <Field label="Chat theme"><Segmented label="Chat theme" value={theme} onChange={setTheme} options={Object.keys(runtime?.themes ?? { light: 1, dark: 1 }).map((t) => ({ value: t, label: t }))} /></Field>
            <Field label={<>Bubble width <span className="font-mono">{width} px</span></>}>
              <Slider min={200} max={600} step={10} value={[width]} onValueChange={([v]) => setWidth(v)} aria-label="Bubble width" />
            </Field>
            <label className="flex items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-1.5">{offline ? <WifiOff className="size-4" /> : <Wifi className="size-4" />} Bot offline <span className="text-xs text-muted-foreground">(requests time out)</span></span>
              <Switch checked={offline} onCheckedChange={setOffline} aria-label="Bot offline" />
            </label>
            <Button size="sm" variant="outline" onClick={() => setReset((r) => r + 1)}><RefreshCw className="size-3.5" /> Reset the widget</Button>
          </Section>
          <DataSection wid={wid} meta={meta} update={updateMeta} state={state} setState={setState} limit={limits.dataBytes} />
          <div className="space-y-4">
            <SendSection meta={meta} update={updateMeta} />
            <Section title="Assets" hint="Inline SVG files: a <!--@file name.svg--> marker in the HTML puts the markup there.">
              {svgs.length > 0 && (
                <ul className="space-y-1">
                  {svgs.map((n) => (
                    <li key={n} className="flex items-center gap-2 rounded-lg bg-muted/40 px-2 py-1.5 text-xs">
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
            </Section>
          </div>
        </div>
      </div>

      <section className="order-first min-w-0 space-y-3 overflow-y-auto border-b bg-muted/20 p-4 lg:order-none lg:h-[calc(100svh-3.5rem)] lg:border-b-0 lg:border-l" aria-label="Preview">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold">Preview</span>
          <span aria-live="polite" className={cn("rounded-full px-2 py-0.5", build.status === "updating" ? "bg-muted" : build.status === "error" ? "bg-red-100 text-red-900" : "bg-emerald-100 text-emerald-900")}>
            {build.status === "updating" ? "building…" : build.status === "error" ? "build failed" : build.status === "ok" ? `built${build.current?.draft ? " from your draft" : ""}` : "waiting"}
          </span>
          {isPrevious && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">previous build</span>}
          <span className="ml-auto font-mono text-muted-foreground">{state} · {lang}</span>
        </div>
        <figure className="overflow-hidden rounded-xl ring-1 ring-border">
          <div className="flex justify-center px-3 py-5" style={{ background: th._chat ?? "#b9cea0" }}>
            <div className="max-w-full overflow-hidden rounded-2xl rounded-bl-md shadow-sm" style={{ width, background: th.bg_color ?? "#fff", color: th.text_color ?? "#000" }}>
              {doc ? (
                <iframe key={session} ref={frameRef} title={`Widget ${wid} preview`} sandbox="allow-scripts" src="/preview-frame.html" scrolling="no" className="block w-full border-0" style={{ height }} />
              ) : (
                <div className="p-4 text-sm opacity-70">{build.status === "updating" || !runtime ? "Building…" : "No successful build yet."}</div>
              )}
              <div className="flex items-end gap-2 px-3 pt-1 pb-1.5 text-[14px]">
                <span className="min-w-0 flex-1">{shown?.caption}</span>
                <span className="shrink-0 text-[11px] opacity-60">10:00</span>
              </div>
            </div>
          </div>
          <figcaption className="border-t bg-background px-3 py-1.5 text-[11px] text-muted-foreground">Browser approximation, not Telegram: real widgets run in QuickJS · {width} px · {height} px high</figcaption>
        </figure>
        <div className="space-y-2.5 rounded-xl bg-card p-3 ring-1 ring-border">
          <Meter label="HTML" value={shown?.rawBytes ?? 0} limit={limits.rawBytes} />
          <Meter label="zlib-9" value={shown?.compressedBytes ?? 0} limit={limits.compressedBytes} />
          <Meter label={`data · ${state}`} value={dataBytes} limit={limits.dataBytes} />
          <p className={cn("rounded-lg px-2 py-1.5 text-xs font-medium", !shown ? "bg-muted text-muted-foreground" : over ? "bg-red-100 text-red-900" : near ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900")} aria-live="polite">
            {!shown ? "No build yet" : over ? "Over the limit: Telegram refuses it" : near ? "Close to the limit: keep headroom" : "Within limits · ready to send"}
          </p>
          {build.status === "error" && (
            <Alert variant="destructive"><AlertTitle className="text-xs">Build errors</AlertTitle>
              <AlertDescription><ul className="list-disc pl-4 font-mono text-[11px]">{(build.current?.errors?.length ? build.current.errors : [build.message]).map((e, i) => <li key={i}>{e}</li>)}</ul></AlertDescription>
            </Alert>
          )}
          {(build.current?.warnings?.length ?? 0) > 0 && (
            <Alert><AlertTitle className="text-xs">Warnings</AlertTitle><AlertDescription><ul className="list-disc pl-4 font-mono text-[11px]">{build.current!.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></AlertDescription></Alert>
          )}
          <Button className="w-full" onClick={doExport} disabled={!build.current?.ok}><Download className="size-4" /> Export HTML + sendWidget payload</Button>
          {exportErr && <p role="alert" className="text-xs text-destructive">{exportErr}</p>}
        </div>
        <Timeline events={events} onClear={() => setEvents([])} />
      </section>

      <section className={cn("flex min-w-0 flex-col border-t bg-background lg:h-[calc(100svh-3.5rem)] lg:border-t-0 lg:border-l", codeMode === "hidden" && "items-center")} aria-label="Code">
        {codeMode === "hidden" ? (
          <button type="button" onClick={() => setCodeMode("narrow")} className="flex w-full items-center justify-center gap-2 py-3 text-xs text-muted-foreground hover:text-foreground lg:h-full lg:flex-col lg:py-0" aria-label="Show the code">
            <Code2 className="size-4" /><span className="lg:[writing-mode:vertical-rl]">Code</span>
          </button>
        ) : (
          <div className="flex min-h-[50svh] min-w-0 flex-1 flex-col p-3 lg:min-h-0">
            <div className="mb-2 flex items-center gap-1">
              <span className="text-xs font-semibold">Code</span>
              <span className="text-[11px] text-muted-foreground">for when you need it</span>
              <span className="ml-auto flex gap-0.5">
                <Button size="icon" variant="ghost" className="size-7" onClick={() => setCodeMode(codeMode === "wide" ? "narrow" : "wide")} aria-label={codeMode === "wide" ? "Make the code panel narrow" : "Make the code panel wide"}>
                  {codeMode === "wide" ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
                </Button>
                <Button size="icon" variant="ghost" className="size-7" onClick={() => setCodeMode("hidden")} aria-label="Hide the code"><PanelRightClose className="size-3.5" /></Button>
              </span>
            </div>
            <div role="tablist" aria-label="Widget files" className="mb-2 flex flex-wrap gap-1 rounded-lg bg-muted p-0.5"
              onKeyDown={(e) => {
                if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                const i = fileTabs.indexOf(tab), j = (i + (e.key === "ArrowRight" ? 1 : fileTabs.length - 1)) % fileTabs.length;
                setTab(fileTabs[j]);
                requestAnimationFrame(() => document.getElementById(`wtab-${fileTabs[j]}`)?.focus());
              }}>
              {fileTabs.map((n) => (
                <button key={n} id={`wtab-${n}`} role="tab" type="button" aria-selected={tab === n} aria-controls={`wf-${n}`} tabIndex={tab === n ? 0 : -1} onClick={() => setTab(n)}
                  className="rounded-md px-2 py-1 font-mono text-[11px] text-muted-foreground aria-selected:bg-background aria-selected:text-foreground aria-selected:shadow-sm">
                  {n === "built" ? "built.html" : n}{store.data.widgets[wid]?.[n] !== undefined ? " •" : ""}
                </button>
              ))}
            </div>
            <div role="tabpanel" id={`wf-${tab}`} className="flex min-h-0 flex-1 flex-col">
              {tab === "built" ? (
                shown ? <CodeView className="min-h-0 flex-1" maxHeight="calc(100svh - 12rem)" tabs={[{ id: "b", label: `Built for ${shown.lang}${isPrevious ? " (previous)" : ""}`, code: shown.html, lang: "html", filename: `${wid}.${shown.lang}.html`, mime: "text/html" }]} />
                  : <p className="p-4 text-sm text-muted-foreground">No successful build yet.</p>
              ) : (
                <CodeArea id={`wf-${tab}-ta`} label={tab} value={files[tab] ?? ""} onChange={(v) => store.setWidgetFile(wid, tab, v)} className="min-h-[40svh] flex-1" />
              )}
            </div>
          </div>
        )}
      </section>

      <Dialog open={!!exported} onOpenChange={(o) => { if (!o) setExported(null); }}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Export {wid} ({lang})</DialogTitle>
            <DialogDescription>Built from the saved sources, source hash <span className="font-mono">{String(exported?.sourceHash ?? "").slice(7, 19)}</span>. The bot sends the payload with sendWidget.</DialogDescription>
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
  const ids = Object.keys(loaded.widgets).sort();
  if (!caps.widgets) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 p-4">
        <Alert>
          <AlertTitle>Widgets are not in the artifact</AlertTitle>
          <AlertDescription>This file carries no widget sources. Open the project with <code className="font-mono">bot-ui studio</code> to edit, build and preview widgets.</AlertDescription>
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
  if (!ids.length) return <p className="p-4 text-sm text-muted-foreground">This project has no widgets (widgets/&lt;id&gt;/widget.json).</p>;
  const wid = id && ids.includes(id) ? id : ids[0];
  return <Workbench key={wid} wid={wid} />;
}
