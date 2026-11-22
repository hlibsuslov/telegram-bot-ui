import { useId, useState, type ReactNode } from "react";
import { AlertCircle, AlertTriangle, Check, ChevronsUpDown, Info, Languages } from "lucide-react";
import type { Diag } from "@/core/lint.ts";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { defaultLocale, fieldDomId, locales } from "@/lib/model";
import { type Highlight, useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";

export function useScreenDiags(sid: string): Diag[] {
  const { diags } = useStudio();
  return diags.filter((d) => d.screenId === sid || d.file === `screens/${sid}.json`);
}

/** Diagnostics whose pointer is exactly this field (or, with `below`, anything under it). */
export function diagsAt(list: Diag[], pointer: string, below = false): Diag[] {
  return list.filter((d) => d.pointer === pointer || (below && d.pointer.startsWith(pointer + "/")));
}

const icon = { error: AlertCircle, warning: AlertTriangle, info: Info };
const tone = { error: "text-destructive", warning: "text-warning", info: "text-muted-foreground" };

export function DiagLine({ d, onClick, showPlace }: { d: Diag; onClick?: () => void; showPlace?: boolean }) {
  const Icon = icon[d.severity] ?? Info;
  const body = (
    <>
      <Icon className={cn("mt-0.5 size-3.5 shrink-0", tone[d.severity])} aria-hidden />
      <span className="min-w-0">
        <span className="sr-only">{d.severity}: </span>
        {d.message} <span className="font-mono text-[11px] text-muted-foreground">{d.code}</span>
        {showPlace && <span className="block font-mono text-[11px] break-all text-muted-foreground">{d.file} {d.pointer}</span>}
      </span>
    </>
  );
  if (onClick) {
    return (
      <li>
        <button type="button" onClick={onClick} className="flex w-full items-start gap-1.5 rounded px-1 py-0.5 text-left text-xs hover:bg-muted">{body}</button>
      </li>
    );
  }
  return <li className="flex items-start gap-1.5 text-xs">{body}</li>;
}

export function FieldDiags({ list, id }: { list: Diag[]; id?: string }) {
  if (!list.length) return null;
  return (
    <ul id={id} className="mt-1 space-y-0.5" aria-live="polite">
      {list.map((d, i) => <DiagLine key={`${d.code}${d.pointer}${i}`} d={d} showPlace />)}
    </ul>
  );
}

export function Field({ label, htmlFor, hint, children, className, extra }: {
  label: ReactNode; htmlFor?: string; hint?: ReactNode; children: ReactNode; className?: string; extra?: ReactNode;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex min-h-5 flex-wrap items-center gap-x-2 gap-y-1">
        <Label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">{label}</Label>
        {extra && <span className="ml-auto flex items-center gap-1">{extra}</span>}
      </div>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Locales whose text is missing for a localized value. */
export function missingLocales(project: Doc, value: any): string[] {
  const def = defaultLocale(project);
  const obj: Doc = typeof value === "string" ? { [def]: value } : value && typeof value === "object" ? value : {};
  return locales(project).filter((l) => typeof obj[l] !== "string" || !obj[l]);
}

/** One localized text in the current editing language, with a "missing" badge and a way to fill it. */
export function LocaleText({ sid, pointer, value, onChange, disabled, label, multiline = true, diags, hl, hint, max }: {
  sid: string; pointer: string; value: any; onChange: (loc: string, text: string) => void; disabled?: boolean;
  label: string; multiline?: boolean; diags: Diag[]; hl?: Omit<Highlight, "sid">; hint?: ReactNode; max?: number;
}) {
  const { loaded, editLocale, setHighlight } = useStudio();
  const def = defaultLocale(loaded.project);
  const ls = locales(loaded.project);
  const obj: Doc = typeof value === "string" ? { [def]: value } : value && typeof value === "object" ? value : {};
  const loc = ls.includes(editLocale) ? editLocale : def;
  const p = `${pointer}/${loc}`;
  const id = fieldDomId(sid, p);
  const here = [...diagsAt(diags, p), ...diagsAt(diags, pointer)];
  const err = here.some((d) => d.severity === "error");
  const current = typeof obj[loc] === "string" ? obj[loc] : "";
  const missing = !current;
  const others = ls.filter((l) => l !== loc && (typeof obj[l] !== "string" || !obj[l]));
  const sourceLoc = loc !== def ? def : ls.find((l) => l !== def && typeof obj[l] === "string" && obj[l]);
  const source = sourceLoc ? obj[sourceLoc] : undefined;
  const common = {
    id, value: current, disabled,
    "aria-invalid": err || undefined, "aria-describedby": here.length ? `${id}-d` : undefined,
    onChange: (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => onChange(loc, e.target.value),
    onFocus: () => hl && setHighlight({ sid, ...hl }),
    onBlur: () => hl && setHighlight(null),
    placeholder: loc === def ? "Required" : `Empty: ${loc} users see the ${def} text`,
  };
  return (
    <Field label={<>{label} <span className="font-mono text-[10px] uppercase">{loc}</span></>} htmlFor={id} hint={hint} extra={
      <>
        {missing && <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-100">missing in {loc}</span>}
        {missing && typeof source === "string" && source && !disabled && (
          <Button type="button" size="sm" variant="ghost" className="h-6 px-1.5 text-[11px]" onClick={() => onChange(loc, source)}>
            <Languages className="size-3" /> Copy {sourceLoc} text
          </Button>
        )}
        {!missing && others.length > 0 && <span className="text-[10px] text-muted-foreground">missing in {others.join(", ")}</span>}
        {max && <span className={cn("font-mono text-[10.5px] tabular-nums", [...current].length > max ? "font-semibold text-destructive" : "text-muted-foreground")}>{[...current].length}/{max}</span>}
      </>
    }>
      {multiline
        ? <Textarea {...common} rows={3} className="min-h-20 text-[13.5px] leading-relaxed" />
        : <Input {...common} className="text-[13.5px]" />}
      <FieldDiags list={here} id={`${id}-d`} />
    </Field>
  );
}

const NONE = "__none__";

/** Radix Select for short enums; "" is allowed through a sentinel. */
export function EnumSelect({ id, value, options, onChange, disabled, label, size = "default", className, invalid }: {
  id?: string; value: string; options: { value: string; label: ReactNode }[]; onChange: (v: string) => void;
  disabled?: boolean; label?: string; size?: "sm" | "default"; className?: string; invalid?: boolean;
}) {
  return (
    <Select value={value === "" ? NONE : value} onValueChange={(v) => onChange(v === NONE ? "" : v)} disabled={disabled}>
      <SelectTrigger id={id} size={size} aria-label={label} aria-invalid={invalid || undefined} className={cn("w-full", className)}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => <SelectItem key={o.value || NONE} value={o.value === "" ? NONE : o.value}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export function SelectField({ id, label, value, options, onChange, disabled, hint, diags = [], onFocus }: {
  id: string; label: string; value: string; options: { value: string; label: ReactNode }[]; onChange: (v: string) => void;
  disabled?: boolean; hint?: ReactNode; diags?: Diag[]; onFocus?: () => void;
}) {
  const uid = useId();
  const fid = id || uid;
  return (
    <Field label={label} htmlFor={fid} hint={hint}>
      <div onFocus={onFocus}>
        <EnumSelect id={fid} value={value} options={options} onChange={onChange} disabled={disabled} invalid={diags.some((d) => d.severity === "error")} />
      </div>
      <FieldDiags list={diags} />
    </Field>
  );
}

export function firstLine(screen: Doc | undefined, locale: string, def: string): string {
  const t = screen?.message?.text;
  const raw = typeof t === "string" ? t : t?.[locale] ?? t?.[def] ?? "";
  return String(raw).replace(/<[^>]+>/g, "").split("\n").find((l: string) => l.trim()) ?? "";
}

/** Searchable screen picker: ID, title, kind and the first line of the message. */
export function ScreenPicker({ id, value, onChange, disabled, allowEmpty, invalid, onFocus }: {
  id?: string; value: string; onChange: (to: string) => void; disabled?: boolean; allowEmpty?: string; invalid?: boolean; onFocus?: () => void;
}) {
  const { working, loaded, editLocale } = useStudio();
  const [open, setOpen] = useState(false);
  const def = defaultLocale(loaded.project);
  const ids = Object.keys(working.screens).sort();
  const cur = value ? working.screens[value] : undefined;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id={id} type="button" variant="outline" role="combobox" aria-expanded={open} disabled={disabled} onFocus={onFocus}
          aria-invalid={invalid || undefined}
          className={cn("h-auto min-h-9 w-full justify-between px-3 py-1.5 text-left font-normal aria-invalid:border-destructive", !value && "text-muted-foreground")}>
          <span className="min-w-0">
            {value ? (
              <>
                <span className="block truncate font-mono text-[12.5px]">{value}{!cur && " (missing)"}</span>
                {cur && <span className="block truncate text-[11px] text-muted-foreground">{cur.title} · {cur.kind}</span>}
              </>
            ) : (allowEmpty ?? "Choose a screen…")}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(92vw,26rem)] p-0" align="start">
        <Command filter={(v, search) => (v.toLowerCase().includes(search.toLowerCase()) ? 1 : 0)}>
          <CommandInput placeholder="Search by ID, title or text…" />
          <CommandList className="max-h-72">
            <CommandEmpty>No screen matches.</CommandEmpty>
            <CommandGroup>
              {allowEmpty && (
                <CommandItem value={`__none ${allowEmpty}`} onSelect={() => { onChange(""); setOpen(false); }}>
                  <span className="text-muted-foreground">{allowEmpty}</span>
                  {!value && <Check className="ml-auto size-4" />}
                </CommandItem>
              )}
              {ids.map((sid) => {
                const s = working.screens[sid];
                const line = firstLine(s, editLocale, def);
                return (
                  <CommandItem key={sid} value={`${sid} ${s.title ?? ""} ${s.kind ?? ""} ${line}`} onSelect={() => { onChange(sid); setOpen(false); }} className="items-start">
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        <span className="truncate font-mono text-[12.5px]">{sid}</span>
                        <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">{s.kind}</span>
                      </span>
                      <span className="block truncate text-[11px] text-muted-foreground">{s.title}{line ? ` — ${line}` : ""}</span>
                    </span>
                    {sid === value && <Check className="mt-0.5 size-4 shrink-0" />}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function TargetSelect({ sid, pointer, value, onChange, disabled, label, diags, allowEmpty, hl }: {
  sid: string; pointer: string; value: any; onChange: (to: string) => void; disabled?: boolean; label: string; diags: Diag[];
  allowEmpty?: string; hl?: Omit<Highlight, "sid">;
}) {
  const { setHighlight } = useStudio();
  const id = fieldDomId(sid, pointer);
  const here = diagsAt(diags, pointer);
  return (
    <Field label={label} htmlFor={id}>
      <ScreenPicker id={id} value={typeof value === "string" ? value : ""} onChange={onChange} disabled={disabled} allowEmpty={allowEmpty}
        invalid={here.some((d) => d.severity === "error")} onFocus={() => hl && setHighlight({ sid, ...hl })} />
      <FieldDiags list={here} />
    </Field>
  );
}

/** Segmented control (radio group) for small choices. */
export function Segmented<T extends string>({ value, options, onChange, label, disabled, size = "sm" }: {
  value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; label: string; disabled?: boolean; size?: "sm" | "xs";
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap rounded-lg bg-muted p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} disabled={disabled}
          onClick={() => onChange(o.value)}
          className={cn("rounded-md font-medium text-muted-foreground transition-colors aria-checked:bg-background aria-checked:text-foreground aria-checked:shadow-sm disabled:opacity-50",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[11px]")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
