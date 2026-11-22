import { ArrowLeft, Map as MapIcon, Plus, Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { defaultLocale, idProblem, KINDS } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { EnumSelect, Field, firstLine } from "../inspector/fields";
import { ScreenEditor } from "../inspector/ScreenInspector";

export function kindDot(kind: string): string {
  if (kind === "error") return "bg-red-500";
  if (kind === "notification") return "bg-amber-500";
  if (kind === "entry") return "bg-sky-500";
  return "bg-slate-300 dark:bg-slate-600";
}

export function ScreenList({ selected }: { selected: string | null }) {
  const { working, store, diags, caps, editLocale, loaded } = useStudio();
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const def = defaultLocale(loaded.project);
  const ids = useMemo(() => {
    const s = q.trim().toLowerCase();
    return Object.keys(working.screens).sort().filter((id) => {
      if (!s) return true;
      const d = working.screens[id];
      const text = typeof d.message?.text === "object" ? Object.values(d.message.text).join(" ") : String(d.message?.text ?? "");
      return `${id} ${d.title ?? ""} ${d.kind ?? ""} ${text}`.toLowerCase().includes(s);
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
      <div className="flex gap-2 p-3">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search ID, title, text" aria-label="Search screens" className="pl-8"
            onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); listRef.current?.querySelector<HTMLAnchorElement>("a[data-sid]")?.focus(); } }} />
        </div>
        {caps.create && <Button type="button" size="icon" variant="outline" aria-label="New screen" onClick={() => setCreating(true)}><Plus className="size-4" /></Button>}
      </div>
      <p className="sr-only" aria-live="polite">{ids.length} screens</p>
      <ul ref={listRef} className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3" onKeyDown={onKey} aria-label="Screens">
        {ids.map((id) => {
          const d = working.screens[id];
          const active = id === selected;
          return (
            <li key={id}>
              <a href={href("screens", id)} data-sid={id} aria-current={active ? "page" : undefined}
                className={cn("block rounded-lg px-2.5 py-2 hover:bg-muted", active && "bg-muted")}>
                <span className="flex items-center gap-2">
                  <span className={cn("size-2 shrink-0 rounded-full", kindDot(d.kind))} title={d.kind} aria-hidden />
                  <span className="min-w-0 flex-1 truncate font-mono text-[12.5px]">{id}</span>
                  {store.isDraft(id) && <span className="rounded-full bg-amber-100 px-1.5 text-[10px] font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-100">draft</span>}
                  {errorsBy[id] > 0 && <span className="rounded-full bg-destructive/10 px-1.5 text-[10px] text-destructive">{errorsBy[id]}</span>}
                </span>
                <span className="block truncate pl-4 text-xs text-muted-foreground">{d.title} — {firstLine(d, editLocale, def)}</span>
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
    go("map", id);
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
              <EnumSelect id="new-screen-kind" value={kind} onChange={setKind} options={KINDS.map((k) => ({ value: k, label: k }))} />
            </Field>
            <Field label="Audience" htmlFor="new-screen-aud">
              <EnumSelect id="new-screen-aud" value={audience} onChange={setAudience} options={["private", "group", "any"].map((k) => ({ value: k, label: k }))} />
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

/** Secondary view: a plain list of screens with the same editor as the map panel. */
export function ScreensView({ id }: { id: string | null }) {
  const { working } = useStudio();
  const exists = !!(id && working.screens[id]);
  return (
    <div className="grid min-h-0 flex-1 md:grid-cols-[300px_minmax(0,1fr)]">
      <aside className={cn("min-h-0 border-r md:sticky md:top-14 md:block md:h-[calc(100svh-3.5rem)]", id ? "hidden" : "h-[calc(100svh-3.5rem)]")} aria-label="Screen list">
        <ScreenList selected={id} />
      </aside>
      {id ? (
        <main className="flex h-[calc(100svh-3.5rem)] min-w-0 flex-col">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Button asChild size="sm" variant="ghost" className="md:hidden"><a href="#/screens"><ArrowLeft className="size-4" /> All screens</a></Button>
            <Button asChild size="sm" variant="outline" className="ml-auto"><a href={href("map", id)}><MapIcon className="size-4" /> Show on the map</a></Button>
          </div>
          {exists ? <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col"><ScreenEditor key={id} sid={id} /></div>
            : <p className="p-4 text-sm text-muted-foreground">No screen <span className="font-mono">{id}</span> in this project.</p>}
        </main>
      ) : (
        <main className="hidden items-center justify-center p-8 text-sm text-muted-foreground md:flex">Choose a screen, or open it from the map.</main>
      )}
    </div>
  );
}
