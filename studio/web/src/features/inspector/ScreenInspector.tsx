import { Bot, Copy, MessageSquarePlus, RotateCcw } from "lucide-react";
import { RequestChange } from "../changes/Tray";
import { useState } from "react";
import { EDITABLE_FORMATS, keyboardRows, renderScreen, type Doc } from "@/core/render.ts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { defaultLocale, exampleValues, fieldDomId, KINDS, locales, screenFile } from "@/lib/model";
import { type Highlight, useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { ScreenPreview, type Hl } from "../preview/Telegram";
import { ActionEditor } from "./ActionEditor";
import { DiagLine, diagsAt, EnumSelect, Field, FieldDiags, LocaleText, Segmented, SelectField, TargetSelect, useScreenDiags } from "./fields";
import { KeyboardEditor, NewAction } from "./KeyboardEditor";

export function CopyButtons({ sid, compact }: { sid: string; compact?: boolean }) {
  const { copyId, copyRequest } = useStudio();
  return (
    <span className="flex flex-wrap items-center gap-1">
      <Button type="button" size="sm" variant="outline" className={cn("h-7 gap-1 px-2 text-xs", compact && "px-1.5")} onClick={() => copyId(sid)} aria-label={`Copy ID ${sid}`}>
        <Copy className="size-3.5" /> {compact ? "ID" : "Copy ID"}
      </Button>
      <Button type="button" size="sm" variant="outline" className={cn("h-7 gap-1 px-2 text-xs", compact && "px-1.5")} onClick={() => copyRequest(sid)} aria-label={`Copy a request for your agent about ${sid}`}>
        <Bot className="size-3.5" /> {compact ? "Ask" : "Copy agent prompt"}
      </Button>
      <RequestChange sid={sid} align="end" trigger={
        <Button type="button" size="sm" variant="outline" className={cn("h-7 gap-1 px-2 text-xs", compact && "px-1.5")} aria-label={`Request a change to ${sid}`}>
          <MessageSquarePlus className="size-3.5" /> {compact ? "Request" : "Request a change"}
        </Button>} />
    </span>
  );
}

export function DraftBadge({ draft, isNew }: { draft: boolean; isNew?: boolean }) {
  return draft ? (
    <Badge variant="outline" className="border-transparent bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100">{isNew ? "New draft" : "Draft"}</Badge>
  ) : (
    <Badge variant="outline" className="border-transparent bg-muted text-muted-foreground">Saved</Badge>
  );
}

function Section({ title, children, id }: { title: string; children: React.ReactNode; id: string }) {
  return (
    <section className="space-y-3 pt-5" aria-labelledby={id}>
      <h3 id={id} className="text-[13px] font-semibold tracking-tight">{title}</h3>
      {children}
    </section>
  );
}

export function hlFor(h: Highlight | null, sid: string): Hl | undefined {
  if (!h || h.sid !== sid) return undefined;
  return { text: h.part === "text", actionId: h.part === "action" ? h.actionId : undefined, keyboard: h.part === "keyboard", input: h.part === "input" };
}

/** Live preview of exactly this message, following the editing language and the highlight. */
export function LivePreview({ sid }: { sid: string }) {
  const { store, loaded, editLocale, highlight } = useStudio();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const screen = store.screen(sid);
  if (!screen) return null;
  const state = highlight?.sid === sid && highlight.state ? highlight.state : null;
  const logical = renderScreen(loaded.project, screen, { locale: editLocale, state, values: exampleValues(loaded.project) });
  return (
    <div className="space-y-1.5">
      <ScreenPreview logical={logical} theme={theme} hl={hlFor(highlight, sid)}
        contextLabel={`${screen.audience ?? "private"} · ${editLocale}${state ? ` · ${state}` : ""} · example values`} />
      <div className="flex items-center justify-between gap-2">
        {logical.diagnostics.length > 0 ? <p className="truncate text-[11px] text-muted-foreground">{logical.diagnostics[0].message}</p> : <span />}
        <Segmented size="xs" label="Preview theme" value={theme} onChange={setTheme} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
      </div>
    </div>
  );
}

export function ScreenInspector({ sid, compact, selectedAction }: { sid: string; compact?: boolean; selectedAction?: string | null }) {
  const { store, loaded, caps, focusField, setHighlight, editLocale } = useStudio();
  const screen = store.screen(sid);
  const diags = useScreenDiags(sid);
  if (!screen) return <p className="p-4 text-sm text-muted-foreground">Screen <span className="font-mono">{sid}</span> does not exist.</p>;
  const def = defaultLocale(loaded.project);
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
    <div>
      {diags.length > 0 && (
        <details className="rounded-lg bg-muted/50 p-2" open={errors > 0 && !compact}>
          <summary className="cursor-pointer text-xs font-medium">
            <span className={errors ? "text-destructive" : ""}>{errors} error{errors === 1 ? "" : "s"}</span>, {warnings} warning{warnings === 1 ? "" : "s"}
            {locales(loaded.project).length > 1 && <span className="text-muted-foreground"> · editing {editLocale}</span>}
          </summary>
          <ul className="mt-1 space-y-0.5">
            {diags.map((d, i) => <DiagLine key={i} d={d} showPlace onClick={() => focusField(sid, d.pointer)} />)}
          </ul>
        </details>
      )}

      <Section title="Message" id={sp("msg")}>
        {editableFormat ? (
          <SelectField id={fieldDomId(sid, "/message/format")} label="Format" value={fmt} disabled={!caps.structure}
            options={[{ value: "regular.plain", label: "Plain text" }, { value: "regular.html", label: "Telegram HTML" }]}
            diags={diagsAt(diags, "/message/format")}
            hint={fmt === "regular.html" ? "Tags: b, i, u, s, a, code, pre, blockquote, tg-spoiler. {field} placeholders are escaped." : "{field} placeholders are filled at send time; {{ and }} are braces."}
            onChange={(v) => set((doc) => { doc.message = { ...(doc.message ?? {}), format: v }; })} />
        ) : (
          <div className="rounded-lg bg-muted/50 p-2 text-xs" id={fieldDomId(sid, "/message/format")} tabIndex={-1}>
            <p><span className="font-mono">{fmt}</span> is read-only in the Studio (FORMAT_READ_ONLY): the file keeps it as is.</p>
            <p className="mt-1 text-muted-foreground">Edit <span className="font-mono">{file}</span> in your editor; the Studio picks up the change.</p>
          </div>
        )}
        <LocaleText sid={sid} pointer="/message/text" label="Text" value={msg.text} disabled={!caps.text || !editableFormat} diags={diags}
          hl={{ part: "text" }} onChange={setText((doc) => (doc.message ??= {}))} />
        {Object.entries<Doc>(msg.states ?? {}).map(([st, v]) => (
          <LocaleText key={st} sid={sid} pointer={`/message/states/${st}/text`} label={`State “${st}”`} value={v?.text}
            hl={{ part: "text", state: st }} disabled={!caps.text || !editableFormat} diags={diags} onChange={setText((doc) => doc.message.states[st])} />
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

      <Section title={`Buttons and actions (${Object.keys(screen.actions ?? {}).length})`} id={sp("act")}>
        {Object.entries<Doc>(screen.actions ?? {}).map(([aid, a]) => (
          <ActionEditor key={aid} sid={sid} aid={aid} action={a} placed={placed.has(aid)} diags={diags} selected={selectedAction === aid} />
        ))}
        {caps.structure && <NewAction sid={sid} screen={screen} />}
      </Section>

      <Section title="Text input" id={sp("input")}>
        <div onFocus={() => setHighlight({ sid, part: "input" })}>
          {screen.input ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <SelectField id={fieldDomId(sid, "/input/field")} label="Stores the text in" value={screen.input.field ?? ""} disabled={!caps.structure}
                options={[{ value: "", label: "Choose a field…" }, ...inputFields.map(([n]) => ({ value: n, label: n }))]}
                diags={diagsAt(diags, "/input/field")} onChange={(v) => set((doc) => { doc.input.field = v; })} />
              <TargetSelect sid={sid} pointer="/input/to" label="Then go to" value={screen.input.to} disabled={!caps.rule} diags={diags} hl={{ part: "input" }}
                onChange={(to) => set((doc) => { doc.input.to = to; })} />
              {caps.structure && (
                <Button type="button" size="sm" variant="ghost" className="justify-self-start" onClick={() => set((doc) => { delete doc.input; })}>Remove text input</Button>
              )}
            </div>
          ) : caps.structure && inputFields.length > 0 ? (
            <Button type="button" size="sm" variant="outline" onClick={() => set((doc) => { doc.input = { field: inputFields[0][0], to: "" }; })}>
              Wait for text input on this screen
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">This screen does not wait for text.</p>
          )}
        </div>
        <FieldDiags list={diagsAt(diags, "/input")} />
      </Section>

      {screen.widget && (
        <Section title="Widget" id={sp("widget")}>
          <p className="text-sm">Sends widget <a className="font-mono underline" href={`#/widgets/${encodeURIComponent(screen.widget.ref)}`}>{screen.widget.ref}</a>; outside a private chat this screen's message is sent instead.</p>
        </Section>
      )}

      <Section title="Screen" id={sp("meta")}>
        <Field label="Title (for the map; not shown to users)" htmlFor={fieldDomId(sid, "/title")}>
          <Input id={fieldDomId(sid, "/title")} value={screen.title ?? ""} disabled={!caps.text}
            onFocus={() => setHighlight(null)} onChange={(e) => set((doc) => { doc.title = e.target.value; }, "title")} />
          <FieldDiags list={diagsAt(diags, "/title")} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Kind" htmlFor={fieldDomId(sid, "/kind")}>
            <EnumSelect id={fieldDomId(sid, "/kind")} value={screen.kind ?? ""} disabled={!caps.structure}
              options={[...(screen.kind && !KINDS.includes(screen.kind) ? [screen.kind] : []), ...KINDS].map((k) => ({ value: k, label: k }))}
              onChange={(v) => set((doc) => { doc.kind = v; })} />
          </Field>
          <Field label="Audience" htmlFor={fieldDomId(sid, "/audience")}>
            <EnumSelect id={fieldDomId(sid, "/audience")} value={screen.audience ?? "private"} disabled={!caps.structure}
              options={["private", "group", "any"].map((k) => ({ value: k, label: k }))}
              onChange={(v) => set((doc) => { doc.audience = v; })} />
          </Field>
        </div>
        <FieldDiags list={[...diagsAt(diags, "/kind"), ...diagsAt(diags, "/audience")]} />
        <p className="font-mono text-[11px] text-muted-foreground">{file}</p>
      </Section>
    </div>
  );
}

/** Editor panel: header (ID, copy actions, draft state), live preview on top, then the form. */
export function ScreenEditor({ sid, selectedAction, onClose, compact }: { sid: string; selectedAction?: string | null; onClose?: () => void; compact?: boolean }) {
  const { store, loaded } = useStudio();
  const screen = store.screen(sid);
  if (!screen) return <p className="p-4 text-sm text-muted-foreground">Screen <span className="font-mono">{sid}</span> does not exist.</p>;
  const draft = store.isDraft(sid);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="space-y-2 border-b px-4 pt-3 pb-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{screen.kind}</span>
          <DraftBadge draft={draft} isNew={!loaded.screens[sid]} />
          {draft && (
            <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={() => store.resetScreen(sid)}>
              <RotateCcw className="size-3.5" /> Reset draft
            </Button>
          )}
          {onClose && <Button type="button" size="sm" variant="ghost" className="ml-auto h-7 text-xs" onClick={onClose}>Close</Button>}
        </div>
        <h2 className="font-mono text-[15px] font-semibold break-all">{sid}</h2>
        {screen.title && <p className="-mt-1 text-xs text-muted-foreground">{screen.title}</p>}
        <CopyButtons sid={sid} />
      </header>
      <div className="relative min-h-0 flex-1 overflow-y-auto" data-scroll-root>
        <div data-scroll-sticky className="sticky top-0 z-10 max-h-[42svh] overflow-y-auto border-b bg-background/95 px-4 py-3 backdrop-blur">
          <LivePreview sid={sid} />
        </div>
        <div className="px-4 pb-8">
          <ScreenInspector sid={sid} compact={compact} selectedAction={selectedAction} />
        </div>
      </div>
    </div>
  );
}
