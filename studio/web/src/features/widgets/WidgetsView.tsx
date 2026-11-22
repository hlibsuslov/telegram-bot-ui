import { Download, RefreshCw, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { renderScreen, type Doc } from "@/core/render.ts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText } from "@/lib/api";
import { defaultLocale, download, exampleValues, fnv1a, utf8Bytes } from "@/lib/model";
import { href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { Field } from "../inspector/fields";
import { DraftBadge } from "../inspector/ScreenInspector";
import { ScreenPreview } from "../preview/Telegram";
import { DesignPanel, widgetParts, type DesignInfo } from "./DesignPanel";
import { composeDoc, type Runtime } from "./frame";

interface Build {
  ok: boolean; html: string; rawBytes: number; compressedBytes: number; limits: { rawBytes: number; compressedBytes: number; dataBytes: number };
  errors: string[]; warnings: string[]; caption?: string | null; sourceHash: string; payload?: Doc; lang: string; draft?: boolean;
  design?: DesignInfo;
}
type BuildState = { status: "idle" | "updating" | "ok" | "error"; current: Build | null; message?: string };
type LogLine = { t: string; m: string; n: number };

const ORDER = ["index.html", "style.css", "widget.js", "widget.json", "design.json"];
const WIDTHS = [200, 320, 430];

function Meter({ label, value, limit }: { label: string; value: number; limit: number }) {
  const pct = Math.min(100, Math.round((value / limit) * 100));
  const over = value > limit;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span>{label}</span><span className={cn("font-mono", over && "text-destructive")}>{value.toLocaleString()} / {limit.toLocaleString()} B</span></div>
      <div className="h-1.5 rounded bg-muted" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={limit} aria-valuenow={value}>
        <div className={cn("h-full rounded", over ? "bg-destructive" : pct > 85 ? "bg-amber-500" : "bg-emerald-600")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Workbench({ wid }: { wid: string }) {
  const { store, loaded, working, notify } = useStudio();
  const files = store.widgetFiles(wid);
  const draft = !!store.data.widgets[wid];
  const names = useMemo(() => [...Object.keys(files)].sort((a, b) => {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  }), [files]);
  const [tab, setTab] = useState(names[0] ?? "index.html");
  const [mode, setMode] = useState<"design" | "code">("design");
  const design: Doc = useMemo(() => { try { const d = files["design.json"] ? JSON.parse(files["design.json"]) : {}; return d && typeof d === "object" && !Array.isArray(d) ? d : {}; } catch { return {}; } }, [files]);
  const designBroken = useMemo(() => { try { if (files["design.json"]) JSON.parse(files["design.json"]); return false; } catch { return true; } }, [files]);
  const parts = useMemo(() => widgetParts(files), [files]);
  const saveDesign = (next: Doc) => {
    const { preset: _p, version: _v, ...rest } = next;
    const savedHasDesign = loaded.widgets[wid]?.files?.["design.json"] !== undefined;
    if (!Object.keys(rest).length && !savedHasDesign) return store.dropNewWidgetFile(wid, "design.json");
    store.setWidgetFile(wid, "design.json", `${JSON.stringify(next, null, 2)}\n`);
  };
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
  const [log, setLog] = useState<LogLine[]>([]);
  const [exportErr, setExportErr] = useState("");
  const seq = useRef(0);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let live = true;
    api("/api/widget/runtime", { widget: wid }).then((res) => { if (live && res.ok) setRuntime(res.data); else if (live) notify(`Widget runtime: ${errorText(res.data)}`, "error"); });
    return () => { live = false; };
  }, [wid, loaded.revision, notify]);

  // Debounced build of the draft files; a response is used only if it answers the latest request.
  const filesJson = JSON.stringify(files);
  const hasDraft = draft;
  const key = fnv1a(`${filesJson}\u0000${lang}\u0000${state}`);
  useEffect(() => {
    const mine = ++seq.current;
    setBuild((b) => ({ ...b, status: "updating" }));
    const t = setTimeout(async () => {
      const res = await api<Build>("/api/widget/build", { widget: wid, lang, state, ...(hasDraft ? { files: JSON.parse(filesJson) } : {}) });
      if (mine !== seq.current) return; // late answer for an older snapshot
      if (!res.ok) return setBuild({ status: "error", current: null, message: errorText(res.data) });
      const b = res.data;
      setBuild({ status: b.ok ? "ok" : "error", current: b, message: b.ok ? undefined : b.errors?.[0] });
      if (b.ok) setLastGood(b);
    }, 400);
    return () => clearTimeout(t);
  }, [key, wid, lang, state, filesJson, hasDraft]);

  const shown = build.status === "ok" ? build.current : lastGood;
  const isPrevious = !!shown && shown !== build.current;
  const session = `s${fnv1a(`${shown?.sourceHash ?? ""}|${shown?.html.length ?? 0}|${state}|${theme}|${lang}|${offline}|${reset}|${width}`)}${reset}`;
  const doc = shown && runtime ? composeDoc(runtime, shown.html, { session, theme, lang, meta, state, offline }) : null;
  const live = useRef({ session, doc, state, offline, runtime, meta });
  live.current = { session, doc, state, offline, runtime, meta };

  useEffect(() => { setLog([]); setHeight(120); }, [session]);

  useEffect(() => {
    let n = 0;
    const add = (t: string, m: string) => setLog((l) => [...l.slice(-60), { t, m: m.slice(0, 300), n: ++n + Date.now() }]);
    const onMsg = (e: MessageEvent) => {
      const win = frameRef.current?.contentWindow;
      if (!win || e.source !== win) return;
      const m = e.data;
      if (!m || typeof m !== "object" || typeof m.k !== "string") return;
      const cur = live.current;
      if (m.k === "frame-ready") {
        if (cur.doc) win.postMessage({ k: "load", doc: cur.doc }, "*");
        return;
      }
      if (m.f !== cur.session) return;
      if (m.k === "size" || m.k === "ready") {
        if (typeof m.h === "number" && Number.isFinite(m.h)) setHeight(Math.max(50, Math.min(600, Math.round(m.h))));
        return;
      }
      if (m.k === "log") {
        if (typeof m.t === "string" && typeof m.m === "string") add(m.t.slice(0, 16), m.m);
        return;
      }
      if (m.k !== "req") return;
      if (typeof m.id !== "string" || m.id.length > 40 || typeof m.data !== "string" || utf8Bytes(m.data) > 64) return;
      const sess = cur.session;
      add("req", `${m.tap ? "tap" : "background"} ${m.data}`);
      const post = (msg: Doc) => { if (live.current.session === sess) frameRef.current?.contentWindow?.postMessage(msg, "*"); };
      if (cur.offline) {
        setTimeout(() => { add("reject", `${m.data} -> TIMEOUT (15 s in Telegram, 2 s here)`); post({ k: "ans", id: m.id, code: "TIMEOUT" }); }, 2000);
        return;
      }
      const pre = cur.runtime?.answers?.[cur.state]?.[m.data];
      setTimeout(() => {
        for (const p of pre?.pushes ?? []) {
          if ((p.field === "chatData" || p.field === "publicData") && typeof p.text === "string" && utf8Bytes(p.text) <= 4096) {
            add("push", p.field);
            post({ k: "push", field: p.field, text: p.text });
          }
        }
        const result = pre?.result ?? JSON.stringify({ ok: false, err: "bad_request", msg: "(mock) no precomputed answer for this query" });
        add("ans", String(result).slice(0, 160));
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
      return setExportErr(code === "STALE_BUILD" ? "STALE_BUILD: export uses the saved sources; this build is of your unsaved draft. Save first, then export." : errorText(res.data));
    }
    download(`${wid}.${lang}.html`, res.data.html, "text/html");
    download(`${wid}.${lang}.sendWidget.json`, JSON.stringify(res.data.payload, null, 2));
    notify(`Exported ${wid}.${lang}.html and the sendWidget payload.`, "success");
  };

  const st: Doc = meta.states?.[state] ?? {};
  const dataBytes = Math.max(st.chatData ? utf8Bytes(JSON.stringify(st.chatData)) : 0, st.publicData ? utf8Bytes(JSON.stringify(st.publicData)) : 0);
  const limits = shown?.limits ?? build.current?.limits ?? { rawBytes: 32768, compressedBytes: 4096, dataBytes: 1024 };
  const fb = meta.fallbackScreen && working.screens[meta.fallbackScreen];
  const th = runtime?.themes?.[theme] ?? {};

  return (
    <div className="grid min-h-0 flex-1 gap-0 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="min-w-0 space-y-3 border-b p-3 sm:p-4 xl:border-r xl:border-b-0" aria-label="Widget sources">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-mono text-base font-semibold">{wid}</h2>
          <DraftBadge draft={draft} />
          {draft && (
            <>
              <Button size="sm" variant="ghost" className="h-7" onClick={() => store.resetWidget(wid)}><RotateCcw className="size-3.5" /> Reset draft</Button>
              <Button asChild size="sm" variant="outline" className="h-7"><a href={href("changes")}>Review and save</a></Button>
            </>
          )}
        </div>
        <div role="radiogroup" aria-label="Editor" className="inline-flex gap-1 rounded-lg bg-muted p-1">
          {(["design", "code"] as const).map((m) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
              className={cn("rounded-md px-3 py-1 text-xs", mode === m ? "bg-background font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}>
              {m === "design" ? "Design" : "Code"}
            </button>
          ))}
        </div>
        {mode === "design" && (designBroken ? (
          <Alert variant="destructive"><AlertTitle>design.json is not valid JSON</AlertTitle><AlertDescription>Fix it in Code, or reset the draft.</AlertDescription></Alert>
        ) : runtime?.design ? (
          <DesignPanel design={design} catalog={runtime.design} parts={parts} theme={theme === "dark" ? "dark" : "light"} onTheme={setTheme}
            onChange={saveDesign} info={build.current?.design ?? (build.current?.ok ? null : undefined)} onReplay={() => setReset((r) => r + 1)} />
        ) : (
          <p className="text-sm text-muted-foreground">{runtime ? "This skill version has no design profiles (scripts/widget_design.py)." : "Loading…"}</p>
        ))}
        {mode === "code" && <>
        <div role="tablist" aria-label="Widget files" className="flex flex-wrap gap-1 border-b">
          {names.map((n) => (
            <button key={n} role="tab" type="button" aria-selected={tab === n} aria-controls={`wf-${n}`} onClick={() => setTab(n)}
              className="-mb-px border-b-2 border-transparent px-2.5 py-1.5 font-mono text-xs aria-selected:border-primary aria-selected:font-semibold">
              {n}{store.data.widgets[wid]?.[n] !== undefined ? " •" : ""}
            </button>
          ))}
        </div>
        {names.includes(tab) && (
          <div role="tabpanel" id={`wf-${tab}`}>
            <label className="sr-only" htmlFor={`wf-${tab}-ta`}>{tab}</label>
            <Textarea id={`wf-${tab}-ta`} value={files[tab] ?? ""} spellCheck={false} rows={22}
              onChange={(e) => store.setWidgetFile(wid, tab, e.target.value)}
              className="min-h-[50svh] font-mono text-[12px] leading-relaxed" />
            {tab === "widget.json" && metaError && <p className="mt-1 text-xs text-destructive">widget.json is not valid JSON: {metaError}</p>}
          </div>
        )}
        </>}
      </section>

      <section className="min-w-0 space-y-3 p-3 sm:p-4 xl:sticky xl:top-0 xl:max-h-svh xl:self-start xl:overflow-y-auto" aria-label="Build and preview">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Language" htmlFor="w-lang"><NativeSelect id="w-lang" size="sm" value={lang} onChange={(e) => setLang(e.target.value)}>{langs.map((l) => <NativeSelectOption key={l} value={l}>{l}</NativeSelectOption>)}</NativeSelect></Field>
          <Field label="Demo state" htmlFor="w-state"><NativeSelect id="w-state" size="sm" value={state} onChange={(e) => setState(e.target.value)}>{states.map((s) => <NativeSelectOption key={s} value={s}>{s}</NativeSelectOption>)}</NativeSelect></Field>
          <Field label="Theme" htmlFor="w-theme"><NativeSelect id="w-theme" size="sm" value={theme} onChange={(e) => setTheme(e.target.value)}>{Object.keys(runtime?.themes ?? { light: 1, dark: 1 }).map((t) => <NativeSelectOption key={t} value={t}>{t}</NativeSelectOption>)}</NativeSelect></Field>
          <Field label="Width" htmlFor="w-width"><NativeSelect id="w-width" size="sm" value={String(width)} onChange={(e) => setWidth(Number(e.target.value))}>{WIDTHS.map((w) => <NativeSelectOption key={w} value={String(w)}>{w} px</NativeSelectOption>)}</NativeSelect></Field>
          <label className="flex h-8 items-center gap-1.5 text-xs"><input type="checkbox" checked={offline} onChange={(e) => setOffline(e.target.checked)} className="size-4" /> Bot offline (TIMEOUT)</label>
          <Button size="sm" variant="outline" className="h-8" onClick={() => setReset((r) => r + 1)}><RefreshCw className="size-3.5" /> Reset frame</Button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs" aria-live="polite">
          {build.status === "updating" && <span className="rounded bg-muted px-2 py-0.5">Updating build…</span>}
          {build.status === "ok" && <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100">Build ok{build.current?.draft ? " (draft sources)" : ""}</span>}
          {build.status === "error" && <span className="rounded bg-destructive/10 px-2 py-0.5 text-destructive">Build failed</span>}
          {isPrevious && <span className="rounded border border-dashed px-2 py-0.5">Showing the previous build</span>}
        </div>

        {(build.current?.errors?.length || build.message) && build.status === "error" ? (
          <Alert variant="destructive">
            <AlertTitle>Build errors</AlertTitle>
            <AlertDescription><ul className="list-disc pl-4 font-mono text-xs">{(build.current?.errors?.length ? build.current.errors : [build.message]).map((e, i) => <li key={i}>{e}</li>)}</ul></AlertDescription>
          </Alert>
        ) : null}
        {(build.current?.warnings?.length ?? 0) > 0 && (
          <Alert><AlertTitle>Warnings</AlertTitle><AlertDescription><ul className="list-disc pl-4 font-mono text-xs">{build.current!.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></AlertDescription></Alert>
        )}

        <div className="grid gap-2 sm:grid-cols-3">
          <Meter label="HTML" value={shown?.rawBytes ?? 0} limit={limits.rawBytes} />
          <Meter label="zlib-9" value={shown?.compressedBytes ?? 0} limit={limits.compressedBytes} />
          <Meter label={`${state} data`} value={dataBytes} limit={limits.dataBytes} />
        </div>

        <figure className="overflow-hidden rounded-xl border">
          <div className="flex justify-center p-4" style={{ background: th._chat ?? "#c9d9b8" }}>
            <div className="overflow-hidden rounded-xl shadow-sm" style={{ width, background: th.bg_color ?? "#fff", color: th.text_color ?? "#000" }}>
              {doc ? (
                <iframe key={session} ref={frameRef} title={`Widget ${wid} preview`} sandbox="allow-scripts" src="/preview-frame.html"
                  scrolling="no" className="block w-full border-0" style={{ height }} />
              ) : (
                <div className="p-4 text-sm opacity-70">{build.status === "updating" || !runtime ? "Building…" : "No successful build yet."}</div>
              )}
              {shown?.caption && <div className="px-3 pt-1 pb-2 text-[14px]">{shown.caption}</div>}
            </div>
          </div>
          <figcaption className="flex flex-wrap justify-between gap-1 border-t bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
            <span className="font-medium">Browser approximation, not Telegram: real widgets run in QuickJS</span>
            <span>{width} px · {height} px content · {state} · {lang}</span>
          </figcaption>
        </figure>

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={doExport} disabled={!build.current?.ok}><Download className="size-4" /> Export HTML + sendWidget payload</Button>
          {exportErr && <p role="alert" className="text-xs text-destructive">{exportErr}</p>}
        </div>

        <details className="rounded-md border p-2">
          <summary className="cursor-pointer text-xs font-medium">Requests and state ({log.length})</summary>
          <ol className="mt-1 max-h-48 overflow-y-auto font-mono text-[11px] break-all">
            {log.map((l) => <li key={l.n}><span className="text-muted-foreground">{l.t}</span> {l.m}</li>)}
            {log.length === 0 && <li className="text-muted-foreground">Requests from the widget are answered from precomputed demo answers; nothing leaves this page.</li>}
          </ol>
        </details>

        {fb && (
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">Fallback screen <a className="font-mono font-normal underline" href={href("screens", meta.fallbackScreen)}>{meta.fallbackScreen}</a></h3>
            <p className="text-xs text-muted-foreground">Sent instead of the widget outside a private chat or where widgets are off.</p>
            <ScreenPreview logical={renderScreen(loaded.project, fb, { locale: lang, values: exampleValues(loaded.project) })} theme={theme === "dark" ? "dark" : "light"} contextLabel={`group chat · ${lang}`} hideWidget />
          </div>
        )}
      </section>
    </div>
  );
}

export function WidgetsView({ id }: { id: string | null }) {
  const { loaded, caps, working } = useStudio();
  const ids = Object.keys(loaded.widgets).sort();
  if (!caps.widgets) {
    return (
      <div className="space-y-4 p-4">
        <Alert>
          <AlertTitle>Widgets are not in the artifact</AlertTitle>
          <AlertDescription>This file carries no widget sources. Open the project with <code className="font-mono">bot-ui studio</code> to edit, build and preview widgets.</AlertDescription>
        </Alert>
        <ul className="space-y-3">
          {ids.map((wid) => {
            const fbId = loaded.widgets[wid].meta.fallbackScreen;
            const fb = fbId && working.screens[fbId];
            return (
              <li key={wid} className="space-y-1">
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
