import type { Snapshot } from "@/core/engine.ts";
import { edges as lintEdges } from "@/core/lint.ts";
import { localized, type Doc } from "@/core/render.ts";

export type MapEdge = ReturnType<typeof lintEdges>[number] & { label: string; dashed: boolean; dotted: boolean };

export function edgeLabel(snap: Snapshot, e: ReturnType<typeof lintEdges>[number]): string {
  const def = snap.project.defaultLocale ?? "en";
  const screen = snap.screens[e.from];
  if (e.via === "input") return `input: ${screen?.input?.field ?? "text"}`;
  const act: Doc = screen?.actions?.[e.actionId ?? ""] ?? {};
  const label = localized(act.label, def, def) ?? e.actionId ?? "";
  if (e.via === "match") return `${label} · ${act.rule?.when?.field} == ${JSON.stringify(act.rule?.when?.eq)}`;
  if (e.via === "otherwise") return `${label} · otherwise`;
  if (e.via.startsWith("outcome:")) return `${label} · ${e.via.slice(8)}`;
  if (e.via === "back-fallback") return `${label} · fallback`;
  return label;
}

export function mapEdges(snap: Snapshot): MapEdge[] {
  return lintEdges(snap).map((e) => ({ ...e, label: edgeLabel(snap, e), dashed: e.via === "back-fallback", dotted: e.via === "input" }));
}

/** Deterministic layered layout: BFS from the entry points (in project order), then from the rest (sorted). */
export function layered(snap: Snapshot, list: MapEdge[]): Record<string, { x: number; y: number }> {
  const ids = Object.keys(snap.screens).sort();
  const adj: Record<string, string[]> = {};
  for (const e of list) if (e.via !== "back-fallback" && snap.screens[e.to]) (adj[e.from] ??= []).push(e.to);
  const layer: Record<string, number> = {};
  const rows: string[][] = [];
  const place = (sid: string, l: number) => { layer[sid] = l; (rows[l] ??= []).push(sid); };
  const bfs = (roots: string[]) => {
    const queue: string[] = [];
    for (const r of roots) if (!(r in layer) && snap.screens[r]) { place(r, 0); queue.push(r); }
    while (queue.length) {
      const cur = queue.shift() as string;
      for (const nxt of adj[cur] ?? []) if (!(nxt in layer)) { place(nxt, layer[cur] + 1); queue.push(nxt); }
    }
  };
  bfs((snap.project.entryPoints ?? []).map((ep: Doc) => ep.screen));
  for (const sid of ids) if (!(sid in layer)) bfs([sid]);
  const pos: Record<string, { x: number; y: number }> = {};
  rows.forEach((col, l) => col.forEach((sid, r) => { pos[sid] = { x: l * 300, y: r * 130 }; }));
  return pos;
}

export function entryLabels(project: Doc): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const ep of project.entryPoints ?? []) {
    const label = ep.type === "command" ? `/${ep.command}` : ep.type === "event" ? `event ${ep.eventKey}` : `link ${ep.payload ?? ""}`;
    (out[ep.screen] ??= []).push(label);
  }
  return out;
}
