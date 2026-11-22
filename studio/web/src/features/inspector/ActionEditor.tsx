import { Trash2 } from "lucide-react";
import type { Diag } from "@/core/lint.ts";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { ACTION_TYPES, defaultLocale, fieldDomId, STYLES } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { diagsAt, Field, FieldDiags, LocaleTexts, SelectField, TargetSelect } from "./fields";

const TYPE_KEYS = ["to", "rule", "fallback", "url", "text", "handlerId", "outcomes", "pending"];

export function defaultsForType(type: string, project: Doc, def: string): Doc {
  switch (type) {
    case "navigate": return { to: "" };
    case "url": return { url: "https://" };
    case "answer": return { text: { [def]: "" } };
    case "handler": {
      const hid = Object.keys(project.handlers ?? {})[0] ?? "";
      return { handlerId: hid, outcomes: {} };
    }
    default: return {};
  }
}

/** Rule editor: field limited to context/state fields, a value typed by the field, two targets. */
export function RuleEditor({ sid, aid, rule, onChange, disabled, diags }: {
  sid: string; aid: string; rule: Doc; onChange: (fn: (rule: Doc) => void, key?: string) => void; disabled?: boolean; diags: Diag[];
}) {
  const { loaded } = useStudio();
  const fields = loaded.project.fields ?? {};
  const ruleFields = Object.entries<Doc>(fields).filter(([, fd]) => fd.source === "context" || fd.source === "state");
  const ptr = `/actions/${aid}/rule`;
  const fname: string = rule.when?.field ?? "";
  const fd: Doc | undefined = fields[fname];
  const eq = rule.when?.eq;
  const eqId = fieldDomId(sid, `${ptr}/when/eq`);
  const eqDiags = diagsAt(diags, `${ptr}/when/eq`);
  const setEq = (v: any) => onChange((r) => { r.when = { ...(r.when ?? {}), eq: v }; }, "eq");
  let valueInput;
  if (fd?.type === "enum" || fd?.type === "boolean") {
    const opts: any[] = fd.type === "enum" ? fd.values ?? [] : [true, false];
    valueInput = (
      <NativeSelect id={eqId} value={eq === undefined ? "" : JSON.stringify(eq)} disabled={disabled} className="w-full font-mono text-[13px]"
        onChange={(e) => setEq(e.target.value ? JSON.parse(e.target.value) : undefined)} aria-invalid={eqDiags.length > 0 || undefined}>
        <NativeSelectOption value="">Choose a value…</NativeSelectOption>
        {opts.map((o) => <NativeSelectOption key={String(o)} value={JSON.stringify(o)}>{String(o)}</NativeSelectOption>)}
      </NativeSelect>
    );
  } else if (fd?.type === "number") {
    valueInput = <Input id={eqId} type="number" value={typeof eq === "number" ? eq : ""} disabled={disabled} className="font-mono text-[13px]"
      onChange={(e) => setEq(e.target.value === "" ? undefined : Number(e.target.value))} aria-invalid={eqDiags.length > 0 || undefined} />;
  } else {
    valueInput = <Input id={eqId} value={typeof eq === "string" ? eq : ""} disabled={disabled || !fd} className="font-mono text-[13px]"
      onChange={(e) => setEq(e.target.value)} aria-invalid={eqDiags.length > 0 || undefined} />;
  }
  const fieldId = fieldDomId(sid, `${ptr}/when/field`);
  return (
    <div className="space-y-2 rounded-md border bg-muted/30 p-2">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
        <Field label="When field" htmlFor={fieldId}>
          <NativeSelect id={fieldId} value={fname} disabled={disabled} className="w-full font-mono text-[13px]"
            onChange={(e) => onChange((r) => {
              const nf = fields[e.target.value];
              r.when = { field: e.target.value, eq: nf?.type === "enum" ? nf.values?.[0] : nf?.type === "boolean" ? true : nf?.type === "number" ? 0 : "" };
            })}>
            <NativeSelectOption value="">Choose a field…</NativeSelectOption>
            {fname && !ruleFields.some(([n]) => n === fname) && <NativeSelectOption value={fname}>{fname} (not allowed)</NativeSelectOption>}
            {ruleFields.map(([n, f]) => <NativeSelectOption key={n} value={n}>{n} ({f.source}, {f.type})</NativeSelectOption>)}
          </NativeSelect>
          <FieldDiags list={diagsAt(diags, `${ptr}/when/field`)} />
        </Field>
        <span className="pb-2 text-center font-mono text-sm text-muted-foreground" aria-hidden>==</span>
        <Field label="Value" htmlFor={eqId}>
          {valueInput}
          <FieldDiags list={eqDiags} />
        </Field>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <TargetSelect sid={sid} pointer={`${ptr}/match`} label="Then (match)" value={rule.match} disabled={disabled} diags={diags}
          onChange={(to) => onChange((r) => { r.match = to; })} />
        <TargetSelect sid={sid} pointer={`${ptr}/otherwise`} label="Otherwise" value={rule.otherwise} disabled={disabled} diags={diags}
          onChange={(to) => onChange((r) => { r.otherwise = to; })} />
      </div>
      <FieldDiags list={diagsAt(diags, ptr)} />
    </div>
  );
}

/** Navigate target: a fixed screen or a rule. */
export function NavigateTarget({ sid, aid, action, update, disabled, diags }: {
  sid: string; aid: string; action: Doc; update: (fn: (a: Doc) => void, key?: string) => void; disabled?: boolean; diags: Diag[];
}) {
  const { loaded } = useStudio();
  const hasRule = !!action.rule;
  const ptr = `/actions/${aid}`;
  const firstRuleField = Object.entries<Doc>(loaded.project.fields ?? {}).find(([, f]) => f.source === "context" || f.source === "state");
  return (
    <div className="space-y-2">
      <div role="radiogroup" aria-label="Target kind" className="inline-flex rounded-md border p-0.5 text-xs">
        {[["to", "One screen"], ["rule", "Rule"]].map(([k, l]) => (
          <button key={k} type="button" role="radio" aria-checked={(k === "rule") === hasRule} disabled={disabled}
            className="rounded px-2 py-1 aria-checked:bg-primary aria-checked:text-primary-foreground disabled:opacity-50"
            onClick={() => update((a) => {
              if (k === "rule" && !a.rule) {
                const [fname, fd] = firstRuleField ?? ["", {}];
                a.rule = { when: { field: fname, eq: fd.type === "enum" ? fd.values?.[0] : "" }, match: a.to ?? "", otherwise: a.to ?? "" };
                delete a.to;
              } else if (k === "to" && a.rule) {
                a.to = a.rule.match ?? "";
                delete a.rule;
              }
            })}>
            {l}
          </button>
        ))}
      </div>
      {hasRule ? (
        <RuleEditor sid={sid} aid={aid} rule={action.rule} disabled={disabled} diags={diags}
          onChange={(fn, key) => update((a) => { fn(a.rule); }, key ? `rule:${key}` : undefined)} />
      ) : (
        <TargetSelect sid={sid} pointer={`${ptr}/to`} label="Go to" value={action.to} disabled={disabled} diags={diags}
          onChange={(to) => update((a) => { a.to = to; })} />
      )}
      <FieldDiags list={diagsAt(diags, ptr).filter((d) => d.code === "NAVIGATE_TARGET")} />
    </div>
  );
}

export function ActionEditor({ sid, aid, action, placed, diags }: { sid: string; aid: string; action: Doc; placed: boolean; diags: Diag[] }) {
  const { store, loaded, caps } = useStudio();
  const def = defaultLocale(loaded.project);
  const ptr = `/actions/${aid}`;
  const update = (fn: (a: Doc) => void, key?: string) =>
    store.updateScreen(sid, (doc) => { fn(doc.actions[aid]); }, key ? `${aid}:${key}` : undefined);
  const setLocale = (field: string) => (loc: string, text: string) =>
    update((a) => { a[field] = typeof a[field] === "object" && a[field] ? { ...a[field], [loc]: text } : { [loc]: text }; }, `${field}:${loc}`);
  const handlers = loaded.project.handlers ?? {};
  const outcomes: string[] = handlers[action.handlerId]?.outcomes ?? Object.keys(action.outcomes ?? {});
  const st = !caps.structure;
  return (
    <article className="space-y-3 rounded-lg border bg-card p-3" aria-labelledby={`${fieldDomId(sid, ptr)}-h`}>
      <header className="flex flex-wrap items-center gap-2">
        <h4 id={`${fieldDomId(sid, ptr)}-h`} className="font-mono text-sm font-semibold" tabIndex={-1}>
          <span id={fieldDomId(sid, ptr)} tabIndex={-1}>{aid}</span>
        </h4>
        {!placed && <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">not on the keyboard</span>}
        {action.hidden && <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">hidden</span>}
        <div className="ml-auto flex items-center gap-1">
          <label className="sr-only" htmlFor={fieldDomId(sid, `${ptr}/type`)}>Type of {aid}</label>
          <NativeSelect id={fieldDomId(sid, `${ptr}/type`)} size="sm" value={action.type ?? ""} disabled={st}
            onChange={(e) => update((a) => {
              for (const k of TYPE_KEYS) delete a[k];
              a.type = e.target.value;
              Object.assign(a, defaultsForType(e.target.value, loaded.project, def));
            })}>
            {ACTION_TYPES.map((t) => <NativeSelectOption key={t} value={t}>{t}</NativeSelectOption>)}
          </NativeSelect>
          {caps.structure && (
            <Button type="button" size="icon" variant="ghost" className="size-8" aria-label={`Delete action ${aid}`}
              onClick={() => store.updateScreen(sid, (doc) => {
                delete doc.actions[aid];
                if (doc.keyboard?.rows) doc.keyboard.rows = doc.keyboard.rows.map((r: string[]) => r.filter((x) => x !== aid)).filter((r: string[]) => r.length);
              })}>
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>
      </header>
      <FieldDiags list={diagsAt(diags, `${ptr}/type`)} />
      <LocaleTexts sid={sid} pointer={`${ptr}/label`} label="Button label" value={action.label} multiline={false}
        disabled={!caps.text} diags={diags} onChange={setLocale("label")} />
      <div className="grid gap-2 sm:grid-cols-2">
        <SelectField id={fieldDomId(sid, `${ptr}/style`)} label="Button style" value={action.style ?? ""} disabled={st}
          options={STYLES.map((s) => ({ value: s, label: s || "default" }))} diags={diagsAt(diags, `${ptr}/style`)}
          onChange={(v) => update((a) => { if (v) a.style = v; else delete a.style; })} />
        {["navigate", "back", "handler"].includes(action.type) && (
          <SelectField id={fieldDomId(sid, `${ptr}/presentation`)} label="Presentation" value={action.presentation ?? ""} disabled={st}
            options={[{ value: "", label: "default (edit for callbacks)" }, { value: "edit", label: "edit the message" }, { value: "send", label: "send a new message" }]}
            diags={diagsAt(diags, `${ptr}/presentation`)}
            onChange={(v) => update((a) => { if (v) a.presentation = v; else delete a.presentation; })} />
        )}
      </div>
      {action.type === "navigate" && <NavigateTarget sid={sid} aid={aid} action={action} update={update} disabled={!caps.rule} diags={diags} />}
      {action.type === "back" && (
        <TargetSelect sid={sid} pointer={`${ptr}/fallback`} label="Fallback after a restart (no history)" value={action.fallback}
          allowEmpty="No fallback" disabled={!caps.rule} diags={diags}
          onChange={(to) => update((a) => { if (to) a.fallback = to; else delete a.fallback; })} />
      )}
      {action.type === "url" && (
        <Field label="URL (never followed by the map or the simulator)" htmlFor={fieldDomId(sid, `${ptr}/url`)}>
          <Input id={fieldDomId(sid, `${ptr}/url`)} value={action.url ?? ""} disabled={st} className="font-mono text-[13px]"
            onChange={(e) => update((a) => { a.url = e.target.value; }, "url")} />
          <FieldDiags list={diagsAt(diags, `${ptr}/url`)} />
        </Field>
      )}
      {action.type === "answer" && (
        <LocaleTexts sid={sid} pointer={`${ptr}/text`} label="Toast text" value={action.text} multiline={false}
          disabled={!caps.text} diags={diags} onChange={setLocale("text")} />
      )}
      {action.type === "handler" && (
        <div className="space-y-2">
          <SelectField id={fieldDomId(sid, `${ptr}/handlerId`)} label="Handler (code the bot registers)" value={action.handlerId ?? ""} disabled={st}
            options={[{ value: "", label: "Choose a handler…" }, ...Object.keys(handlers).map((h) => ({ value: h, label: h }))]}
            diags={diagsAt(diags, `${ptr}/handlerId`)}
            onChange={(v) => update((a) => { a.handlerId = v; a.outcomes = {}; })} />
          <fieldset className="space-y-2 rounded-md border bg-muted/30 p-2">
            <legend className="px-1 text-xs font-medium text-muted-foreground">Outcomes</legend>
            {outcomes.length === 0 && <p className="text-xs text-muted-foreground">This handler declares no outcomes in project.json.</p>}
            {outcomes.map((o) => (
              <TargetSelect key={o} sid={sid} pointer={`${ptr}/outcomes/${o}`} label={`On ${o}`} value={action.outcomes?.[o]}
                disabled={!caps.rule} diags={diags}
                onChange={(to) => update((a) => { a.outcomes = { ...(a.outcomes ?? {}), [o]: to }; if (!to) delete a.outcomes[o]; })} />
            ))}
          </fieldset>
          <LocaleTexts sid={sid} pointer={`${ptr}/pending`} label="While it runs (callback answer)" value={action.pending} multiline={false}
            disabled={!caps.text} diags={diags} onChange={setLocale("pending")} />
        </div>
      )}
      {action.type === "disabled" && <p className="text-xs text-muted-foreground">Answers with the project's “disabled” text.</p>}
      <FieldDiags list={diagsAt(diags, ptr).filter((d) => d.code !== "NAVIGATE_TARGET")} />
    </article>
  );
}
