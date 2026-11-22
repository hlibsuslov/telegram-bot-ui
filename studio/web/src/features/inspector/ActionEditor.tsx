import { ChevronRight, Trash2 } from "lucide-react";
import type { Diag } from "@/core/lint.ts";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ACTION_TYPES, defaultLocale, fieldDomId, STYLE_LABELS, STYLES } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { CustomEmoji } from "@/features/emoji/CustomEmoji";
import { EmojiPicker } from "@/features/emoji/EmojiPicker";
import { useEmoji } from "@/features/emoji/context";
import { diagsAt, dropLeadingEmoji, EnumSelect, Field, FieldDiags, LocaleText, Segmented, SelectField, TargetSelect } from "./fields";

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
  const hl = { part: "action" as const, actionId: aid };
  const setEq = (v: any) => onChange((r) => { r.when = { ...(r.when ?? {}), eq: v }; }, "eq");
  let valueInput;
  if (fd?.type === "enum" || fd?.type === "boolean") {
    const opts: any[] = fd.type === "enum" ? fd.values ?? [] : [true, false];
    valueInput = (
      <EnumSelect id={eqId} value={eq === undefined ? "" : JSON.stringify(eq)} disabled={disabled} invalid={eqDiags.length > 0} className="font-mono text-[13px]"
        onChange={(v) => setEq(v ? JSON.parse(v) : undefined)}
        options={[{ value: "", label: "Choose a value…" }, ...opts.map((o) => ({ value: JSON.stringify(o), label: String(o) }))]} />
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
    <div className="space-y-3 rounded-lg bg-muted/50 p-3">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
        <Field label="When field" htmlFor={fieldId}>
          <EnumSelect id={fieldId} value={fname} disabled={disabled} className="font-mono text-[13px]"
            onChange={(v) => onChange((r) => {
              const nf = fields[v];
              r.when = { field: v, eq: nf?.type === "enum" ? nf.values?.[0] : nf?.type === "boolean" ? true : nf?.type === "number" ? 0 : "" };
            })}
            options={[
              { value: "", label: "Choose a field…" },
              ...(fname && !ruleFields.some(([n]) => n === fname) ? [{ value: fname, label: `${fname} (not allowed)` }] : []),
              ...ruleFields.map(([n, f]) => ({ value: n, label: <span><span className="font-mono">{n}</span> <span className="text-muted-foreground">{f.source}</span></span> })),
            ]} />
          <FieldDiags list={diagsAt(diags, `${ptr}/when/field`)} />
        </Field>
        <span className="hidden pb-2 text-center font-mono text-sm text-muted-foreground sm:block" aria-hidden>==</span>
        <Field label="Equals" htmlFor={eqId}>
          {valueInput}
          <FieldDiags list={eqDiags} />
        </Field>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <TargetSelect sid={sid} pointer={`${ptr}/match`} label="Then (match)" value={rule.match} disabled={disabled} diags={diags} hl={hl}
          onChange={(to) => onChange((r) => { r.match = to; })} />
        <TargetSelect sid={sid} pointer={`${ptr}/otherwise`} label="Otherwise" value={rule.otherwise} disabled={disabled} diags={diags} hl={hl}
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
      <Segmented label="Target kind" value={hasRule ? "rule" : "to"} disabled={disabled}
        options={[{ value: "to", label: "One screen" }, { value: "rule", label: "Rule (two branches)" }]}
        onChange={(k) => update((a) => {
          if (k === "rule" && !a.rule) {
            const [fname, fd] = firstRuleField ?? ["", {}];
            a.rule = { when: { field: fname, eq: fd.type === "enum" ? fd.values?.[0] : "" }, match: a.to ?? "", otherwise: a.to ?? "" };
            delete a.to;
          } else if (k === "to" && a.rule) {
            a.to = a.rule.match ?? "";
            delete a.rule;
          }
        })} />
      {hasRule ? (
        <RuleEditor sid={sid} aid={aid} rule={action.rule} disabled={disabled} diags={diags}
          onChange={(fn, key) => update((a) => { fn(a.rule); }, key ? `rule:${key}` : undefined)} />
      ) : (
        <TargetSelect sid={sid} pointer={`${ptr}/to`} label="Go to" value={action.to} disabled={disabled} diags={diags} hl={{ part: "action", actionId: aid }}
          onChange={(to) => update((a) => { a.to = to; })} />
      )}
      <FieldDiags list={diagsAt(diags, ptr).filter((d) => d.code === "NAVIGATE_TARGET")} />
    </div>
  );
}

function useActionUpdate(sid: string, aid: string) {
  const { store } = useStudio();
  const update = (fn: (a: Doc) => void, key?: string) =>
    store.updateScreen(sid, (doc) => { fn(doc.actions[aid]); }, key ? `${aid}:${key}` : undefined);
  const setLocale = (field: string) => (loc: string, text: string) =>
    update((a) => { a[field] = typeof a[field] === "object" && a[field] ? { ...a[field], [loc]: text } : { [loc]: text }; }, `${field}:${loc}`);
  return { update, setLocale };
}

const TYPE_LABEL: Record<string, string> = {
  navigate: "opens a screen", back: "goes back", url: "opens a link", answer: "shows a short notice", handler: "runs your bot's code", disabled: "is disabled",
};

/** Buttons group: what the button says and looks like. */
export function ButtonCard({ sid, aid, action, placed, diags, selected }: { sid: string; aid: string; action: Doc; placed: boolean; diags: Diag[]; selected?: boolean }) {
  const { store, loaded, caps, setHighlight, pro, working } = useStudio();
  const def = defaultLocale(loaded.project);
  const ptr = `/actions/${aid}`;
  const hl = { part: "action" as const, actionId: aid };
  const { update, setLocale } = useActionUpdate(sid, aid);
  const keyboardType = working.screens[sid]?.keyboard?.type ?? "inline";
  // An icon goes before the label; the emoji the label started with would show twice.
  const setIcon = (id: string) => update((a) => {
    if (!id) { delete a.icon; return; }
    a.icon = { customEmojiId: id };
    if (typeof a.label === "string") a.label = dropLeadingEmoji(a.label) || a.label;
    else if (a.label && typeof a.label === "object") for (const k of Object.keys(a.label)) a.label[k] = dropLeadingEmoji(a.label[k]) || a.label[k];
  }, "icon");
  return (
    <article id={`${fieldDomId(sid, ptr)}-card`} className={cn("scroll-mt-4 space-y-3 rounded-xl bg-card p-3 ring-1 ring-border transition-shadow", selected && "ring-2 ring-amber-400")}
      aria-label={`Button ${aid}`} onFocus={() => setHighlight({ sid, ...hl })}>
      <header className="flex flex-wrap items-center gap-2">
        <span id={fieldDomId(sid, ptr)} tabIndex={-1} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[11px]">{aid}</span>
        <span className="text-xs text-muted-foreground">{TYPE_LABEL[action.type] ?? action.type}</span>
        {!placed && <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">not on the keyboard</span>}
        <div className="ml-auto flex items-center gap-1">
          {pro && (
            <div className="w-32">
              <EnumSelect id={fieldDomId(sid, `${ptr}/type`)} label={`Type of ${aid}`} size="sm" value={action.type ?? ""} disabled={!caps.structure}
                options={ACTION_TYPES.map((t) => ({ value: t, label: t }))}
                onChange={(v) => update((a) => { for (const k of TYPE_KEYS) delete a[k]; a.type = v; Object.assign(a, defaultsForType(v, loaded.project, def)); })} />
            </div>
          )}
          {caps.structure && (
            <Button type="button" size="icon" variant="ghost" className="size-8" aria-label={`Delete button ${aid}`} title="Delete this button"
              onClick={() => store.updateScreen(sid, (doc) => {
                delete doc.actions[aid];
                if (doc.keyboard?.rows) doc.keyboard.rows = doc.keyboard.rows.map((r: string[]) => r.filter((x) => x !== aid)).filter((r: string[]) => r.length);
              })}>
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>
      </header>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <LocaleText sid={sid} pointer={`${ptr}/label`} label="Label" value={action.label} multiline={false} disabled={!caps.text} diags={diags} onChange={setLocale("label")} hl={hl}
          emojiLabel="Icon" emojiPick={caps.structure && ["inline", "reply"].includes(keyboardType) ? (p) => setIcon(p.id) : undefined} />
        <SelectField id={fieldDomId(sid, `${ptr}/style`)} label="Colour" value={action.style ?? ""} disabled={!caps.structure}
          options={STYLES.map((s) => ({ value: s, label: STYLE_LABELS[s] ?? s }))} diags={diagsAt(diags, `${ptr}/style`)}
          onChange={(v) => update((a) => { if (v) a.style = v; else delete a.style; })} />
      </div>
      <Field label="Premium emoji icon (optional)" htmlFor={fieldDomId(sid, `${ptr}/icon`)}
        hint="Shown before the label. Pick it from the bot's icons (Emoji page); Telegram shows it only if your bot may use custom emoji (Fragment username or a Premium owner).">
        <IconField sid={sid} ptr={ptr} value={action.icon?.customEmojiId ?? ""} disabled={!caps.structure} onChange={setIcon} />
        <FieldDiags list={diagsAt(diags, `${ptr}/icon`)} />
      </Field>
      <FieldDiags list={diagsAt(diags, ptr).filter((d) => d.code !== "NAVIGATE_TARGET")} />
    </article>
  );
}

/** "Where buttons lead" group: the target, rule, outcomes or link of one button. */
export function ButtonRoute({ sid, aid, action, diags, selected }: { sid: string; aid: string; action: Doc; diags: Diag[]; selected?: boolean }) {
  const { loaded, caps, setHighlight, editLocale } = useStudio();
  const def = defaultLocale(loaded.project);
  const ptr = `/actions/${aid}`;
  const hl = { part: "action" as const, actionId: aid };
  const { update, setLocale } = useActionUpdate(sid, aid);
  const handlers = loaded.project.handlers ?? {};
  const outcomes: string[] = handlers[action.handlerId]?.outcomes ?? Object.keys(action.outcomes ?? {});
  const label = typeof action.label === "object" ? action.label?.[editLocale] ?? action.label?.[def] : action.label;
  if (action.type === "disabled") return null;
  return (
    <div className={cn("space-y-2 rounded-xl p-3 ring-1 ring-border", selected && "ring-2 ring-amber-400")} onFocus={() => setHighlight({ sid, ...hl })}>
      <p className="flex items-center gap-1.5 text-sm"><span className="font-medium">«{label || aid}»</span><ChevronRight className="size-3.5 text-muted-foreground" aria-hidden /><span className="text-xs text-muted-foreground">{TYPE_LABEL[action.type] ?? action.type}</span></p>
      {action.type === "navigate" && <NavigateTarget sid={sid} aid={aid} action={action} update={update} disabled={!caps.rule} diags={diags} />}
      {action.type === "back" && (
        <TargetSelect sid={sid} pointer={`${ptr}/fallback`} label="If there is nothing to go back to (after a restart)" value={action.fallback}
          allowEmpty="No fallback" disabled={!caps.rule} diags={diags} hl={hl}
          onChange={(to) => update((a) => { if (to) a.fallback = to; else delete a.fallback; })} />
      )}
      {action.type === "url" && (
        <Field label="Link (never opened by the Studio)" htmlFor={fieldDomId(sid, `${ptr}/url`)}>
          <Input id={fieldDomId(sid, `${ptr}/url`)} value={action.url ?? ""} disabled={!caps.structure} className="font-mono text-[13px]"
            onChange={(e) => update((a) => { a.url = e.target.value; }, "url")} />
          <FieldDiags list={diagsAt(diags, `${ptr}/url`)} />
        </Field>
      )}
      {action.type === "answer" && (
        <LocaleText sid={sid} pointer={`${ptr}/text`} label="Notice text" value={action.text} multiline={false} disabled={!caps.text} diags={diags} onChange={setLocale("text")} hl={hl} />
      )}
      {action.type === "handler" && (
        <div className="space-y-2">
          {outcomes.length === 0 && <p className="text-xs text-muted-foreground">Choose the bot code in Advanced.</p>}
          {outcomes.map((o) => (
            <TargetSelect key={o} sid={sid} pointer={`${ptr}/outcomes/${o}`} label={`When the code answers “${o}”`} value={action.outcomes?.[o]}
              disabled={!caps.rule} diags={diags} hl={hl}
              onChange={(to) => update((a) => { a.outcomes = { ...(a.outcomes ?? {}), [o]: to }; if (!to) delete a.outcomes[o]; })} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Advanced group: presentation, handler wiring, pending text. */
export function ButtonAdvanced({ sid, aid, action, diags }: { sid: string; aid: string; action: Doc; diags: Diag[] }) {
  const { loaded, caps } = useStudio();
  const ptr = `/actions/${aid}`;
  const { update, setLocale } = useActionUpdate(sid, aid);
  const handlers = loaded.project.handlers ?? {};
  if (!["navigate", "back", "handler"].includes(action.type)) return null;
  return (
    <div className="space-y-2 rounded-xl bg-muted/40 p-3">
      <p className="font-mono text-xs font-medium">{aid}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <SelectField id={fieldDomId(sid, `${ptr}/presentation`)} label="Presentation" value={action.presentation ?? ""} disabled={!caps.structure}
          options={[{ value: "", label: "default (edit)" }, { value: "edit", label: "edit the message" }, { value: "send", label: "send a new message" }]}
          diags={diagsAt(diags, `${ptr}/presentation`)} onChange={(v) => update((a) => { if (v) a.presentation = v; else delete a.presentation; })} />
        {action.type === "handler" && (
          <SelectField id={fieldDomId(sid, `${ptr}/handlerId`)} label="Bot code (handler)" value={action.handlerId ?? ""} disabled={!caps.structure}
            options={[{ value: "", label: "Choose…" }, ...Object.keys(handlers).map((h) => ({ value: h, label: h }))]}
            diags={diagsAt(diags, `${ptr}/handlerId`)} onChange={(v) => update((a) => { a.handlerId = v; a.outcomes = {}; })} />
        )}
      </div>
      {action.type === "handler" && (
        <LocaleText sid={sid} pointer={`${ptr}/pending`} label="While the code runs" value={action.pending} multiline={false} disabled={!caps.text} diags={diags} onChange={setLocale("pending")} />
      )}
    </div>
  );
}

function IconField({ sid, ptr, value, disabled, onChange }: { sid: string; ptr: string; value: string; disabled: boolean; onChange: (id: string) => void }) {
  const { slotOf } = useEmoji();
  const slot = value ? slotOf.get(value) : undefined;
  return (
    <div className="flex items-center gap-2">
      <EmojiPicker selected={value || null} disabled={disabled} align="start" onPick={(p) => onChange(p.id)}
        trigger={
          <Button type="button" variant="outline" size="sm" className="h-9 min-w-24 justify-start gap-1.5" disabled={disabled} aria-label="Choose a premium emoji icon">
            {value ? <CustomEmoji id={value} className="size-5" /> : <span className="text-muted-foreground">Choose…</span>}
            {slot && <span className="truncate text-xs">{slot}</span>}
          </Button>
        } />
      <Input id={fieldDomId(sid, `${ptr}/icon`)} value={value} disabled={disabled} inputMode="numeric" placeholder="or paste an id" className="h-9 font-mono text-[13px]"
        onChange={(e) => onChange(e.target.value.trim())} aria-label="Custom emoji id" />
      {value && !disabled && <Button type="button" size="sm" variant="ghost" className="h-9" onClick={() => onChange("")}>Remove</Button>}
    </div>
  );
}
