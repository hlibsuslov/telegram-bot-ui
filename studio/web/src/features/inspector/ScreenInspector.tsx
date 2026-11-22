import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";
import { EDITABLE_FORMATS, keyboardRows, type Doc } from "@/core/render.ts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { copyText, defaultLocale, fieldDomId, KINDS, screenFile } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { ActionEditor } from "./ActionEditor";
import { DiagLine, diagsAt, Field, FieldDiags, LocaleTexts, SelectField, TargetSelect, useScreenDiags } from "./fields";
import { KeyboardEditor, NewAction } from "./KeyboardEditor";

export function CopyId({ id }: { id: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button type="button" size="icon" variant="ghost" className="size-7" aria-label={`Copy ID ${id}`}
      onClick={async () => { if (await copyText(id)) { setDone(true); setTimeout(() => setDone(false), 1200); } }}>
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

export function DraftBadge({ draft, isNew }: { draft: boolean; isNew?: boolean }) {
  return draft ? (
    <Badge variant="outline" className="border-amber-500/60 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100">{isNew ? "New draft" : "Draft"}</Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">Saved</Badge>
  );
}

function Section({ title, children, id }: { title: string; children: React.ReactNode; id?: string }) {
  return (
    <section className="space-y-3 border-t pt-4" aria-labelledby={id}>
      <h3 id={id} className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

export function ScreenInspector({ sid, compact }: { sid: string; compact?: boolean }) {
  const { store, loaded, caps, focusField } = useStudio();
  const screen = store.screen(sid);
  const diags = useScreenDiags(sid);
  if (!screen) return <p className="p-4 text-sm text-muted-foreground">Screen <span className="font-mono">{sid}</span> does not exist.</p>;
  const def = defaultLocale(loaded.project);
  const draft = store.isDraft(sid);
  const isNew = !loaded.screens[sid];
  const file = screenFile(loaded, sid);
  const msg = screen.message ?? {};
  const fmt: string = msg.format ?? "regular.plain";
  const editableFormat = EDITABLE_FORMATS.has(fmt);
  const set = (fn: (doc: Doc) => void, key?: string) => store.updateScreen(sid, fn, key);
  const setText = (base: (doc: Doc) => Doc) => (loc: string, text: string) =>
    set((doc) => { const o = base(doc); o.text = typeof o.text === "object" && o.text ? { ...o.text, [loc]: text } : { [loc]: text }; }, `text:${loc}`);
  const placed = new Set(keyboardRows(screen).flat());
  const inputFields = Object.entries<Doc>(loaded.project.fields ?? {}).filter(([, f]) => f.source === "input");
  const errors = diags.filter((d) => d.severity === "error").length;
  const warnings = diags.filter((d) => d.severity === "warning").length;
  const sp = (s: string) => `${sid}-${s}`;
  return (
    <div className="space-y-4">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <h2 className="font-mono text-base font-semibold break-all">{sid}</h2>
          <CopyId id={sid} />
          <DraftBadge draft={draft} isNew={isNew} />
          {draft && (
            <Button type="button" size="sm" variant="ghost" className="ml-auto h-7" onClick={() => store.resetScreen(sid)}>
              <RotateCcw className="size-3.5" /> Reset draft
            </Button>
          )}
        </div>
        <p className="font-mono text-[11px] text-muted-foreground">{file}</p>
        {diags.length > 0 && (
          <details className="rounded-md border bg-muted/30 p-2" open={errors > 0 && !compact}>
            <summary className="cursor-pointer text-xs font-medium">
              {errors} error{errors === 1 ? "" : "s"}, {warnings} warning{warnings === 1 ? "" : "s"}
            </summary>
            <ul className="mt-1 space-y-0.5">
              {diags.map((d, i) => <DiagLine key={i} d={d} showPlace onClick={() => focusField(sid, d.pointer)} />)}
            </ul>
          </details>
        )}
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Title (for the map; not shown to users)" htmlFor={fieldDomId(sid, "/title")} className="sm:col-span-2">
          <Input id={fieldDomId(sid, "/title")} value={screen.title ?? ""} disabled={!caps.text}
            onChange={(e) => set((doc) => { doc.title = e.target.value; }, "title")} />
          <FieldDiags list={diagsAt(diags, "/title")} />
        </Field>
        <SelectField id={fieldDomId(sid, "/kind")} label="Kind" value={screen.kind ?? ""} disabled={!caps.structure}
          options={[...(screen.kind && !KINDS.includes(screen.kind) ? [screen.kind] : []), ...KINDS].map((k) => ({ value: k, label: k }))}
          diags={diagsAt(diags, "/kind")} onChange={(v) => set((doc) => { doc.kind = v; })} />
        <SelectField id={fieldDomId(sid, "/audience")} label="Audience" value={screen.audience ?? "private"} disabled={!caps.structure}
          options={["private", "group", "any"].map((k) => ({ value: k, label: k }))}
          diags={diagsAt(diags, "/audience")} onChange={(v) => set((doc) => { doc.audience = v; })} />
      </div>

      <Section title="Message" id={sp("msg")}>
        {editableFormat ? (
          <SelectField id={fieldDomId(sid, "/message/format")} label="Format" value={fmt} disabled={!caps.structure}
            options={[{ value: "regular.plain", label: "Plain text" }, { value: "regular.html", label: "Telegram HTML" }]}
            diags={diagsAt(diags, "/message/format")}
            hint={fmt === "regular.html" ? "Tags: b, i, u, s, a, code, pre, blockquote, tg-spoiler. {field} placeholders are escaped." : "{field} placeholders are filled at send time; {{ and }} are braces."}
            onChange={(v) => set((doc) => { doc.message = { ...(doc.message ?? {}), format: v }; })} />
        ) : (
          <div className="rounded-md border border-dashed p-2 text-xs" id={fieldDomId(sid, "/message/format")} tabIndex={-1}>
            <p><span className="font-mono">{fmt}</span> is read-only in the Studio (FORMAT_READ_ONLY): the file keeps it as is.</p>
            <p className="mt-1 text-muted-foreground">Edit <span className="font-mono">{file}</span> in your editor; the Studio picks up the change.</p>
          </div>
        )}
        <LocaleTexts sid={sid} pointer="/message/text" label="Text" value={msg.text} disabled={!caps.text || !editableFormat} diags={diags}
          onChange={setText((doc) => (doc.message ??= {}))} />
        {Object.entries<Doc>(msg.states ?? {}).map(([st, v]) => (
          <div key={st} className="rounded-md border bg-muted/20 p-2">
            <LocaleTexts sid={sid} pointer={`/message/states/${st}/text`} label={`State “${st}”`} value={v?.text}
              disabled={!caps.text || !editableFormat} diags={diags} onChange={setText((doc) => doc.message.states[st])} />
          </div>
        ))}
        {caps.structure && editableFormat && !msg.states?.loading && (
          <Button type="button" size="sm" variant="outline"
            onClick={() => set((doc) => { doc.message = { ...(doc.message ?? {}), states: { ...(doc.message?.states ?? {}), loading: { text: { [def]: "⏳" } } } }; })}>
            Add a loading state
          </Button>
        )}
      </Section>

      <Section title="Keyboard" id={sp("kb")}>
        <KeyboardEditor sid={sid} screen={screen} diags={diags} />
      </Section>

      <Section title={`Actions (${Object.keys(screen.actions ?? {}).length})`} id={sp("act")}>
        {Object.entries<Doc>(screen.actions ?? {}).map(([aid, a]) => (
          <ActionEditor key={aid} sid={sid} aid={aid} action={a} placed={placed.has(aid)} diags={diags} />
        ))}
        {caps.structure && <NewAction sid={sid} screen={screen} />}
      </Section>

      <Section title="Text input" id={sp("input")}>
        {screen.input ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <SelectField id={fieldDomId(sid, "/input/field")} label="Stores the text in" value={screen.input.field ?? ""} disabled={!caps.structure}
              options={[{ value: "", label: "Choose a field…" }, ...inputFields.map(([n]) => ({ value: n, label: n }))]}
              diags={diagsAt(diags, "/input/field")} onChange={(v) => set((doc) => { doc.input.field = v; })} />
            <TargetSelect sid={sid} pointer="/input/to" label="Then go to" value={screen.input.to} disabled={!caps.rule} diags={diags}
              onChange={(to) => set((doc) => { doc.input.to = to; })} />
            {caps.structure && (
              <Button type="button" size="sm" variant="ghost" className="justify-self-start" onClick={() => set((doc) => { delete doc.input; })}>Remove text input</Button>
            )}
          </div>
        ) : caps.structure && inputFields.length > 0 ? (
          <Button type="button" size="sm" variant="outline"
            onClick={() => set((doc) => { doc.input = { field: inputFields[0][0], to: "" }; })}>
            Wait for text input on this screen
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">This screen does not wait for text.</p>
        )}
        <FieldDiags list={diagsAt(diags, "/input")} />
      </Section>

      {screen.widget && (
        <Section title="Widget" id={sp("widget")}>
          <p className="text-sm">Sends widget <a className="font-mono underline" href={`#/widgets/${encodeURIComponent(screen.widget.ref)}`}>{screen.widget.ref}</a>; outside a private chat this screen's message is sent instead.</p>
        </Section>
      )}
    </div>
  );
}
