import { Check, Copy, Download, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import type { Diag } from "@/core/lint.ts";
import { makePatch } from "@/core/patch.ts";
import type { Doc } from "@/core/render.ts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, errorText } from "@/lib/api";
import { copyText, download, getPointer, sha256Text, shortRev } from "@/lib/model";
import { go, href } from "@/lib/route";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useStudio } from "@/lib/studio";
import { CodeView } from "@/components/code-view";
import { DiagLine } from "../inspector/fields";

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

export function ChangesView() {
  const { store, loaded, caps, reload, replaceLoaded, saving, setSaveDiags, saveDiags, notify, focusField, diags, pendingBase, refreshGit, git } = useStudio();
  const [savedFiles, setSavedFiles] = useState<string[] | null>(null);
  const [patch, setPatch] = useState<Doc | null>(null);
  const [preview, setPreview] = useState<{ diff: string; files: string[]; error?: string } | null>(null);
  const [conflict, setConflict] = useState<Doc | null>(null);
  const [busy, setBusy] = useState(false);
  const [exported, setExported] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const count = store.count();
  const errors = diags.filter((d) => d.severity === "error");

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

  const save = async () => {
    if (!patch) return;
    setBusy(true);
    saving.current = true;
    setConflict(null);
    try {
      const sentScreens = structuredClone(store.data.screens);
      const sentWidgets = structuredClone(store.data.widgets);
      const res = await api("/api/save", { patch });
      if (res.ok) {
        setSaveDiags([]);
        const next = await reload();
        if (next) {
          store.afterSave(next, sentScreens, sentWidgets);
          replaceLoaded(next);
        }
        setSavedFiles(res.data.changedFiles ?? []);
        void refreshGit();
      } else if (res.status === 409) {
        setConflict(res.data.error);
      } else if (res.status === 422) {
        const ds: Diag[] = res.data.error?.diagnostics ?? [];
        setSaveDiags(ds);
        notify(`Not saved: ${errorText(res.data)}`, "error");
      } else {
        notify(`Not saved: ${errorText(res.data)}`, "error");
      }
    } finally {
      saving.current = false;
      setBusy(false);
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

  const exportPatch = () => {
    if (!patch) return;
    const name = `bot-ui-patch-${loaded.projectId}-${shortRev(store.data.baseRevision)}.json`;
    download(name, JSON.stringify(patch, null, 2) + "\n");
    setExported(name);
  };

  const applyCmd = (loaded.apply ?? "py -3 studio/bot-ui.py apply-patch --project <bot-ui folder> --patch-file <exported .json>").replace("<exported .json>", exported ?? "<exported .json>");

  return (
    <div className="mx-auto w-full max-w-4xl space-y-4 p-3 sm:p-4">
      <Dialog open={!!savedFiles} onOpenChange={(o) => { if (!o) setSavedFiles(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Saved to files</DialogTitle>
            <DialogDescription>Written to your repository. Not committed and not live: nothing is sent to Telegram or production.</DialogDescription>
          </DialogHeader>
          <ul className="space-y-1 rounded-lg bg-muted/50 p-3 font-mono text-xs">
            {(savedFiles ?? []).map((f) => <li key={f}>{git?.projectPath ? `${git.projectPath}/` : ""}{f}</li>)}
            {savedFiles?.length === 0 && <li className="font-sans text-muted-foreground">No byte changes: the files already held this content.</li>}
          </ul>
          <p className="text-sm text-muted-foreground">Your bot shows it after your usual commit and deploy. Next: hand it to your agent, or commit it yourself.</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSavedFiles(null)}>Done</Button>
            <Button onClick={() => { setSavedFiles(null); go("task"); }}>Task for the agent</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">Changes</h2>
        <span className="text-sm text-muted-foreground">{count} draft change{count === 1 ? "" : "s"} on revision <span className="font-mono">{shortRev(store.data.baseRevision)}</span></span>
        <div className="ml-auto flex gap-2">
          {count > 0 && <Button size="sm" variant="ghost" onClick={() => { if (confirm("Discard all draft changes? Saved files are not touched.")) store.resetAll(); }}><RotateCcw className="size-4" /> Discard all</Button>}
          {caps.save ? (
            <Button size="sm" onClick={save} disabled={busy || !count || !patch?.changes.length || !!pendingBase}><Save className="size-4" /> {busy ? "Saving…" : "Save to the project"}</Button>
          ) : (
            <Button size="sm" onClick={exportPatch} disabled={!patch?.changes.length}><Download className="size-4" /> Export patch</Button>
          )}
        </div>
      </div>

      {pendingBase && caps.save && !conflict && (
        <p className="text-xs text-muted-foreground">Saving waits until you reload the newer saved project (banner above); your draft is kept.</p>
      )}
      {conflict && <Conflict err={conflict} onRebase={rebase} />}
      {saveDiags.length > 0 && (
        <Alert variant="destructive"><AlertTitle>Not saved: the result would have errors (VALIDATION_FAILED)</AlertTitle>
          <AlertDescription><ul className="w-full space-y-0.5">{saveDiags.map((d, i) => <DiagLine key={i} d={d} showPlace onClick={d.screenId ? () => focusField(d.screenId as string, d.pointer) : undefined} />)}</ul></AlertDescription>
        </Alert>
      )}
      {errors.length > 0 && count > 0 && !saveDiags.length && (
        <p className="text-xs text-destructive">{errors.length} error{errors.length === 1 ? "" : "s"} in the project; a save with errors is refused. <a className="underline" href={href("map", errors[0].screenId)} onClick={(e) => { if (errors[0].screenId) { e.preventDefault(); focusField(errors[0].screenId, errors[0].pointer); } }}>Show the first</a></p>
      )}

      {count === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No draft changes. Edit a screen, a rule on the map or a widget file; it stays a draft until you {caps.save ? "save" : "export a patch"}.</p>
      ) : (
        <>
          <section className="space-y-2" aria-label="Drafted items">
            <ul className="divide-y rounded-md border">
              {Object.keys(store.data.screens).sort().map((sid) => (
                <li key={sid} className="flex items-center gap-2 px-3 py-2 text-sm">
                  <a className="font-mono underline-offset-2 hover:underline" href={href("map", sid)}>{sid}</a>
                  <span className="text-xs text-muted-foreground">{store.saved.screens[sid] ? "changed" : "new screen"}</span>
                  <Button size="sm" variant="ghost" className="ml-auto h-7" onClick={() => store.resetScreen(sid)}><RotateCcw className="size-3.5" /> Reset</Button>
                </li>
              ))}
              {Object.entries(store.data.widgets).map(([wid, files]) => (
                <li key={wid} className="flex items-center gap-2 px-3 py-2 text-sm">
                  <a className="font-mono underline-offset-2 hover:underline" href={href("widgets", wid)}>widgets/{wid}</a>
                  <span className="text-xs text-muted-foreground">{Object.keys(files).join(", ")}</span>
                  <Button size="sm" variant="ghost" className="ml-auto h-7" onClick={() => store.resetWidget(wid)}><RotateCcw className="size-3.5" /> Reset</Button>
                </li>
              ))}
            </ul>
          </section>

          {caps.save ? (
            <section className="space-y-2" aria-label="Diff">
              <h3 className="text-sm font-semibold">Diff (dry run on the project) {preview?.files?.length ? <span className="font-normal text-muted-foreground">· {preview.files.join(", ")}</span> : null}</h3>
              {preview?.error && preview.error !== "conflict" && <p className="text-xs text-destructive">{preview.error}</p>}
              {preview ? (
                <CodeView tabs={[
                  { id: "diff", label: "Diff", code: preview.diff || "(no byte changes)", lang: "diff" },
                  ...(patch ? [{ id: "patch", label: "Patch (bot-ui-patch/v1)", code: JSON.stringify(patch, null, 2), lang: "json" as const, filename: `bot-ui-patch-${loaded.projectId}-${shortRev(store.data.baseRevision)}.json` }] : []),
                ]} />
              ) : <p className="text-sm text-muted-foreground">Computing…</p>}
            </section>
          ) : (
            <section className="space-y-3" aria-label="Patch">
              {exported && (
                <Alert>
                  <AlertTitle>Patch exported, pending: apply with the CLI</AlertTitle>
                  <AlertDescription className="space-y-2">
                    <p><span className="font-mono">{exported}</span> is in your downloads. Nothing changes in Git until the CLI applies it with the same checks as a Studio save; a patch from an older revision conflicts.</p>
                    <div className="flex items-start gap-1">
                      <code className="min-w-0 flex-1 rounded bg-muted p-1.5 text-xs break-all">{applyCmd}</code>
                      <Button size="icon" variant="ghost" className="size-7" aria-label="Copy the apply command"
                        onClick={async () => { if (await copyText(applyCmd)) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
                        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                      </Button>
                    </div>
                    <p>Then export a fresh snapshot (<code className="font-mono">bot-ui export-snapshot --format json</code>) and load it here.</p>
                  </AlertDescription>
                </Alert>
              )}
              <h3 className="text-sm font-semibold">Patch operations (bot-ui-patch/v1)</h3>
              {patch && <Ops patch={patch} />}
              {patch && <CodeView tabs={[{ id: "patch", label: "Patch JSON", code: JSON.stringify(patch, null, 2), lang: "json", filename: `bot-ui-patch-${loaded.projectId}-${shortRev(store.data.baseRevision)}.json` }]} />}
            </section>
          )}
        </>
      )}
    </div>
  );
}
