import { Check, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { fromSnapshot, shortRev } from "@/lib/model";
import { useStudio } from "@/lib/studio";

const LABELS: Record<string, string> = {
  map: "Screen map", simulate: "Simulator (both branches of every rule)", editText: "Edit texts and labels", editRule: "Edit targets and rules",
  exportPatch: "Export a bot-ui-patch/v1 file", save: "Save to the repository", widgets: "Widget sources, builds and previews", createScreen: "Create screens",
};

export function LoadSnapshot() {
  const { replaceLoaded, notify } = useStudio();
  const input = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState("");
  return (
    <div className="space-y-1">
      <input ref={input} type="file" accept="application/json,.json" className="sr-only" id="load-snapshot" tabIndex={-1}
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          try {
            const next = fromSnapshot(JSON.parse(await f.text()));
            replaceLoaded(next);
            setErr("");
            notify(`Loaded snapshot ${next.projectId} at ${shortRev(next.revision)}.`, "success");
          } catch (ex) {
            setErr(`Not loaded: ${(ex as Error).message}`);
          }
        }} />
      <Button size="sm" variant="outline" onClick={() => input.current?.click()}><Upload className="size-4" /> Load snapshot JSON</Button>
      {err && <p role="alert" className="text-xs text-destructive">{err}</p>}
    </div>
  );
}

export function AboutView() {
  const { loaded } = useStudio();
  const features = loaded.features;
  return (
    <div className="mx-auto w-full max-w-2xl space-y-4 p-3 sm:p-4">
      <h2 className="text-base font-semibold">What works here</h2>
      <p className="text-sm text-muted-foreground">
        This is a single offline file with a snapshot of <span className="font-mono">{loaded.projectId}</span> at revision <span className="font-mono">{shortRev(loaded.revision)}</span>.
        It makes no network requests. Changes stay in this browser until you export a patch.
      </p>
      <ul className="divide-y rounded-md border">
        {Object.entries(LABELS).map(([k, label]) => {
          const on = !!features[k];
          return (
            <li key={k} className="flex items-center gap-2 px-3 py-2 text-sm">
              {on ? <Check className="size-4 text-success" aria-hidden /> : <X className="size-4 text-muted-foreground" aria-hidden />}
              <span className={on ? "" : "text-muted-foreground"}>{label}</span>
              <span className="sr-only">{on ? "available" : "not available"}</span>
            </li>
          );
        })}
      </ul>
      <Alert>
        <AlertTitle>Applying your changes</AlertTitle>
        <AlertDescription className="space-y-2">
          <p>Export the patch on the Changes page, then run in the bot repository:</p>
          <code className="block rounded bg-muted p-2 text-xs break-all">{loaded.apply ?? "py -3 studio/bot-ui.py apply-patch --project <bot-ui folder> --patch-file <exported .json>"}</code>
          <p>After the CLI applied it, export a fresh snapshot with <code className="font-mono">bot-ui export-snapshot --format json</code> and load it here.</p>
        </AlertDescription>
      </Alert>
      <LoadSnapshot />
    </div>
  );
}
