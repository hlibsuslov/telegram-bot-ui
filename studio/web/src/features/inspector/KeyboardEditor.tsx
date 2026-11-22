import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Plus, X } from "lucide-react";
import { useState } from "react";
import type { Diag } from "@/core/lint.ts";
import { keyboardRows, localized, type Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { ACTION_ID_RE, ACTION_TYPES, defaultLocale, fieldDomId, KEYBOARD_TYPES } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { defaultsForType } from "./ActionEditor";
import { diagsAt, Field, FieldDiags, LocaleTexts, SelectField } from "./fields";

export function KeyboardEditor({ sid, screen, diags }: { sid: string; screen: Doc; diags: Diag[] }) {
  const { store, loaded, caps } = useStudio();
  const def = defaultLocale(loaded.project);
  const kb = screen.keyboard ?? { type: "none" };
  const rows = keyboardRows(screen);
  const actions = screen.actions ?? {};
  const placed = new Set(rows.flat());
  const unplaced = Object.keys(actions).filter((a) => !placed.has(a));
  const st = !caps.structure;
  const setRows = (fn: (rows: string[][]) => string[][]) =>
    store.updateScreen(sid, (doc) => {
      doc.keyboard = { ...(doc.keyboard ?? { type: "inline" }), rows: fn(keyboardRows(doc).map((r) => [...r])).filter((r) => r.length) };
    });
  const label = (aid: string) => localized(actions[aid]?.label, def, def) ?? aid;
  const hasRows = ["inline", "reply"].includes(kb.type);
  return (
    <div className="space-y-3">
      <SelectField id={fieldDomId(sid, "/keyboard/type")} label="Keyboard type" value={kb.type ?? "none"} disabled={st}
        options={KEYBOARD_TYPES.map((t) => ({ value: t, label: t }))} diags={diagsAt(diags, "/keyboard/type")}
        onChange={(v) => store.updateScreen(sid, (doc) => {
          doc.keyboard = { ...(doc.keyboard ?? {}), type: v };
          if (!["inline", "reply"].includes(v)) delete doc.keyboard.rows;
          else doc.keyboard.rows ??= [];
          if (v !== "force_reply") delete doc.keyboard.placeholder;
        })} />
      {kb.type === "force_reply" && (
        <LocaleTexts sid={sid} pointer="/keyboard/placeholder" label="Input placeholder" value={kb.placeholder} multiline={false}
          disabled={!caps.text} diags={diags}
          onChange={(loc, text) => store.updateScreen(sid, (doc) => { doc.keyboard.placeholder = { ...(typeof doc.keyboard.placeholder === "object" ? doc.keyboard.placeholder : {}), [loc]: text }; }, `ph:${loc}`)} />
      )}
      {hasRows && (
        <ol className="space-y-2" aria-label="Keyboard rows">
          {rows.map((row, r) => (
            <li key={r} className="rounded-md border p-2">
              <div className="mb-1.5 flex items-center gap-1">
                <span className="text-[11px] font-medium text-muted-foreground">Row {r + 1}</span>
                {caps.structure && (
                  <span className="ml-auto flex gap-0.5">
                    <Button type="button" size="icon" variant="ghost" className="size-7" disabled={r === 0} aria-label={`Move row ${r + 1} up`}
                      onClick={() => setRows((rs) => { [rs[r - 1], rs[r]] = [rs[r], rs[r - 1]]; return rs; })}><ArrowUp className="size-3.5" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="size-7" disabled={r === rows.length - 1} aria-label={`Move row ${r + 1} down`}
                      onClick={() => setRows((rs) => { [rs[r + 1], rs[r]] = [rs[r], rs[r + 1]]; return rs; })}><ArrowDown className="size-3.5" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="size-7" aria-label={`Remove row ${r + 1} (actions stay defined)`}
                      onClick={() => setRows((rs) => rs.filter((_, i) => i !== r))}><X className="size-3.5" /></Button>
                  </span>
                )}
              </div>
              <ul className="flex flex-wrap gap-1.5">
                {row.map((aid, c) => (
                  <li key={aid} id={fieldDomId(sid, `/keyboard/rows/${r}/${c}`)} tabIndex={-1}
                    className="flex items-center gap-0.5 rounded-md border bg-muted/40 py-0.5 pr-0.5 pl-2 text-xs">
                    <span className="font-mono">{aid}</span>
                    <span className="max-w-32 truncate text-muted-foreground">· {label(aid)}</span>
                    {caps.structure && (
                      <>
                        <Button type="button" size="icon" variant="ghost" className="size-6" disabled={c === 0} aria-label={`Move ${aid} left`}
                          onClick={() => setRows((rs) => { [rs[r][c - 1], rs[r][c]] = [rs[r][c], rs[r][c - 1]]; return rs; })}><ArrowLeft className="size-3" /></Button>
                        <Button type="button" size="icon" variant="ghost" className="size-6" disabled={c === row.length - 1} aria-label={`Move ${aid} right`}
                          onClick={() => setRows((rs) => { [rs[r][c + 1], rs[r][c]] = [rs[r][c], rs[r][c + 1]]; return rs; })}><ArrowRight className="size-3" /></Button>
                        <Button type="button" size="icon" variant="ghost" className="size-6" aria-label={`Take ${aid} off the keyboard`}
                          onClick={() => setRows((rs) => { rs[r] = rs[r].filter((x) => x !== aid); return rs; })}><X className="size-3" /></Button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
              {row.map((_, c) => <FieldDiags key={c} list={diagsAt(diags, `/keyboard/rows/${r}/${c}`)} />)}
              {caps.structure && unplaced.length > 0 && (
                <div className="mt-1.5">
                  <label className="sr-only" htmlFor={`${sid}-addto-${r}`}>Add an action to row {r + 1}</label>
                  <NativeSelect id={`${sid}-addto-${r}`} size="sm" value="" onChange={(e) => e.target.value && setRows((rs) => { rs[r].push(e.target.value); return rs; })}>
                    <NativeSelectOption value="">+ Add to this row…</NativeSelectOption>
                    {unplaced.map((a) => <NativeSelectOption key={a} value={a}>{a}</NativeSelectOption>)}
                  </NativeSelect>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
      {hasRows && caps.structure && unplaced.length > 0 && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground" htmlFor={`${sid}-newrow`}>New row with</label>
          <NativeSelect id={`${sid}-newrow`} size="sm" value="" onChange={(e) => e.target.value && setRows((rs) => [...rs, [e.target.value]])}>
            <NativeSelectOption value="">Choose an action…</NativeSelectOption>
            {unplaced.map((a) => <NativeSelectOption key={a} value={a}>{a}</NativeSelectOption>)}
          </NativeSelect>
        </div>
      )}
      <FieldDiags list={diagsAt(diags, "/keyboard", false)} />
    </div>
  );
}

export function NewAction({ sid, screen }: { sid: string; screen: Doc }) {
  const { store, loaded } = useStudio();
  const def = defaultLocale(loaded.project);
  const [id, setId] = useState("");
  const [type, setType] = useState("navigate");
  const exists = !!screen.actions?.[id];
  const problem = !id ? null : !ACTION_ID_RE.test(id) ? "Lowercase letters, digits, _ and -, one segment." : exists ? "This screen already has that action." : null;
  const add = () => {
    if (!id || problem) return;
    store.updateScreen(sid, (doc) => {
      doc.actions = { ...(doc.actions ?? {}), [id]: { label: { [def]: id }, type, ...defaultsForType(type, loaded.project, def) } };
      const kt = doc.keyboard?.type;
      if (kt === "inline" || kt === "reply") doc.keyboard.rows = [...keyboardRows(doc), [id]];
      else if (!doc.keyboard || kt === "none") doc.keyboard = { type: "inline", rows: [[id]] };
    });
    setId("");
    requestAnimationFrame(() => document.getElementById(fieldDomId(sid, `/actions/${id}/label/${def}`))?.focus());
  };
  return (
    <form className="flex flex-wrap items-end gap-2 rounded-md border border-dashed p-2" onSubmit={(e) => { e.preventDefault(); add(); }}>
      <Field label="New action ID" htmlFor={`${sid}-newaction`} className="min-w-40 flex-1">
        <Input id={`${sid}-newaction`} value={id} onChange={(e) => setId(e.target.value.trim())} placeholder="e.g. help" className="font-mono text-[13px]"
          aria-invalid={!!problem || undefined} aria-describedby={problem ? `${sid}-newaction-p` : undefined} />
      </Field>
      <Field label="Type" htmlFor={`${sid}-newaction-type`}>
        <NativeSelect id={`${sid}-newaction-type`} value={type} onChange={(e) => setType(e.target.value)}>
          {ACTION_TYPES.map((t) => <NativeSelectOption key={t} value={t}>{t}</NativeSelectOption>)}
        </NativeSelect>
      </Field>
      <Button type="submit" size="sm" variant="secondary" disabled={!id || !!problem}><Plus className="size-4" /> Add action</Button>
      {problem && <p id={`${sid}-newaction-p`} className="w-full text-xs text-destructive">{problem}</p>}
    </form>
  );
}
