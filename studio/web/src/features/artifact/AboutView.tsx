import { Check, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DEMO_SITE, fromSnapshot, shortRev } from "@/lib/model";
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

const DEMO_TRY = [
  ["Map", "every screen of the bot as the message people see, with arrows from each button to where it leads."],
  ["Simulator", "press START and use the bot. The trace on the right shows what the engine did with each update."],
  ["Screens", "open a screen, change a text or a button label, and see the preview and the map update."],
  ["Changes", "your edits as one list, plus a ready task for your coding agent."],
];

function DemoAbout() {
  const { loaded } = useStudio();
  return (
    <div className="mx-auto w-full max-w-2xl space-y-4 p-3 sm:p-4">
      <h2 className="text-base font-semibold">About this demo</h2>
      <p className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{loaded.title}</span> is a sample coffee bot built for this demo. Everything runs in this
        browser tab: no account, no bot token, no requests to Telegram or anywhere else. Your edits stay in this browser.
      </p>
      <ul className="divide-y rounded-md border">
        {DEMO_TRY.map(([title, text]) => (
          <li key={title} className="px-3 py-2 text-sm"><span className="font-medium">{title}</span>: <span className="text-muted-foreground">{text}</span></li>
        ))}
      </ul>
      <Alert>
        <AlertTitle>On your own bot</AlertTitle>
        <AlertDescription className="space-y-2">
          <p>The Studio runs on your machine next to the bot's repository. Saving writes the screen files, and <code className="font-mono">git diff</code> shows the change.
            Widgets get a live preview and a size check there too.</p>
          <a href={DEMO_SITE} target="_top" className="inline-flex items-center gap-1 font-medium underline underline-offset-4">How to run it on your bot</a>
        </AlertDescription>
      </Alert>
    </div>
  );
}

export function AboutView() {
  const { loaded } = useStudio();
  const features = loaded.features;
  if (features.demo) return <DemoAbout />;
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
