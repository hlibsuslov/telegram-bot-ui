import { ArrowLeft, Check, ChevronRight, Code2, LayoutList, Copy, MessageCircle, MousePointerClick, Play, RotateCcw, Server, Settings2, SlidersHorizontal, Terminal, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Engine, newSession, parityView, runScenario, type Session, type Snapshot } from "@/core/engine.ts";
import type { Doc, Logical } from "@/core/render.ts";
import { CodeBlock } from "@/components/code-view";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SunMoonThemeToggle } from "@/components/ui/sun-moon-theme-toggle";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText } from "@/lib/api";
import { copyText, exampleValues, locales } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, Segmented } from "../inspector/fields";
import { Bubble, Composer, ForceReplyBar, OutgoingBubble, ReplyKeyboard } from "../preview/Telegram";
import { chatLayout, DevicePresets, DeviceStage, useDevice } from "./DeviceFrame";
import { ChatTypeSwitch, LocaleChip, StartPicker, Tip } from "./SimControls";

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
  if (u.type === "message" && u.text === `/${OPEN_CMD}`) run.chat.push({ k: "note", text: "Opened this screen directly", tone: "info" });
  else if (u.type === "message") run.chat.push({ k: "user", text: u.text });
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

function updateText(u: Doc): { icon: React.ReactNode; text: string } {
  if (u.type === "message" && u.text === `/${OPEN_CMD}`) return { icon: <LayoutList className="size-3.5" />, text: "opened a screen directly" };
  if (u.type === "message") return { icon: <MessageCircle className="size-3.5" />, text: `“${u.text}”` };
  if (u.type === "callback_query") return { icon: <MousePointerClick className="size-3.5" />, text: `pressed ${u.actionId}${u.message ? ` in message #${u.message}` : ""}` };
  if (u.type === "event") return { icon: <Zap className="size-3.5" />, text: `event ${u.eventKey}` };
  const rest = Object.fromEntries(Object.entries(u).filter(([k]) => k !== "type"));
  if ("expect" in rest) return { icon: <Check className="size-3.5" />, text: `expect ${JSON.stringify(rest.expect)}` };
  return { icon: <Settings2 className="size-3.5" />, text: `set ${JSON.stringify(rest)}` };
}

function TraceStep({ e, last, pro }: { e: Doc; last: boolean; pro: boolean }) {
  const [open, setOpen] = useState(false);
  const u = updateText(e.update ?? {});
  const t = e.transition;
  const diags: Doc[] = e.diagnostics ?? [];
  const failed = diags.some((d) => d.severity === "error");
  const quiet = !e.action && !t && !(e.effects ?? []).length && !diags.length;
  return (
    <li className="relative flex gap-3 pb-4 last:pb-1">
      <span className="absolute top-6 bottom-0 left-[11px] w-px bg-border" aria-hidden />
      <span className={cn("relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-[10.5px] ring-4 ring-background",
        failed ? "bg-red-600 text-white" : last ? "bg-foreground text-background" : "bg-muted text-muted-foreground")}>{e.step}</span>
      <div className={cn("min-w-0 flex-1 text-xs", quiet && "text-muted-foreground")}>
        <div className="flex items-center gap-1.5 pt-1 font-medium">{u.icon}<span className="min-w-0 truncate">{u.text}</span></div>
        {e.action && e.action.type !== "stale" && (
          <p className="mt-1 text-muted-foreground">button <span className="font-mono text-foreground">{e.action.actionId ?? e.action.field}</span> on <span className="font-mono text-foreground">{e.action.screenId}</span> · {e.action.type}</p>
        )}
        {e.action?.type === "stale" && <p className="mt-1 text-amber-700 dark:text-amber-300">stale button: acknowledged, nothing changes</p>}
        {t && (
          <p className="mt-1 flex flex-wrap items-center gap-1 font-mono">
            <span>{t.from ?? "start"}</span><ChevronRight className="size-3 text-muted-foreground" /><span className="font-semibold">{t.to}</span>
            {t.rule && <span className={cn("rounded-full px-1.5 font-sans text-[10px] font-medium", t.rule.matched ? "bg-emerald-100 text-emerald-900" : "bg-slate-200 text-slate-800")}>{t.rule.field} {t.rule.matched ? "matched" : "not matched"} → {t.rule.branch}</span>}
          </p>
        )}
        {(e.effects ?? []).length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {e.effects.map((x: Doc, i: number) => (
              <span key={i} className={cn("rounded-md px-1.5 py-0.5 font-mono text-[10.5px]",
                x.type === "send" ? "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100" : x.type === "edit" ? "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-100"
                  : x.type === "fallback" ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100" : "bg-muted")}>
                {x.type}{x.instance ? ` #${x.instance}` : ""}{x.type === "answer" && x.text ? ` “${x.text}”` : ""}{x.reason ? ` · ${x.reason}` : ""}
              </span>
            ))}
          </div>
        )}
        {diags.map((d, i) => <p key={i} className={cn("mt-1", d.severity === "error" ? "text-destructive" : "text-amber-700 dark:text-amber-300")}>{d.code}: {d.message}</p>)}
        {pro && !quiet && (
          <button type="button" className="mt-1 text-[11px] text-muted-foreground underline-offset-2 hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide details" : "Details"}</button>
        )}
        {open && (
          <div className="mt-1"><CodeBlock lang="json" wrap maxHeight="16rem" code={JSON.stringify({ ...e, effects: (e.effects ?? []).map((x: Doc) => Object.fromEntries(Object.entries(x).filter(([k]) => k !== "render"))) }, null, 2)} /></div>
        )}
      </div>
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
  const { working, loaded, store, caps, pro } = useStudio();
  const project = loaded.project;
  const ls = locales(project);
  const commands = (project.entryPoints ?? []).filter((e: Doc) => e.type === "command");
  const events = (project.entryPoints ?? []).filter((e: Doc) => e.type === "event");
  const enumContext = Object.entries<Doc>(project.fields ?? {}).filter(([, f]) => f.source === "context" && f.type === "enum");
  const handlers = Object.entries<Doc>(project.handlers ?? {});

  const [start, setStartState] = useState(() => {
    try { const v = localStorage.getItem("bot-ui-studio:sim-start"); if (v) return v; } catch { /* storage blocked */ }
    return commands[0] ? `cmd:${commands[0].command}` : `screen:${Object.keys(working.screens).sort()[0] ?? ""}`;
  });
  const setStart = (v: string) => { setStartState(v); try { localStorage.setItem("bot-ui-studio:sim-start", v); } catch { /* storage blocked */ } };
  const [device, setDevice] = useDevice();
  const [scale, setScale] = useState(1);
  const layout = chatLayout(device.w);
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
    else if (start.startsWith("ev:")) {
      let data: Doc = {};
      try { data = JSON.parse(eventData || "{}"); } catch { /* example data only */ }
      feed(r, { event: start.slice(3), data });
    } else if (start.startsWith("screen:") && working.screens[start.slice(7)]) feed(r, { command: OPEN_CMD }, start.slice(7));
    setRun({ ...r });
  };

  const act = (ev: Doc) => {
    if (!run) return;
    const r = { ...run, chat: [...run.chat], trace: [...run.trace] };
    feed(r, ev);
    setRun(r);
  };

  // Scroll the chat and the trace lists themselves, never the page.
  useEffect(() => {
    for (const el of [chatEnd.current?.parentElement, traceEnd.current?.parentElement]) if (el) el.scrollTop = el.scrollHeight;
  }, [run]);
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

  const startText = start.startsWith("scenario:") ? `runs the scenario ${start.slice(9)}` : start.startsWith("cmd:") ? `sends /${start.slice(4)}` : start.startsWith("ev:") ? `fires ${start.slice(3)}` : `opens ${start.slice(7)}`;

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_400px]">
      <section aria-label="Chat" className="flex h-[86svh] min-w-0 flex-col bg-muted/30 lg:h-[calc(100svh-3.5rem)]">
        <div className="flex flex-wrap items-center gap-2 border-b bg-background px-3 py-2" role="toolbar" aria-label="Simulator">
          <StartPicker value={start} onChange={setStart} />
          <Tip label={run ? "Restart clean from here" : "Start the chat"}>
            <Button size="icon" variant={run ? "outline" : "default"} className="size-8" onClick={begin} aria-label={run ? "Restart clean" : "Start the chat"}>
              {run ? <RotateCcw className="size-4" /> : <Play className="size-4" />}
            </Button>
          </Tip>
          <span className="mx-1 h-5 w-px bg-border" aria-hidden />
          <DevicePresets device={device} onChange={setDevice} scale={scale} />
          <span className="ml-auto flex items-center gap-2">
            <Tip label={theme === "dark" ? "Telegram dark theme" : "Telegram light theme"}>
              <span className="inline-flex"><SunMoonThemeToggle theme={theme} onThemeChange={setTheme} syncDocument={false} sky={false} size={32} /></span>
            </Tip>
            <LocaleChip value={locale} options={ls} onChange={(v) => { setLocale(v); act({ locale: v }); }} />
            <ChatTypeSwitch value={chat} onChange={(v) => { setChat(v); act({ context: { chat: v } }); }} />
            {(enumContext.length > 0 || handlers.length > 0) && (
              <Popover>
                <Tip label="Context: server values and handler results">
                  <PopoverTrigger asChild>
                    <Button size="icon" variant="outline" className="size-8" aria-label="Context: server values and handler results"><SlidersHorizontal className="size-4" /></Button>
                  </PopoverTrigger>
                </Tip>
                <PopoverContent align="end" className="w-[min(94vw,22rem)] space-y-4">
                  {enumContext.length > 0 && (
                    <div className="space-y-2">
                      <p className="flex items-center gap-1.5 text-xs font-semibold"><Server className="size-3.5" aria-hidden /> Values from your server</p>
                      <p className="text-[11px] text-muted-foreground">Trusted values your server sets, e.g. delivery.method. Switch them to try both branches of a rule.</p>
                      {enumContext.map(([n, f]) => (
                        <Field key={n} label={<span className="font-mono">{n}</span>}>
                          <Segmented label={n} value={String(ctx[n])} onChange={(v) => { const val = (f.values ?? []).find((x: any) => String(x) === v); setCtx({ ...ctx, [n]: val }); act({ context: { [n]: val } }); }}
                            options={(f.values ?? []).map((v: any) => ({ value: String(v), label: String(v) }))} />
                        </Field>
                      ))}
                    </div>
                  )}
                  {handlers.length > 0 && (
                    <div className="space-y-2 border-t pt-3">
                      <p className="flex items-center gap-1.5 text-xs font-semibold"><Code2 className="size-3.5" aria-hidden /> Handler results</p>
                      <p className="text-[11px] text-muted-foreground">What your bot code returns when a handler button is pressed here.</p>
                      {handlers.map(([h, d]) => (
                        <Field key={h} label={<span className="font-mono">{h}</span>}>
                          <Segmented label={h} value={outcome[h] ?? ""} onChange={(v) => setOutcome({ ...outcome, [h]: v })} options={(d.outcomes ?? []).map((o: string) => ({ value: o, label: o }))} />
                        </Field>
                      ))}
                    </div>
                  )}
                </PopoverContent>
              </Popover>
            )}
          {events.length > 0 && (
            <Popover>
              <Tip label="Fire an event from your server">
                <PopoverTrigger asChild>
                  <Button size="icon" variant="outline" className="size-8" disabled={!run} aria-label="Fire an event from your server"><Zap className="size-4" /></Button>
                </PopoverTrigger>
              </Tip>
              <PopoverContent align="end" className="w-[min(94vw,22rem)] space-y-2">
                <p className="text-xs font-semibold">Fire an external event</p>
                <p className="text-[11px] text-muted-foreground">Like your server would, e.g. when an order status changes.</p>
                <EnumSelect label="Event" size="sm" value={eventKey} onChange={setEventKey}
                  options={events.map((e: Doc) => ({ value: e.eventKey, label: <span className="font-mono">{e.eventKey}</span> }))} />
                {pro ? (
                  <>
                    <label className="sr-only" htmlFor="sim-ev-data">Event data (JSON)</label>
                    <Textarea id="sim-ev-data" rows={4} value={eventData} onChange={(e) => setEventData(e.target.value)} className="font-mono text-xs" />
                  </>
                ) : (() => {
                  let obj: Doc = {};
                  try { obj = JSON.parse(eventData || "{}"); } catch { /* edited in Pro */ }
                  return (
                    <div className="space-y-2">
                      {Object.entries(obj).map(([k, v]) => (
                        <Field key={k} label={k} htmlFor={`sim-ev-${k}`}>
                          <Input id={`sim-ev-${k}`} value={String(v ?? "")} onChange={(e) => setEventData(JSON.stringify({ ...obj, [k]: e.target.value }, null, 1))} className="h-8 text-xs" />
                        </Field>
                      ))}
                    </div>
                  );
                })()}
                <Button type="button" size="sm" className="w-full"
                  onClick={() => {
                    let data: Doc;
                    try { data = JSON.parse(eventData || "{}"); } catch (err) { return setEventErr(`Event data is not JSON: ${(err as Error).message}`); }
                    setEventErr("");
                    act({ event: eventKey, data });
                  }}>
                  <Zap className="size-3.5" /> Fire {eventKey}
                </Button>
                {eventErr && <p role="alert" className="text-[11px] text-destructive">{eventErr}</p>}
              </PopoverContent>
            </Popover>
          )}
          </span>
        </div>

        <DeviceStage device={device} onChange={setDevice} onScale={setScale}>
          <figure className={cn("flex size-full flex-col overflow-hidden shadow-[0_10px_40px_-14px_rgba(0,0,0,.35)] ring-1 ring-black/10", layout.wide ? "rounded-xl" : device.w >= 700 ? "rounded-[18px]" : "rounded-[26px]")}>
            <div className="tg flex min-h-0 flex-1 flex-col" data-theme={theme}>
              <header className="flex items-center gap-3 bg-[var(--tg-theme-header-bg-color)] px-3 py-2 shadow-[0_1px_0_rgba(0,0,0,.08)]">
                <ArrowLeft className="size-5 text-[var(--tg-theme-hint-color)]" aria-hidden />
                {loaded.demoAvatar ? (
                  <img src={loaded.demoAvatar} alt="" className="size-9 shrink-0 rounded-full" />
                ) : (
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-indigo-500 text-sm font-semibold text-white" aria-hidden>
                    {loaded.title.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <span className="min-w-0">
                  <span className="block truncate text-[15px] font-semibold">{loaded.title}</span>
                  <span className="block text-[12.5px] text-[var(--tg-theme-hint-color)]">bot</span>
                </span>
              </header>
              <div className="tg-wallpaper relative flex min-h-0 flex-1 flex-col">
                <div className="mx-auto flex min-h-0 w-full flex-1 flex-col gap-1.5 overflow-y-auto py-3" style={{ maxWidth: layout.column, paddingLeft: layout.pad, paddingRight: layout.pad }} aria-live="polite">
                  {!run ? (
                    <div className="m-auto max-w-[82%] rounded-2xl bg-[var(--tg-service-bg)] px-4 py-3 text-center text-[13px] text-white">
                      <p className="font-semibold">What can this bot do?</p>
                      <p className="opacity-90">{loaded.title}. START {startText}.</p>
                    </div>
                  ) : <Service>Today</Service>}
                  {run?.chat.map((c, i) => {
                    if (c.k === "user") return <div key={i} className="ml-auto flex w-full" style={{ maxWidth: layout.bubble }}><OutgoingBubble text={c.text} /></div>;
                    if (c.k === "note") return <div key={i} className="py-0.5"><Service tone={c.tone}>{c.text}</Service></div>;
                    const next = run.chat[i + 1];
                    return (
                      <div key={`b${c.instance}`} style={{ maxWidth: layout.bubble }} className={cn("w-full pl-1.5", run.touched === c.instance && "animate-in fade-in-0 slide-in-from-bottom-1")}>
                        <Bubble logical={c.render} edited={c.edited > 0} widget={c.widget} tail={!next || next.k !== "bot"}
                          meta={<span className="font-mono opacity-70">#{c.instance}</span>}
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
                        onClick={() => { setMenu(false); act({ command: c.command }); }}>
                        <Terminal className="size-4 text-[var(--tg-theme-hint-color)]" aria-hidden />
                        <span className="font-medium">/{c.command}</span>
                        <span className="truncate text-[12.5px] text-[var(--tg-theme-hint-color)]">{c.screen}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {!run ? (
                // Telegram's START bar spans the whole chat width, whatever the device.
                <button type="button" onClick={begin} className="block w-full shrink-0 border-t border-black/5 bg-[var(--tg-theme-bg-color)] py-3.5 text-center text-[15px] font-semibold tracking-wide text-[var(--tg-theme-button-color)] uppercase hover:bg-[var(--tg-theme-secondary-bg-color)]">
                  Start
                </button>
              ) : (
              <div className="mx-auto w-full" style={{ maxWidth: layout.wide ? layout.column : undefined }}>
                <>
                  {forcePh && <ForceReplyBar placeholder={forcePh} />}
                  <Composer key={run.trace.length} placeholder={reply ? "Message or a key below" : "Message"}
                    onSend={(text) => { setMenu(false); act({ text }); }} onMenu={commands.length ? () => setMenu(!menu) : undefined} />
                  {reply && reply.keyboard.type === "reply" && <ReplyKeyboard logical={reply} onKey={(text) => act({ text })} />}
                </>
              </div>
              )}
            </div>
            <figcaption className="flex flex-wrap justify-between gap-1 bg-background px-3 py-1.5 text-[11px] text-muted-foreground">
              <span className="font-medium">Local preview, not Telegram</span>
              <span>{lastBot ? (lastBot as any).render.screenId : ""}</span>
            </figcaption>
          </figure>
        </DeviceStage>
      </section>

      <section aria-label="Trace" className="flex min-h-0 min-w-0 flex-col border-t bg-background lg:h-[calc(100svh-3.5rem)] lg:border-t-0 lg:border-l">
        <div className="flex items-baseline justify-between gap-2 border-b px-4 py-3">
          <h2 className="text-[15px] font-semibold">Trace</h2>
          <span className="text-[11px] text-muted-foreground">{run?.trace.length ?? 0} steps · what the engine did with each update</span>
        </div>
        {sc && (
          <div className="space-y-2 border-b px-4 py-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-mono font-medium">{sc.scenarioId}</span>
              {run?.trace.some((e) => e.diagnostics?.some((d: Doc) => d.severity === "error"))
                ? <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-800">expectations failed</span>
                : <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-900">expectations met</span>}
            </div>
            {replay && (
              <div className="flex items-start gap-1">
                <code className="min-w-0 flex-1 rounded-md bg-muted p-1.5 font-mono text-[11px] break-all">{replay}</code>
                <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Copy the CLI replay command"
                  onClick={async () => { if (await copyText(replay)) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                </Button>
              </div>
            )}
            {caps.save && (
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" size="sm" variant="outline" className="h-7" onClick={crossCheck} disabled={parity.state === "busy"}>Cross-check with the Python engine</Button>
                {parity.state === "same" && <span className="font-medium text-success">identical</span>}
                {parity.state === "diff" && <span className="text-destructive">differs: {parity.text}</span>}
                {parity.state === "error" && <span className="text-destructive">{parity.text}</span>}
              </div>
            )}
          </div>
        )}
        {!run && <p className="flex items-center gap-2 px-4 py-4 text-xs text-muted-foreground"><MousePointerClick className="size-4" /> Press START in the chat; each update appears here as a step.</p>}
        <ol className="min-h-0 flex-1 overflow-y-auto px-4 py-3" aria-label="Trace steps">
          {run?.trace.map((e, i) => <TraceStep key={i} e={e} last={i === run.trace.length - 1} pro={pro} />)}
          <li ref={traceEnd} aria-hidden className="h-px" />
        </ol>
      </section>
    </div>
  );
}
