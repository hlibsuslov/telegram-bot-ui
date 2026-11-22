import { Check, Copy, Play, RotateCcw, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Engine, newSession, parityView, runScenario, type Session, type Snapshot } from "@/core/engine.ts";
import type { Doc, Logical } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText } from "@/lib/api";
import { copyText, exampleValues, locales } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { Field } from "../inspector/fields";
import { Bubble, Composer, PreviewCaption, ReplyKeyboard } from "../preview/Telegram";

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
    run.chat.push({ k: "note", text: `Changed ${Object.entries(rest).map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join(", ")}`, tone: "info" });
  }
  if (entry.action?.type === "stale") run.chat.push({ k: "note", text: `Stale button “${entry.action.actionId}”: acknowledged, nothing else changes.`, tone: "warn" });
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
        edit_unavailable: `message #${eff.instance} is no longer accessible`, edit_kind: `message #${eff.instance} cannot be edited into this screen`,
        edit_keyboard: "a reply/ForceReply keyboard needs a new message", widget_unsupported: "widgets are off here; the screen's message is sent",
      };
      run.chat.push({ k: "note", text: `Fallback: ${why[eff.reason] ?? eff.reason} → new message.`, tone: "warn" });
    } else if (eff.type === "link") run.chat.push({ k: "note", text: `Opens ${eff.url} (not followed in the simulator)`, tone: "info" });
    else if (eff.type === "noop") run.chat.push({ k: "note", text: eff.reason, tone: "info" });
  }
  for (const d of entry.diagnostics ?? []) run.chat.push({ k: "note", text: `${d.code}: ${d.message}`, tone: d.severity === "error" ? "error" : "warn" });
}

function TraceStep({ e, last }: { e: Doc; last: boolean }) {
  const u = e.update ?? {};
  const upd = u.type === "message" ? `message “${u.text}”` : u.type === "callback_query" ? `press ${u.actionId}${u.message ? ` on #${u.message}` : ""}` : u.type === "event" ? `event ${u.eventKey}` : `local ${JSON.stringify(Object.fromEntries(Object.entries(u).filter(([k]) => k !== "type")))}`;
  const t = e.transition;
  return (
    <li className={cn("rounded-md border p-2 text-xs break-words", last && "border-ring")}>
      <div className="font-medium">#{e.step} · {upd}</div>
      {e.action && <div><span className="text-muted-foreground">action</span> <span className="font-mono">{e.action.screenId}/{e.action.actionId ?? e.action.field} ({e.action.type})</span></div>}
      {t && (
        <div>
          <span className="text-muted-foreground">transition</span> <span className="font-mono">{t.from ?? "∅"} → {t.to}</span> via <span className="font-mono">{t.via}</span>
          {t.rule && <span className="block pl-3 font-mono">rule {t.rule.field}: {t.rule.matched ? "matched" : "not matched"} → {t.rule.branch}</span>}
        </div>
      )}
      {(e.effects ?? []).length > 0 && (
        <div><span className="text-muted-foreground">effects</span> <span className="font-mono">{e.effects.map((x: Doc) => x.type + (x.instance ? ` #${x.instance}` : "") + (x.type === "answer" && x.text ? ` “${x.text}”` : "") + (x.reason ? ` (${x.reason})` : "")).join(", ")}</span></div>
      )}
      {(e.diagnostics ?? []).map((d: Doc, i: number) => <div key={i} className={d.severity === "error" ? "text-destructive" : "text-warning"}>{d.code}: {d.message}</div>)}
    </li>
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

  const [start, setStart] = useState(commands[0] ? `cmd:${commands[0].command}` : "");
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

  const context = () => ({ chat, ...ctx });
  const begin = () => {
    queues.current = null;
    setParity({ state: "idle" });
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
    const r: Run = { session: newSession(project, { locale, context: context(), data: exampleValues(project) }), chat: [], trace: [], toast: null, scenarioId: null, touched: null };
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
  const forcePh = awaiting?.keyboard?.type === "force_reply" ? eng.render(s as Session, awaiting.id).keyboard.placeholder : null;
  const sc = run?.scenarioId ? loaded.scenarios[run.scenarioId] : null;
  const replay = sc && loaded.cliProject ? `py -3 studio/bot-ui.py simulate --scenario ${sc.scenarioId} --project "${loaded.cliProject}"` : null;

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
    <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[300px_minmax(0,1fr)_340px]">
      <section aria-label="Simulator controls" className="space-y-3 border-b p-3 sm:p-4 lg:border-r lg:border-b-0">
        <h2 className="text-base font-semibold">Simulator</h2>
        <p className="text-xs text-muted-foreground">Runs the bot-ui engine in this page on your current draft. Nothing is sent to Telegram.</p>
        <Field label="Start from" htmlFor="sim-start">
          <NativeSelect id="sim-start" value={start} onChange={(e) => setStart(e.target.value)} className="w-full">
            {commands.map((c: Doc) => <NativeSelectOption key={c.command} value={`cmd:${c.command}`}>/{c.command} → {c.screen}</NativeSelectOption>)}
            <NativeSelectOption value="screen">A screen…</NativeSelectOption>
            {scenarios.length > 0 && <optgroup label="Scenario fixtures">{scenarios.map((x) => <option key={x.scenarioId} value={`scenario:${x.scenarioId}`}>{x.scenarioId}{x.title ? ` · ${x.title}` : ""}</option>)}</optgroup>}
          </NativeSelect>
        </Field>
        {start === "screen" && (
          <Field label="Screen" htmlFor="sim-screen">
            <NativeSelect id="sim-screen" value={startScreen} onChange={(e) => setStartScreen(e.target.value)} className="w-full font-mono text-[13px]">
              {Object.keys(working.screens).sort().map((id) => <NativeSelectOption key={id} value={id}>{id}</NativeSelectOption>)}
            </NativeSelect>
          </Field>
        )}
        <div className="flex gap-2">
          <Button type="button" onClick={begin} className="flex-1">{run ? <><RotateCcw className="size-4" /> Restart clean</> : <><Play className="size-4" /> Start</>}</Button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Language" htmlFor="sim-locale">
            <NativeSelect id="sim-locale" value={locale} className="w-full" onChange={(e) => { setLocale(e.target.value); act({ locale: e.target.value }); }}>
              {ls.map((l) => <NativeSelectOption key={l} value={l}>{l}</NativeSelectOption>)}
            </NativeSelect>
          </Field>
          <Field label="Chat" htmlFor="sim-chat">
            <NativeSelect id="sim-chat" value={chat} className="w-full" onChange={(e) => { setChat(e.target.value); act({ context: { chat: e.target.value } }); }}>
              <NativeSelectOption value="private">private</NativeSelectOption>
              <NativeSelectOption value="group">group</NativeSelectOption>
            </NativeSelect>
          </Field>
          {enumContext.map(([n, f]) => (
            <Field key={n} label={n} htmlFor={`sim-ctx-${n}`} className="col-span-2">
              <div role="radiogroup" id={`sim-ctx-${n}`} aria-label={n} className="flex flex-wrap gap-1">
                {(f.values ?? []).map((v: any) => (
                  <button key={String(v)} type="button" role="radio" aria-checked={ctx[n] === v}
                    className="rounded-md border px-2 py-1 text-xs aria-checked:border-primary aria-checked:bg-primary aria-checked:text-primary-foreground"
                    onClick={() => { setCtx({ ...ctx, [n]: v }); act({ context: { [n]: v } }); }}>{String(v)}</button>
                ))}
              </div>
            </Field>
          ))}
          <Field label="Theme" htmlFor="sim-theme" className="col-span-2">
            <div role="radiogroup" id="sim-theme" aria-label="Theme" className="flex gap-1">
              {(["light", "dark"] as const).map((t) => (
                <button key={t} type="button" role="radio" aria-checked={theme === t} onClick={() => setTheme(t)}
                  className="rounded-md border px-2 py-1 text-xs aria-checked:border-primary aria-checked:bg-primary aria-checked:text-primary-foreground">{t}</button>
              ))}
            </div>
          </Field>
        </div>
        {handlers.length > 0 && (
          <fieldset className="space-y-2 rounded-md border p-2">
            <legend className="px-1 text-xs font-medium text-muted-foreground">Handler outcomes (interactive presses)</legend>
            {handlers.map(([h, d]) => (
              <Field key={h} label={h} htmlFor={`sim-h-${h}`}>
                <NativeSelect id={`sim-h-${h}`} size="sm" value={outcome[h] ?? ""} className="w-full" onChange={(e) => setOutcome({ ...outcome, [h]: e.target.value })}>
                  {(d.outcomes ?? []).map((o: string) => <NativeSelectOption key={o} value={o}>{o}</NativeSelectOption>)}
                </NativeSelect>
              </Field>
            ))}
          </fieldset>
        )}
        {events.length > 0 && (
          <fieldset className="space-y-2 rounded-md border p-2">
            <legend className="px-1 text-xs font-medium text-muted-foreground">Fire an event</legend>
            <NativeSelect aria-label="Event" size="sm" value={eventKey} className="w-full" onChange={(e) => setEventKey(e.target.value)}>
              {events.map((e: Doc) => <NativeSelectOption key={e.eventKey} value={e.eventKey}>{e.eventKey} → {e.screen}</NativeSelectOption>)}
            </NativeSelect>
            <label className="sr-only" htmlFor="sim-ev-data">Event data (JSON)</label>
            <Textarea id="sim-ev-data" rows={3} value={eventData} onChange={(e) => setEventData(e.target.value)} className="font-mono text-xs" />
            <Button type="button" size="sm" variant="secondary" disabled={!run}
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
          </fieldset>
        )}
      </section>

      <section aria-label="Chat" className="flex min-h-[70svh] flex-col p-3 sm:p-4 lg:h-[calc(100svh-3.5rem)] lg:min-h-0">
        <figure className="mx-auto flex min-h-0 w-full max-w-[440px] flex-1 flex-col overflow-hidden rounded-xl border">
          <div className="tg-chat relative flex min-h-0 flex-1 flex-col" data-theme={theme}>
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-3" aria-live="polite">
              {!run && <p className="m-auto text-center text-sm tg-hint">Press Start to open the bot.</p>}
              {run?.chat.map((c, i) => c.k === "bot" ? (
                <div key={`b${c.instance}`} className="flex flex-col items-start">
                  <Bubble logical={c.render} edited={c.edited > 0} widget={c.widget} highlight={run.touched === c.instance}
                    label={<span className="font-mono">#{c.instance}</span>}
                    onPress={(aid) => act({ press: aid, message: c.instance })} />
                </div>
              ) : c.k === "user" ? (
                <div key={i} className="ml-auto max-w-[80%] rounded-xl rounded-br-sm bg-[#e1ffc7] px-3 py-1.5 text-[15px] text-black dark:bg-[#2b5278] dark:text-white">{c.text}</div>
              ) : (
                <p key={i} className={cn("mx-auto max-w-[90%] rounded-full px-3 py-0.5 text-center text-xs",
                  c.tone === "error" ? "bg-red-700 text-white" : c.tone === "warn" ? "bg-amber-200 text-amber-950" : "bg-black/35 text-white")}>{c.text}</p>
              ))}
              <div ref={chatEnd} />
            </div>
            {run?.toast && (
              <div role="status" className="absolute inset-x-0 top-3 mx-auto w-fit max-w-[85%] rounded-lg bg-black/80 px-3 py-2 text-center text-sm text-white shadow-lg">{run.toast.text}</div>
            )}
            <Composer key={run?.trace.length ?? 0} placeholder={forcePh || (reply ? "Message or a key below" : "Message, e.g. /start")} disabled={!run} onSend={(text) => act({ text })} />
            {reply && reply.keyboard.type === "reply" && <ReplyKeyboard logical={reply} onKey={(text) => act({ text })} />}
          </div>
          <PreviewCaption contextLabel={`${chat} chat · ${locale}${enumContext.map(([n]) => ` · ${n}=${ctx[n]}`).join("")} · ${theme}`} />
        </figure>
      </section>

      <section aria-label="Trace" className="flex min-h-0 flex-col border-t p-3 sm:p-4 lg:h-[calc(100svh-3.5rem)] lg:border-t-0 lg:border-l">
        <h2 className="text-sm font-semibold">Trace</h2>
        <p className="mb-2 text-[11px] text-muted-foreground">update → action → transition → effects, per step</p>
        {sc && (
          <div className="mb-2 space-y-1.5 rounded-md border bg-muted/30 p-2 text-xs">
            <div>Scenario <span className="font-mono">{sc.scenarioId}</span>: {run?.trace.some((e) => e.diagnostics?.some((d: Doc) => d.severity === "error")) ? <span className="text-destructive">failed</span> : <span className="text-success">all expectations met</span>}</div>
            {replay && (
              <div className="flex items-start gap-1">
                <code className="min-w-0 flex-1 rounded bg-background p-1 text-[11px] break-all">{replay}</code>
                <Button type="button" size="icon" variant="ghost" className="size-7" aria-label="Copy the CLI replay command"
                  onClick={async () => { if (await copyText(replay)) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
                  {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                </Button>
              </div>
            )}
            {caps.save && (
              <div className="flex items-center gap-2">
                <Button type="button" size="sm" variant="outline" className="h-7" onClick={crossCheck} disabled={parity.state === "busy"}>Cross-check with the Python engine</Button>
                {parity.state === "same" && <span className="text-success">identical</span>}
                {parity.state === "diff" && <span className="text-destructive">differs: {parity.text}</span>}
                {parity.state === "error" && <span className="text-destructive">{parity.text}</span>}
              </div>
            )}
          </div>
        )}
        <ol className="min-h-0 flex-1 space-y-1.5 overflow-y-auto" aria-label="Trace steps">
          {run?.trace.map((e, i) => <TraceStep key={i} e={e} last={i === run.trace.length - 1} />)}
          <li ref={traceEnd} aria-hidden className="h-px" />
        </ol>
      </section>
    </div>
  );
}
