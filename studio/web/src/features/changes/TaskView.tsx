import { Check, Copy, Download, MessageSquarePlus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CodeView } from "@/components/code-view";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { copyText, download, locales, shortRev } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { EnumSelect } from "../inspector/fields";
import { buildPatch } from "./ChangesView";
import { buildPrompt, type PromptLang } from "./prompt";
import { RequestChange } from "./Tray";

const LANGS: { value: PromptLang; label: string }[] = [
  { value: "en", label: "English" }, { value: "ru", label: "Русский" }, { value: "uk", label: "Українська" },
];

function Card({ n, title, hint, children, empty }: { n: number; title: string; hint: string; children?: React.ReactNode; empty?: string }) {
  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-border">
      <div className="flex items-baseline gap-2">
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[11px]">{n}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="mt-0.5 pl-7 text-xs text-muted-foreground">{hint}</p>
      <div className="mt-3 pl-7">{children ?? <p className="text-xs text-muted-foreground">{empty}</p>}</div>
    </section>
  );
}

export function TaskView() {
  const { loaded, store, git, requests, removeRequest, markHandedOff, editLocale, refreshGit } = useStudio();
  const studio = loaded.mode === "studio";
  const [lang, setLang] = useState<PromptLang>(["en", "ru", "uk"].includes(editLocale) ? (editLocale as PromptLang) : "en");
  const [withDiff, setWithDiff] = useState(false);
  const [patchFile, setPatchFile] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const drafts = Object.keys(store.data.screens).sort();
  const draftCount = store.count();
  useEffect(() => { void refreshGit(); }, [refreshGit]);

  const projectPath = git?.projectPath || loaded.cliProject || "<bot-ui folder>";
  const prompt = useMemo(() => buildPrompt({
    lang, title: loaded.title, projectPath, locales: locales(loaded.project),
    saved: git?.files ?? [], diff: withDiff ? git?.diff : undefined,
    requests: requests.map((r) => ({ sid: r.sid, text: r.text })),
    patchFile: patchFile ?? undefined, draftScreens: patchFile ? drafts : undefined,
  }), [lang, loaded, projectPath, git, withDiff, requests, patchFile, drafts]);

  const exportPatch = async () => {
    const patch = await buildPatch(store, loaded.projectId);
    const name = `bot-ui-patch-${loaded.projectId}-${shortRev(store.data.baseRevision)}.json`;
    download(name, JSON.stringify(patch, null, 2) + "\n");
    setPatchFile(name);
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold tracking-tight">Task for the agent</h2>
          <p className="text-sm text-muted-foreground">One prompt from your saved changes and requests. Your agent commits on a branch; nothing here deploys.</p>
        </div>
        <div className="w-40"><EnumSelect label="Prompt language" value={lang} onChange={(v) => setLang(v as PromptLang)} options={LANGS} /></div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="min-w-0 space-y-4">
          {draftCount > 0 && (
            <Card n={0} title={`Unsaved drafts (${draftCount})`} hint="Only in this browser: the agent cannot see them yet.">
              <p className="mb-2 font-mono text-xs break-words">{drafts.join(", ") || "widget files"}</p>
              <div className="flex flex-wrap gap-2">
                {studio && <Button size="sm" onClick={() => go("changes")}><Save className="size-4" /> Save to files first</Button>}
                <Button size="sm" variant={studio ? "outline" : "default"} onClick={exportPatch}><Download className="size-4" /> Export as a patch</Button>
              </div>
              {patchFile && <p className="mt-2 text-xs text-muted-foreground">Exported <span className="font-mono">{patchFile}</span>: the prompt tells the agent to apply it first.</p>}
            </Card>
          )}
          <Card n={1} title={`Saved to files, not committed${git ? ` (${git.files.length})` : ""}`}
            hint={studio ? `In ${projectPath}${git?.branch ? ` on branch ${git.branch}` : ""}. Not live until your usual commit and deploy.` : "Not available in the artifact: the patch carries your changes."}
            empty={studio ? (git ? "No uncommitted changes in the bot-ui folder." : "Git status is not available (not a Git repository, or an older Studio server).") : "—"}>
            {git && git.files.length > 0 ? (
              <>
                <ul className="space-y-1 text-xs">
                  {git.files.map((f) => (
                    <li key={f.path} className="flex items-center gap-2">
                      <span className="w-6 shrink-0 rounded bg-muted text-center font-mono text-[10px]">{f.status}</span>
                      {f.screenId ? <a className="font-mono underline-offset-2 hover:underline" href={href("map", f.screenId)}>{f.screenId}</a> : f.widgetId ? <a className="font-mono underline-offset-2 hover:underline" href={href("widgets", f.widgetId)}>{f.widgetId}</a> : null}
                      <span className="truncate font-mono text-muted-foreground">{f.path}</span>
                    </li>
                  ))}
                </ul>
                <label className="mt-3 flex items-center gap-2 text-xs"><Switch checked={withDiff} onCheckedChange={setWithDiff} size="sm" /> Include the diff in the prompt</label>
              </>
            ) : undefined}
          </Card>
          <Card n={2} title={`Requests (${requests.length})`} hint="Notes about screens. Add them from a map node or here." empty="No requests queued.">
            {requests.length > 0 ? (
              <ul className="space-y-1.5">
                {requests.map((r) => (
                  <li key={r.id} className="flex items-start gap-2 rounded-lg bg-muted/50 px-2 py-1.5 text-xs">
                    <span className="min-w-0 flex-1"><span className="font-mono font-medium">{r.sid ?? "general"}</span> <span>{r.text}</span></span>
                    <button type="button" className="rounded p-0.5 text-muted-foreground hover:text-foreground" aria-label="Remove this request" onClick={() => removeRequest(r.id)}><Trash2 className="size-3.5" /></button>
                  </li>
                ))}
              </ul>
            ) : undefined}
            <div className="mt-2">
              <RequestChange sid={null} trigger={<Button size="sm" variant="outline"><MessageSquarePlus className="size-4" /> Add a general request</Button>} />
            </div>
          </Card>
        </div>

        <section className="min-w-0 space-y-3">
          <CodeView maxHeight="60svh" tabs={[{ id: "prompt", label: `Prompt (${lang})`, code: prompt, lang: "text", filename: "agent-task.md", mime: "text/markdown" }]} />
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={async () => { if (await copyText(prompt)) { setCopied(true); setTimeout(() => setCopied(false), 1500); } }}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />} Copy prompt
            </Button>
            <Button variant="outline" onClick={markHandedOff}>Mark as handed off</Button>
            <span className="text-xs text-muted-foreground">Clears the request queue; saved files stay as they are.</span>
          </div>
        </section>
      </div>
    </div>
  );
}
