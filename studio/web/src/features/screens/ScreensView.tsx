import { ArrowLeft, Plus, Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { renderScreen, type Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { defaultLocale, exampleValues, idProblem, KINDS, locales } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { CopyId, DraftBadge, ScreenInspector } from "../inspector/ScreenInspector";
import { Field } from "../inspector/fields";
import { ScreenPreview } from "../preview/Telegram";

export function kindTone(kind: string): string {
  if (kind === "error") return "border-l-red-600";
  if (kind === "notification") return "border-l-amber-500";
  if (kind === "entry") return "border-l-sky-600";
  return "border-l-transparent";
}

export function ScreenList({ selected }: { selected: string | null }) {
  const { working, store, diags, caps } = useStudio();
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const ids = useMemo(() => {
    const s = q.trim().toLowerCase();
    return Object.keys(working.screens).sort().filter((id) => {
      if (!s) return true;
      const d = working.screens[id];
      return id.includes(s) || String(d.title ?? "").toLowerCase().includes(s) || String(d.kind ?? "").includes(s);
    });
  }, [working, q]);
  const errorsBy = useMemo(() => {
    const m: Record<string, number> = {};
    for (const d of diags) if (d.severity === "error" && d.screenId) m[d.screenId] = (m[d.screenId] ?? 0) + 1;
    return m;
  }, [diags]);
  const onKey = (e: React.KeyboardEvent) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const links = [...(listRef.current?.querySelectorAll<HTMLAnchorElement>("a[data-sid]") ?? [])];
    if (!links.length) return;
    e.preventDefault();
    const i = links.indexOf(document.activeElement as HTMLAnchorElement);
    const next = e.key === "Home" ? 0 : e.key === "End" ? links.length - 1 : e.key === "ArrowDown" ? Math.min(i + 1, links.length - 1) : Math.max(i - 1, 0);
    links[next].focus();
  };
  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-2 border-b p-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search ID, title, kind" aria-label="Search screens" className="pl-8"
            onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); listRef.current?.querySelector<HTMLAnchorElement>("a[data-sid]")?.focus(); } }} />
        </div>
        {caps.create && (
          <Button type="button" size="icon" variant="outline" aria-label="New screen" onClick={() => setCreating(true)}><Plus className="size-4" /></Button>
        )}
      </div>
      <p className="sr-only" aria-live="polite">{ids.length} screens</p>
      <ul ref={listRef} className="min-h-0 flex-1 overflow-y-auto p-1" onKeyDown={onKey} aria-label="Screens">
        {ids.map((id) => {
          const d = working.screens[id];
          const active = id === selected;
          return (
            <li key={id}>
              <a href={href("screens", id)} data-sid={id} aria-current={active ? "page" : undefined}
                className={cn("block rounded-md border-l-2 px-2 py-1.5 hover:bg-muted", kindTone(d.kind), active && "bg-muted")}>
                <span className="flex items-center gap-1.5">
                  <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{id}</span>
                  {store.isDraft(id) && <span className="size-2 rounded-full bg-amber-500" title="Draft" aria-label="draft" />}
                  {errorsBy[id] > 0 && <span className="rounded bg-destructive/10 px-1 text-[11px] text-destructive">{errorsBy[id]}</span>}
                </span>
                <span className="block truncate text-xs text-muted-foreground">{d.title} · {d.kind}</span>
              </a>
            </li>
          );
        })}
        {ids.length === 0 && <li className="p-3 text-sm text-muted-foreground">No screen matches “{q}”.</li>}
      </ul>
      <NewScreenDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}

export function NewScreenDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { store, working, loaded } = useStudio();
  const [id, setId] = useState("");
  const [kind, setKind] = useState("menu");
  const [audience, setAudience] = useState("private");
  const problem = id ? idProblem(id) ?? (working.screens[id] ? "A screen with this ID exists." : null) : null;
  const def = defaultLocale(loaded.project);
  const create = () => {
    if (!id || problem) return;
    const doc: Doc = {
      id, title: id, kind, audience,
      message: { id: "main", format: "regular.plain", text: { [def]: "" } },
      keyboard: { type: "inline", rows: [] }, actions: {},
    };
    store.createScreen(doc);
    onOpenChange(false);
    setId("");
    go("screens", id);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(e) => { e.preventDefault(); create(); }} className="space-y-4">
          <DialogHeader>
            <DialogTitle>New screen</DialogTitle>
            <DialogDescription>A draft until you save. The ID never changes later; it names screens/&lt;id&gt;.json.</DialogDescription>
          </DialogHeader>
          <Field label="Screen ID" htmlFor="new-screen-id" hint="Lowercase letters, digits, _ and -, with . between segments; up to 64 characters.">
            <Input id="new-screen-id" value={id} autoFocus onChange={(e) => setId(e.target.value.trim())} placeholder="orders.history"
              className="font-mono" aria-invalid={!!problem || undefined} aria-describedby={problem ? "new-screen-id-p" : undefined} />
            {problem && <p id="new-screen-id-p" className="text-xs text-destructive">{problem}</p>}
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Kind" htmlFor="new-screen-kind">
              <NativeSelect id="new-screen-kind" value={kind} onChange={(e) => setKind(e.target.value)} className="w-full">
                {KINDS.map((k) => <NativeSelectOption key={k} value={k}>{k}</NativeSelectOption>)}
              </NativeSelect>
            </Field>
            <Field label="Audience" htmlFor="new-screen-aud">
              <NativeSelect id="new-screen-aud" value={audience} onChange={(e) => setAudience(e.target.value)} className="w-full">
                {["private", "group", "any"].map((k) => <NativeSelectOption key={k} value={k}>{k}</NativeSelectOption>)}
              </NativeSelect>
            </Field>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!id || !!problem}>Create draft</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function PreviewPanel({ sid, idPrefix }: { sid: string; idPrefix: string }) {
  const { store, loaded } = useStudio();
  const screen = store.screen(sid);
  const ls = locales(loaded.project);
  const [locale, setLocale] = useState(ls[0]);
  const [state, setState] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  if (!screen) return null;
  const states = Object.keys(screen.message?.states ?? {});
  const st = states.includes(state) ? state : "";
  const logical = renderScreen(loaded.project, screen, { locale, state: st || null, values: exampleValues(loaded.project) });
  return (
    <section aria-label="Telegram preview" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor={`${idPrefix}-locale`}>Preview language</label>
        <NativeSelect id={`${idPrefix}-locale`} size="sm" value={locale} onChange={(e) => setLocale(e.target.value)}>
          {ls.map((l) => <NativeSelectOption key={l} value={l}>{l}</NativeSelectOption>)}
        </NativeSelect>
        {states.length > 0 && (
          <>
            <label className="sr-only" htmlFor={`${idPrefix}-state`}>Preview state</label>
            <NativeSelect id={`${idPrefix}-state`} size="sm" value={st} onChange={(e) => setState(e.target.value)}>
              <NativeSelectOption value="">default</NativeSelectOption>
              {states.map((s) => <NativeSelectOption key={s} value={s}>{s}</NativeSelectOption>)}
            </NativeSelect>
          </>
        )}
        <Button type="button" size="sm" variant="outline" className="h-8" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-pressed={theme === "dark"}>
          {theme === "light" ? "Dark" : "Light"} theme
        </Button>
      </div>
      <ScreenPreview logical={logical} theme={theme} contextLabel={`${screen.audience ?? "private"} chat · ${locale}${st ? ` · ${st}` : ""} · example values`} />
      {logical.diagnostics.length > 0 && (
        <ul className="space-y-0.5 text-[11px] text-muted-foreground">
          {logical.diagnostics.map((d, i) => <li key={i}>{d.message}</li>)}
        </ul>
      )}
    </section>
  );
}

export function ScreensView({ id }: { id: string | null }) {
  const { working } = useStudio();
  const exists = !!(id && working.screens[id]);
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  return (
    <div className="grid min-h-0 flex-1 md:grid-cols-[260px_1fr] xl:grid-cols-[260px_minmax(0,1fr)_380px]">
      <aside className={cn("min-h-0 border-r md:block md:h-[calc(100svh-3.5rem)] md:sticky md:top-14", id ? "hidden" : "h-[calc(100svh-3.5rem)]")} aria-label="Screen list">
        <ScreenList selected={id} />
      </aside>
      {id ? (
        <>
          <main className="min-w-0 p-3 sm:p-4">
            <div className="mb-3 flex items-center gap-2 md:hidden">
              <Button asChild size="sm" variant="ghost"><a href="#/screens"><ArrowLeft className="size-4" /> All screens</a></Button>
              <div role="tablist" aria-label="Screen panes" className="ml-auto inline-flex rounded-md border p-0.5 text-sm xl:hidden">
                {(["edit", "preview"] as const).map((t) => (
                  <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
                    className="rounded px-2.5 py-1 capitalize aria-selected:bg-primary aria-selected:text-primary-foreground">{t}</button>
                ))}
              </div>
            </div>
            {exists ? (
              <>
                <div className={cn(tab === "preview" && "hidden md:block")}><ScreenInspector sid={id} /></div>
                <div className={cn("mt-4 md:mt-6 xl:hidden", tab === "edit" && "hidden md:block")}><PreviewPanel sid={id} idPrefix="pv-inline" /></div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No screen <span className="font-mono">{id}</span> in this project.</p>
            )}
          </main>
          {exists && (
            <aside className="hidden min-w-0 border-l p-4 xl:block" aria-label="Preview">
              <div className="sticky top-18"><PreviewPanel sid={id} idPrefix="pv-side" /></div>
            </aside>
          )}
        </>
      ) : (
        <main className="hidden items-center justify-center p-8 text-sm text-muted-foreground md:flex">Choose a screen to edit it.</main>
      )}
    </div>
  );
}

export { CopyId, DraftBadge };
