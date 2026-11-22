import { Check, ChevronDown, Languages, MessageSquarePlus } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { locales } from "@/lib/model";
import { go } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";

/** Where a change stands: Draft -> Saved to files -> Handed to the agent, with one next action. */
export function useChangeState() {
  const { store, git, requests, handoff, workSignature, loaded } = useStudio();
  const drafts = store.count();
  const saved = git?.files.length ?? 0;
  const queued = requests.length;
  const handedOff = !!handoff && handoff.signature === workSignature && drafts === 0 && queued === 0;
  const next: { label: string; run: () => void } | null =
    drafts > 0 ? { label: loaded.mode === "studio" ? "Save to files" : "Export patch", run: () => go("changes") }
      : (saved > 0 || queued > 0) && !handedOff ? { label: "Task for the agent", run: () => go("task") }
        : null;
  return { drafts, saved, queued, handedOff, next, gitKnown: !!git };
}

function Row({ dot, title, hint, count, action }: { dot: string; title: string; hint: string; count: ReactNode; action?: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", dot)} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2 text-sm font-medium">{title}<span className="font-mono text-xs text-muted-foreground">{count}</span></span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      {action}
    </li>
  );
}

export function ChangeTray() {
  const { loaded } = useStudio();
  const { drafts, saved, queued, handedOff, next, gitKnown } = useChangeState();
  const [open, setOpen] = useState(false);
  const studio = loaded.mode === "studio";
  const summary = drafts ? `${drafts} draft${drafts === 1 ? "" : "s"}` : handedOff ? "handed to the agent" : saved ? `${saved} saved, not committed` : queued ? `${queued} request${queued === 1 ? "" : "s"}` : "no changes";
  const dot = drafts ? "bg-amber-500" : handedOff ? "bg-emerald-500" : saved || queued ? "bg-sky-500" : "bg-muted-foreground/40";
  return (
    <div className="flex items-center gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8 gap-1.5 px-2 text-xs" aria-label={`Changes: ${summary}`}>
            <span className={cn("size-2 rounded-full", dot)} aria-hidden />
            <span className="hidden sm:inline">{summary}</span>
            <ChevronDown className="size-3.5 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-[min(92vw,24rem)]">
          <p className="text-sm font-semibold">Where your changes are</p>
          <ul className="mt-1 divide-y">
            <Row dot="bg-amber-500" title="Draft" count={drafts} hint="Only in this browser. Nothing is written yet."
              action={drafts ? <Button size="sm" variant="outline" className="h-7" onClick={() => { setOpen(false); go("changes"); }}>{studio ? "Review and save" : "Export patch"}</Button> : undefined} />
            {studio && (
              <Row dot="bg-sky-500" title="Saved to files" count={gitKnown ? saved : "?"} hint="Written to bot-ui/ in your repo. Not committed, not live: the bot shows it after your usual commit and deploy." />
            )}
            <Row dot="bg-violet-500" title="Requests for the agent" count={queued} hint="Notes about screens, queued here until you hand them off." />
            <Row dot="bg-emerald-500" title="Handed to the agent" count={handedOff ? <Check className="inline size-3.5" /> : "–"} hint="You copied the task prompt; your agent commits on a branch." />
          </ul>
          {(saved > 0 || queued > 0 || drafts > 0) && (
            <Button size="sm" className="mt-2 w-full" onClick={() => { setOpen(false); go("task"); }}>Open the task for the agent</Button>
          )}
        </PopoverContent>
      </Popover>
      {next && <Button size="sm" className="hidden h-8 px-3 text-xs sm:inline-flex" onClick={next.run}>{next.label}</Button>}
    </div>
  );
}

/** Queue a note for the agent about one screen, without editing it. */
export function RequestChange({ sid, trigger, align = "start" }: { sid: string | null; trigger: ReactNode; align?: "start" | "end" }) {
  const { addRequest, requests } = useStudio();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const mine = requests.filter((r) => r.sid === sid);
  const add = () => { if (!text.trim()) return; addRequest(sid, text); setText(""); setOpen(false); };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent align={align} className="w-[min(92vw,22rem)] space-y-2" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm font-semibold">Request a change{sid && <> to <span className="font-mono text-xs">{sid}</span></>}</p>
        <p className="text-xs text-muted-foreground">A note for your agent; nothing is edited. It goes into the task prompt.</p>
        {mine.length > 0 && (
          <ul className="space-y-1 text-xs">{mine.map((r) => <li key={r.id} className="rounded-md bg-muted px-2 py-1">{r.text}</li>)}</ul>
        )}
        <Textarea autoFocus rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. shorter text, add a back button to the payment options"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); add(); } }} aria-label="Request text" />
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button size="sm" onClick={add} disabled={!text.trim()}><MessageSquarePlus className="size-4" /> Add request</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** Editing language for every text field and preview; a dot marks locales with missing text. */
export function EditLocaleSelect() {
  const { loaded, editLocale, setEditLocale, diags } = useStudio();
  const [open, setOpen] = useState(false);
  const ls = locales(loaded.project);
  if (ls.length < 2) return null;
  const missing = (l: string) => diags.filter((d) => (d.code === "LOCALE_TEXT_MISSING" || d.code === "DEFAULT_LOCALE_TEXT_MISSING") && d.pointer.endsWith(`/${l}`)).length;
  const def = loaded.project.defaultLocale;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 px-2 font-mono text-xs uppercase" aria-label={`Editing language: ${editLocale}`}>
          <Languages className="size-3.5" aria-hidden />{editLocale}
          {missing(editLocale) > 0 && <span className="size-1.5 rounded-full bg-amber-500" aria-hidden />}
          <ChevronDown className="size-3.5 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-60 p-1">
        <p className="px-2 py-1.5 text-xs text-muted-foreground">Editing language: text fields, labels and previews</p>
        <div role="listbox" aria-label="Editing language">
          {ls.map((l) => {
            const n = missing(l);
            return (
              <button key={l} type="button" role="option" aria-selected={l === editLocale} onClick={() => { setEditLocale(l); setOpen(false); }}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted aria-selected:bg-muted">
                <span className="w-7 font-mono text-xs uppercase">{l}</span>
                <span className="flex-1 text-xs text-muted-foreground">{l === def ? "default" : n ? `${n} missing` : "complete"}</span>
                {n > 0 && <span className="size-2 rounded-full bg-amber-500" aria-label={`${n} missing texts`} />}
                {l === editLocale && <Check className="size-4" />}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
