// Beginner data form: one labelled control per chat_data / public_data key, from widget.json
// dataFields (label, type, options, help, advanced); undescribed keys get a humanised label and
// an inferred type. Lists and objects without a description stay for Pro.
import { CalendarClock, Hash, List, Minus, Plus, ToggleLeft, Type } from "lucide-react";
import { localized, type Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useStudio } from "@/lib/studio";
import { EnumSelect, Field } from "../inspector/fields";

export interface FieldSpec { label?: any; type?: "text" | "number" | "choice" | "time" | "boolean"; options?: { value: any; label: any }[]; help?: any; advanced?: boolean }

export function humanize(key: string): string {
  const s = key.replace(/[_.-]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : key;
}

function inferType(v: any): FieldSpec["type"] | "complex" {
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "number") return "number";
  if (v === null || typeof v === "string") return "text";
  return "complex";
}

const ICON = { text: Type, number: Hash, choice: List, time: CalendarClock, boolean: ToggleLeft };

/** unix seconds <-> the value of <input type="datetime-local"> in local time */
const toLocalInput = (s: number) => {
  const d = new Date(s * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const fromLocalInput = (v: string) => Math.floor(new Date(v).getTime() / 1000);

export function BeginnerDataForm({ id, value, specs, onChange }: { id: string; value: Doc; specs: Record<string, FieldSpec>; onChange: (key: string, v: any) => void }) {
  const { editLocale, loaded } = useStudio();
  const def = loaded.project.defaultLocale ?? "en";
  const text = (x: any) => (x == null ? undefined : localized(x, editLocale, def) ?? undefined);
  const keys = [...Object.keys(specs), ...Object.keys(value).filter((k) => !(k in specs))];
  const hidden = keys.filter((k) => specs[k]?.advanced).length;
  const complex = keys.filter((k) => !specs[k] && inferType(value[k]) === "complex");
  const shown = keys.filter((k) => !specs[k]?.advanced && !complex.includes(k));
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-3">
        {shown.map((k) => {
          const spec = specs[k] ?? {};
          const v = value[k];
          const type = spec.type ?? (inferType(v) as FieldSpec["type"]);
          const fid = `${id}-${k}`;
          const Icon = ICON[type ?? "text"] ?? Type;
          const label = <span className="inline-flex items-center gap-1"><Icon className="size-3.5" aria-hidden />{text(spec.label) ?? humanize(k)}</span>;
          let control;
          if (type === "choice") {
            const opts = spec.options ?? [];
            control = <EnumSelect id={fid} value={v === undefined ? "" : JSON.stringify(v)} onChange={(x) => onChange(k, x ? JSON.parse(x) : undefined)}
              options={[{ value: "", label: "Choose…" }, ...opts.map((o) => ({ value: JSON.stringify(o.value), label: text(o.label) ?? String(o.value) }))]} />;
          } else if (type === "time") {
            control = <Input id={fid} type="datetime-local" value={typeof v === "number" ? toLocalInput(v) : ""} onChange={(e) => e.target.value && onChange(k, fromLocalInput(e.target.value))} />;
          } else if (type === "boolean") {
            control = <div className="flex h-9 items-center"><Switch id={fid} checked={!!v} onCheckedChange={(x) => onChange(k, x)} /></div>;
          } else if (type === "number") {
            const n = typeof v === "number" ? v : 0;
            control = (
              <div className="flex items-center gap-1">
                <Button type="button" size="icon" variant="outline" className="size-9 shrink-0" aria-label={`Decrease ${k}`} onClick={() => onChange(k, n - 1)}><Minus className="size-4" /></Button>
                <Input id={fid} type="number" value={typeof v === "number" ? v : ""} onChange={(e) => onChange(k, e.target.value === "" ? 0 : Number(e.target.value))} className="text-center" />
                <Button type="button" size="icon" variant="outline" className="size-9 shrink-0" aria-label={`Increase ${k}`} onClick={() => onChange(k, n + 1)}><Plus className="size-4" /></Button>
              </div>
            );
          } else {
            control = <Input id={fid} value={v ?? ""} onChange={(e) => onChange(k, e.target.value)} />;
          }
          return <Field key={k} label={label} htmlFor={fid} hint={text(spec.help)}>{control}</Field>;
        })}
      </div>
      {(hidden > 0 || complex.length > 0) && (
        <p className="text-xs text-muted-foreground">
          {hidden > 0 && <>{hidden} technical field{hidden === 1 ? "" : "s"} hidden. </>}
          {complex.length > 0 && <>Lists and groups ({complex.map(humanize).join(", ")}) are edited in Pro. </>}
        </p>
      )}
    </div>
  );
}
