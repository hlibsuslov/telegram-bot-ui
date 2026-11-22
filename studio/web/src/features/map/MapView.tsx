import {
  Background, Controls, Handle, MarkerType, Position, ReactFlow,
  type Edge, type EdgeChange, type Node, type NodeChange, type NodeProps,
} from "@xyflow/react";
import { ExternalLink, EyeOff, Map as MapIcon, Play } from "lucide-react";
import { memo, useMemo, useState } from "react";
import { localized, type Doc } from "@/core/render.ts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { defaultLocale } from "@/lib/model";
import { href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { NavigateTarget } from "../inspector/ActionEditor";
import { diagsAt, FieldDiags, TargetSelect, useScreenDiags } from "../inspector/fields";
import { ScreenInspector } from "../inspector/ScreenInspector";
import { entryLabels, layered, mapEdges, type MapEdge } from "./graph";

type ScreenData = { id: string; title: string; kind: string; entries: string[]; draft: boolean; errors: number };
type ScreenNodeT = Node<ScreenData, "screen">;

const ScreenNode = memo(function ScreenNode({ data }: NodeProps<ScreenNodeT>) {
  const tone =
    data.kind === "error" ? "border-red-600 bg-red-50 dark:bg-red-950/40"
      : data.kind === "notification" ? "border-amber-500 border-dashed bg-amber-50 dark:bg-amber-950/40"
        : "border-border bg-card";
  return (
    <div className={cn("bui-node w-[230px] rounded-lg border-2 px-3 py-2 shadow-sm", tone)}>
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      {data.entries.length > 0 && (
        <div className="mb-1 flex flex-wrap gap-1">
          {data.entries.map((e) => (
            <span key={e} className="inline-flex items-center gap-0.5 rounded bg-sky-100 px-1 text-[10px] font-medium text-sky-900 dark:bg-sky-900 dark:text-sky-100">
              <Play className="size-2.5" aria-hidden />{e}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-1">
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] font-semibold">{data.id}</span>
        {data.draft && <span className="size-2 shrink-0 rounded-full bg-amber-500" title="Draft" />}
      </div>
      <div className="truncate text-[11px] text-muted-foreground">{data.title}</div>
      <div className="mt-1 flex items-center gap-1">
        <span className="rounded bg-muted px-1 text-[10px]">{data.kind}</span>
        {data.errors > 0 && <span className="rounded bg-destructive/10 px-1 text-[10px] text-destructive">{data.errors} error{data.errors > 1 ? "s" : ""}</span>}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
    </div>
  );
});

const nodeTypes = { screen: ScreenNode };

export type Selection = { type: "node"; id: string } | { type: "edge"; id: string; from: string; actionId: string | null; via: string } | null;

export function TransitionInspector({ from, actionId, via }: { from: string; actionId: string | null; via: string }) {
  const { store, loaded, caps } = useStudio();
  const diags = useScreenDiags(from);
  const screen = store.screen(from);
  if (!screen) return null;
  const def = defaultLocale(loaded.project);
  const act: Doc | undefined = actionId ? screen.actions?.[actionId] : undefined;
  const update = (fn: (a: Doc) => void, key?: string) => actionId && store.updateScreen(from, (doc) => { fn(doc.actions[actionId]); }, key ? `${actionId}:${key}` : undefined);
  const row = (k: string, v: React.ReactNode) => (
    <div className="grid grid-cols-[6.5rem_1fr] gap-2 py-1 text-sm"><dt className="text-muted-foreground">{k}</dt><dd className="min-w-0 break-words">{v}</dd></div>
  );
  return (
    <div className="space-y-3">
      <h2 className="text-base font-semibold">Transition</h2>
      <dl className="divide-y rounded-md border px-3">
        {row("From", <a className="font-mono underline" href={href("screens", from)}>{from}</a>)}
        {via === "input" ? (
          row("Trigger", <>text input into <span className="font-mono">{screen.input?.field}</span></>)
        ) : (
          <>
            {row("Action", <><span className="font-mono">{actionId}</span> · {localized(act?.label, def, def)}</>)}
            {row("Type", act?.type)}
          </>
        )}
        {row("Via", <span className="font-mono">{via}</span>)}
        {act?.rule && row("When", <span className="font-mono">{act.rule.when?.field} == {JSON.stringify(act.rule.when?.eq)}</span>)}
        {act?.rule && row("Targets", <span className="font-mono">match → {act.rule.match}; otherwise → {act.rule.otherwise}</span>)}
        {act?.to && row("Target", <span className="font-mono">{act.to}</span>)}
        {act?.outcomes && row("Outcomes", <span className="font-mono">{Object.entries(act.outcomes).map(([k, v]) => `${k} → ${v}`).join("; ")}</span>)}
        {act && ["navigate", "back", "handler"].includes(act.type) && row("Presentation", act.presentation ?? "default (edit for callbacks)")}
      </dl>
      {!caps.rule && <p className="text-xs text-muted-foreground">Targets and rules are read-only here.</p>}
      {via === "input" && (
        <TargetSelect sid={from} pointer="/input/to" label="Then go to" value={screen.input?.to} disabled={!caps.rule} diags={diags}
          onChange={(to) => store.updateScreen(from, (doc) => { doc.input.to = to; })} />
      )}
      {act?.type === "navigate" && actionId && (
        <NavigateTarget sid={from} aid={actionId} action={act} update={update} disabled={!caps.rule} diags={diags} />
      )}
      {act?.type === "back" && actionId && (
        <TargetSelect sid={from} pointer={`/actions/${actionId}/fallback`} label="Fallback after a restart" value={act.fallback} allowEmpty="No fallback"
          disabled={!caps.rule} diags={diags} onChange={(to) => update((a) => { if (to) a.fallback = to; else delete a.fallback; })} />
      )}
      {act?.type === "handler" && actionId && Object.keys(act.outcomes ?? {}).map((o) => (
        <TargetSelect key={o} sid={from} pointer={`/actions/${actionId}/outcomes/${o}`} label={`On ${o}`} value={act.outcomes[o]}
          disabled={!caps.rule} diags={diags} onChange={(to) => update((a) => { a.outcomes[o] = to; })} />
      ))}
      {actionId && <FieldDiags list={diagsAt(diags, `/actions/${actionId}`)} />}
      <Button asChild size="sm" variant="outline"><a href={href("screens", from)}><ExternalLink className="size-3.5" /> Open {from}</a></Button>
    </div>
  );
}

function EdgeTable({ list, onPick, selected }: { list: MapEdge[]; onPick: (e: MapEdge) => void; selected: string | null }) {
  return (
    <div className="overflow-x-auto p-3">
      <table className="w-full min-w-[520px] text-left text-sm">
        <caption className="mb-2 text-left text-xs text-muted-foreground">Transitions ({list.length}); the map is hidden.</caption>
        <thead className="text-xs text-muted-foreground"><tr><th className="py-1 pr-2">From</th><th className="pr-2">Label</th><th className="pr-2">Via</th><th>To</th></tr></thead>
        <tbody>
          {list.map((e) => (
            <tr key={e.id} className={cn("border-t", selected === e.id && "bg-muted")}>
              <td className="py-1 pr-2 font-mono text-xs">{e.from}</td>
              <td className="pr-2"><button type="button" className="text-left underline-offset-2 hover:underline" onClick={() => onPick(e)}>{e.label}</button></td>
              <td className="pr-2 font-mono text-xs">{e.via}</td>
              <td className="font-mono text-xs">{e.to}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MapView() {
  const { working, loaded, store, diags } = useStudio();
  const [sel, setSel] = useState<Selection>(null);
  const [hidden, setHidden] = useState(false);
  const list = useMemo(() => mapEdges(working), [working]);
  const savedEdgeIds = useMemo(() => new Set(mapEdges({ project: loaded.project, screens: loaded.screens }).map((e) => `${e.id}>${e.to}`)), [loaded]);
  const pos = useMemo(() => layered(working, list), [working, list]);
  const entries = useMemo(() => entryLabels(loaded.project), [loaded.project]);
  const errorsBy = useMemo(() => {
    const m: Record<string, number> = {};
    for (const d of diags) if (d.severity === "error" && d.screenId) m[d.screenId] = (m[d.screenId] ?? 0) + 1;
    return m;
  }, [diags]);

  const nodes: ScreenNodeT[] = Object.entries(working.screens).map(([id, s]) => ({
    id, type: "screen", position: pos[id] ?? { x: 0, y: 0 },
    data: { id, title: s.title ?? "", kind: s.kind ?? "", entries: entries[id] ?? [], draft: store.isDraft(id), errors: errorsBy[id] ?? 0 },
    selected: sel?.type === "node" && sel.id === id,
    ariaLabel: `Screen ${id}, ${s.kind ?? "screen"}${entries[id] ? `, entry point ${entries[id].join(", ")}` : ""}${store.isDraft(id) ? ", draft" : ""}`,
  }));
  const edges: Edge[] = list.filter((e) => working.screens[e.to]).map((e) => {
    const draft = !savedEdgeIds.has(`${e.id}>${e.to}`);
    const stroke = draft ? "#d97706" : e.via === "otherwise" ? "#6b7280" : "#475569";
    return {
      id: e.id, source: e.from, target: e.to, label: e.label,
      selected: sel?.type === "edge" && sel.id === e.id,
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 },
      style: { stroke, strokeWidth: 1.6, strokeDasharray: e.dashed ? "6 4" : e.dotted ? "2 3" : undefined },
      labelStyle: { fontSize: 11, fill: "currentColor" },
      labelBgStyle: { fill: "var(--background)", fillOpacity: 0.92 },
      labelBgPadding: [4, 2] as [number, number],
      ariaLabel: `Transition from ${e.from} to ${e.to}: ${e.label}${draft ? ", draft" : ""}`,
      data: e,
    };
  });

  const pickEdge = (e: MapEdge) => setSel({ type: "edge", id: e.id, from: e.from, actionId: e.actionId, via: e.via });
  const onNodesChange = (changes: NodeChange[]) => {
    for (const c of changes) if (c.type === "select" && c.selected) setSel({ type: "node", id: c.id });
  };
  const onEdgesChange = (changes: EdgeChange[]) => {
    for (const c of changes) if (c.type === "select" && c.selected) { const e = list.find((x) => x.id === c.id); if (e) pickEdge(e); }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div className="relative min-w-0 flex-1 border-b lg:border-r lg:border-b-0">
        <div className="absolute top-2 left-2 z-10 flex gap-1">
          <Button type="button" size="sm" variant="outline" className="h-8 bg-background" onClick={() => setHidden(!hidden)} aria-pressed={hidden}>
            {hidden ? <><MapIcon className="size-3.5" /> Show map</> : <><EyeOff className="size-3.5" /> Hide map</>}
          </Button>
        </div>
        {hidden ? (
          <div className="h-full pt-10"><EdgeTable list={list} onPick={pickEdge} selected={sel?.type === "edge" ? sel.id : null} /></div>
        ) : (
          <div className="h-[60svh] lg:h-[calc(100svh-3.5rem)]">
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              onPaneClick={() => setSel(null)}
              nodesDraggable={false} nodesConnectable={false} nodesFocusable edgesFocusable elementsSelectable
              fitView fitViewOptions={{ padding: 0.15 }} minZoom={0.2} proOptions={{ hideAttribution: true }}
              ariaLabelConfig={{ "node.a11yDescription.default": "Press Enter or Space to inspect the screen." }}
              aria-label="Screen map"
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        )}
      </div>
      <aside className="w-full shrink-0 overflow-y-auto p-3 sm:p-4 lg:h-[calc(100svh-3.5rem)] lg:w-[440px]" aria-label="Inspector">
        {sel?.type === "node" && working.screens[sel.id] ? (
          <div className="space-y-3">
            <Button asChild size="sm" variant="outline"><a href={href("screens", sel.id)}><ExternalLink className="size-3.5" /> Open with preview</a></Button>
            <ScreenInspector sid={sel.id} compact />
          </div>
        ) : sel?.type === "edge" ? (
          <TransitionInspector from={sel.from} actionId={sel.actionId} via={sel.via} />
        ) : (
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>Select a screen or an arrow to inspect it. Tab moves through screens and arrows; Enter selects.</p>
            <ul className="space-y-1.5 text-xs">
              <li className="flex items-center gap-2"><Badge variant="outline" className="border-sky-600">entry</Badge> screens with a <Play className="inline size-3" /> chip are entry points</li>
              <li className="flex items-center gap-2"><span className="inline-block h-3 w-6 rounded border-2 border-red-600" /> error screens</li>
              <li className="flex items-center gap-2"><span className="inline-block h-3 w-6 rounded border-2 border-dashed border-amber-500" /> notifications</li>
              <li className="flex items-center gap-2"><svg width="28" height="6" aria-hidden><line x1="0" y1="3" x2="28" y2="3" stroke="currentColor" strokeDasharray="6 4" /></svg> back fallback</li>
              <li className="flex items-center gap-2"><svg width="28" height="6" aria-hidden><line x1="0" y1="3" x2="28" y2="3" stroke="currentColor" strokeDasharray="2 3" /></svg> text input</li>
              <li className="flex items-center gap-2"><svg width="28" height="6" aria-hidden><line x1="0" y1="3" x2="28" y2="3" stroke="#d97706" strokeWidth="2" /></svg> changed in your draft</li>
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
