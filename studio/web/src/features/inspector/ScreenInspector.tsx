import {
  Bot, ChevronDown, Copy, FolderGit2, ImagePlus, Keyboard, MessageSquarePlus, PencilLine, RotateCcw, Settings2, TextCursorInput, Type, Waypoints, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { CAPTION_MAX, CAPTION_MEDIA, EDITABLE_FORMATS, keyboardRows, mediaOf, MEDIA_TYPES, renderScreen, SPOILER_MEDIA, type Doc } from "@/core/render.ts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { defaultLocale, exampleValues, fieldDomId, KINDS, screenFile } from "@/lib/model";
import { href } from "@/lib/route";
import { type Highlight, useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { RequestChange } from "../changes/Tray";
import { ScreenPreview, type Hl } from "../preview/Telegram";
import { ButtonAdvanced, ButtonCard, ButtonRoute } from "./ActionEditor";
import { DiagLine, diagsAt, EnumSelect, Field, FieldDiags, LocaleText, Segmented, SelectField, TargetSelect, useScreenDiags } from "./fields";
import { KeyboardEditor, NewAction } from "./KeyboardEditor";

export function DraftBadge({ draft, isNew }: { draft: boolean; isNew?: boolean }) {
  return draft ? (
    <Badge variant="outline" className="border-transparent bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100">{isNew ? "New draft" : "Draft"}</Badge>
  ) : (
    <Badge variant="outline" className="border-transparent bg-muted text-muted-foreground">Saved</Badge>
  );
}

/** Small links from an editor or map node back to its entries on the Changes page. */
export function ChangeBadges({ kind, id, compact }: { kind: "screen" | "widget"; id: string; compact?: boolean }) {
  const { changeState } = useStudio();
  const s = changeState(kind, id);
  const chip = "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium hover:underline";
  return (
    <>
      {s.draft && <a href={href("changes", `${kind}-${id}`)} className={cn(chip, "bg-amber-100 text-amber-900")} title="Not saved yet: open in Changes" onClick={(e) => e.stopPropagation()}><PencilLine className="size-3" aria-hidden />{compact ? "" : "draft"}<span className="sr-only">draft, open in Changes</span></a>}
      {s.saved && <a href={href("changes", `saved-${kind}-${id}`)} className={cn(chip, "bg-sky-100 text-sky-900")} title="Saved to files, not committed: open in Changes" onClick={(e) => e.stopPropagation()}><FolderGit2 className="size-3" aria-hidden />{compact ? "" : "saved"}<span className="sr-only">saved, not committed, open in Changes</span></a>}
      {s.requests > 0 && <a href={href("changes", `request-${id}`)} className={cn(chip, "bg-violet-100 text-violet-900")} title="Requests for the agent: open in Changes" onClick={(e) => e.stopPropagation()}><MessageSquarePlus className="size-3" aria-hidden />{s.requests}<span className="sr-only">requests, open in Changes</span></a>}
    </>
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

function Group({ icon: Icon, title, hint, children, collapsible, defaultOpen = true, id }: {
  icon: typeof Type; title: string; hint?: string; children: ReactNode; collapsible?: boolean; defaultOpen?: boolean; id: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const head = (
    <>
      <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted"><Icon className="size-4" aria-hidden /></span>
      <span className="min-w-0 flex-1 text-left">
        <span id={id} className="block text-[13.5px] font-semibold tracking-tight">{title}</span>
        {hint && <span className="block text-[11.5px] text-muted-foreground">{hint}</span>}
      </span>
    </>
  );
  return (
    <section className="space-y-3 pt-5" aria-labelledby={id}>
      {collapsible ? (
        <button type="button" className="flex w-full items-center gap-2.5" aria-expanded={open} onClick={() => setOpen(!open)}>
          {head}<ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      ) : <div className="flex items-center gap-2.5">{head}</div>}
      {(!collapsible || open) && <div className="space-y-3">{children}</div>}
    </section>
  );
}

export function ScreenInspector({ sid, compact, selectedAction }: { sid: string; compact?: boolean; selectedAction?: string | null }) {
  const { store, loaded, caps, focusField, setHighlight, pro } = useStudio();
  const screen = store.screen(sid);
  const diags = useScreenDiags(sid);
  if (!screen) return <p className="p-4 text-sm text-muted-foreground">Screen <span className="font-mono">{sid}</span> does not exist.</p>;
  const def = defaultLocale(loaded.project);
  const file = screenFile(loaded, sid);
  const msg = screen.message ?? {};
  const media = mediaOf(screen);
  const fmt: string = msg.format ?? "regular.plain";
  const editableFormat = EDITABLE_FORMATS.has(fmt);
  const set = (fn: (doc: Doc) => void, key?: string) => store.updateScreen(sid, fn, key);
  const setText = (base: (doc: Doc) => Doc) => (loc: string, text: string) =>
    set((doc) => { const o = base(doc); o.text = typeof o.text === "object" && o.text ? { ...o.text, [loc]: text } : { [loc]: text }; }, `text:${loc}`);
  const placed = new Set(keyboardRows(screen).flat());
  const actions = Object.entries<Doc>(screen.actions ?? {});
  const inputFields = Object.entries<Doc>(loaded.project.fields ?? {}).filter(([, f]) => f.source === "input");
  const errors = diags.filter((d) => d.severity === "error").length;
  const warnings = diags.filter((d) => d.severity === "warning").length;
  const sp = (s: string) => `${sid}-${s}`;
  const advancedActions = actions.filter(([, a]) => ["navigate", "back", "handler"].includes(a.type));
  return (
    <div>
      {diags.length > 0 && (
        <details className="mt-3 rounded-lg bg-muted/50 p-2" open={errors > 0 && !compact}>
          <summary className="cursor-pointer text-xs font-medium">
            <span className={errors ? "text-destructive" : ""}>{errors} error{errors === 1 ? "" : "s"}</span>, {warnings} warning{warnings === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 space-y-0.5">
            {diags.map((d, i) => <DiagLine key={i} d={d} showPlace onClick={() => focusField(sid, d.pointer)} />)}
          </ul>
        </details>
      )}

      <MediaGroup sid={sid} screen={screen} diags={diags} />

      <Group icon={Type} title="Text" hint={media && !CAPTION_MEDIA.has(media.type) ? "This kind of media has no caption." : media ? "The caption under the media." : "What the message says."} id={sp("text")}>
        {media && !CAPTION_MEDIA.has(media.type) ? (
          <p className="text-xs text-muted-foreground">A {media.type === "video_note" ? "round video message" : "sticker"} is sent without text; put any text on its own screen.</p>
        ) : <LocaleText sid={sid} pointer="/message/text" label={media ? "Caption" : "Message"} value={msg.text} disabled={!caps.text || !editableFormat} diags={diags}
          max={media ? CAPTION_MAX : 4096}
          hl={{ part: "text" }} onChange={setText((doc) => (doc.message ??= {}))}
          hint={fmt === "regular.html" ? "Bold: <b>…</b>, italic: <i>…</i>, link: <a href=\"…\">…</a>, custom emoji: <tg-emoji emoji-id=\"…\">☕</tg-emoji>. {field} is filled in when sent." : "{field} is filled in when sent."} />}
        {!editableFormat && <p className="text-xs text-muted-foreground"><span className="font-mono">{fmt}</span> is read-only here; edit <span className="font-mono">{file}</span> in your editor.</p>}
      </Group>

      <Group icon={Keyboard} title={`Buttons (${actions.length})`} hint="What the buttons say, their colour and order." id={sp("buttons")}>
        <KeyboardEditor sid={sid} screen={screen} diags={diags} showType={pro} />
        {actions.map(([aid, a]) => <ButtonCard key={aid} sid={sid} aid={aid} action={a} placed={placed.has(aid)} diags={diags} selected={selectedAction === aid} />)}
        {caps.structure && <NewAction sid={sid} screen={screen} />}
      </Group>

      <Group icon={Waypoints} title="Where buttons lead" hint="The screen each button opens; a rule can pick one of two." id={sp("lead")}>
        {actions.map(([aid, a]) => <ButtonRoute key={aid} sid={sid} aid={aid} action={a} diags={diags} selected={selectedAction === aid} />)}
        <div className="rounded-xl p-3 ring-1 ring-border" onFocus={() => setHighlight({ sid, part: "input" })}>
          <p className="mb-2 flex items-center gap-1.5 text-sm font-medium"><TextCursorInput className="size-4 text-muted-foreground" aria-hidden /> When the user types a message</p>
          {screen.input ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <SelectField id={fieldDomId(sid, "/input/field")} label="Keep the text as" value={screen.input.field ?? ""} disabled={!caps.structure}
                options={[{ value: "", label: "Choose a field…" }, ...inputFields.map(([n]) => ({ value: n, label: n }))]}
                diags={diagsAt(diags, "/input/field")} onChange={(v) => set((doc) => { doc.input.field = v; })} />
              <TargetSelect sid={sid} pointer="/input/to" label="Then go to" value={screen.input.to} disabled={!caps.rule} diags={diags} hl={{ part: "input" }}
                onChange={(to) => set((doc) => { doc.input.to = to; })} />
              {caps.structure && <Button type="button" size="sm" variant="ghost" className="justify-self-start" onClick={() => set((doc) => { delete doc.input; })}><X className="size-3.5" /> Stop waiting for text</Button>}
            </div>
          ) : caps.structure && inputFields.length > 0 ? (
            <Button type="button" size="sm" variant="outline" onClick={() => set((doc) => { doc.input = { field: inputFields[0][0], to: "" }; })}>Wait for a text reply on this screen</Button>
          ) : <p className="text-xs text-muted-foreground">This screen does not wait for text.</p>}
          <FieldDiags list={diagsAt(diags, "/input")} />
        </div>
      </Group>

      {screen.widget && (
        <Group icon={Bot} title="Widget" id={sp("widget")}>
          <p className="text-sm">Sends widget <a className="font-mono underline" href={`#/widgets/${encodeURIComponent(screen.widget.ref)}`}>{screen.widget.ref}</a>; outside a private chat this message is sent instead.</p>
        </Group>
      )}

      <Group icon={Settings2} title="Advanced" hint="Format, extra states, how a button shows the next screen, kind and audience." id={sp("adv")} collapsible defaultOpen={pro}>
        {editableFormat ? (
          <SelectField id={fieldDomId(sid, "/message/format")} label="Text format" value={fmt} disabled={!caps.structure}
            options={[{ value: "regular.plain", label: "Plain text" }, { value: "regular.html", label: "Telegram HTML" }]}
            diags={diagsAt(diags, "/message/format")} onChange={(v) => set((doc) => { doc.message = { ...(doc.message ?? {}), format: v }; })} />
        ) : <p className="text-xs"><span className="font-mono">{fmt}</span> is read-only in the Studio (FORMAT_READ_ONLY).</p>}
        {Object.entries<Doc>(msg.states ?? {}).map(([st, v]) => (
          <LocaleText key={st} sid={sid} pointer={`/message/states/${st}/text`} label={`Text while “${st}”`} value={v?.text}
            hl={{ part: "text", state: st }} disabled={!caps.text || !editableFormat} diags={diags} onChange={setText((doc) => doc.message.states[st])} />
        ))}
        {caps.structure && editableFormat && !msg.states?.loading && (
          <Button type="button" size="sm" variant="outline"
            onClick={() => set((doc) => { doc.message = { ...(doc.message ?? {}), states: { ...(doc.message?.states ?? {}), loading: { text: { [def]: "⏳" } } } }; })}>
            Add a “loading” text
          </Button>
        )}
        {!pro && <KeyboardEditor sid={sid} screen={screen} diags={diags} onlyType />}
        {advancedActions.map(([aid, a]) => <ButtonAdvanced key={aid} sid={sid} aid={aid} action={a} diags={diags} />)}
        <div className="grid grid-cols-2 gap-2">
          <Field label="Kind" htmlFor={fieldDomId(sid, "/kind")}>
            <EnumSelect id={fieldDomId(sid, "/kind")} value={screen.kind ?? ""} disabled={!caps.structure}
              options={[...(screen.kind && !KINDS.includes(screen.kind) ? [screen.kind] : []), ...KINDS].map((k) => ({ value: k, label: k }))}
              onChange={(v) => set((doc) => { doc.kind = v; })} />
          </Field>
          <Field label="Audience" htmlFor={fieldDomId(sid, "/audience")}>
            <EnumSelect id={fieldDomId(sid, "/audience")} value={screen.audience ?? "private"} disabled={!caps.structure}
              options={["private", "group", "any"].map((k) => ({ value: k, label: k }))} onChange={(v) => set((doc) => { doc.audience = v; })} />
          </Field>
        </div>
        <FieldDiags list={[...diagsAt(diags, "/kind"), ...diagsAt(diags, "/audience")]} />
        <p className="font-mono text-[11px] text-muted-foreground">{file}</p>
      </Group>
    </div>
  );
}

/** Editor: one compact header, the form on the left and the live preview in a sticky right column
 * (stacked above the form when the panel is narrow). */
export function ScreenEditor({ sid, selectedAction, onClose, compact }: { sid: string; selectedAction?: string | null; onClose?: () => void; compact?: boolean }) {
  const { store, loaded, caps, copyId, copyRequest, diags } = useStudio();
  const screen = store.screen(sid);
  if (!screen) return <p className="p-4 text-sm text-muted-foreground">Screen <span className="font-mono">{sid}</span> does not exist.</p>;
  const draft = store.isDraft(sid);
  const titleErr = diags.filter((d) => d.screenId === sid && d.pointer === "/title");
  return (
    <div className="@container flex h-full min-h-0 flex-col">
      <header className="space-y-2 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor={fieldDomId(sid, "/title")}>Screen title (for you; not shown to users)</label>
          <Input id={fieldDomId(sid, "/title")} value={screen.title ?? ""} disabled={!caps.text} placeholder="Untitled screen" title="Title for you; not shown to users"
            onChange={(e) => store.updateScreen(sid, (doc) => { doc.title = e.target.value; }, "title")}
            className="h-9 min-w-0 flex-1 border-transparent bg-transparent px-1.5 text-base font-semibold shadow-none hover:border-input focus-visible:border-input" />
          {draft && <Button type="button" size="icon" variant="ghost" className="size-8" onClick={() => store.resetScreen(sid)} aria-label="Discard this screen's draft" title="Discard the draft"><RotateCcw className="size-4" /></Button>}
          {onClose && <Button type="button" size="icon" variant="ghost" className="size-8" onClick={onClose} aria-label="Close the editor" title="Close"><X className="size-4" /></Button>}
        </div>
        <FieldDiags list={titleErr} />
        <div className="flex flex-wrap items-center gap-1.5">
          <button type="button" onClick={() => copyId(sid)} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 font-mono text-[11.5px] hover:bg-muted/70" aria-label={`Copy ID ${sid}`} title="Copy the screen ID">
            {sid}<Copy className="size-3 text-muted-foreground" aria-hidden />
          </button>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{screen.kind}</span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{screen.audience ?? "private"}</span>
          <DraftBadge draft={draft} isNew={!loaded.screens[sid]} />
          <ChangeBadges kind="screen" id={sid} />
          <span className="ml-auto flex items-center gap-1">
            <Button type="button" size="sm" variant="outline" className="h-7 gap-1 px-2 text-xs" onClick={() => copyRequest(sid)} aria-label={`Copy a prompt for your agent about ${sid}`} title="Copy a ready prompt for your coding agent">
              <Bot className="size-3.5" /> Agent prompt
            </Button>
            <RequestChange sid={sid} align="end" trigger={
              <Button type="button" size="sm" variant="outline" className="h-7 gap-1 px-2 text-xs" aria-label={`Request a change to ${sid}`} title="Queue a note for your agent">
                <MessageSquarePlus className="size-3.5" /> Request
              </Button>} />
          </span>
        </div>
      </header>
      <div className="relative min-h-0 flex-1 overflow-y-auto" data-scroll-root>
        <div className="grid grid-cols-1 @[46rem]:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] @[46rem]:gap-5">
          <div data-scroll-sticky className="sticky top-0 z-10 max-h-[42svh] overflow-y-auto border-b bg-background/95 px-4 py-3 backdrop-blur @[46rem]:order-2 @[46rem]:max-h-[calc(100svh-12rem)] @[46rem]:border-b-0 @[46rem]:bg-transparent @[46rem]:px-0 @[46rem]:pr-4 @[46rem]:backdrop-blur-none">
            <LivePreview sid={sid} />
          </div>
          <div className="min-w-0 px-4 pb-10 @[46rem]:order-1 @[46rem]:pr-0">
            <ScreenInspector sid={sid} compact={compact} selectedAction={selectedAction} />
          </div>
        </div>
      </div>
    </div>
  );
}

const MEDIA_LABEL: Record<string, string> = { photo: "Photo", video: "Video", animation: "GIF / animation", audio: "Audio", voice: "Voice message", video_note: "Round video", sticker: "Sticker" };

/** Media above the text: type, where the file comes from (no uploads), spoiler, sticker emoji. */
function MediaGroup({ sid, screen, diags }: { sid: string; screen: Doc; diags: ReturnType<typeof useScreenDiags> }) {
  const { store, caps, loaded } = useStudio();
  const m: Doc | null = screen.message?.media && typeof screen.message.media === "object" ? screen.message.media : null;
  const set = (fn: (media: Doc | null) => Doc | null, key?: string) => store.updateScreen(sid, (doc) => {
    doc.message ??= {};
    const next = fn(doc.message.media ?? null);
    if (next) doc.message.media = next; else delete doc.message.media;
  }, key);
  const source = m?.file && typeof m.file === "object" ? (["fileId", "url", "field"].find((k) => k in m.file) ?? "fileId") : "fileId";
  const fields = Object.keys(loaded.project.fields ?? {});
  const at = (p: string) => diagsAt(diags, p);
  return (
    <Group icon={ImagePlus} title="Media" hint="A photo, video, voice or sticker sent with the message. Files are referenced, never uploaded." id={`${sid}-media`} collapsible defaultOpen={!!m}>
      <div className="grid gap-2 sm:grid-cols-2">
        <SelectField id={fieldDomId(sid, "/message/media/type")} label="Kind" value={m?.type ?? ""} disabled={!caps.structure} diags={at("/message/media/type")}
          options={[{ value: "", label: "No media (text only)" }, ...Object.keys(MEDIA_TYPES).map((t) => ({ value: t, label: MEDIA_LABEL[t] ?? t }))]}
          onChange={(v) => set((cur) => (v ? { ...(cur ?? { file: { fileId: "" } }), type: v } : null))} />
        {m && (
          <SelectField id={fieldDomId(sid, "/message/media/file")} label="File comes from" value={source} disabled={!caps.structure} diags={at("/message/media/file")}
            options={[{ value: "fileId", label: "Telegram file_id" }, { value: "url", label: "https:// link" }, { value: "field", label: "A field (set by the bot)" }]}
            onChange={(v) => set((cur) => ({ ...cur, file: { [v]: v === "field" ? fields[0] ?? "" : "" } }))} />
        )}
      </div>
      {m && source !== "field" && (
        <Field label={source === "url" ? "Link" : "file_id"} htmlFor={fieldDomId(sid, `/message/media/file/${source}`)} hint={source === "fileId" ? "Copy it from a message your bot received or sent." : "Telegram downloads it from this address."}>
          <Input id={fieldDomId(sid, `/message/media/file/${source}`)} value={m.file?.[source] ?? ""} disabled={!caps.structure} className="font-mono text-[13px]"
            onChange={(e) => set((cur) => ({ ...cur, file: { [source]: e.target.value } }), "media-file")} />
          <FieldDiags list={at(`/message/media/file/${source}`)} />
        </Field>
      )}
      {m && source === "field" && (
        <SelectField id={fieldDomId(sid, "/message/media/file/field")} label="Field" value={m.file?.field ?? ""} disabled={!caps.structure} diags={at("/message/media/file/field")}
          options={fields.map((f) => ({ value: f, label: f }))} onChange={(v) => set((cur) => ({ ...cur, file: { field: v } }))} />
      )}
      {m && SPOILER_MEDIA.has(m.type) && (
        <label className="flex items-center justify-between gap-3 text-sm">Hide under a spoiler<Switch checked={!!m.spoiler} disabled={!caps.structure} onCheckedChange={(v) => set((cur) => { const n = { ...cur }; if (v) n.spoiler = true; else delete n.spoiler; return n; })} aria-label="Spoiler" /></label>
      )}
      {m?.type === "sticker" && (
        <Field label="Emoji shown in the preview" htmlFor={fieldDomId(sid, "/message/media/emoji")}>
          <Input id={fieldDomId(sid, "/message/media/emoji")} value={m.emoji ?? ""} disabled={!caps.structure} className="w-24 text-lg" onChange={(e) => set((cur) => ({ ...cur, emoji: e.target.value }), "media-emoji")} />
        </Field>
      )}
      <FieldDiags list={diagsAt(diags, "/message/media")} />
    </Group>
  );
}
