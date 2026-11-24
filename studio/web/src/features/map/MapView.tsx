import {
  Background, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge, type EdgeChange, type EdgeProps, type Node, type NodeChange, type NodeProps,
} from "@xyflow/react";
import { Copy, Maximize2, MessageSquarePlus, Minus, Play, Plus, Search, Zap } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { renderScreen, type Logical } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";
import { defaultLocale, exampleValues, fieldDomId, scrollWithin } from "@/lib/model";
import { go } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { RequestChange } from "../changes/Tray";
import { firstLine } from "../inspector/fields";
import { ChangeBadges, hlFor, ScreenEditor } from "../inspector/ScreenInspector";
import { Bubble, ForceReplyBar, ReplyKeyboard, type Hl } from "../preview/Telegram";
import { computeLayout, entryLabel, entryNodeId, layoutKey, mapEdges, midpoint, roundedPath, smoothPath, type Layout, type Pt } from "./graph";

type ScreenData = {
  sid: string; logical: Logical; kind: string; draft: boolean; errors: number; hl?: Hl; flash: boolean;
  unplaced: { aid: string; label: string }[]; input: string | null;
  onAction: (sid: string, aid: string) => void; onCopy: (sid: string) => void; requests: number;
};
type ScreenNodeT = Node<ScreenData, "screen">;
type EntryNodeT = Node<{ label: string; kind: string }, "entry">;

const port = (id: string) => <Handle type="source" position={Position.Right} id={id} className="bui-port" style={{ right: -14 }} />;

const ScreenNode = memo(function ScreenNode({ data }: NodeProps<ScreenNodeT>) {
  const { sid, logical, kind, errors, hl, unplaced, input, flash } = data;
  const kt = logical.keyboard.type;
  const tone = kind === "error" ? "bg-red-500" : kind === "notification" ? "bg-amber-500" : kind === "entry" ? "bg-sky-500" : "bg-slate-400";
  return (
    <div className={cn("bui-node w-[300px] rounded-2xl bg-card p-2 shadow-[0_1px_3px_rgba(0,0,0,.08),0_8px_24px_-12px_rgba(0,0,0,.18)] transition-shadow", flash && "ring-4 ring-amber-300")}>
      <Handle type="target" position={Position.Left} id="in" className="bui-port" style={{ top: 46, left: -6 }} />
      <div className="flex items-center gap-1.5 px-1 pb-1.5">
        <span className={cn("size-2 shrink-0 rounded-full", tone)} aria-hidden />
        <span className="text-[10.5px] text-muted-foreground">{kind}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-[11.5px] font-semibold" title={sid}>{sid}</span>
        <ChangeBadges kind="screen" id={sid} compact />
        {errors > 0 && <span className="rounded-full bg-red-100 px-1.5 text-[10px] font-medium text-red-800">{errors}</span>}
        <button type="button" className="nodrag rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Copy ID ${sid}`} title="Copy ID"
          onClick={(e) => { e.stopPropagation(); data.onCopy(sid); }}><Copy className="size-3.5" /></button>
<RequestChange sid={sid} trigger={
          <button type="button" className="nodrag relative rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Request a change to ${sid}`} title="Request a change (note for your agent)"
            onClick={(e) => e.stopPropagation()}>
            <MessageSquarePlus className="size-3.5" />
            {data.requests > 0 && <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-violet-600 text-[9px] font-semibold text-white">{data.requests}</span>}
          </button>} />
      </div>
      <div className="tg tg-wallpaper overflow-hidden rounded-xl" data-theme="light">
        <div className="relative py-2.5 pr-3 pl-3.5">
          {input && kt !== "force_reply" && port("input")}
          <Bubble logical={logical} widget={logical.widget} hl={hl} clampText tail
            onPress={(aid) => data.onAction(sid, aid)} buttonSlot={kt === "inline" ? (aid) => port(`a:${aid}`) : undefined} />
        </div>
        {kt === "reply" && <ReplyKeyboard logical={logical} hl={hl} onKey={() => undefined} buttonSlot={(aid) => port(`a:${aid}`)} />}
        {kt === "force_reply" && (
          <div className="relative">
            <ForceReplyBar placeholder={logical.keyboard.placeholder || "Reply…"} hl={hl?.input} />
            {input && port("input")}
          </div>
        )}
      </div>
      {unplaced.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1 px-1">
          {unplaced.map((u) => (
            <span key={u.aid} className="relative rounded-full bg-muted px-2 py-0.5 text-[10.5px] text-muted-foreground" title="Action not on the keyboard">
              {u.label}{port(`u:${u.aid}`)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
});

const EntryNode = memo(function EntryNode({ data }: NodeProps<EntryNodeT>) {
  return (
    <div className="bui-node flex items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-[12px] font-medium text-background shadow-sm">
      {data.kind === "event" ? <Zap className="size-3.5" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
      <span className="font-mono">{data.label}</span>
      <Handle type="source" position={Position.Right} id="out" className="bui-port" style={{ right: -4 }} />
    </div>
  );
});

type RouteData = { label: string | null; dashed: boolean; dotted: boolean; hl: boolean; draft: boolean; points?: Pt[]; lane?: number };

function RoutedEdge({ id, sourceX, sourceY, targetX, targetY, data, markerEnd, selected }: EdgeProps<Edge<RouteData>>) {
  const d = data as RouteData;
  const s = { x: sourceX, y: sourceY }, t = { x: targetX, y: targetY };
  let path: string, mid: Pt;
  if (d.lane !== undefined) {
    const pts = [s, { x: s.x + 18, y: s.y }, { x: s.x + 18, y: d.lane }, { x: t.x - 22, y: d.lane }, { x: t.x - 22, y: t.y }, t];
    path = roundedPath(pts, 14);
    mid = { x: (s.x + t.x) / 2, y: d.lane };
  } else {
    const inner = (d.points ?? []).slice(1, -1).filter((p) => p.x > s.x + 20 && p.x < t.x - 20);
    const pts = [s, { x: s.x + 16, y: s.y }, ...inner, { x: t.x - 16, y: t.y }, t];
    path = smoothPath(pts);
    mid = inner.length ? midpoint(inner.length > 1 ? inner : [inner[0], inner[0]]) : midpoint(pts);
  }
  const stroke = d.hl || selected ? "#d97706" : d.draft ? "#b45309" : "#7c8896";
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} interactionWidth={14}
        style={{ stroke, strokeWidth: d.hl || selected ? 2.6 : 1.5, strokeDasharray: d.dashed ? "6 5" : d.dotted ? "2 4" : undefined }} />
      {d.label && (
        <EdgeLabelRenderer>
          <div className="nodrag nopan pointer-events-none absolute rounded-full px-2 py-0.5 font-mono text-[10.5px] shadow-sm"
            style={{ transform: `translate(-50%, -50%) translate(${mid.x}px, ${mid.y}px)`, background: d.hl || selected ? "#fef3c7" : "var(--background)", color: "var(--foreground)" }}>
            {d.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { screen: ScreenNode, entry: EntryNode };
const PANEL_KEY = "bot-ui-studio:panel-width";
const PANEL_DEFAULT = 780;
const edgeTypes = { routed: RoutedEdge };

function MapSearch({ onPick }: { onPick: (sid: string) => void }) {
  const { working, loaded, editLocale } = useStudio();
  const [open, setOpen] = useState(false);
  const def = defaultLocale(loaded.project);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !(e.target as HTMLElement).closest("input, textarea, [contenteditable=true]"))) {
        e.preventDefault();
        setOpen(true);
      }
    };
    addEventListener("keydown", on);
    return () => removeEventListener("keydown", on);
  }, []);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" className="h-9 w-[min(70vw,300px)] justify-start gap-2 bg-background/95 px-3 font-normal text-muted-foreground shadow-sm backdrop-blur">
          <Search className="size-4" /> <span className="truncate">Find a screen by ID, title or text</span>
          <kbd className="ml-auto hidden rounded bg-muted px-1.5 font-mono text-[10px] sm:inline">Ctrl K</kbd>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(92vw,26rem)] p-0" align="start">
        <Command filter={(v, s) => (v.toLowerCase().includes(s.toLowerCase()) ? 1 : 0)}>
          <CommandInput placeholder="checkout.payment, Оплата, …" />
          <CommandList className="max-h-80">
            <CommandEmpty>No screen matches.</CommandEmpty>
            <CommandGroup>
              {Object.keys(working.screens).sort().map((sid) => {
                const s = working.screens[sid];
                const text = typeof s.message?.text === "object" ? Object.values(s.message.text).join(" ") : String(s.message?.text ?? "");
                return (
                  <CommandItem key={sid} value={`${sid} ${s.title ?? ""} ${text}`} onSelect={() => { setOpen(false); onPick(sid); }}>
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-[12.5px]">{sid}</span>
                      <span className="block truncate text-[11px] text-muted-foreground">{s.title} — {firstLine(s, editLocale, def)}</span>
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

function ZoomControls() {
  const rf = useReactFlow();
  const btn = "flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground";
  return (
    <div className="absolute bottom-3 left-3 z-10 flex flex-col rounded-lg bg-background/95 p-0.5 shadow-sm ring-1 ring-border backdrop-blur">
      <button type="button" className={btn} onClick={() => rf.zoomIn({ duration: 200 })} aria-label="Zoom in"><Plus className="size-4" /></button>
      <button type="button" className={btn} onClick={() => rf.zoomOut({ duration: 200 })} aria-label="Zoom out"><Minus className="size-4" /></button>
      <button type="button" className={btn} onClick={() => rf.fitView({ padding: 0.12, duration: 300 })} aria-label="Fit the whole map"><Maximize2 className="size-4" /></button>
    </div>
  );
}

function Canvas({ selected, selectedAction, onAction }: { selected: string | null; selectedAction: string | null; onAction: (sid: string, aid: string) => void }) {
  const { working, loaded, store, diags, editLocale, highlight, copyId, requests } = useStudio();
  const rf = useReactFlow();
  const [sizes, setSizes] = useState<Record<string, { width: number; height: number }>>({});
  const [layout, setLayout] = useState<Layout | null>(null);
  const [fitted, setFitted] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const list = useMemo(() => mapEdges(working), [working]);
  const savedEdges = useMemo(() => new Set(mapEdges({ project: loaded.project, screens: loaded.screens }).map((e) => `${e.id}>${e.to}`)), [loaded]);
  const entries = loaded.project.entryPoints ?? [];
  const values = useMemo(() => exampleValues(loaded.project), [loaded.project]);
  const def = defaultLocale(loaded.project);
  const ids = useMemo(() => [
    ...entries.filter((ep: any) => working.screens[ep.screen]).map((ep: any) => entryNodeId(ep.id)),
    ...Object.keys(working.screens).sort(),
  ], [working, entries]);
  const errorsBy = useMemo(() => {
    const m: Record<string, number> = {};
    for (const d of diags) if (d.severity === "error" && d.screenId) m[d.screenId] = (m[d.screenId] ?? 0) + 1;
    return m;
  }, [diags]);

  const nodes: Node[] = ids.map((id) => {
    const p = layout?.pos[id] ?? { x: 0, y: 0 };
    const common = { id, position: p, measured: sizes[id], style: layout ? undefined : { opacity: 0 } };
    if (id.startsWith("entry:")) {
      const ep = entries.find((x: any) => entryNodeId(x.id) === id);
      return { ...common, type: "entry", selectable: false, focusable: false, data: { label: entryLabel(ep), kind: ep.type }, ariaLabel: `Entry point ${entryLabel(ep)}` };
    }
    const s = working.screens[id];
    const actions = s.actions ?? {};
    const onKb = new Set((s.keyboard?.rows ?? []).flat());
    const unplaced = Object.entries<any>(actions)
      .filter(([aid, a]) => (!onKb.has(aid) || a.hidden) && list.some((e) => e.from === id && e.actionId === aid))
      .map(([aid, a]) => ({ aid, label: (typeof a.label === "object" ? a.label[editLocale] ?? a.label[def] : a.label) ?? aid }));
    const data: ScreenData = {
      sid: id, logical: renderScreen(loaded.project, s, { locale: editLocale, values }), kind: s.kind ?? "", draft: store.isDraft(id),
      errors: errorsBy[id] ?? 0, hl: hlFor(highlight, id) ?? (selected === id && selectedAction ? { actionId: selectedAction } : undefined),
      flash: flash === id, unplaced, input: s.input?.field ?? null, onAction, onCopy: copyId, requests: requests.filter((r) => r.sid === id).length,
    };
    return { ...common, type: "screen", data, selected: selected === id, ariaLabel: `Screen ${id}, ${s.kind ?? "screen"}${store.isDraft(id) ? ", draft" : ""}. Enter opens the editor.` };
  });

  const hlAction = highlight?.part === "action" ? highlight.actionId : selectedAction;
  const hlFrom = highlight?.sid ?? selected;
  const edges: Edge<RouteData>[] = list.map((e) => {
    const hl = !!hlAction && e.from === hlFrom && e.actionId === hlAction;
    const draft = !e.entry && !savedEdges.has(`${e.id}>${e.to}`);
    const stroke = hl ? "#d97706" : draft ? "#b45309" : "#7c8896";
    return {
      id: e.id, source: e.from, target: e.to, sourceHandle: e.sourceHandle, targetHandle: "in", type: "routed",
      zIndex: hl ? 5 : 0, focusable: !e.entry, selectable: !e.entry,
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 16, height: 16 },
      ariaLabel: e.entry ? undefined : `Transition from ${e.from} to ${e.to}${e.label ? `: ${e.label}` : ""}${e.actionId ? ` (button ${e.actionId})` : ""}`,
      data: { label: e.label, dashed: e.dashed, dotted: e.dotted, hl, draft, points: layout?.points[e.id], lane: layout?.lanes[e.id] },
    };
  });

  // Re-layout once React Flow has measured every node, and whenever a size or the graph changes.
  useEffect(() => {
    if (!ids.every((id) => sizes[id]?.width)) return;
    const key = layoutKey(ids, list, sizes);
    if (layout?.key === key) return;
    setLayout(computeLayout(ids, list, sizes));
  }, [ids, list, sizes, layout?.key]);

  const centre = useCallback((sid: string) => {
    const p = layout?.pos[sid], s = layout?.size[sid];
    if (!p || !s) return;
    rf.setCenter(p.x + s.width / 2, p.y + Math.min(s.height / 2, 220), { zoom: Math.max(rf.getZoom(), 0.9), duration: 450 });
    setFlash(sid);
    setTimeout(() => setFlash((f) => (f === sid ? null : f)), 1400);
  }, [layout, rf]);

  useEffect(() => {
    if (!layout || fitted) return;
    setFitted(true);
    requestAnimationFrame(async () => {
      if (selected && layout.pos[selected]) { centre(selected); return; }
      const canvas = document.querySelector<HTMLElement>(".react-flow");
      const start = loaded.features.demo && layout.pos["entry.start"];
      if (canvas && start) {
        const zoom = 0.62;
        const cardWidth = layout.size["entry.start"].width * zoom;
        const left = Math.max(12, Math.min(152, canvas.clientWidth - cardWidth - 20));
        const top = canvas.clientWidth < 600 ? 88 : 166;
        await rf.setViewport({ x: left - start.x * zoom, y: top - start.y * zoom, zoom });
        return;
      }
      await rf.fitView({ padding: 0.12 });
      // A wide bot fits only at a tiny zoom: start readable at the entry points instead.
      if (rf.getZoom() < 0.5) {
        const h = canvas?.clientHeight ?? 800;
        const z = 0.62;
        rf.setViewport({ x: 40 - layout.bounds.minX * z, y: h / 2 - ((layout.bounds.minY + layout.bounds.maxY) / 2) * z, zoom: z });
      }
    });
  }, [layout, fitted, selected, centre, rf, loaded.features.demo]);

  // Wait a frame for the editor panel to take its width, then centre the selected screen.
  useEffect(() => {
    if (!fitted || !selected) return;
    const t = setTimeout(() => centre(selected), 80);
    return () => clearTimeout(t);
  }, [selected, fitted, centre]);

  const onNodesChange = (changes: NodeChange[]) => {
    const dims = changes.filter((c): c is Extract<NodeChange, { type: "dimensions" }> => c.type === "dimensions" && !!c.dimensions);
    if (dims.length) setSizes((prev) => {
      const next = { ...prev };
      for (const c of dims) next[c.id] = { width: c.dimensions!.width, height: c.dimensions!.height };
      return next;
    });
    for (const c of changes) if (c.type === "select" && c.selected && working.screens[c.id]) go("map", c.id);
  };
  const onEdgesChange = (changes: EdgeChange[]) => {
    for (const c of changes) if (c.type === "select" && c.selected) {
      const e = list.find((x) => x.id === c.id);
      if (e?.actionId) onAction(e.from, e.actionId);
      else if (e) go("map", e.from);
    }
  };

  return (
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
      onNodeClick={(_, n) => { if (n.type === "screen") go("map", n.id); }}
      onEdgeClick={(_, e) => { const x = list.find((y) => y.id === e.id); if (x?.actionId) onAction(x.from, x.actionId); }}
      nodesDraggable={false} nodesConnectable={false} nodesFocusable edgesFocusable elementsSelectable
      minZoom={0.1} maxZoom={1.6} proOptions={{ hideAttribution: true }} onlyRenderVisibleElements={false}
      ariaLabelConfig={{ "node.a11yDescription.default": "Press Enter to open the screen editor." }}
      aria-label="Screen map" className="bg-muted/40">
      <Background gap={22} size={1.2} color="var(--border)" />
      <ZoomControls />
      {ids.length > 12 && <MiniMap pannable zoomable className="!hidden md:!block" nodeColor={(n) => (n.type === "entry" ? "#0f172a" : "#cbd5e1")} maskColor="rgba(240,240,240,.6)" />}
    </ReactFlow>
  );
}

export function MapView({ id }: { id: string | null }) {
  const { working, setHighlight } = useStudio();
  const isMobile = useIsMobile();
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const selected = id && working.screens[id] ? id : null;
  useEffect(() => { setSelectedAction(null); }, [selected]);
  const onAction = useCallback((sid: string, aid: string) => {
    go("map", sid);
    requestAnimationFrame(() => {
      setSelectedAction(aid);
      setHighlight({ sid, part: "action", actionId: aid });
      setTimeout(() => { const el = document.getElementById(`${fieldDomId(sid, `/actions/${aid}`)}-card`); if (el) scrollWithin(el); }, 60);
    });
  }, [setHighlight]);
  const close = () => { setHighlight(null); go("map"); };
  const [panelW, setPanelW] = useState(() => { try { return Number(localStorage.getItem(PANEL_KEY)) || PANEL_DEFAULT; } catch { return PANEL_DEFAULT; } });
  const setPanel = (w: number) => {
    const c = Math.round(Math.max(420, Math.min(w, Math.max(480, window.innerWidth * 0.72))));
    setPanelW(c);
    try { localStorage.setItem(PANEL_KEY, String(c)); } catch { /* storage blocked */ }
  };
  const startResize = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    const move = (ev: PointerEvent) => setPanel(window.innerWidth - ev.clientX);
    const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  };
  const editor = selected ? <ScreenEditor key={selected} sid={selected} selectedAction={selectedAction} onClose={close} /> : null;
  return (
    <ReactFlowProvider>
      <div className="flex min-h-0 flex-1">
        <div className="relative h-[calc(100svh-3.5rem)] min-w-0 flex-1">
          <div className="absolute top-3 left-3 z-10"><MapSearch onPick={(sid) => go("map", sid)} /></div>
          <Canvas selected={selected} selectedAction={selectedAction} onAction={onAction} />
        </div>
        {!isMobile && editor && (
          <aside className="relative h-[calc(100svh-3.5rem)] shrink-0 border-l bg-background" style={{ width: panelW }} aria-label="Screen editor">
            <div role="separator" aria-orientation="vertical" aria-label="Resize the editor panel" aria-valuenow={panelW} aria-valuemin={420} aria-valuemax={1400} tabIndex={0}
              title="Drag to resize; double-click to reset"
              className="group absolute inset-y-0 -left-1.5 z-20 flex w-3 cursor-col-resize items-center justify-center"
              onPointerDown={startResize} onDoubleClick={() => setPanel(PANEL_DEFAULT)}
              onKeyDown={(e) => { if (e.key === "ArrowLeft") setPanel(panelW + 40); if (e.key === "ArrowRight") setPanel(panelW - 40); }}>
              <span className="h-12 w-1 rounded-full bg-border group-hover:bg-foreground/40 group-focus-visible:bg-ring" />
            </div>
            {editor}
          </aside>
        )}
      </div>
      {isMobile && (
        <Sheet open={!!editor} onOpenChange={(o) => { if (!o) close(); }}>
          <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-full [&>button:last-child]:hidden">
            <SheetTitle className="sr-only">Screen editor</SheetTitle>
            <SheetDescription className="sr-only">Edit the selected screen</SheetDescription>
            <div className="flex h-full min-h-0 flex-col">{editor}</div>
          </SheetContent>
        </Sheet>
      )}
    </ReactFlowProvider>
  );
}
