// Friendly editors for widget.json: message (caption, fallback screen), data & demo states, send
// options. Every edit rewrites widget.json as a draft file (2-space JSON, key order kept).
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { renderScreen, type Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { defaultLocale, exampleValues, locales, utf8Bytes } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { Field, ScreenPicker, Segmented } from "../inspector/fields";
import { ScreenPreview } from "../preview/Telegram";

export type UpdateMeta = (fn: (meta: Doc) => void) => void;

export function Section({ title, hint, children, className, id, bare }: { title: string; hint?: string; children: ReactNode; className?: string; id?: string; bare?: boolean }) {
  if (bare) return <div id={id} className={cn("space-y-3", className)}>{children}</div>;
  return (
    <section id={id} className={cn("space-y-3 rounded-xl bg-card p-4 ring-1 ring-border", className)} aria-label={title}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

export function MessageSection({ wid, meta, update, lang, bare }: { wid: string; meta: Doc; update: UpdateMeta; lang: string; bare?: boolean }) {
  const { loaded, working, editLocale } = useStudio();
  const ls = locales(loaded.project);
  const def = defaultLocale(loaded.project);
  const loc = ls.includes(editLocale) ? editLocale : def;
  const cap = meta.caption;
  const capObj: Doc = typeof cap === "string" ? { [def]: cap } : cap && typeof cap === "object" ? cap : {};
  const missing = ls.filter((l) => !capObj[l]);
  const fb = meta.fallbackScreen && working.screens[meta.fallbackScreen];
  return (
    <Section bare={bare} title="Message" hint="What arrives with the widget: the caption under it, and the screen sent where widgets are unavailable.">
      <Field label={<>Caption <span className="font-mono text-[10px] uppercase">{loc}</span></>} htmlFor={`${wid}-caption`}
        extra={missing.length > 0 ? <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-900">missing in {missing.join(", ")}</span> : undefined}
        hint="{field} placeholders are filled from your data (example values here).">
        <Input id={`${wid}-caption`} value={capObj[loc] ?? ""} placeholder={loc === def ? "No caption" : `Empty: ${loc} users see the ${def} caption`}
          onChange={(e) => update((m) => { const c: Doc = typeof m.caption === "object" && m.caption ? m.caption : typeof m.caption === "string" ? { [def]: m.caption } : {}; c[loc] = e.target.value; if (!c[loc]) delete c[loc]; m.caption = c; })} />
      </Field>
      <Field label="Fallback screen" htmlFor={`${wid}-fallback`} hint="Sent instead of the widget in groups or where widgets are off.">
        <ScreenPicker id={`${wid}-fallback`} value={meta.fallbackScreen ?? ""} allowEmpty="No fallback screen"
          onChange={(v) => update((m) => { if (v) m.fallbackScreen = v; else delete m.fallbackScreen; })} />
      </Field>
      {fb && (
        <ScreenPreview logical={renderScreen(loaded.project, fb, { locale: lang, values: exampleValues(loaded.project) })} theme="light" hideWidget
          contextLabel={`fallback · ${meta.fallbackScreen}`} />
      )}
    </Section>
  );
}

function ValueInput({ id, value, onChange }: { id: string; value: any; onChange: (v: any) => void }) {
  const [raw, setRaw] = useState(() => JSON.stringify(value));
  const [err, setErr] = useState("");
  if (typeof value === "boolean") return <Switch id={id} checked={value} onCheckedChange={onChange} />;
  if (typeof value === "number") return <Input id={id} type="number" value={value} onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))} className="font-mono text-[13px]" />;
  if (typeof value === "string" || value === null) return <Input id={id} value={value ?? ""} placeholder="null" onChange={(e) => onChange(e.target.value)} className="text-[13px]" />;
  return (
    <div>
      <Textarea id={id} rows={2} value={raw} className="font-mono text-xs" onChange={(e) => {
        setRaw(e.target.value);
        try { onChange(JSON.parse(e.target.value)); setErr(""); } catch (ex) { setErr((ex as Error).message); }
      }} />
      {err && <p className="text-[11px] text-destructive">{err}</p>}
    </div>
  );
}

function DataEditor({ wid, state, field, value, update, limit }: { wid: string; state: string; field: "chatData" | "publicData"; value: Doc | undefined; update: UpdateMeta; limit: number }) {
  const [raw, setRaw] = useState(false);
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [err, setErr] = useState("");
  const bytes = value ? utf8Bytes(JSON.stringify(value)) : 0;
  const set = (fn: (d: Doc) => void) => update((m) => { m.states ??= {}; m.states[state] ??= {}; m.states[state][field] ??= {}; fn(m.states[state][field]); });
  const isObj = value && typeof value === "object" && !Array.isArray(value);
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold">{field === "chatData" ? "chat_data" : "public_data"}</span>
        <span className={cn("font-mono text-[11px]", bytes > limit ? "font-semibold text-destructive" : "text-muted-foreground")}>{bytes} / {limit} B</span>
        <span className="h-1.5 min-w-16 flex-1 overflow-hidden rounded-full bg-muted" role="meter" aria-label={`${field} size`} aria-valuemin={0} aria-valuemax={limit} aria-valuenow={bytes}>
          <span className={cn("block h-full rounded-full", bytes > limit ? "bg-destructive" : bytes > limit * 0.85 ? "bg-amber-500" : "bg-emerald-600")} style={{ width: `${Math.min(100, (bytes / limit) * 100)}%` }} />
        </span>
        <span><Segmented size="xs" label={`${field} editor`} value={raw ? "raw" : "form"} onChange={(v) => { setRaw(v === "raw"); setText(JSON.stringify(value ?? {}, null, 2)); setErr(""); }}
          options={[{ value: "form", label: "Form" }, { value: "raw", label: "JSON" }]} /></span>
      </div>
      {!value && !raw && <p className="text-xs text-muted-foreground">Not sent in this state. <button type="button" className="underline" onClick={() => set(() => undefined)}>Add an empty object</button></p>}
      {value && !raw && isObj && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2">
          {Object.entries(value).map(([k, v]) => (
            <Field key={k} label={<span className="font-mono">{k}</span>} htmlFor={`${wid}-${state}-${field}-${k}`}>
              <ValueInput id={`${wid}-${state}-${field}-${k}`} value={v} onChange={(nv) => set((d) => { d[k] = nv; })} />
            </Field>
          ))}
        </div>
      )}
      {(raw || (value && !isObj)) && (
        <>
          <Textarea rows={6} value={text} className="font-mono text-xs" aria-label={`${field} JSON`} onChange={(e) => {
            setText(e.target.value);
            try { const v = JSON.parse(e.target.value); setErr(""); update((m) => { m.states ??= {}; m.states[state] ??= {}; m.states[state][field] = v; }); } catch (ex) { setErr((ex as Error).message); }
          }} />
          {err && <p className="text-[11px] text-destructive">Not valid JSON yet: {err}</p>}
        </>
      )}
    </div>
  );
}

export function DataSection({ wid, meta, update, state, setState, limit, bare }: { wid: string; meta: Doc; update: UpdateMeta; state: string; setState: (s: string) => void; limit: number; bare?: boolean }) {
  const states = Object.keys(meta.states ?? {});
  const [name, setName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const valid = /^[a-z0-9][a-z0-9_-]{0,31}$/.test(name) && !states.includes(name);
  const rename = (from: string, to: string) => update((m) => {
    m.states = Object.fromEntries(Object.entries(m.states ?? {}).map(([k, v]) => [k === from ? to : k, v]));
  });
  const st: Doc = meta.states?.[state] ?? {};
  return (
    <Section bare={bare} title="Data and demo states" hint="chat_data / public_data the bot sends with the widget. Each demo state is one example to preview.">
      <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Demo states">
        {states.map((s) => (
          <span key={s} className="flex items-center">
            {renaming === s ? (
              <form onSubmit={(e) => { e.preventDefault(); if (valid) { rename(s, name); setState(name); } setRenaming(null); setName(""); }}>
                <Input autoFocus value={name} onChange={(e) => setName(e.target.value.trim())} onBlur={() => setRenaming(null)} className="h-7 w-32 font-mono text-xs" aria-label={`New name for ${s}`} />
              </form>
            ) : (
              <button type="button" role="tab" aria-selected={state === s} onClick={() => setState(s)}
                className="rounded-full px-2.5 py-1 font-mono text-xs text-muted-foreground ring-1 ring-border aria-selected:bg-foreground aria-selected:text-background aria-selected:ring-foreground">{s}</button>
            )}
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <form className="flex items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); if (!valid) return; update((m) => { m.states = { ...(m.states ?? {}), [name]: JSON.parse(JSON.stringify(st)) }; }); setState(name); setName(""); }}>
          <Input value={renaming ? "" : name} onChange={(e) => setName(e.target.value.trim())} placeholder="new-state" className="h-8 w-36 font-mono text-xs" aria-label="New state name" />
          <Button type="submit" size="sm" variant="outline" className="h-8" disabled={!valid || !!renaming}><Plus className="size-3.5" /> Copy of {state}</Button>
        </form>
        <Button size="sm" variant="ghost" className="h-8" onClick={() => { setName(state); setRenaming(state); }}><Pencil className="size-3.5" /> Rename</Button>
        {states.length > 1 && (
          <Button size="sm" variant="ghost" className="h-8 text-destructive" onClick={() => { const next = states.find((x) => x !== state)!; update((m) => { delete m.states[state]; }); setState(next); }}>
            <Trash2 className="size-3.5" /> Delete {state}
          </Button>
        )}
      </div>
      <DataEditor key={`${state}-chat`} wid={wid} state={state} field="chatData" value={st.chatData} update={update} limit={limit} />
      <DataEditor key={`${state}-public`} wid={wid} state={state} field="publicData" value={st.publicData} update={update} limit={limit} />
    </Section>
  );
}

export function SendSection({ meta, update, bare }: { meta: Doc; update: UpdateMeta; bare?: boolean }) {
  const send: Doc = meta.send ?? {};
  const set = (k: string, v: any) => update((m) => { m.send ??= {}; if (v === undefined || v === false || v === "") delete m.send[k]; else m.send[k] = v; });
  return (
    <Section bare={bare} title="Send options" hint="Parameters of sendWidget, outside the HTML.">
      <label className="flex items-center justify-between gap-3 text-sm"><span><span className="font-mono text-xs">allow_queries</span><span className="block text-xs text-muted-foreground">The widget may ask the bot (request()).</span></span>
        <Switch checked={!!send.allow_queries} onCheckedChange={(v) => set("allow_queries", v)} aria-label="allow_queries" /></label>
      <label className="flex items-center justify-between gap-3 text-sm"><span><span className="font-mono text-xs">is_shared</span><span className="block text-xs text-muted-foreground">One shared widget for everyone in the chat.</span></span>
        <Switch checked={!!send.is_shared} onCheckedChange={(v) => set("is_shared", v)} aria-label="is_shared" /></label>
      <div className="grid grid-cols-2 gap-2">
        {(["width", "height"] as const).map((k) => (
          <Field key={k} label={<span className="font-mono">{k}</span>} htmlFor={`send-${k}`} hint="empty = auto">
            <Input id={`send-${k}`} type="number" min={0} max={600} value={send[k] ?? ""} onChange={(e) => set(k, e.target.value === "" ? undefined : Number(e.target.value))} className="font-mono text-[13px]" />
          </Field>
        ))}
      </div>
    </Section>
  );
}
