import { useState } from "react";
import { diffOps } from "@/core/patch.ts";
import { Button } from "@/components/ui/button";
import { deepEqual, getPointer, shortRev } from "@/lib/model";
import { useStudio } from "@/lib/studio";

const show = (v: any) => (v === undefined || v === null ? "∅" : JSON.stringify(v));

/** A newer saved project than the draft's base: show both versions, offer the rebase. */
export function PendingBanner() {
  const { pendingBase, store, adoptPendingBase, loaded } = useStudio();
  const [open, setOpen] = useState(false);
  if (!pendingBase) return null;
  // Only the fields you changed (base -> draft), each with its value saved now.
  const rows = Object.entries(store.data.screens).flatMap(([sid, draft]) => {
    const base = store.data.bases[sid];
    const saved = pendingBase.screens[sid];
    if (!base) return [{ sid, path: "(whole screen)", saved: saved ? "exists now" : undefined, draft: "new screen", clash: !!saved }];
    return diffOps(base, draft).map((o) => {
      const now = saved ? getPointer(saved, o.path) : undefined;
      return { sid, path: o.path, saved: saved ? now : "screen deleted", draft: o.op === "remove" ? undefined : o.value, clash: !deepEqual(now, o.from ?? undefined) };
    });
  });
  const widgetRows = Object.entries(store.data.widgets).flatMap(([wid, files]) => Object.keys(files).map((f) => ({ wid, f })));
  return (
    <div role="status" className="border-b border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 sm:px-4 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-50">
      <div className="flex flex-wrap items-center gap-2">
        <span>
          {loaded.mode === "studio" ? "The project changed outside the Studio" : "The loaded snapshot is newer than your draft"}{" "}
          (draft on <span className="font-mono">{shortRev(store.data.baseRevision)}</span>, saved <span className="font-mono">{shortRev(pendingBase.revision)}</span>). Your draft is kept.
        </span>
        <span className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" className="h-7 bg-transparent" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Hide" : "Compare"} versions</Button>
          <Button size="sm" className="h-7" onClick={adoptPendingBase}>Reload saved and keep my draft</Button>
        </span>
      </div>
      {open && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-xs">
            <caption className="pb-1 text-left">Fields you changed; rows marked “also changed” were edited on disk too, and your value wins on reload.</caption>
            <thead><tr><th className="pr-2">Screen · field</th><th className="pr-2">Saved now</th><th>Your draft</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-amber-300/60 align-top">
                  <td className="pr-2 font-mono">{r.sid} {r.path}{r.clash && <span className="ml-1 rounded bg-amber-200 px-1 font-sans text-amber-950">also changed</span>}</td>
                  <td className="pr-2 font-mono break-all">{show(r.saved)}</td>
                  <td className="font-mono break-all">{show(r.draft)}</td>
                </tr>
              ))}
              {widgetRows.map((r) => (
                <tr key={`${r.wid}/${r.f}`} className="border-t border-amber-300/60"><td className="pr-2 font-mono">widgets/{r.wid}/{r.f}</td><td className="pr-2">file on disk</td><td>your edited file</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
