// Map model: one node per screen (a Telegram message preview), one pill per entry point, one edge
// per transition starting at the button that causes it. Layout is dagre (left to right) over the
// real measured node sizes; edges that go back to the left run in a lane under the bubbles.
import { graphlib, layout as dagreLayout } from "@dagrejs/dagre";
import type { Snapshot } from "@/core/engine.ts";
import { edges as lintEdges } from "@/core/lint.ts";
import { keyboardRows, type Doc } from "@/core/render.ts";

export type Pt = { x: number; y: number };
export interface MapEdge {
  id: string; from: string; to: string; actionId: string | null; via: string;
  sourceHandle: string; label: string | null; dashed: boolean; dotted: boolean; entry?: boolean;
}

export const entryNodeId = (epId: string) => `entry:${epId}`;

export function entryLabel(ep: Doc): string {
  return ep.type === "command" ? `/${ep.command}` : ep.type === "event" ? `event ${ep.eventKey}` : `link ${ep.payload ?? ""}`;
}

function viaLabel(snap: Snapshot, from: string, actionId: string | null, via: string): string | null {
  const act: Doc = snap.screens[from]?.actions?.[actionId ?? ""] ?? {};
  if (via === "match") return `${act.rule?.when?.field} == ${typeof act.rule?.when?.eq === "string" ? act.rule.when.eq : JSON.stringify(act.rule?.when?.eq)}`;
  if (via === "otherwise") return "otherwise";
  if (via.startsWith("outcome:")) return via.slice(8);
  if (via === "back-fallback") return "fallback";
  if (via === "input") return `text → ${snap.screens[from]?.input?.field ?? "input"}`;
  return null;
}

/** Which port a transition leaves from: the button, the input area, or the list of off-keyboard actions. */
export function sourceHandle(screen: Doc, actionId: string | null, via: string): string {
  if (via === "input" || !actionId) return "input";
  const placed = keyboardRows(screen).flat().includes(actionId) && !screen.actions?.[actionId]?.hidden;
  return placed ? `a:${actionId}` : `u:${actionId}`;
}

export function mapEdges(snap: Snapshot): MapEdge[] {
  const out: MapEdge[] = [];
  for (const ep of snap.project.entryPoints ?? []) {
    if (!snap.screens[ep.screen]) continue;
    out.push({ id: `entry/${ep.id}`, from: entryNodeId(ep.id), to: ep.screen, actionId: null, via: "entry", sourceHandle: "out", label: null, dashed: false, dotted: false, entry: true });
  }
  for (const e of lintEdges(snap)) {
    if (!snap.screens[e.to]) continue;
    out.push({
      ...e, sourceHandle: sourceHandle(snap.screens[e.from], e.actionId, e.via),
      label: viaLabel(snap, e.from, e.actionId, e.via), dashed: e.via === "back-fallback", dotted: e.via === "input",
    });
  }
  return out;
}

export interface Layout {
  key: string;
  pos: Record<string, Pt>;
  size: Record<string, { width: number; height: number }>;
  points: Record<string, Pt[]>;
  lanes: Record<string, number>;
  bounds: { minX: number; maxX: number; minY: number; maxY: number };
}

const R = (n: number) => Math.round(n / 8) * 8;

export function layoutKey(ids: string[], list: MapEdge[], sizes: Record<string, { width: number; height: number }>): string {
  return ids.map((id) => `${id}:${R(sizes[id]?.width ?? 0)}x${R(sizes[id]?.height ?? 0)}`).join("|") + "#" + list.map((e) => `${e.from}>${e.to}`).join("|");
}

export function computeLayout(ids: string[], list: MapEdge[], sizes: Record<string, { width: number; height: number }>): Layout {
  const g = new graphlib.Graph({ multigraph: true });
  g.setGraph({ rankdir: "LR", ranksep: 150, nodesep: 56, edgesep: 24, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const id of ids) g.setNode(id, { width: sizes[id].width, height: sizes[id].height });
  for (const e of list) {
    if (e.from === e.to) continue;
    // Fallbacks and "back" transitions should not pull screens around.
    g.setEdge(e.from, e.to, { weight: e.dashed ? 0 : e.entry ? 4 : 1, minlen: 1 }, e.id);
  }
  dagreLayout(g);
  const pos: Record<string, Pt> = {};
  const centre: Record<string, Pt> = {};
  for (const id of ids) {
    const n = g.node(id) as any;
    centre[id] = { x: n.x, y: n.y };
    pos[id] = { x: Math.round(n.x - sizes[id].width / 2), y: Math.round(n.y - sizes[id].height / 2) };
  }
  const points: Record<string, Pt[]> = {};
  for (const e of list) {
    if (e.from === e.to) continue;
    const ge = g.edge(e.from, e.to, e.id) as any;
    if (ge?.points) points[e.id] = ge.points.map((p: Pt) => ({ x: p.x, y: p.y }));
  }
  // Lanes under the bubbles for edges whose target is not to the right of their source.
  const lanes: Record<string, number> = {};
  const box = (id: string) => ({ x1: pos[id].x, x2: pos[id].x + sizes[id].width, y2: pos[id].y + sizes[id].height });
  const used: { x1: number; x2: number; y: number }[] = [];
  const back = list.filter((e) => e.from === e.to || pos[e.to].x <= pos[e.from].x + 10);
  back.sort((a, b) => (pos[a.from].x - pos[a.to].x) - (pos[b.from].x - pos[b.to].x) || a.id.localeCompare(b.id));
  for (const e of back) {
    const x1 = pos[e.to].x - 30, x2 = pos[e.from].x + sizes[e.from].width + 30;
    let y = 0;
    for (const id of ids) {
      const b = box(id);
      if (b.x2 >= x1 && b.x1 <= x2) y = Math.max(y, b.y2);
    }
    y += 28;
    while (used.some((u) => u.x2 >= x1 && u.x1 <= x2 && Math.abs(u.y - y) < 14)) y += 14;
    used.push({ x1, x2, y });
    lanes[e.id] = y;
  }
  const xs = ids.map((id) => pos[id].x), ys = ids.map((id) => pos[id].y);
  const bounds = {
    minX: Math.min(...xs), maxX: Math.max(...ids.map((id) => pos[id].x + sizes[id].width)),
    minY: Math.min(...ys), maxY: Math.max(...ids.map((id) => pos[id].y + sizes[id].height), ...Object.values(lanes)),
  };
  return { key: layoutKey(ids, list, sizes), pos, size: sizes, points, lanes, bounds };
}

/** Rounded orthogonal path through the given corners. */
export function roundedPath(pts: Pt[], r = 12): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i - 1], c = pts[i], n = pts[i + 1];
    const d1 = Math.hypot(c.x - p.x, c.y - p.y), d2 = Math.hypot(n.x - c.x, n.y - c.y);
    const rr = Math.min(r, d1 / 2, d2 / 2);
    const a = { x: c.x - ((c.x - p.x) / (d1 || 1)) * rr, y: c.y - ((c.y - p.y) / (d1 || 1)) * rr };
    const b = { x: c.x + ((n.x - c.x) / (d2 || 1)) * rr, y: c.y + ((n.y - c.y) / (d2 || 1)) * rr };
    d += ` L ${a.x},${a.y} Q ${c.x},${c.y} ${b.x},${b.y}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L ${last.x},${last.y}`;
}

/** Smooth curve (Catmull-Rom as cubic Béziers) through the points. */
export function smoothPath(pts: Pt[]): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] ?? p2;
    const c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
    const c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };
    d += ` C ${c1.x},${c1.y} ${c2.x},${c2.y} ${p2.x},${p2.y}`;
  }
  return d;
}

export function midpoint(pts: Pt[]): Pt {
  const lens: number[] = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); lens.push(l); total += l; }
  let half = total / 2;
  for (let i = 1; i < pts.length; i++) {
    if (half <= lens[i - 1]) { const t = half / (lens[i - 1] || 1); return { x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t }; }
    half -= lens[i - 1];
  }
  return pts[pts.length - 1];
}
