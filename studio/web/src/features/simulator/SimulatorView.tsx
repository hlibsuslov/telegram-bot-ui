import { ArrowLeft, Check, Copy, MousePointerClick, Play, RotateCcw, Send, Terminal, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Engine, newSession, parityView, runScenario, type Session, type Snapshot } from "@/core/engine.ts";
import type { Doc, Logical } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText } from "@/lib/api";
import { copyText, exampleValues, locales } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, Segmented } from "../inspector/fields";
import { Bubble, Composer, ForceReplyBar, OutgoingBubble, ReplyKeyboard } from "../preview/Telegram";

const OPEN_CMD = "__studio_open";

type ChatItem =
  | { k: "bot"; instance: number; render: Logical; widget: string | null; edited: number }
  | { k: "user"; text: string }
  | { k: "note"; text: string; tone: "info" | "warn" | "error" };

interface Run {
  session: Session;
  chat: ChatItem[];
  trace: Doc[];
  toast: { text: string; n: number } | null;
  scenarioId: string | null;
  touched: number | null;
}

const canon = (v: any): any => Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v;

function effectNotes(entry: Doc, run: Run) {
  const u = entry.update ?? {};
  if (u.type === "message") run.chat.push({ k: "user", text: u.text });
  else if (u.type === "event") run.chat.push({ k: "note", text: `External event ${u.eventKey}`, tone: "info" });
  else if (u.type === "local" && !("expect" in u)) {
    const { type: _t, ...rest } = u;
    const pairs = Object.entries(rest).flatMap(([k, v]) => (v && typeof v === "object" ? Object.entries(v).map(([kk, vv]) => `${kk} = ${String(vv)}`) : [`${k} = ${String(v)}`]));
    run.chat.push({ k: "note", text: pairs.join(", "), tone: "info" });
  }
  if (entry.action?.type === "stale") run.chat.push({ k: "note", text: `Stale button “${entry.action.actionId}”: acknowledged, nothing changes`, tone: "warn" });
  run.touched = null;
  for (const eff of entry.effects ?? []) {
    if (eff.type === "send") {
      run.chat.push({ k: "bot", instance: eff.instance, render: eff.render, widget: eff.widget ?? null, edited: 0 });
      run.touched = eff.instance;
    } else if (eff.type === "edit") {
      const item = run.chat.find((c) => c.k === "bot" && c.instance === eff.instance) as Extract<ChatItem, { k: "bot" }> | undefined;
      if (item) { item.render = eff.render; item.edited++; }
      run.touched = eff.instance;
    } else if (eff.type === "answer") {
      if (eff.text) run.toast = { text: eff.text, n: (run.toast?.n ?? 0) + 1 };
    } else if (eff.type === "fallback") {
      const why: Record<string, string> = {
        edit_unavailable: `message #${eff.instance} is no longer accessible`, edit_kind: `message #${eff.instance} cannot become this screen`,
        edit_keyboard: "a reply or ForceReply keyboard needs a new message", widget_unsupported: "widgets are off here, the screen's message is sent",
      };
      run.chat.push({ k: "note", text: `Fallback: ${why[eff.reason] ?? eff.reason} → new message`, tone: "warn" });
    } else if (eff.type === "link") run.chat.push({ k: "note", text: `Opens ${eff.url} (not followed)`, tone: "info" });
    else if (eff.type === "noop") run.chat.push({ k: "note", text: eff.reason, tone: "info" });
  }
  for (const d of entry.diagnostics ?? []) run.chat.push({ k: "note", text: `${d.code}: ${d.message}`, tone: d.severity === "error" ? "error" : "warn" });
}

const UPDATE_STYLE: Record<string, string> = {
  message: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100",
  callback_query: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-100",
  event: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100",
  local: "bg-muted text-muted-foreground",
};

function TraceStep({ e, last }: { e: Doc; last: boolean }) {
  const u = e.update ?? {};
  const what = u.type === "message" ? `“${u.text}”` : u.type === "callback_query" ? `${u.actionId}${u.message ? ` on #${u.message}` : ""}` : u.type === "event" ? u.eventKey
    : JSON.stringify(Object.fromEntries(Object.entries(u).filter(([k]) => k !== "type")));
  const t = e.transition;
  const failed = (e.diagnostics ?? []).some((d: Doc) => d.severity === "error");
  return (
    <li className={cn("rounded-xl bg-card p-2.5 text-xs shadow-xs ring-1 ring-border", last && "ring-2 ring-foreground/70", failed && "ring-destructive")}>
      <div className="flex items-center gap-2">
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[10px]">{e.step}</span>
        <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-medium", UPDATE_STYLE[u.type] ?? UPDATE_STYLE.local)}>{u.type === "callback_query" ? "press" : u.type}</span>
        <span className="min-w-0 truncate font-mono">{what}</span>
      </div>
      <dl className="mt-1.5 grid grid-cols-[4.5rem_1fr] gap-x-2 gap-y-0.5 pl-7 [overflow-wrap:anywhere]">
        {e.action && (<><dt className="text-muted-foreground">action</dt><dd className="font-mono">{e.action.screenId}/{e.action.actionId ?? e.action.field} · {e.action.type}</dd></>)}
        {t && (<><dt className="text-muted-foreground">transition</dt><dd className="font-mono">{t.from ?? "∅"} → {t.to} <span className="text-muted-foreground">via {t.via}</span></dd></>)}
        {t?.rule && (<><dt className="text-muted-foreground">rule</dt><dd className="font-mono">{t.rule.field}: {t.rule.matched ? "matched" : "not matched"} → <b>{t.rule.branch}</b></dd></>)}
        {(e.effects ?? []).length > 0 && (
          <><dt className="text-muted-foreground">effects</dt>
            <dd className="flex flex-wrap gap-1">{e.effects.map((x: Doc, i: number) => (
              <span key={i} className="rounded bg-muted px-1 font-mono">{x.type}{x.instance ? ` #${x.instance}` : ""}{x.type === "answer" && x.text ? ` “${x.text}”` : ""}{x.reason ? ` (${x.reason})` : ""}</span>
            ))}</dd></>
        )}
      </dl>
      {(e.diagnostics ?? []).map((d: Doc, i: number) => <p key={i} className={cn("mt-1 pl-7", d.severity === "error" ? "text-destructive" : "text-warning")}>{d.code}: {d.message}</p>)}
    </li>
  );
}

function Service({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" | "error" }) {
  return (
    <p className={cn("tg-service mx-auto max-w-[88%] rounded-full px-2.5 py-0.5 text-center text-[12px] leading-5",
      tone === "warn" && "!bg-amber-500/90 !text-amber-950", tone === "error" && "!bg-red-600/90")}>{children}</p>
  );
}

export function SimulatorView() {
  const { working, loaded, store, caps } = useStudio();
  const project = loaded.project;
  const ls = locales(project);
  const commands = (project.entryPoints ?? []).filter((e: Doc) => e.type === "command");
  const events = (project.entryPoints ?? []).filter((e: Doc) => e.type === "event");
  const enumContext = Object.entries<Doc>(project.fields ?? {}).filter(([, f]) => f.source === "context" && f.type === "enum");
  const handlers = Object.entries<Doc>(project.handlers ?? {});
  const scenarios = Object.values<Doc>(loaded.scenarios ?? {});

  const [start, setStart] = useState(commands[0] ? `cmd:${commands[0].command}` : "screen");
  const [startScreen, setStartScreen] = useState(Object.keys(working.screens).sort()[0] ?? "");
  const [locale, setLocale] = useState(ls[0]);
  const [chat, setChat] = useState("private");
  const [ctx, setCtx] = useState<Doc>(() => Object.fromEntries(enumContext.map(([n, f]) => [n, f.values?.[0]])));
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [outcome, setOutcome] = useState<Doc>(() => Object.fromEntries(handlers.map(([h, d]) => [h, d.outcomes?.[0] ?? ""])));
  const [eventKey, setEventKey] = useState(events[0]?.eventKey ?? "");
  const dataExample = useMemo(() => {
    const ex = exampleValues(project);
    return JSON.stringify(Object.fromEntries(Object.entries<Doc>(project.fields ?? {}).filter(([n, f]) => f.source === "data" && n in ex).map(([n]) => [n, ex[n]])), null, 1);
  }, [project]);
  const [eventData, setEventData] = useState(dataExample);
  const [eventErr, setEventErr] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [menu, setMenu] = useState(false);
  const [parity, setParity] = useState<{ state: "idle" | "busy" | "same" | "diff" | "error"; text?: string }>({ state: "idle" });
  const [copied, setCopied] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const traceEnd = useRef<HTMLLIElement>(null);
  const queues = useRef<Record<string, string[]> | null>(null);

  const handlerFn = (hid: string) => (queues.current ? (queues.current[hid] ?? []).shift() ?? "" : outcome[hid] ?? "");
  const engine = (snap: Snapshot, open?: string) => new Engine(
    open ? { ...snap, project: { ...snap.project, entryPoints: [...(snap.project.entryPoints ?? []), { id: "studio-open", type: "command", command: OPEN_CMD, screen: open }] } } : snap,
    handlerFn,
  );
  const feed = (r: Run, ev: Doc, open?: string) => {
    const entry = engine(working, open).feed(r.session, ev);
    entry.step = r.trace.length + 1;
    r.trace.push(entry);
    effectNotes(entry, r);
  };

  const begin = () => {
    queues.current = null;
    setParity({ state: "idle" });
    setMenu(false);
    if (start.startsWith("scenario:")) {
      const sc = loaded.scenarios[start.slice(9)];
      if (!sc) return;
      const r: Run = { session: newSession(project, { locale: sc.locale, context: sc.context, data: sc.data }), chat: [], trace: [], toast: null, scenarioId: sc.scenarioId, touched: null };
      queues.current = Object.fromEntries(Object.entries<string[]>(sc.handlers ?? {}).map(([k, v]) => [k, [...v]]));
      for (const st of sc.steps ?? []) feed(r, st);
      queues.current = null;
      if (sc.locale) setLocale(sc.locale);
      if (sc.context?.chat) setChat(sc.context.chat);
      setCtx((c) => ({ ...c, ...Object.fromEntries(Object.entries(sc.context ?? {}).filter(([k]) => k in c)) }));
      setRun({ ...r });
      return;
    }
    const r: Run = { session: newSession(project, { locale, context: { chat, ...ctx }, data: exampleValues(project) }), chat: [], trace: [], toast: null, scenarioId: null, touched: null };
    if (start.startsWith("cmd:")) feed(r, { command: start.slice(4) });
    else if (start === "screen" && startScreen) feed(r, { command: OPEN_CMD }, startScreen);
    setRun({ ...r });
  };

  const act = (ev: Doc) => {
    if (!run) return;
    const r = { ...run, chat: [...run.chat], trace: [...run.trace] };
    feed(r, ev);
    setRun(r);
  };

  useEffect(() => { chatEnd.current?.scrollIntoView({ block: "end" }); traceEnd.current?.scrollIntoView({ block: "nearest" }); }, [run]);
  useEffect(() => {
    if (!run?.toast) return;
    const t = setTimeout(() => setRun((r) => (r ? { ...r, toast: null } : r)), 2600);
    return () => clearTimeout(t);
  }, [run?.toast]);

  const s = run?.session;
  const eng = engine(working);
  const reply = s?.reply && working.screens[s.reply] ? eng.render(s, s.reply) : null;
  const awaiting = s?.awaiting ? working.screens[s.awaiting] : null;
  const forcePh = awaiting?.keyboard?.type === "force_reply" ? eng.render(s as Session, awaiting.id).keyboard.placeholder || "Reply…" : null;
  const sc = run?.scenarioId ? loaded.scenarios[run.scenarioId] : null;
  const replay = sc && loaded.cliProject ? `py -3 studio/bot-ui.py simulate --scenario ${sc.scenarioId} --project "${loaded.cliProject}"` : null;
  const lastBot = run ? [...run.chat].reverse().find((c) => c.k === "bot") : undefined;

  const crossCheck = async () => {
    if (!sc) return;
    setParity({ state: "busy" });
    const mine = parityView(runScenario(working, sc));
    const res = await api("/api/simulate", { scenario: sc.scenarioId, screens: store.data.screens });
    if (!res.ok) return setParity({ state: "error", text: errorText(res.data) });
    const same = JSON.stringify(canon(mine)) === JSON.stringify(canon(res.data));
    const firstDiff = same ? "" : (() => {
      const a = mine.steps ?? [], b = res.data.steps ?? [];
      for (let i = 0; i < Math.max(a.length, b.length); i++) if (JSON.stringify(canon(a[i])) !== JSON.stringify(canon(b[i]))) return `step ${i + 1} differs`;
      return "the final state differs";
    })();
    setParity({ state: same ? "same" : "diff", text: firstDiff });
  };

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_360px]">
      <section aria-label="Simulator controls" className="min-w-0 space-y-4 border-b p-4 lg:h-[calc(100svh-3.5rem)] lg:overflow-y-auto lg:border-r lg:border-b-0">
        <div>
          <h2 className="text-[15px] font-semibold">Simulator</h2>
          <p className="text-xs text-muted-foreground">The bot-ui engine runs in this page on your current draft. Nothing is sent to Telegram.</p>
        </div>
        <Field label="Start from" htmlFor="sim-start">
          <EnumSelect id="sim-start" value={start} onChange={setStart} options={[
            ...commands.map((c: Doc) => ({ value: `cmd:${c.command}`, label: <span><span className="font-mono">/{c.command}</span> <span className="text-muted-foreground">→ {c.screen}</span></span> })),
            { value: "screen", label: "A screen…" },
            ...scenarios.map((x) => ({ value: `scenario:${x.scenarioId}`, label: <span>Scenario <span className="font-mono">{x.scenarioId}</span></span> })),
          ]} />
        </Field>
        {start === "screen" && (
          <Field label="Screen" htmlFor="sim-screen">
            <EnumSelect id="sim-screen" value={startScreen} onChange={setStartScreen} className="font-mono text-[12.5px]"
              options={Object.keys(working.screens).sort().map((id) => ({ value: id, label: id }))} />
          </Field>
        )}
        <Button type="button" onClick={begin} className="w-full">{run ? <><RotateCcw className="size-4" /> Restart clean</> : <><Play className="size-4" /> Start</>}</Button>

        <div className="space-y-3 rounded-xl bg-muted/50 p-3">
          <p className="text-xs font-medium">Context</p>
          {ls.length > 1 && (
            <Field label="Language">
              <Segmented label="Language" value={locale} onChange={(v) => { setLocale(v); act({ locale: v }); }} options={ls.map((l) => ({ value: l, label: l }))} />
            </Field>
          )}
          <Field label="Chat">
            <Segmented label="Chat type" value={chat} onChange={(v) => { setChat(v); act({ context: { chat: v } }); }} options={[{ value: "private", label: "private" }, { value: "group", label: "group" }]} />
          </Field>
          {enumContext.map(([n, f]) => (
            <Field key={n} label={<span className="font-mono">{n}</span>}>
              <Segmented label={n} value={String(ctx[n])} onChange={(v) => { const val = (f.values ?? []).find((x: any) => String(x) === v); setCtx({ ...ctx, [n]: val }); act({ context: { [n]: val } }); }}
                options={(f.values ?? []).map((v: any) => ({ value: String(v), label: String(v) }))} />
            </Field>
          ))}
          <Field label="Theme">
            <Segmented label="Theme" value={theme} onChange={setTheme} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
          </Field>
        </div>

        {handlers.length > 0 && (
          <div className="space-y-2 rounded-xl bg-muted/50 p-3">
            <p className="text-xs font-medium">Handler outcomes <span className="font-normal text-muted-foreground">(for presses)</span></p>
            {handlers.map(([h, d]) => (
              <Field key={h} label={<span className="font-mono">{h}</span>}>
                <Segmented label={h} value={outcome[h] ?? ""} onChange={(v) => setOutcome({ ...outcome, [h]: v })} options={(d.outcomes ?? []).map((o: string) => ({ value: o, label: o }))} />
              </Field>
            ))}
          </div>
        )}

        {events.length > 0 && (
          <div className="space-y-2 rounded-xl bg-muted/50 p-3">
            <p className="text-xs font-medium">Fire an event</p>
            <EnumSelect label="Event" size="sm" value={eventKey} onChange={setEventKey}
              options={events.map((e: Doc) => ({ value: e.eventKey, label: <span className="font-mono">{e.eventKey}</span> }))} />
            <label className="sr-only" htmlFor="sim-ev-data">Event data (JSON)</label>
            <Textarea id="sim-ev-data" rows={3} value={eventData} onChange={(e) => setEventData(e.target.value)} className="bg-background font-mono text-xs" />
            <Button type="button" size="sm" variant="secondary" disabled={!run} className="w-full"
              onClick={() => {
                let data: Doc;
                try { data = JSON.parse(eventData || "{}"); } catch (err) { return setEventErr(`Event data is not JSON: ${(err as Error).message}`); }
                setEventErr("");
                act({ event: eventKey, data });
              }}>
              <Zap className="size-3.5" /> Fire {eventKey}
            </Button>
            {eventErr && <p role="alert" className="text-[11px] text-destructive">{eventErr}</p>}
            {!run && <p className="text-[11px] text-muted-foreground">Start a session first.</p>}
          </div>
        )}
      </section>

      <section aria-label="Chat" className="flex min-h-[78svh] justify-center bg-muted/30 p-3 sm:p-5 lg:h-[calc(100svh-3.5rem)] lg:min-h-0">
        <figure className="flex min-h-0 w-full max-w-[440px] flex-col overflow-hidden rounded-[22px] shadow-[0_10px_40px_-14px_rgba(0,0,0,.35)] ring-1 ring-black/10">
          <div className="tg flex min-h-0 flex-1 flex-col" data-theme={theme}>
            <header className="flex items-center gap-3 bg-[var(--tg-theme-header-bg-color)] px-3 py-2 shadow-[0_1px_0_rgba(0,0,0,.08)]">
              <ArrowLeft className="size-5 text-[var(--tg-theme-hint-color)]" aria-hidden />
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-indigo-500 text-sm font-semibold text-white" aria-hidden>
                {loaded.title.slice(0, 1).toUpperCase()}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[15px] font-semibold">{loaded.title}</span>
                <span className="block text-[12.5px] text-[var(--tg-theme-hint-color)]">bot</span>
              </span>
            </header>
            <div className="tg-wallpaper relative flex min-h-0 flex-1 flex-col">
              <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-3 py-3" aria-live="polite">
                {!run ? (
                  <div className="m-auto max-w-[80%] rounded-2xl bg-[var(--tg-service-bg)] px-4 py-3 text-center text-[13px] text-white">
                    <p className="font-semibold">{loaded.title}</p>
                    <p className="opacity-90">Press Start (or Menu → a command) to open the bot.</p>
                  </div>
                ) : <Service>Today</Service>}
                {run?.chat.map((c, i) => {
                  if (c.k === "user") return <div key={i} className="flex pl-10"><OutgoingBubble text={c.text} /></div>;
                  if (c.k === "note") return <div key={i} className="py-0.5"><Service tone={c.tone}>{c.text}</Service></div>;
                  const next = run.chat[i + 1];
                  return (
                    <div key={`b${c.instance}`} className={cn("w-full max-w-[86%] pl-1.5 transition-transform", run.touched === c.instance && "animate-in fade-in-0 slide-in-from-bottom-1")}>
                      <Bubble logical={c.render} edited={c.edited > 0} widget={c.widget} tail={!next || next.k !== "bot"}
                        meta={<span className="font-mono opacity-70">#{c.instance}</span>}
                        hl={run.touched === c.instance && c.edited > 0 ? { text: false } : undefined}
                        onPress={(aid) => act({ press: aid, message: c.instance })} />
                    </div>
                  );
                })}
                <div ref={chatEnd} />
              </div>
              {run?.toast && (
                <div key={run.toast.n} role="status" className="absolute inset-x-0 top-3 z-10 mx-auto w-fit max-w-[86%] animate-in rounded-xl bg-black/75 px-4 py-2.5 text-center text-[13.5px] text-white shadow-lg backdrop-blur fade-in-0 slide-in-from-top-2">
                  {run.toast.text}
                </div>
              )}
              {menu && commands.length > 0 && (
                <div className="absolute inset-x-2 bottom-2 z-10 overflow-hidden rounded-xl bg-[var(--tg-theme-bg-color)] shadow-xl ring-1 ring-black/10" role="menu" aria-label="Bot commands">
                  {commands.map((c: Doc) => (
                    <button key={c.command} type="button" role="menuitem" className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-[14px] hover:bg-[var(--tg-theme-secondary-bg-color)]"
                      onClick={() => { setMenu(false); if (run) act({ command: c.command }); else { setStart(`cmd:${c.command}`); } }}>
                      <Terminal className="size-4 text-[var(--tg-theme-hint-color)]" aria-hidden />
                      <span className="font-medium">/{c.command}</span>
                      <span className="truncate text-[12.5px] text-[var(--tg-theme-hint-color)]">{c.screen}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {forcePh && <ForceReplyBar placeholder={forcePh} />}
            <Composer key={run?.trace.length ?? 0} placeholder={reply ? "Message or a key below" : "Message"} disabled={!run}
              onSend={(text) => { setMenu(false); act({ text }); }} onMenu={commands.length ? () => setMenu(!menu) : undefined} />
            {reply && reply.keyboard.type === "reply" && <ReplyKeyboard logical={reply} onKey={(text) => act({ text })} />}
          </div>
          <figcaption className="flex flex-wrap justify-between gap-1 bg-background px-3 py-1.5 text-[11px] text-muted-foreground">
            <span className="font-medium">Local preview, not Telegram</span>
            <span>{chat} · {locale}{enumContext.map(([n]) => ` · ${n}=${ctx[n]}`).join("")}{lastBot ? ` · ${(lastBot as any).render.screenId}` : ""}</span>
          </figcaption>
        </figure>
      </section>

      <section aria-label="Trace" className="flex min-h-0 flex-col border-t p-4 lg:h-[calc(100svh-3.5rem)] lg:border-t-0 lg:border-l">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h2 className="text-[15px] font-semibold">Trace</h2>
          <span className="text-[11px] text-muted-foreground">{run?.trace.length ?? 0} steps</span>
        </div>
        {sc && (
          <div className="mb-3 space-y-2 rounded-xl bg-muted/50 p-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-mono font-medium">{sc.scenarioId}</span>
              {run?.trace.some((e) => e.diagnostics?.some((d: Doc) => d.severity === "error"))
                ? <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-800">failed</span>
                : <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-900">expectations met</span>}
            </div>
            {replay && (
              <div className="flex items-start gap-1">
                <code className="min-w-0 flex-1 rounded-md bg-background p-1.5 font-mono text-[11px] break-all">{replay}</code>
                <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Copy the CLI replay command"
                  onClick={async () => { if (await copyText(replay)) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                </Button>
              </div>
            )}
            {caps.save && (
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" size="sm" variant="outline" className="h-7 bg-background" onClick={crossCheck} disabled={parity.state === "busy"}>Cross-check with the Python engine</Button>
                {parity.state === "same" && <span className="font-medium text-success">identical</span>}
                {parity.state === "diff" && <span className="text-destructive">differs: {parity.text}</span>}
                {parity.state === "error" && <span className="text-destructive">{parity.text}</span>}
              </div>
            )}
          </div>
        )}
        {!run && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground"><MousePointerClick className="size-4" /> Each update shows its action, transition and effects here.</p>
        )}
        <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1" aria-label="Trace steps">
          {run?.trace.map((e, i) => <TraceStep key={i} e={e} last={i === run.trace.length - 1} />)}
          <li ref={traceEnd} aria-hidden className="h-px" />
        </ol>
        <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground"><Send className="size-3" /> Buttons in older messages stay pressable to test stale presses.</p>
      </section>
    </div>
  );
}
