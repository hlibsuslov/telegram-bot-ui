// Port of skills/telegram-bot-ui/scripts/bot_ui/engine.py (see its docstring for events, effects and policies).
import { type Doc, EDITABLE_MEDIA, keyboardRows, localized, renderScreen, type Logical } from "./render.ts";

export const HISTORY_MAX = 20;
const DEFAULT_TEXTS: Doc = {
  stale: { en: "This button is out of date.", ru: "Эта кнопка устарела.", uk: "Ця кнопка застаріла." },
  disabled: { en: "Not available right now.", ru: "Сейчас недоступно.", uk: "Зараз недоступно." },
};

export interface Snapshot { project: Doc; screens: Record<string, Doc>; scenarios?: Record<string, Doc>; revision?: string }
export interface Session {
  screen: string | null; locale: string; context: Doc; state: Doc; data: Doc; input: Doc; history: string[];
  messages: { instance: number; screen: string; state: string | null; kind: string; media?: string | null; accessible: boolean; rich?: string[] }[];
  active: number | null; reply: string | null; awaiting: string | null; next: number;
}
export type HandlerFn = (handlerId: string, ctx: Doc) => string;

export function newSession(project: Doc, o: { locale?: string; context?: Doc; data?: Doc } = {}): Session {
  return {
    screen: null, locale: o.locale || project.defaultLocale || "en", context: { ...(o.context ?? {}) }, state: {},
    data: { ...(o.data ?? {}) }, input: {}, history: [], messages: [], active: null, reply: null, awaiting: null, next: 1,
  };
}

export class Engine {
  project: Doc;
  snap: Snapshot;
  handler?: HandlerFn;
  constructor(snap: Snapshot, handler?: HandlerFn) { this.snap = snap; this.handler = handler; this.project = snap.project ?? {}; }

  private text(key: string, locale: string): string {
    const custom = (this.project.messages ?? {})[key];
    return localized(custom || DEFAULT_TEXTS[key], locale, "en") ?? "";
  }
  values(s: Session): Doc { return { ...s.data, ...s.context, ...s.state, ...s.input }; }
  render(s: Session, sid: string, state: string | null = null): Logical {
    return renderScreen(this.project, this.snap.screens[sid], { locale: s.locale, state, values: this.values(s) });
  }
  view(l: Logical): Doc {
    return { screenId: l.screenId, state: l.state, text: l.text, media: l.media ? l.media.type : null,
      keyboard: { type: l.keyboard.type, rows: l.keyboard.rows.map((r) => r.map((b) => ({ actionId: b.actionId, text: b.text }))) },
      richButtons: l.richButtons.map((b) => ({ actionId: b.actionId, text: b.text })) };
  }
  private widgetsOk(s: Session): boolean {
    return !!(this.project.capabilities ?? {}).widgets && (s.context.chat ?? "private") === "private";
  }
  private fieldValue(s: Session, name: string): any {
    const fd = (this.project.fields ?? {})[name] ?? {};
    return fd.source === "state" ? s.state[name] : s.context[name];
  }

  private show(s: Session, sid: string, o: { origin: string; presentation: string | null; instance: number | null; effects: Doc[]; state?: string | null }) {
    const state = o.state ?? null;
    const screen = this.snap.screens[sid];
    const logical = this.render(s, sid, state);
    let isWidget = !!screen.widget;
    let wantEdit = o.origin === "callback" && (o.presentation || "edit") === "edit" && o.instance !== null;
    const msg = s.messages.find((m) => m.instance === o.instance);
    if (isWidget && !this.widgetsOk(s)) {
      o.effects.push({ type: "fallback", reason: "widget_unsupported", screenId: sid });
      isWidget = false;
    }
    const ktype = (screen.keyboard ?? {}).type ?? "none";
    const targetMedia = logical.media ? logical.media.type : null;
    const mediaOk = editOk(msg?.media ?? null, targetMedia);
    if (wantEdit && msg && (!msg.accessible || msg.kind !== "message" || isWidget || !mediaOk || !["inline", "none"].includes(ktype))) {
      const reason = !msg.accessible ? "edit_unavailable" : msg.kind !== "message" || isWidget || !mediaOk ? "edit_kind" : "edit_keyboard";
      o.effects.push({ type: "fallback", reason, instance: o.instance });
      wantEdit = false;
    }
    // The callback buttons inside this rendering of a rich document (this locale, this state):
    // a press is checked against what the user was actually shown.
    const richIds = logical.richButtons.filter((b) => b.actionId && b.callbackData).map((b) => b.actionId as string);
    let target: number;
    if (wantEdit && msg) {
      msg.screen = sid; msg.state = state; msg.media = targetMedia; msg.rich = richIds;
      o.effects.push({ type: "edit", instance: o.instance, render: logical, view: this.view(logical) });
      target = o.instance as number;
    } else {
      target = s.next++;
      const kind = isWidget ? "widget" : "message";
      s.messages.push({ instance: target, screen: sid, state, kind, media: isWidget ? null : targetMedia, accessible: true, rich: isWidget ? [] : richIds });
      const eff: Doc = { type: "send", instance: target, kind, render: logical, view: this.view(logical) };
      if (isWidget) eff.widget = screen.widget.ref;
      o.effects.push(eff);
    }
    if (state === null) {
      s.screen = sid;
      const kt = (screen.keyboard ?? {}).type ?? "none";
      if (kt === "inline" || richIds.length) s.active = target;
      if (kt === "reply") s.reply = sid;
      else if (kt === "remove") s.reply = null;
      s.awaiting = screen.input && typeof screen.input === "object" ? sid : null;
    }
  }

  private navigate(s: Session, target: string, via: string, o: { origin: string; presentation: string | null; instance: number | null; effects: Doc[]; push?: boolean }): Doc {
    const from = s.screen;
    if ((o.push ?? true) && from && from !== target) s.history = [...s.history, from].slice(-HISTORY_MAX);
    this.show(s, target, o);
    return { from, to: target, via };
  }

  feed(s: Session, event: Doc): Doc {
    const effects: Doc[] = [];
    const entry: Doc = { update: summary(event), action: null, transition: null, effects, diagnostics: [] };
    if ("command" in event) this.command(s, String(event.command).replace(/^\/+/, "").split("@")[0], entry);
    else if ("text" in event) {
      const text = String(event.text);
      if (text.startsWith("/")) this.command(s, text.slice(1).split(/\s/)[0].split("@")[0], entry);
      else this.textIn(s, text, entry);
    } else if ("press" in event) this.press(s, String(event.press), event.message ?? null, entry, "callback");
    else if ("event" in event) this.event(s, event, entry);
    else if ("context" in event) Object.assign(s.context, event.context);
    else if ("locale" in event) s.locale = event.locale;
    else if ("inaccessible" in event) { for (const m of s.messages) if (m.instance === event.inaccessible) m.accessible = false; }
    else if ("expect" in event) this.expect(s, event.expect, entry);
    else entry.diagnostics.push({ code: "EVENT_UNKNOWN", severity: "error", message: `unknown event ${JSON.stringify(event)}` });
    return entry;
  }

  private command(s: Session, cmd: string, entry: Doc) {
    const ep = (this.project.entryPoints ?? []).find((e: Doc) => e.type === "command" && e.command === cmd);
    if (!ep) { entry.effects.push({ type: "noop", reason: `/${cmd} is not an entry point` }); return; }
    s.history = [];
    entry.transition = this.navigate(s, ep.screen, `entry:${ep.id ?? cmd}`, { origin: "text", presentation: "send", instance: null, effects: entry.effects, push: false });
  }

  private textIn(s: Session, text: string, entry: Doc) {
    if (s.reply) {
      const logical = this.render(s, s.reply);
      for (const row of logical.keyboard.rows) for (const b of row) {
        if (b.text === text) { this.press(s, b.actionId, null, entry, "reply", s.reply); return; }
      }
    }
    if (s.awaiting) {
      const screen = this.snap.screens[s.awaiting];
      const inp = screen.input;
      const fd = (this.project.fields ?? {})[inp.field] ?? {};
      if (fd.maxLength && [...text].length > fd.maxLength) {
        entry.diagnostics.push({ code: "INPUT_TOO_LONG", severity: "warning", message: `${[...text].length} > ${fd.maxLength} characters; the screen is shown again` });
        this.show(s, screen.id, { origin: "text", presentation: "send", instance: null, effects: entry.effects });
        return;
      }
      s.input[inp.field] = text;
      entry.action = { screenId: screen.id, actionId: null, type: "input", field: inp.field };
      entry.transition = this.navigate(s, inp.to, "input", { origin: "text", presentation: "send", instance: null, effects: entry.effects });
      return;
    }
    entry.effects.push({ type: "noop", reason: "text is not expected here" });
  }

  private press(s: Session, aid: string, instance: number | null, entry: Doc, origin: string, screenId: string | null = null) {
    let screen: Doc, act: Doc;
    if (origin === "callback") {
      instance = instance ?? s.active;
      const msg = s.messages.find((m) => m.instance === instance);
      screenId = msg ? msg.screen : null;
      const current = !!msg && instance === s.active && msg.state === null;
      screen = this.snap.screens[screenId ?? ""];
      act = screen?.actions?.[aid];
      const onKb = !!screen && (keyboardRows(screen).some((r) => r.includes(aid)) || (msg?.rich ?? []).includes(aid));
      if (!(current && act && onKb)) {
        entry.action = { screenId, actionId: aid, type: "stale" };
        entry.effects.push({ type: "answer", text: this.text("stale", s.locale) });
        return;
      }
    } else {
      screen = this.snap.screens[screenId as string];
      act = screen.actions[aid];
    }
    const t = act.type;
    const def = this.project.defaultLocale ?? "en";
    entry.action = { screenId, actionId: aid, type: t };
    for (const [k, v] of Object.entries(act.set ?? {})) s.state[k] = v;
    const eff = entry.effects as Doc[];
    const ack = origin === "callback";
    const pres = act.presentation ?? null;
    if (t === "url") { eff.push({ type: "link", url: act.url ?? null }); return; }
    if (t === "answer") { eff.push({ type: "answer", text: localized(act.text, s.locale, def) }); return; }
    if (t === "disabled") { eff.push({ type: "answer", text: this.text("disabled", s.locale) }); return; }
    if (t === "navigate") {
      if (ack) eff.push({ type: "answer", text: null });
      if (act.rule && typeof act.rule === "object") {
        const r = act.rule;
        const matched = this.fieldValue(s, r.when.field) === r.when.eq;
        const branch = matched ? "match" : "otherwise";
        const tr = this.navigate(s, r[branch], `rule:${branch}`, { origin, presentation: pres, instance, effects: eff });
        tr.rule = { field: r.when.field, matched, branch };
        entry.transition = tr;
      } else {
        entry.transition = this.navigate(s, act.to, "to", { origin, presentation: pres, instance, effects: eff });
      }
      return;
    }
    if (t === "back") {
      if (ack) eff.push({ type: "answer", text: null });
      let target: string | null, via: string;
      if (s.history.length) { target = s.history.pop() as string; via = "back"; }
      else { target = act.fallback ?? null; via = "back-fallback"; }
      if (!target) { eff.push({ type: "noop", reason: "no history and no fallback" }); return; }
      entry.transition = this.navigate(s, target, via, { origin, presentation: pres, instance, effects: eff, push: false });
      return;
    }
    if (t === "handler") {
      const hid = act.handlerId;
      eff.push(ack ? { type: "answer", text: localized(act.pending, s.locale, def) } : { type: "noop", reason: "handler started" });
      const states = (screen.message ?? {}).states ?? {};
      if ("loading" in states && origin === "callback") {
        this.show(s, screenId as string, { origin: "callback", presentation: "edit", instance, effects: eff, state: "loading" });
      }
      const outcome = this.handler ? this.handler(hid, { screenId, actionId: aid, session: s }) : null;
      const target = outcome ? (act.outcomes ?? {})[outcome] : null;
      if (!target) {
        entry.diagnostics.push({ code: "HANDLER_RESULT_UNKNOWN", severity: "error", message: `${hid} returned ${JSON.stringify(outcome)}, which has no target` });
        return;
      }
      entry.transition = this.navigate(s, target, `outcome:${outcome}`, { origin, presentation: pres, instance, effects: eff });
    }
  }

  private event(s: Session, event: Doc, entry: Doc) {
    const ep = (this.project.entryPoints ?? []).find((e: Doc) => e.type === "event" && e.eventKey === event.event);
    if (!ep) { entry.effects.push({ type: "noop", reason: `no entry point for event ${event.event}` }); return; }
    Object.assign(s.data, event.data ?? {});
    entry.transition = this.navigate(s, ep.screen, `event:${event.event}`, { origin: "event", presentation: "send", instance: null, effects: entry.effects });
  }

  private expect(s: Session, exp: Doc, entry: Doc) {
    if ("screen" in exp && s.screen !== exp.screen) {
      entry.diagnostics.push({ code: "EXPECT_SCREEN", severity: "error", message: `expected screen ${exp.screen}, got ${s.screen}` });
    }
    if ("contains" in exp) {
      const last = [...s.messages].reverse().find((m) => m.screen === s.screen);
      const text = last ? this.render(s, last.screen, last.state).text : "";
      if (!text.includes(exp.contains)) {
        entry.diagnostics.push({ code: "EXPECT_TEXT", severity: "error", message: `text of ${s.screen} does not contain ${JSON.stringify(exp.contains)}` });
      }
    }
  }
}

/** What Telegram edits in place: text -> text, text or editable media -> editable media. */
export function editOk(current: string | null, target: string | null): boolean {
  if (target === null) return current === null;
  return EDITABLE_MEDIA.has(target) && (current === null || EDITABLE_MEDIA.has(current));
}

export function summary(event: Doc): Doc {
  if ("command" in event) return { type: "message", text: "/" + String(event.command).replace(/^\/+/, "") };
  if ("text" in event) return { type: "message", text: event.text };
  if ("press" in event) {
    const out: Doc = { type: "callback_query", actionId: event.press };
    if ("message" in event) out.message = event.message;
    return out;
  }
  if ("event" in event) return { type: "event", eventKey: event.event };
  return { type: "local", ...event };
}

export function runScenario(snap: Snapshot, scenario: Doc, overrides: Doc = {}): Doc {
  const sc = structuredClone(scenario);
  if (overrides.locale) sc.locale = overrides.locale;
  sc.context = { ...(sc.context ?? {}), ...(overrides.context ?? {}) };
  const queues: Record<string, string[]> = {};
  for (const [k, v] of Object.entries(sc.handlers ?? {})) queues[k] = [...(v as string[])];
  const eng = new Engine(snap, (hid) => (queues[hid] ?? []).shift() ?? "");
  const s = newSession(snap.project, { locale: sc.locale, context: sc.context, data: sc.data });
  const trace: Doc[] = [];
  (sc.steps ?? []).forEach((ev: Doc, i: number) => { const e = eng.feed(s, ev); e.step = i + 1; trace.push(e); });
  const ok = !trace.some((e) => e.diagnostics.some((d: Doc) => d.severity === "error"));
  return { ok, scenarioId: sc.scenarioId ?? null, revision: snap.revision, locale: s.locale, trace, final: { screen: s.screen, history: s.history } };
}

export function parityView(result: Doc): Doc {
  return {
    ok: result.ok, scenarioId: result.scenarioId, final: result.final,
    steps: result.trace.map((e: Doc) => ({
      step: e.step, update: e.update, action: e.action, transition: e.transition,
      effects: e.effects.map((x: Doc) => Object.fromEntries(Object.entries(x).filter(([k]) => k !== "render"))),
      diagnostics: e.diagnostics.map((d: Doc) => d.code),
    })),
  };
}
