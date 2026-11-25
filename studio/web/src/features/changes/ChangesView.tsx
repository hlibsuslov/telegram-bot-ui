import { Bot, Check, Copy, Download, FileDiff, FolderCheck, FolderGit2, GitCompareArrows, MessageSquarePlus, MessageSquareText, PencilLine, Puzzle, RotateCcw, Save, Send, Trash2, Undo2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { makePatch } from "@/core/patch.ts";
import type { Doc } from "@/core/render.ts";
import { CodeView } from "@/components/code-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { api, errorText } from "@/lib/api";
import { copyText, download, getPointer, locales, sha256Text, shortRev } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { DiagLine, EnumSelect } from "../inspector/fields";
import { buildPrompt, type PromptLang } from "./prompt";
import { useEmoji } from "@/features/emoji/context";
import { RequestChange } from "./Tray";

const show = (v: any) => (v === undefined ? "∅" : JSON.stringify(v));

export async function buildPatch(store: ReturnType<typeof useStudio>["store"], projectId: string): Promise<Doc> {
  const patch = makePatch(projectId, store.data.baseRevision, store.saved.screens, store.data.screens);
  for (const [wid, files] of Object.entries(store.data.widgets)) {
    for (const [file, content] of Object.entries(files)) {
      const base = store.data.widgetBases[wid]?.[file];
      const change: Doc = { widgetId: wid, file, content };
      if (typeof base === "string") change.fromHash = await sha256Text(base);
      patch.changes.push(change);
    }
  }
  return patch;
}

function Ops({ patch }: { patch: Doc }) {
  return (
    <ul className="space-y-2">
      {patch.changes.map((c: Doc, i: number) => (
        <li key={i} className="rounded-lg bg-muted/40 p-2.5 text-xs">
          <div className="font-mono font-semibold">{c.screenId ?? `widgets/${c.widgetId}/${c.file}`}{c.create ? " (new screen)" : ""}</div>
          {c.ops?.map((o: Doc, j: number) => (
            <div key={j} className="mt-1 grid gap-1 sm:grid-cols-[minmax(0,14rem)_1fr]">
              <span className="font-mono break-all text-muted-foreground">{o.op} {o.path}</span>
              <span className="font-mono break-all"><span className="text-red-800 line-through dark:text-red-300">{show(o.from)}</span> → <span className="text-emerald-800 dark:text-emerald-300">{o.op === "remove" ? "removed" : show(o.value)}</span></span>
            </div>
          ))}
          {c.content !== undefined && <div className="mt-1 text-muted-foreground">{c.content.length} characters{c.fromHash ? `, from ${shortRev(c.fromHash)}` : ", new file"}</div>}
        </li>
      ))}
    </ul>
  );
}

function Conflict({ err, onRebase }: { err: Doc; onRebase: () => void }) {
  const { store } = useStudio();
  return (
    <Alert variant="destructive" className="space-y-2">
      <AlertTitle>The project changed since your draft (REVISION_CONFLICT)</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>Nothing was written. Saved is now <span className="font-mono">{shortRev(err.currentRevision)}</span>; your draft was made on <span className="font-mono">{shortRev(err.expectedRevision)}</span>. Your draft is kept.</p>
        {(err.fieldConflicts ?? []).length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-xs text-foreground">
              <caption className="pb-1 text-left">Fields changed on both sides</caption>
              <thead><tr className="text-muted-foreground"><th className="pr-2">Where</th><th className="pr-2">When you started</th><th className="pr-2">Saved now</th><th>Your draft</th></tr></thead>
              <tbody>
                {err.fieldConflicts.map((c: Doc, i: number) => (
                  <tr key={i} className="border-t align-top">
                    <td className="pr-2 font-mono">{c.screenId ?? c.widgetId} {c.path}</td>
                    <td className="pr-2 font-mono break-all">{show(c.expected)}</td>
                    <td className="pr-2 font-mono break-all">{show(c.current)}</td>
                    <td className="font-mono break-all">{c.screenId ? show(getPointer(store.data.screens[c.screenId], c.path)) : "(your file)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No field you changed was changed on disk: your draft can be replayed on top of the new revision.</p>
        )}
        <Button size="sm" variant="outline" className="text-foreground" onClick={onRebase}>Reload saved and keep my draft</Button>
      </AlertDescription>
    </Alert>
  );
}

type Item = { kind: "screen" | "widget"; id: string; label: string; files: string[]; isNew: boolean };

/** Split a unified diff of several files into one block per file path. */
function splitDiff(diff: string): Record<string, string> {
  const out: Record<string, string> = {};
  let cur = "";
  for (const line of diff.split("\n")) {
    if (line.startsWith("--- ")) cur = "";
    const m = /^\+\+\+ b\/(.+)$/.exec(line);
    if (m) cur = m[1];
    const key = cur || "__pending";
    out[key] = (out[key] ?? "") + line + "\n";
    if (m && out.__pending) { out[cur] = out.__pending + out[cur]; delete out.__pending; }
  }
  delete out.__pending;
  return out;
}

function PartHeader({ n, icon: Icon, title, hint, count, id }: { n: number; icon: typeof Save; title: string; hint: string; count?: number; id: string }) {
  return (
    <div className="flex items-start gap-3" id={id}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted"><Icon className="size-4" aria-hidden /></span>
      <div className="min-w-0 flex-1">
        <h3 className="flex items-baseline gap-2 text-[15px] font-semibold tracking-tight"><span className="font-mono text-xs text-muted-foreground">{n}</span>{title}{count !== undefined && <span className="rounded-full bg-muted px-2 text-xs font-medium text-muted-foreground">{count}</span>}</h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
    </div>
  );
}

const LANGS: { value: PromptLang; label: string }[] = [
  { value: "en", label: "English" }, { value: "ru", label: "Русский" }, { value: "uk", label: "Українська" },
];

export function ChangesView({ anchor }: { anchor?: string | null }) {
  const { store, loaded, caps, reload, replaceLoaded, saving, setSaveDiags, saveDiags, notify, focusField, diags, pendingBase, refreshGit, git,
    requests, removeRequest, markHandedOff, editLocale, pro, requestsToProject, setRequestsToProject } = useStudio();
  const studio = loaded.mode === "studio";
  const [savedFiles, setSavedFiles] = useState<string[] | null>(null);
  const [patch, setPatch] = useState<Doc | null>(null);
  const [preview, setPreview] = useState<{ diff: string; files: string[]; error?: string } | null>(null);
  const [conflict, setConflict] = useState<Doc | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [openDiff, setOpenDiff] = useState<Set<string>>(new Set());
  const [exported, setExported] = useState<string | null>(null);
  const [lang, setLang] = useState<PromptLang>(["en", "ru", "uk"].includes(editLocale) ? (editLocale as PromptLang) : "en");
  const [withDiff, setWithDiff] = useState(false);
  const [copied, setCopied] = useState(false);
  const errors = diags.filter((d) => d.severity === "error");

  const items: Item[] = [
    ...Object.keys(store.data.screens).sort().map((sid) => ({
      kind: "screen" as const, id: sid, label: store.data.screens[sid].title ?? "", files: [loaded.screenFiles[sid] ?? `screens/${sid}.json`], isNew: !store.saved.screens[sid],
    })),
    ...Object.keys(store.data.widgets).sort().map((wid) => ({
      kind: "widget" as const, id: wid, label: loaded.widgets[wid]?.meta.title ?? "", files: Object.keys(store.data.widgets[wid]).map((f) => `widgets/${wid}/${f}`), isNew: false,
    })),
  ];

  useEffect(() => {
    let live = true;
    (async () => {
      const p = await buildPatch(store, loaded.projectId);
      if (!live) return;
      setPatch(p);
      if (!caps.save || !p.changes.length) return setPreview(null);
      const res = await api("/api/preview-patch", { patch: p });
      if (!live) return;
      if (res.ok) setPreview({ diff: res.data.diff, files: res.data.changedFiles });
      else if (res.status === 409) { setPreview({ diff: "", files: [], error: "conflict" }); setConflict(res.data.error); }
      else setPreview({ diff: res.data?.error?.diff ?? "", files: [], error: errorText(res.data) });
    })();
    return () => { live = false; };
  }, [store, store.version, loaded.projectId, loaded.revision, caps.save]);

  useEffect(() => { void refreshGit(); }, [refreshGit]);
  useEffect(() => {
    if (!anchor) return;
    const t = setTimeout(() => {
      const el = document.getElementById(`chg-${anchor}`);
      if (!el) return;
      el.scrollIntoView({ block: "start", behavior: "smooth" });
      el.classList.add("ring-2", "ring-amber-400");
      setTimeout(() => el.classList.remove("ring-2", "ring-amber-400"), 1600);
    }, 150);
    return () => clearTimeout(t);
  }, [anchor]);

  /** Save everything, or only one screen / widget. */
  const save = async (only?: Item) => {
    if (!patch) return;
    const p = only ? { ...patch, changes: patch.changes.filter((c: Doc) => (only.kind === "screen" ? c.screenId === only.id : c.widgetId === only.id)) } : patch;
    setBusy(only ? `${only.kind}:${only.id}` : "all");
    saving.current = true;
    setConflict(null);
    try {
      const sentScreens = only ? (only.kind === "screen" ? { [only.id]: structuredClone(store.data.screens[only.id]) } : {}) : structuredClone(store.data.screens);
      const sentWidgets = only ? (only.kind === "widget" ? { [only.id]: structuredClone(store.data.widgets[only.id]) } : {}) : structuredClone(store.data.widgets);
      const res = await api("/api/save", { patch: p });
      if (res.ok) {
        setSaveDiags([]);
        const next = await reload();
        if (next) { store.afterSave(next, sentScreens, sentWidgets); replaceLoaded(next); }
        setSavedFiles(res.data.changedFiles ?? []);
        void refreshGit();
      } else if (res.status === 409) setConflict(res.data.error);
      else {
        if (res.status === 422) setSaveDiags(res.data.error?.diagnostics ?? []);
        notify(`Not saved: ${errorText(res.data)}`, "error");
      }
    } finally {
      saving.current = false;
      setBusy(null);
    }
  };

  const rebase = async () => {
    const next = await reload();
    if (!next) return;
    store.rebase(next);
    replaceLoaded(next);
    setConflict(null);
    notify("Reloaded the saved project; your draft now sits on the new revision.", "success");
  };

  const patchName = `bot-ui-patch-${loaded.projectId}-${shortRev(store.data.baseRevision)}.json`;
  const exportPatch = () => {
    if (!patch) return;
    download(patchName, JSON.stringify(patch, null, 2) + "\n");
    setExported(patchName);
  };
  const applyCmd = (loaded.apply ?? "py -3 studio/bot-ui.py apply-patch --project <bot-ui folder> --patch-file <exported .json>").replace("<exported .json>", exported ?? "<exported .json>");

  const fileDiffs = preview ? splitDiff(preview.diff) : {};
  const projectPath = git?.projectPath || loaded.cliProject || "<bot-ui folder>";
  const { doc: emojiDoc, index: emojiIndex } = useEmoji();
  const emoji = useMemo(() => ({
    route: (loaded.project.capabilities ?? {}).customEmoji ?? "none",
    packs: Object.values(emojiDoc.library.packs ?? {}).map((p) => p.link.replace(/^https?:\/\//, "")),
    icons: Object.entries(emojiDoc.library.icons ?? {}).map(([slot, ic]) => ({ slot, id: ic.id, fallback: ic.fallback })),
    unknown: emojiDoc.usage.filter((u) => !emojiIndex.has(u.id)).length,
  }), [emojiDoc, emojiIndex, loaded.project]);
  const prompt = useMemo(() => buildPrompt({
    lang, title: loaded.title, projectPath, locales: locales(loaded.project),
    saved: git?.files ?? [], diff: withDiff ? git?.diff : undefined,
    requests: requests.map((r) => ({ sid: r.sid, text: r.text })),
    patchFile: exported ?? undefined, draftScreens: exported ? Object.keys(store.data.screens) : undefined, emoji,
  }), [lang, loaded, projectPath, git, withDiff, requests, exported, store.version, emoji]);
  const link = (kind: "screen" | "widget", id: string) => (kind === "screen" ? href("map", id) : href("widgets", id));

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-3 sm:p-5">
      <Dialog open={!!savedFiles} onOpenChange={(o) => { if (!o) setSavedFiles(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><FolderCheck className="size-5" /> Saved to files</DialogTitle>
            <DialogDescription>Written to your repository. Not committed and not live: nothing is sent to Telegram or production.</DialogDescription>
          </DialogHeader>
          <ul className="space-y-1 rounded-lg bg-muted/50 p-3 font-mono text-xs">
            {(savedFiles ?? []).map((f) => <li key={f}>{git?.projectPath ? `${git.projectPath}/` : ""}{f}</li>)}
            {savedFiles?.length === 0 && <li className="font-sans text-muted-foreground">No byte changes: the files already held this content.</li>}
          </ul>
          <p className="text-sm text-muted-foreground">Your bot shows it after your usual commit and deploy. Next: hand it to your agent, or commit it yourself.</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSavedFiles(null)}>Done</Button>
            <Button onClick={() => { setSavedFiles(null); go("changes", "prompt"); }}><Bot className="size-4" /> Prompt for the agent</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight"><GitCompareArrows className="size-5" /> Changes</h2>
        <p className="text-sm text-muted-foreground">Your edits go from this browser, to your files, to your agent. Nothing here sends anything to Telegram.</p>
      </div>

      {pendingBase && caps.save && !conflict && <p className="text-xs text-muted-foreground">Saving waits until you reload the newer saved project (banner above); your drafts are kept.</p>}
      {conflict && <Conflict err={conflict} onRebase={rebase} />}
      {saveDiags.length > 0 && (
        <Alert variant="destructive"><AlertTitle>Not saved: the result would have errors</AlertTitle>
          <AlertDescription><ul className="w-full space-y-0.5">{saveDiags.map((d, i) => <DiagLine key={i} d={d} showPlace onClick={d.screenId ? () => focusField(d.screenId as string, d.pointer) : undefined} />)}</ul></AlertDescription>
        </Alert>
      )}

      <section className="space-y-3" aria-labelledby="chg-drafts-h">
        <PartHeader n={1} icon={PencilLine} id="chg-drafts" title="Not saved yet" count={items.length} hint="Only in this browser. Save writes them to your bot-ui files; nothing is committed or sent." />
        {items.length === 0 ? (
          <p className="rounded-xl bg-muted/40 px-4 py-3 text-sm text-muted-foreground">No drafts. Edit a screen on the map or a widget; it shows up here.</p>
        ) : (
          <ul className="divide-y rounded-xl ring-1 ring-border">
            {items.map((it) => {
              const key = `${it.kind}-${it.id}`;
              const Icon = it.kind === "screen" ? MessageSquareText : Puzzle;
              const open = openDiff.has(key);
              const diffText = it.files.map((f) => fileDiffs[f] ?? "").join("");
              return (
                <li key={key} id={`chg-${key}`} className="scroll-mt-20 rounded-xl px-4 py-3 transition-shadow">
                  <div className="flex flex-wrap items-center gap-2">
                    <Icon className="size-4 text-muted-foreground" aria-hidden />
                    <a className="font-mono text-sm font-medium underline-offset-2 hover:underline" href={link(it.kind, it.id)}>{it.id}</a>
                    {it.label && <span className="truncate text-xs text-muted-foreground">{it.label}</span>}
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-900">{it.isNew ? "new" : "changed"}</span>
                    <span className="ml-auto flex items-center gap-1">
                      <Button size="sm" variant="ghost" className="h-7" aria-expanded={open} onClick={() => setOpenDiff((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; })}>
                        <FileDiff className="size-3.5" /> {open ? "Hide" : "What changed"}
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7" onClick={() => (it.kind === "screen" ? store.resetScreen(it.id) : store.resetWidget(it.id))}><Undo2 className="size-3.5" /> Discard</Button>
                      {caps.save && <Button size="sm" variant="outline" className="h-7" disabled={!!busy || !!pendingBase} onClick={() => save(it)}><Save className="size-3.5" /> Save</Button>}
                    </span>
                  </div>
                  {open && (
                    <div className="mt-2">
                      {caps.save
                        ? <CodeView tabs={[{ id: "d", label: it.files.join(", "), code: diffText || "(no byte changes)", lang: "diff" }]} maxHeight="22rem" />
                        : patch && <Ops patch={{ changes: patch.changes.filter((c: Doc) => (it.kind === "screen" ? c.screenId === it.id : c.widgetId === it.id)) }} />}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {items.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {caps.save
              ? <Button onClick={() => save()} disabled={!!busy || !patch?.changes.length || !!pendingBase}><Save className="size-4" /> {busy === "all" ? "Saving…" : "Save all to files"}</Button>
              : <Button onClick={exportPatch} disabled={!patch?.changes.length}><Download className="size-4" /> Export patch</Button>}
            <Button variant="ghost" onClick={() => { if (confirm("Discard all drafts? Saved files are not touched.")) store.resetAll(); }}><RotateCcw className="size-4" /> Discard all</Button>
            {errors.length > 0 && <span className="text-xs text-destructive">{errors.length} error{errors.length === 1 ? "" : "s"} in the project: a save with errors is refused. <button type="button" className="underline" onClick={() => errors[0].screenId && focusField(errors[0].screenId, errors[0].pointer)}>Show the first</button></span>}
          </div>
        )}
        {!caps.save && exported && (
          <Alert>
            <AlertTitle>Patch exported, pending: apply with the CLI</AlertTitle>
            <AlertDescription className="space-y-1">
              <p><span className="font-mono">{exported}</span> is in your downloads. Nothing changes in Git until the CLI applies it.</p>
              <code className="block rounded bg-muted p-1.5 text-xs break-all">{applyCmd}</code>
            </AlertDescription>
          </Alert>
        )}
        {pro && caps.save && preview?.diff && items.length > 1 && (
          <details className="rounded-xl bg-muted/30 p-3"><summary className="cursor-pointer text-xs font-medium">Whole diff and patch (Pro)</summary>
            <div className="mt-2"><CodeView tabs={[{ id: "diff", label: "Diff", code: preview.diff, lang: "diff" }, ...(patch ? [{ id: "patch", label: "Patch", code: JSON.stringify(patch, null, 2), lang: "json" as const, filename: patchName }] : [])]} /></div>
          </details>
        )}
      </section>

      {studio && (
        <section className="space-y-3" aria-labelledby="chg-saved-h">
          <PartHeader n={2} icon={FolderGit2} id="chg-saved" title="Saved to your files, not committed" count={git?.files.length}
            hint={git ? `In ${projectPath}${git.branch ? ` on branch ${git.branch}` : ""}. The bot shows them after your usual commit and deploy.` : "Git status is not available (not a Git repository)."} />
          {git && git.files.length > 0 ? (
            <ul className="divide-y rounded-xl ring-1 ring-border">
              {git.files.map((f) => {
                const kind = f.screenId ? "screen" : f.widgetId ? "widget" : null;
                const id = f.screenId ?? f.widgetId;
                return (
                  <li key={f.path} id={kind && id ? `chg-saved-${kind}-${id}` : undefined} className="flex items-center gap-2 px-4 py-2.5 text-sm">
                    <span className="w-7 shrink-0 rounded bg-muted text-center font-mono text-[10px]" title={f.status === "M" ? "modified" : f.status === "D" ? "deleted" : "new"}>{f.status}</span>
                    {kind && id ? <a className="font-mono underline-offset-2 hover:underline" href={link(kind, id)}>{id}</a> : null}
                    <span className="min-w-0 truncate font-mono text-xs text-muted-foreground">{f.path}</span>
                  </li>
                );
              })}
            </ul>
          ) : git ? <p className="rounded-xl bg-muted/40 px-4 py-3 text-sm text-muted-foreground">Nothing uncommitted in the bot-ui folder.</p> : null}
        </section>
      )}

      <section className="space-y-3" aria-labelledby="chg-requests-h">
        <PartHeader n={studio ? 3 : 2} icon={MessageSquarePlus} id="chg-requests" title="Requests for the agent" count={requests.length} hint="Notes about screens, without editing them. Add one from a map node or here." />
        {requests.length > 0 && (
          <ul className="divide-y rounded-xl ring-1 ring-border">
            {requests.map((r) => (
              <li key={r.id} id={r.sid ? `chg-request-${r.sid}` : undefined} className="flex items-start gap-2 px-4 py-2.5 text-sm">
                {r.sid ? <a className="shrink-0 font-mono underline-offset-2 hover:underline" href={href("map", r.sid)}>{r.sid}</a> : <span className="shrink-0 text-muted-foreground">general</span>}
                <span className="min-w-0 flex-1">{r.text}</span>
                <button type="button" className="rounded p-1 text-muted-foreground hover:text-foreground" aria-label="Remove this request" onClick={() => removeRequest(r.id)}><Trash2 className="size-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <RequestChange sid={null} trigger={<Button size="sm" variant="outline"><MessageSquarePlus className="size-4" /> Add a general request</Button>} />
          {studio && caps.save && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <Switch size="sm" checked={requestsToProject} onCheckedChange={setRequestsToProject} />
              Also save new requests in the project (bot-ui/context/requests, goes into git)
            </label>
          )}
        </div>
      </section>

      <section className="scroll-mt-20 space-y-3 rounded-2xl transition-shadow" id="chg-prompt" aria-labelledby="chg-prompt-h">
        <PartHeader n={studio ? 4 : 3} icon={Bot} id="chg-prompt-head" title="Prompt for your agent" hint="One message with everything above. Paste it to your coding agent; it commits on a branch and does not deploy." />
        {items.length > 0 && (
          <p className="rounded-xl bg-amber-50 px-4 py-2.5 text-xs text-amber-950 dark:bg-amber-950 dark:text-amber-100">
            {items.length} draft{items.length === 1 ? " is" : "s are"} not saved, so the agent cannot see {items.length === 1 ? "it" : "them"}.{" "}
            {caps.save ? <button type="button" className="font-medium underline" onClick={() => save()}>Save all</button> : null}
            {caps.save ? " or " : ""}<button type="button" className="font-medium underline" onClick={exportPatch}>export a patch</button>{exported ? ` (exported ${exported}; the prompt says to apply it)` : ""}.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-40"><EnumSelect label="Prompt language" value={lang} onChange={(v) => setLang(v as PromptLang)} options={LANGS} /></div>
          {git && git.files.length > 0 && <label className="flex items-center gap-2 text-xs"><Switch size="sm" checked={withDiff} onCheckedChange={setWithDiff} /> Include the diff</label>}
        </div>
        <CodeView maxHeight="50svh" tabs={[{ id: "prompt", label: `Prompt (${lang})`, code: prompt, lang: "text", filename: "agent-task.md", mime: "text/markdown" }]} />
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={async () => { if (await copyText(prompt)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }}>
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />} Copy prompt
          </Button>
          <Button variant="outline" onClick={markHandedOff}><Send className="size-4" /> Mark as handed off</Button>
          <span className="text-xs text-muted-foreground">Clears the requests; saved files stay as they are.</span>
        </div>
      </section>
    </div>
  );
}
