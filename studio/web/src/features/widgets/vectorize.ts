// Photo -> SVG for widget assets, entirely in the browser (pure functions, no DOM): downscale,
// k-means colour quantization, contour tracing of each colour (marching squares on pixel
// corners), Ramer-Douglas-Peucker simplification, one evenodd <path> per colour, integer coords.
// Node-testable: no enums or parameter properties (type stripping).

export interface RGBAImage { width: number; height: number; data: ArrayLike<number> }
export interface VectorizeOptions {
  /** 2..8 colours. */
  colors: number;
  /** 0 (coarse) .. 1 (fine): simplification tolerance and the smallest kept region. */
  detail: number;
}
export interface VectorResult { svg: string; width: number; height: number; palette: string[]; paths: number; points: number }

export type Pt = [number, number];

/** Box-filter downscale so the longer side is at most maxSide (never upscales). */
export function downscale(img: RGBAImage, maxSide: number): RGBAImage {
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
  if (scale >= 1) return img;
  const w = Math.max(1, Math.round(img.width * scale)), h = Math.max(1, Math.round(img.height * scale));
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    const y0 = Math.floor((y * img.height) / h), y1 = Math.max(y0 + 1, Math.floor(((y + 1) * img.height) / h));
    for (let x = 0; x < w; x++) {
      const x0 = Math.floor((x * img.width) / w), x1 = Math.max(x0 + 1, Math.floor(((x + 1) * img.width) / w));
      let r = 0, g = 0, b = 0, a = 0, n = 0;
      for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) {
        const i = (yy * img.width + xx) * 4;
        r += img.data[i]; g += img.data[i + 1]; b += img.data[i + 2]; a += img.data[i + 3]; n++;
      }
      const o = (y * w + x) * 4;
      out[o] = r / n; out[o + 1] = g / n; out[o + 2] = b / n; out[o + 3] = a / n;
    }
  }
  return { width: w, height: h, data: out };
}

/** Deterministic k-means: luminance-quantile seeds, a fixed number of rounds. Label -1 = transparent. */
export function quantize(img: RGBAImage, k: number, rounds = 10): { palette: [number, number, number][]; labels: Int16Array } {
  const n = img.width * img.height;
  const labels = new Int16Array(n).fill(-1);
  const idx: number[] = [];
  for (let p = 0; p < n; p++) if (img.data[p * 4 + 3] >= 128) idx.push(p);
  if (!idx.length) return { palette: [], labels };
  // Farthest-first seeds (deterministic): the mean colour, then the pixel farthest from every seed.
  const kk = Math.max(1, Math.min(k, idx.length));
  const px = (p: number): [number, number, number] => [img.data[p * 4], img.data[p * 4 + 1], img.data[p * 4 + 2]];
  const mean: [number, number, number] = [0, 0, 0];
  for (const p of idx) { mean[0] += img.data[p * 4]; mean[1] += img.data[p * 4 + 1]; mean[2] += img.data[p * 4 + 2]; }
  let centres: [number, number, number][] = [[mean[0] / idx.length, mean[1] / idx.length, mean[2] / idx.length]];
  const nearest = idx.map(() => Infinity);
  while (centres.length < kk) {
    const c = centres[centres.length - 1];
    let far = -1, farD = 0;
    idx.forEach((p, i) => {
      const d = (img.data[p * 4] - c[0]) ** 2 + (img.data[p * 4 + 1] - c[1]) ** 2 + (img.data[p * 4 + 2] - c[2]) ** 2;
      if (d < nearest[i]) nearest[i] = d;
      if (nearest[i] > farD) { farD = nearest[i]; far = p; }
    });
    if (far < 0) break;
    centres.push(px(far));
  }
  for (let round = 0; round < rounds; round++) {
    const sum = centres.map(() => [0, 0, 0, 0]);
    for (const p of idx) {
      const r = img.data[p * 4], g = img.data[p * 4 + 1], b = img.data[p * 4 + 2];
      let best = 0, bestD = Infinity;
      for (let c = 0; c < centres.length; c++) {
        const d = (r - centres[c][0]) ** 2 + (g - centres[c][1]) ** 2 + (b - centres[c][2]) ** 2;
        if (d < bestD) { bestD = d; best = c; }
      }
      labels[p] = best;
      const s = sum[best]; s[0] += r; s[1] += g; s[2] += b; s[3]++;
    }
    centres = centres.map((c, i) => (sum[i][3] ? [sum[i][0] / sum[i][3], sum[i][1] / sum[i][3], sum[i][2] / sum[i][3]] : c));
  }
  return { palette: centres.map((c) => [Math.round(c[0]), Math.round(c[1]), Math.round(c[2])]), labels };
}

/** Closed boundary loops of a binary mask, as pixel-corner points (outer loops clockwise). */
export function traceMask(mask: Uint8Array, w: number, h: number): Pt[][] {
  const inside = (x: number, y: number) => x >= 0 && y >= 0 && x < w && y < h && mask[y * w + x] === 1;
  // Directed boundary edges keyed by start corner; the inside is on the right (screen coords).
  const out = new Map<number, number[]>();
  const key = (x: number, y: number) => y * (w + 1) + x;
  const add = (ax: number, ay: number, bx: number, by: number) => {
    const k = key(ax, ay);
    const list = out.get(k);
    if (list) list.push(key(bx, by)); else out.set(k, [key(bx, by)]);
  };
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (!inside(x, y)) continue;
    if (!inside(x, y - 1)) add(x, y, x + 1, y);
    if (!inside(x + 1, y)) add(x + 1, y, x + 1, y + 1);
    if (!inside(x, y + 1)) add(x + 1, y + 1, x, y + 1);
    if (!inside(x - 1, y)) add(x, y + 1, x, y);
  }
  const xy = (k: number): Pt => [k % (w + 1), Math.floor(k / (w + 1))];
  const loops: Pt[][] = [];
  const starts = [...out.keys()].sort((a, b) => a - b);
  for (const s of starts) {
    while ((out.get(s)?.length ?? 0) > 0) {
      const loop: number[] = [s];
      let prev = s, cur = out.get(s)!.shift()!;
      while (cur !== s) {
        loop.push(cur);
        const nexts = out.get(cur) ?? [];
        if (!nexts.length) break;
        // At a corner shared by two diagonal pixels take the right-hand turn, so regions stay separate.
        let pick = 0;
        if (nexts.length > 1) {
          const [px, py] = xy(prev), [cx, cy] = xy(cur);
          const dx = cx - px, dy = cy - py;
          pick = nexts.findIndex((nk) => { const [nx, ny] = xy(nk); return (nx - cx) === -dy && (ny - cy) === dx; });
          if (pick < 0) pick = 0;
        }
        prev = cur;
        cur = nexts.splice(pick, 1)[0];
      }
      if (loop.length >= 4) loops.push(removeCollinear(loop.map(xy)));
    }
  }
  return loops;
}

function removeCollinear(pts: Pt[]): Pt[] {
  const out: Pt[] = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[(i - 1 + pts.length) % pts.length], b = pts[i], c = pts[(i + 1) % pts.length];
    if ((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) !== 0) out.push(b);
  }
  return out;
}

export function polygonArea(pts: Pt[]): number {
  let s = 0;
  for (let i = 0; i < pts.length; i++) { const a = pts[i], b = pts[(i + 1) % pts.length]; s += a[0] * b[1] - b[0] * a[1]; }
  return s / 2;
}

function perpDist(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len = Math.hypot(dx, dy);
  if (!len) return Math.hypot(p[0] - a[0], p[1] - a[1]);
  return Math.abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / len;
}

/** Ramer-Douglas-Peucker on an open polyline. */
export function rdp(pts: Pt[], eps: number): Pt[] {
  if (pts.length < 3) return pts;
  let idx = 0, max = 0;
  for (let i = 1; i < pts.length - 1; i++) { const d = perpDist(pts[i], pts[0], pts[pts.length - 1]); if (d > max) { max = d; idx = i; } }
  if (max <= eps) return [pts[0], pts[pts.length - 1]];
  return [...rdp(pts.slice(0, idx + 1), eps).slice(0, -1), ...rdp(pts.slice(idx), eps)];
}

/** RDP on a closed loop: split at the point farthest from the first one. */
export function simplifyLoop(loop: Pt[], eps: number): Pt[] {
  if (loop.length <= 4 || eps <= 0) return loop;
  let far = 0, max = -1;
  for (let i = 1; i < loop.length; i++) { const d = Math.hypot(loop[i][0] - loop[0][0], loop[i][1] - loop[0][1]); if (d > max) { max = d; far = i; } }
  const a = rdp(loop.slice(0, far + 1), eps), b = rdp([...loop.slice(far), loop[0]], eps);
  const out = [...a.slice(0, -1), ...b.slice(0, -1)];
  return out.length >= 3 ? out : loop;
}

const num = (v: number) => String(Math.round(v * 10) / 10);

/** Compact path data: absolute move, relative line-tos with implicit commands. */
export function pathData(loops: Pt[][]): string {
  return loops.map((l) => {
    let d = `M${num(l[0][0])} ${num(l[0][1])}l`;
    for (let i = 1; i < l.length; i++) {
      const dx = l[i][0] - l[i - 1][0], dy = l[i][1] - l[i - 1][1];
      const sx = num(dx), sy = num(dy);
      d += (i > 1 && !sx.startsWith("-") ? " " : "") + sx + (sy.startsWith("-") ? "" : " ") + sy;
    }
    return d + "z";
  }).join("");
}

const hex = (c: [number, number, number]) => "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
function shortHex(h: string): string {
  return h[1] === h[2] && h[3] === h[4] && h[5] === h[6] ? `#${h[1]}${h[3]}${h[5]}` : h;
}

export function vectorize(img: RGBAImage, o: VectorizeOptions): VectorResult {
  const k = Math.max(2, Math.min(8, Math.round(o.colors)));
  const detail = Math.max(0, Math.min(1, o.detail));
  const { width: w, height: h } = img;
  const { palette, labels } = quantize(img, k);
  const counts = palette.map((_, c) => labels.reduce((n, l) => n + (l === c ? 1 : 0), 0));
  const order = palette.map((_, c) => c).filter((c) => counts[c] > 0).sort((a, b) => counts[b] - counts[a] || a - b);
  const transparent = labels.some((l) => l < 0);
  const eps = 0.35 + (1 - detail) * 1.6;
  const minArea = Math.max(1, Math.round((1 - detail) * 6));
  const parts: string[] = [];
  let paths = 0, points = 0;
  order.forEach((c, i) => {
    const fill = shortHex(hex(palette[c]));
    if (i === 0 && !transparent) { parts.push(`<rect width="${w}" height="${h}" fill="${fill}"/>`); paths++; return; }
    const mask = new Uint8Array(w * h);
    for (let p = 0; p < w * h; p++) if (labels[p] === c) mask[p] = 1;
    const loops = traceMask(mask, w, h)
      .filter((l) => Math.abs(polygonArea(l)) >= minArea)
      .map((l) => simplifyLoop(l, eps))
      .filter((l) => l.length >= 3);
    if (!loops.length) return;
    points += loops.reduce((n, l) => n + l.length, 0);
    parts.push(`<path fill="${fill}" fill-rule="evenodd" d="${pathData(loops)}"/>`);
    paths++;
  });
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}">${parts.join("")}</svg>`;
  return { svg, width: w, height: h, palette: order.map((c) => hex(palette[c])), paths, points };
}

export function utf8Size(s: string): number {
  return new TextEncoder().encode(s).length;
}
