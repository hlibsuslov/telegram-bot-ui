// Visual builder flow for widgets with `builder` in widget.json: Template, Content and logic,
// Design, Check. The form is generated from the builder schema; every edit rewrites only
// widget.json `builder` as a draft (saved through the usual Changes / /api/save path).
import {
  AlarmClock, ArrowDown, ArrowUp, Brush, Check, ClipboardCopy, Code2, Eye, EyeOff, ImageUp, Link2, ListChecks, MessageSquare, MessageSquareText,
  Palette, Play, Plus, RotateCcw, Send, ShieldCheck, ShoppingBag, Ticket, Trash2, Undo2, type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Doc } from "@/core/render.ts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText } from "@/lib/api";
import { defaultLocale } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, Segmented } from "../../inspector/fields";
import { PhotoToSvg } from "../PhotoToSvg";
import { Step } from "../Step";
import {
  applicableFields, blockOn, changeStyle, charLen, choosePreset, defaultStyle, effectiveColors, effectiveCustom, getAt, keyOfPointer, localIssues,
  previewStates, resetColors, shortId, restoreMyDesign, setAt, setColor, switchType, utf8Len, type Issue, type Style,
} from "./logic";
import type { BField, BSchema } from "./schema";

// ------------------------------------------------------------------ schema and validation
let schemaPromise: Promise<{ schema: BSchema | null; error?: string }> | null = null;
export function loadSchema() {
  return (schemaPromise ??= api<BSchema>("/api/widget/builder-schema", {}).then((r) => {
    if (r.ok && r.data && typeof r.data === "object" && r.data.types) return { schema: r.data };
    schemaPromise = null; // try again next time
    return { schema: null, error: errorText(r.data) };
  }));
}
export function useBuilderSchema() {
  const [s, setS] = useState<{ schema: BSchema | null; error?: string } | null>(null);
  useEffect(() => { let live = true; void loadSchema().then((v) => { if (live) setS(v); }); return () => { live = false; }; }, []);
  return s;
}

function useIssues(builder: Doc, schema: BSchema | null, wid: string) {
  const [issues, setIssues] = useState<Issue[]>([]);
  const key = JSON.stringify(builder);
  useEffect(() => {
    if (!schema) return;
    let live = true;
    const t = setTimeout(async () => {
      const res = await api<Issue[] | { issues: Issue[] }>("/api/widget/builder-validate", { config: builder, widget: wid });
      if (!live) return;
      const list = res.ok ? (Array.isArray(res.data) ? res.data : (res.data as any)?.issues) : null;
      setIssues(Array.isArray(list) ? list : localIssues(builder, schema));
    }, 450);
    return () => { live = false; clearTimeout(t); };
    // builder is read through its JSON key
  }, [key, schema]);
  return issues;
}

const TYPE_ICON: Record<string, LucideIcon> = { message: MessageSquare, product: ShoppingBag, promo: Ticket, countdown: AlarmClock, quiz: ListChecks };
export const typeIcon = (t: string) => TYPE_ICON[t] ?? MessageSquareText;
// Telegram's default theme colours, shown on slots that inherit the chat theme.
const TG_DEFAULT: Record<"light" | "dark", Record<string, string>> = {
  light: { bg: "#ffffff", text: "#000000", hint: "#707579", button: "#3390ec", buttonText: "#ffffff", border: "#e7e7ea", counter: "#3390ec", counterText: "#ffffff", answer: "#3390ec", answerText: "#ffffff" },
  dark: { bg: "#212d3b", text: "#ffffff", hint: "#7d8b99", button: "#50a8eb", buttonText: "#ffffff", border: "#0f161e", counter: "#50a8eb", counterText: "#ffffff", answer: "#50a8eb", answerText: "#ffffff" },
};
const fieldDom = (key: string) => `bf-${key.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

// ------------------------------------------------------------------ field renderer
interface Ctx {
  locale: string; langs: string[]; svgs: string[]; issues: Issue[]; ptr: string; root: Doc;
  onPhoto: (apply: (name: string) => void) => void;
}

function Counter({ value, max, bytes }: { value: string; max?: number; bytes?: boolean }) {
  if (!max) return null;
  const n = bytes ? utf8Len(value) : charLen(value);
  return <span className={cn("font-mono text-[10.5px] tabular-nums", n > max ? "font-semibold text-destructive" : "text-muted-foreground")}>{n}/{max}{bytes ? " B" : ""}</span>;
}

function IssueLines({ list }: { list: Issue[] }) {
  if (!list.length) return null;
  return <ul className="mt-1 space-y-0.5">{list.map((i, n) => <li key={n} className="text-[11.5px] text-destructive">{i.message}</li>)}</ul>;
}

function ActionEditor({ value, onChange, ctx, label }: { value: Doc | undefined; onChange: (v: Doc) => void; ctx: Ctx; label: string }) {
  const v = value ?? { kind: "request" };
  const set = (k: string, x: any) => onChange({ ...v, [k]: x });
  const mine = (sub: string) => ctx.issues.filter((i) => i.pointer === `${ctx.ptr}/${sub}`);
  const doneText: string = v.done && typeof v.done === "object" ? v.done[ctx.locale] ?? "" : v.done ?? "";
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3">
      <Segmented label={label} value={v.kind ?? "request"} onChange={(k) => onChange({ kind: k })}
        options={[{ value: "request", label: <span className="inline-flex items-center gap-1"><Send className="size-3" />Tell the bot</span> },
          { value: "link", label: <span className="inline-flex items-center gap-1"><Link2 className="size-3" />Open a link</span> },
          { value: "copy", label: <span className="inline-flex items-center gap-1"><ClipboardCopy className="size-3" />Copy text</span> }]} />
      {v.kind === "request" && (
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="What the bot receives" extra={<Counter value={v.data ?? ""} max={64} bytes />} hint="Your bot decides what happens; {n} is the quantity.">
            <Input value={v.data ?? ""} onChange={(e) => set("data", e.target.value)} className="font-mono text-[13px]" />
            <IssueLines list={mine("data")} />
          </Field>
          <Field label={<>Shown after the tap <span className="font-mono text-[10px] uppercase">{ctx.locale}</span></>} extra={<Counter value={doneText} max={64} />}>
            <Input value={doneText} onChange={(e) => set("done", ctx.langs.length > 1 || (v.done && typeof v.done === "object")
              ? { ...(v.done && typeof v.done === "object" ? v.done : typeof v.done === "string" && v.done ? { [ctx.langs[0]]: v.done } : {}), [ctx.locale]: e.target.value }
              : e.target.value)} />
            <IssueLines list={[...mine("done"), ...mine(`done/${ctx.locale}`)]} />
          </Field>
        </div>
      )}
      {v.kind === "link" && (
        <Field label="Link (https://)" extra={<Counter value={v.url ?? ""} max={256} />}>
          <Input value={v.url ?? ""} onChange={(e) => set("url", e.target.value)} placeholder="https://" className="font-mono text-[13px]" />
          <IssueLines list={mine("url")} />
        </Field>
      )}
      {v.kind === "copy" && (
        <Field label="Text to copy" extra={<Counter value={v.text ?? ""} max={256} />} hint="Empty copies the button label.">
          <Input value={v.text ?? ""} onChange={(e) => set("text", e.target.value)} />
          <IssueLines list={mine("text")} />
        </Field>
      )}
    </div>
  );
}

function DateTimeField({ value, onChange }: { value: number | undefined; onChange: (v: number) => void }) {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [now] = useState(() => Math.floor(Date.now() / 1000));
  const p = (n: number) => String(n).padStart(2, "0");
  const local = (s: number) => { const d = new Date(s * 1000); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };
  const diff = value ? value - now : 0;
  const span = (s: number) => { const a = Math.abs(s); const d = Math.floor(a / 86400), h = Math.floor((a % 86400) / 3600), m = Math.floor((a % 3600) / 60); return [d && `${d} d`, h && `${h} h`, `${m} min`].filter(Boolean).join(" "); };
  return (
    <div className="space-y-1">
      <Input type="datetime-local" value={value ? local(value) : ""} onChange={(e) => e.target.value && onChange(Math.floor(new Date(e.target.value).getTime() / 1000))} />
      <p className="text-[11.5px] text-muted-foreground">Your time zone: {tz}. {value ? (diff > 0 ? `Ends in ${span(diff)}.` : `Ended ${span(diff)} ago.`) : "Not set."} Everyone sees the same moment.</p>
    </div>
  );
}

function Leaf({ f, value, onChange, ctx }: { f: BField; value: any; onChange: (v: any) => void; ctx: Ctx }) {
  const here = ctx.issues.filter((i) => i.pointer === ctx.ptr || i.pointer.startsWith(`${ctx.ptr}/`) && f.type === "text");
  if (f.type === "text") {
    const loc = f.localized ? ctx.locale : "";
    const obj: Doc = f.localized ? (value && typeof value === "object" ? value : typeof value === "string" ? { [ctx.langs[0]]: value } : {}) : {};
    const cur = f.localized ? obj[loc] ?? "" : value ?? "";
    const missing = f.localized ? ctx.langs.filter((l) => !obj[l]) : [];
    const set = (t: string) => onChange(f.localized ? { ...obj, [loc]: t } : t);
    const Comp = f.multiline ? Textarea : Input;
    return (
      <Field label={<>{f.label}{f.localized && <span className="ml-1 font-mono text-[10px] uppercase">{loc}</span>}</>}
        extra={<>{missing.length > 0 && cur && <span className="text-[10px] text-muted-foreground">missing in {missing.join(", ")}</span>}<Counter value={cur} max={f.max} /></>} hint={f.help}>
        <Comp value={cur} onChange={(e: React.ChangeEvent<HTMLInputElement & HTMLTextAreaElement>) => set(e.target.value)} rows={f.multiline ? 3 : undefined} aria-invalid={here.length > 0 || undefined} />
        <IssueLines list={here} />
      </Field>
    );
  }
  if (f.type === "number") {
    const n = typeof value === "number" ? value : f.default ?? f.min ?? 0;
    return (
      <Field label={<>{f.label} <span className="font-mono">{n}{f.unit ? ` ${f.unit}` : ""}</span></>} hint={f.help}>
        {f.min !== undefined && f.max !== undefined
          ? <Slider min={f.min} max={f.max} step={f.step ?? 1} value={[n]} onValueChange={([x]) => onChange(x)} aria-label={f.label} />
          : <Input type="number" value={n} onChange={(e) => onChange(Number(e.target.value))} />}
        <IssueLines list={here} />
      </Field>
    );
  }
  if (f.type === "toggle") return <label className="flex items-center justify-between gap-3 text-sm"><span>{f.label}{f.help && <span className="block text-xs text-muted-foreground">{f.help}</span>}</span><Switch checked={!!value} onCheckedChange={onChange} aria-label={f.label} /></label>;
  if (f.type === "choice") {
    const opts = f.options ?? [];
    return (
      <Field label={f.label} hint={f.help}>
        {opts.length <= 4
          ? <div><Segmented label={f.label} value={JSON.stringify(value ?? f.default ?? opts[0]?.value)} onChange={(x) => onChange(JSON.parse(x))} options={opts.map((o) => ({ value: JSON.stringify(o.value), label: o.label }))} /></div>
          : <EnumSelect label={f.label} value={JSON.stringify(value ?? "")} onChange={(x) => onChange(JSON.parse(x))} options={opts.map((o) => ({ value: JSON.stringify(o.value), label: o.label }))} />}
      </Field>
    );
  }
  if (f.type === "color") return <ColorRow label={f.label} value={value ?? null} onChange={onChange} />;
  if (f.type === "datetime") return <Field label={f.label} hint={f.help}><DateTimeField value={value} onChange={onChange} /><IssueLines list={here} /></Field>;
  if (f.type === "action") return <Field label={f.label}><ActionEditor value={value} onChange={onChange} ctx={ctx} label={f.label} /></Field>;
  if (f.type === "image") {
    return (
      <Field label={f.label} hint="An SVG picture from this widget; make one from a photo.">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-40 flex-1"><EnumSelect label={f.label} value={value ?? ""} onChange={(x) => onChange(x || undefined)}
            options={[{ value: "", label: "No picture" }, ...ctx.svgs.map((s) => ({ value: s, label: s }))]} /></div>
          <Button type="button" size="sm" variant="outline" onClick={() => ctx.onPhoto((name) => onChange(name))}><ImageUp className="size-3.5" /> From a photo</Button>
        </div>
      </Field>
    );
  }
  return null;
}

function ListField({ f, value, onChange, ctx }: { f: BField; value: any[] | undefined; onChange: (v: any[]) => void; ctx: Ctx }) {
  const items = Array.isArray(value) ? value : [];
  const max = f.maxItems ?? 99, min = f.minItems ?? 0;
  const move = (i: number, d: number) => { const n = [...items]; [n[i], n[i + d]] = [n[i + d], n[i]]; onChange(n); };
  const blank = () => {
    const prefix = f.key === "answers" ? "a" : f.key.slice(0, 1);
    const it: Doc = { id: shortId(prefix, ctx.root) };
    for (const sf of f.item?.fields ?? []) {
      if (sf.type === "list" && sf.minItems) {
        const kids: Doc[] = [];
        for (let k = 0; k < sf.minItems; k++) kids.push({ id: shortId("a", [ctx.root, it, kids]) });
        it[sf.key] = kids;
      }
    }
    return it;
  };
  return (
    <fieldset className="space-y-2">
      <legend className="flex w-full items-center gap-2 text-xs font-medium text-muted-foreground">{f.label}<span className="font-mono">{items.length}/{max}</span></legend>
      <ol className="space-y-2">
        {items.map((it, i) => (
          <li key={it.id ?? i} className="rounded-xl p-3 ring-1 ring-border">
            <div className="mb-2 flex items-center gap-1">
              <span className="text-xs font-medium">{f.item?.fields[0]?.label ?? "Item"} {i + 1}</span>
              <span className="ml-auto flex gap-0.5">
                <Button type="button" size="icon" variant="ghost" className="size-7" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move ${i + 1} up`}><ArrowUp className="size-3.5" /></Button>
                <Button type="button" size="icon" variant="ghost" className="size-7" disabled={i === items.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${i + 1} down`}><ArrowDown className="size-3.5" /></Button>
                <Button type="button" size="icon" variant="ghost" className="size-7" disabled={items.length <= min} onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label={`Remove ${i + 1}`}><Trash2 className="size-3.5" /></Button>
              </span>
            </div>
            <Fields fields={f.item?.fields ?? []} obj={it} onChange={(n) => onChange(items.map((x, j) => (j === i ? n : x)))} ctx={{ ...ctx, ptr: `${ctx.ptr}/${i}` }} />
          </li>
        ))}
      </ol>
      <Button type="button" size="sm" variant="outline" disabled={items.length >= max} onClick={() => onChange([...items, blank()])}><Plus className="size-3.5" /> Add</Button>
    </fieldset>
  );
}

/** Renders the applicable fields of a schema section against `obj` (content or a list item). */
function Fields({ fields, obj, onChange, ctx }: { fields: BField[]; obj: Doc; onChange: (o: Doc) => void; ctx: Ctx }) {
  return (
    <div className="space-y-4">
      {applicableFields(fields, obj).map((f) => {
        const v = getAt(obj, f.key);
        const set = (x: any) => onChange(setAt(obj, f.key, x));
        const sub = { ...ctx, ptr: `${ctx.ptr}/${f.key.replace(/\./g, "/")}` };
        const on = blockOn(f, obj);
        const body = f.type === "list" ? <ListField f={f} value={v} onChange={set} ctx={sub} /> : <Leaf f={f} value={v} onChange={set} ctx={sub} />;
        return (
          <div key={f.key} id={fieldDom(sub.ptr)} data-bkey={keyOfPointer(sub.ptr)} className="scroll-mt-24 rounded-lg transition-shadow">
            {f.toggle ? (
              <div className={cn("space-y-2 rounded-xl p-3 ring-1 ring-border", !on && "bg-muted/40")}>
                <div className="flex items-center gap-2">
                  {on ? <Eye className="size-4 text-muted-foreground" aria-hidden /> : <EyeOff className="size-4 text-muted-foreground" aria-hidden />}
                  <span className="text-sm font-medium">{f.label}</span>
                  <Switch className="ml-auto" checked={on} onCheckedChange={(x) => onChange(setAt(obj, f.toggle!, x))} aria-label={`Show ${f.label}`} />
                </div>
                {on ? body : <p className="text-xs text-muted-foreground">Hidden in the widget; what you entered is kept.</p>}
              </div>
            ) : body}
          </div>
        );
      })}
    </div>
  );
}

function ColorRow({ label, value, onChange, placeholder }: { label: string; value: string | null; onChange: (v: string | null) => void; placeholder?: string }) {
  const shown = value ?? placeholder ?? "#888888";
  return (
    <div className="flex items-center gap-2 text-sm">
      <label className="relative size-8 shrink-0 cursor-pointer overflow-hidden rounded-lg ring-1 ring-border" style={{ background: shown }} title={value ? value : "Telegram theme colour"}>
        <input type="color" value={/^#[0-9a-f]{6}$/i.test(shown) ? shown : "#888888"} onChange={(e) => onChange(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label={label} />
      </label>
      <span className="min-w-0 flex-1">{label}<span className="block font-mono text-[11px] text-muted-foreground">{value ?? "Telegram"}</span></span>
      {value && <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => onChange(null)} title="Use the Telegram theme colour"><Undo2 className="size-3.5" /> Telegram</Button>}
    </div>
  );
}

function PresetTile({ title, values, active, onClick }: { title: string; values: Doc; active: boolean; onClick: () => void }) {
  const mini = (theme: "light" | "dark") => {
    const c = values.colors?.[theme] ?? {};
    const tg = theme === "light" ? { bg: "#ffffff", text: "#000000", button: "#3390ec", buttonText: "#ffffff" } : { bg: "#212d3b", text: "#ffffff", button: "#50a8eb", buttonText: "#ffffff" };
    const col = { ...tg, ...Object.fromEntries(Object.entries(c).filter(([, v]) => v)) } as Doc;
    const r = Math.min(values.block?.radius ?? 12, 14), br = Math.min(values.button?.radius ?? 10, 10);
    return (
      <div className="flex-1 p-1.5" style={{ background: theme === "light" ? "#c2d6a9" : "#0e1621" }}>
        <div className="space-y-1 p-1.5" style={{ background: col.bg, borderRadius: r, border: values.block?.border ? `1px solid ${col.border ?? "#ddd"}` : undefined }}>
          <div className="h-1.5 w-3/4 rounded-full" style={{ background: col.text, opacity: 0.85 }} />
          <div className="h-1 w-full rounded-full" style={{ background: col.text, opacity: 0.35 }} />
          <div className="h-2.5 w-full" style={{ background: values.button?.look === "outline" ? "transparent" : col.button, border: values.button?.look === "outline" ? `1px solid ${col.button}` : undefined, borderRadius: br }} />
        </div>
      </div>
    );
  };
  return (
    <button type="button" role="radio" aria-checked={active} onClick={onClick}
      className="overflow-hidden rounded-xl text-left ring-1 ring-border hover:ring-foreground/40 aria-checked:ring-2 aria-checked:ring-foreground">
      <div className="flex">{mini("light")}{mini("dark")}</div>
      <div className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium">{title}{active && <Check className="ml-auto size-3.5" />}</div>
    </button>
  );
}

// ------------------------------------------------------------------ the flow
export interface BuilderProps {
  wid: string; meta: Doc; updateMeta: (fn: (m: Doc) => void) => void; svgs: string[];
  addAsset: (name: string, svg: string, place: "top" | "end" | "none") => Promise<void>; saving: boolean;
  open: Set<number>; toggle: (n: number) => void; openOnly: (n: number) => void;
  theme: string; setTheme: (t: string) => void; replay: () => void; onEject: () => void;
  checkContent: ReactNode; messageContent: ReactNode; buildErrors: number;
}

export function BuilderSteps(p: BuilderProps) {
  const { editLocale, loaded, pro } = useStudio();
  const loadedSchema = useBuilderSchema();
  const schema = loadedSchema?.schema ?? null;
  const builder: Doc = p.meta.builder ?? {};
  const issues = useIssues(builder, schema, p.wid);
  const [pending, setPending] = useState<string | null>(null);
  const [photo, setPhoto] = useState<((name: string) => void) | null>(null);
  const langs: string[] = p.meta.languages?.length ? p.meta.languages : [defaultLocale(loaded.project)];
  const locale = langs.includes(editLocale) ? editLocale : langs[0];
  const setBuilder = (fn: (b: Doc) => Doc) => p.updateMeta((m) => { m.builder = fn(m.builder ?? {}); });
  const style: Style = useMemo(() => {
    const s = builder.style as Style | undefined;
    return s && typeof s === "object" ? { preset: s.preset ?? null, custom: s.custom ?? {}, palette: s.palette ?? "per-theme", colors: { light: s.colors?.light ?? {}, dark: s.colors?.dark ?? {} } } : (schema ? defaultStyle(schema) : { preset: null, custom: {}, palette: "per-theme", colors: { light: {}, dark: {} } });
  }, [builder.style, schema]);
  const setStyle = (s: Style) => setBuilder((b) => ({ ...b, style: s }));
  const editTheme: "light" | "dark" = p.theme === "dark" ? "dark" : "light";

  if (!loadedSchema) return <p className="p-4 text-sm text-muted-foreground">Loading the builder…</p>;
  if (!schema) return <Alert variant="destructive"><AlertTitle>The visual builder is not available</AlertTitle><AlertDescription>{loadedSchema.error ?? "The Studio server did not send the builder schema."} Restart <code className="font-mono">bot-ui studio</code> from an up-to-date checkout.</AlertDescription></Alert>;
  const type = schema.types[builder.type];
  const content: Doc = builder.content ?? {};
  const ctx: Ctx = { locale, langs, svgs: p.svgs, issues, ptr: "/content", root: content, onPhoto: (apply) => setPhoto(() => apply) };
  const goTo = (pointer: string) => {
    const step = pointer.startsWith("/style") ? 3 : 2;
    p.openOnly(step);
    setTimeout(() => {
      const key = keyOfPointer(pointer);
      let el: HTMLElement | null = null;
      for (let k = key; k && !el; k = k.includes(".") ? k.slice(0, k.lastIndexOf(".")) : "") el = document.querySelector(`[data-bkey="${k}"]`);
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      el.classList.add("ring-2", "ring-amber-400");
      setTimeout(() => el?.classList.remove("ring-2", "ring-amber-400"), 1600);
      el.querySelector<HTMLElement>("input, textarea, button[role=combobox], [role=radio]")?.focus({ preventScroll: true });
    }, 120);
  };
  const custom = effectiveCustom(style, schema);
  const colors = effectiveColors(style, schema, editTheme);
  const slots = [...(schema.style.colorSlots.common ?? []), ...(schema.style.colorSlots[builder.type] ?? [])];
  const pendingType = pending ? schema.types[pending] : null;

  return (
    <>

      <Step n={1} icon={typeIcon(builder.type)} title="Template" hint="What kind of widget this is. Switching keeps your text for the previous kind." open={p.open.has(1)} onToggle={() => p.toggle(1)}
        right={pro ? <Button size="sm" variant="ghost" className="h-8" onClick={p.onEject}><Code2 className="size-3.5" /> Edit the code</Button> : undefined}>
        <div role="radiogroup" aria-label="Widget type" className="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-2">
          {Object.entries(schema.types).map(([id, t]) => {
            const Icon = typeIcon(id);
            return (
              <button key={id} type="button" role="radio" aria-checked={id === builder.type} onClick={() => id !== builder.type && setPending(id)}
                className="flex flex-col gap-1.5 rounded-xl p-3 text-left ring-1 ring-border hover:bg-muted/50 aria-checked:bg-muted aria-checked:ring-2 aria-checked:ring-foreground">
                <Icon className="size-5" aria-hidden />
                <span className="text-sm font-medium">{t.title}</span>
                <span className="line-clamp-2 text-xs text-muted-foreground">{t.summary}</span>
              </button>
            );
          })}
        </div>
      </Step>

      <Step n={2} icon={MessageSquareText} title="Content and logic" hint="Texts, the button and what it does. Only what applies right now is shown." open={p.open.has(2)} onToggle={() => p.toggle(2)}>
        {!type ? <p className="text-sm text-destructive">Unknown type “{builder.type}”.</p> : type.sections.map((s) => (
          <section key={s.id} className="space-y-3">
            {type.sections.length > 1 && <h4 className="text-sm font-semibold">{s.title}</h4>}
            <Fields fields={s.fields} obj={content} onChange={(c) => setBuilder((b) => ({ ...b, content: c }))} ctx={ctx} />
          </section>
        ))}
      </Step>

      <Step n={3} icon={Palette} title="Design" hint="A ready look or your own: colours, corners, sizes and motion." open={p.open.has(3)} onToggle={() => p.toggle(3)}>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">Looks</span>
            <Button size="sm" variant="ghost" className="ml-auto h-7 text-xs" disabled={style.preset === null} onClick={() => setStyle(restoreMyDesign(style))}><RotateCcw className="size-3.5" /> Restore my design</Button>
          </div>
          <div role="radiogroup" aria-label="Design presets" className="grid grid-cols-[repeat(auto-fill,minmax(9.5rem,1fr))] gap-2">
            {schema.style.presets.map((pr) => <PresetTile key={pr.id} title={pr.title} values={pr.values} active={style.preset === pr.id} onClick={() => setStyle(choosePreset(style, pr.id))} />)}
          </div>
          {style.preset === null && <p className="text-[11.5px] text-muted-foreground">Your own design. Picking a look keeps it; “Restore my design” brings it back.</p>}
        </div>

        <div className="space-y-3 rounded-xl p-3 ring-1 ring-border">
          <div className="flex flex-wrap items-center gap-2">
            <Brush className="size-4 text-muted-foreground" aria-hidden />
            <span className="text-sm font-medium">Colours</span>
            <Segmented size="xs" label="Palette" value={style.palette} onChange={(v) => setStyle({ ...style, palette: v as Style["palette"] })}
              options={[{ value: "per-theme", label: "Each theme its own" }, { value: "shared", label: "One for both" }]} />
            <span className="ml-auto flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">Editing:</span>
              {style.palette === "shared" ? <span className="rounded-full bg-muted px-2 py-0.5 font-medium">both themes</span>
                : <Segmented size="xs" label="Theme being edited" value={editTheme} onChange={p.setTheme} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />}
            </span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {slots.map((sl) => <ColorRow key={sl.key} label={sl.label} value={colors[sl.key] ?? null} placeholder={TG_DEFAULT[style.palette === "shared" ? "light" : editTheme][sl.key]} onChange={(v) => setStyle(setColor(style, schema, editTheme, sl.key, v))} />)}
          </div>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setStyle(resetColors(style, schema, "all"))}><Undo2 className="size-3.5" /> All colours from Telegram</Button>
        </div>

        {schema.style.sections.map((s) => (
          <section key={s.id} className="space-y-3 rounded-xl p-3 ring-1 ring-border" data-bkey={`style.${s.id}`}>
            <h4 className="text-sm font-medium">{s.title}</h4>
            <div className="grid gap-4 sm:grid-cols-2">
              {applicableFields(s.fields, custom).map((f) => (
                <div key={f.key} data-bkey={`style.${f.key}`}><Leaf f={f} value={getAt(custom, f.key)} onChange={(v) => { setStyle(changeStyle(style, schema, f.key, v)); if (f.key === "animation") setTimeout(p.replay, 700); }} ctx={{ ...ctx, ptr: `/style/custom/${f.key.replace(/\./g, "/")}` }} /></div>
              ))}
              {s.id === "motion" && <div className="flex items-end"><Button size="sm" variant="outline" className="h-8" onClick={p.replay}><Play className="size-3.5" /> Replay</Button></div>}
            </div>
          </section>
        ))}

      </Step>

      <Step n={4} icon={ShieldCheck} title="Check" hint="Does it build, fit Telegram's limits, and is every field filled correctly?" open={p.open.has(4)} onToggle={() => p.toggle(4)}>
        {issues.length > 0 ? (
          <Alert variant="destructive">
            <AlertTitle>{issues.length} field{issues.length === 1 ? "" : "s"} to fix</AlertTitle>
            <AlertDescription>
              <ul className="w-full space-y-1">
                {issues.map((i, n) => (
                  <li key={n} className="flex items-center gap-2 text-xs">
                    <span className="min-w-0 flex-1"><span className="font-mono">{keyOfPointer(i.pointer) || i.pointer}</span>: {i.message}</span>
                    <Button size="sm" variant="outline" className="h-6 px-2 text-[11px] text-foreground" onClick={() => goTo(i.pointer)}>Go to field</Button>
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : <p className="flex items-center gap-1.5 text-xs text-emerald-700"><Check className="size-4" /> Every field is within its limits.</p>}
        {p.checkContent}
        <div className="border-t pt-4">{p.messageContent}</div>
      </Step>

      <Dialog open={!!pending} onOpenChange={(o) => { if (!o) setPending(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Switch to {pendingType?.title}?</DialogTitle>
            <DialogDescription>The form changes to the new kind. Your current content is kept aside and comes back if you switch back. The design stays as it is.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPending(null)}>Cancel</Button>
            <Button onClick={() => { const t = pending!; setPending(null); setBuilder((b) => switchType(b, t, schema)); }}>Switch</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!photo} onOpenChange={(o) => { if (!o) setPhoto(null); }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Picture from a photo</DialogTitle>
            <DialogDescription>Converted in this page into a small SVG and saved in the widget folder.</DialogDescription>
          </DialogHeader>
          <PhotoToSvg existing={p.svgs} busy={p.saving} onAdd={async (name, svg) => { await p.addAsset(name, svg, "none"); photo?.(name); setPhoto(null); }} />
        </DialogContent>
      </Dialog>
    </>
  );
}

/** A builder widget's preview states (schema), or null for hand-written widgets. */
export function useBuilderStates(meta: Doc): { id: string; title: string }[] | null {
  const s = useBuilderSchema();
  const b = meta.builder;
  if (!b || b.ejected || !s?.schema) return null;
  const states = s.schema.types[b.type]?.states;
  return states ? previewStates(states, b) : null;
}
