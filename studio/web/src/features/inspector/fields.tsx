import { useId, type ReactNode } from "react";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { Diag } from "@/core/lint.ts";
import type { Doc } from "@/core/render.ts";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { defaultLocale, fieldDomId, locales } from "@/lib/model";
import { useStudio } from "@/lib/studio";
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
        <button type="button" onClick={onClick} className="flex w-full items-start gap-1.5 rounded px-1 py-0.5 text-left text-xs hover:bg-muted">
          {body}
        </button>
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

export function Field({ label, htmlFor, hint, children, className }: { label: ReactNode; htmlFor?: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1", className)}>
      <Label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** One textarea (or input) per project locale, default locale first. */
export function LocaleTexts({ sid, pointer, value, onChange, disabled, label, multiline = true, diags }: {
  sid: string; pointer: string; value: any; onChange: (loc: string, text: string) => void; disabled?: boolean;
  label: string; multiline?: boolean; diags: Diag[];
}) {
  const { loaded } = useStudio();
  const def = defaultLocale(loaded.project);
  const obj: Doc = typeof value === "string" ? { [def]: value } : value && typeof value === "object" ? value : {};
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium text-muted-foreground">{label}</legend>
      {locales(loaded.project).map((loc) => {
        const p = `${pointer}/${loc}`;
        const id = fieldDomId(sid, p);
        const here = diagsAt(diags, p);
        const err = here.some((d) => d.severity === "error");
        const common = {
          id, value: typeof obj[loc] === "string" ? obj[loc] : "", disabled,
          "aria-invalid": err || undefined, "aria-describedby": here.length ? `${id}-d` : undefined,
          onChange: (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => onChange(loc, e.target.value),
          placeholder: loc === def ? "required" : `optional; falls back to ${def}`,
        };
        return (
          <div key={loc}>
            <div className="flex gap-2">
              <span className="w-7 shrink-0 pt-2 font-mono text-[11px] text-muted-foreground uppercase" aria-hidden>{loc}</span>
              <div className="min-w-0 flex-1">
                <label htmlFor={id} className="sr-only">{label} ({loc})</label>
                {multiline ? <Textarea {...common} rows={3} className="min-h-16 font-mono text-[13px]" /> : <Input {...common} className="font-mono text-[13px]" />}
                <FieldDiags list={here} id={`${id}-d`} />
              </div>
            </div>
          </div>
        );
      })}
      <FieldDiags list={diagsAt(diags, pointer)} />
    </fieldset>
  );
}

export function TargetSelect({ sid, pointer, value, onChange, disabled, label, diags, allowEmpty }: {
  sid: string; pointer: string; value: any; onChange: (to: string) => void; disabled?: boolean; label: string; diags: Diag[]; allowEmpty?: string;
}) {
  const { working } = useStudio();
  const id = fieldDomId(sid, pointer);
  const here = diagsAt(diags, pointer);
  const ids = Object.keys(working.screens).sort();
  const v = typeof value === "string" ? value : "";
  return (
    <Field label={label} htmlFor={id}>
      <NativeSelect id={id} value={v} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="w-full font-mono text-[13px]"
        aria-invalid={here.some((d) => d.severity === "error") || undefined}>
        <NativeSelectOption value="">{allowEmpty ?? "Choose a screen…"}</NativeSelectOption>
        {v && !ids.includes(v) && <NativeSelectOption value={v}>{v} (missing)</NativeSelectOption>}
        {ids.map((s) => <NativeSelectOption key={s} value={s}>{s}{working.screens[s]?.title ? ` · ${working.screens[s].title}` : ""}</NativeSelectOption>)}
      </NativeSelect>
      <FieldDiags list={here} />
    </Field>
  );
}

export function SelectField({ id, label, value, options, onChange, disabled, hint, diags = [] }: {
  id: string; label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void;
  disabled?: boolean; hint?: ReactNode; diags?: Diag[];
}) {
  const uid = useId();
  const fid = id || uid;
  return (
    <Field label={label} htmlFor={fid} hint={hint}>
      <NativeSelect id={fid} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="w-full"
        aria-invalid={diags.some((d) => d.severity === "error") || undefined}>
        {options.map((o) => <NativeSelectOption key={o.value} value={o.value}>{o.label}</NativeSelectOption>)}
      </NativeSelect>
      <FieldDiags list={diags} />
    </Field>
  );
}
