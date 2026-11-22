// Photo -> SVG asset: the image is read locally (FileReader, data: URL), drawn on a canvas,
// vectorized by vectorize.ts and saved as widgets/<id>/<name>.svg with a marker in index.html.
import { Check, Copy, ImageUp, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { copyText, utf8Bytes } from "@/lib/model";
import { cn } from "@/lib/utils";
import { EnumSelect, Field } from "../inspector/fields";
import { downscale, vectorize, type VectorResult } from "./vectorize";

const ASSET_WARN = 1500;
const NAME_RE = /^[a-z0-9][a-z0-9_.-]*\.svg$/;

async function deflateSize(text: string): Promise<number | null> {
  try {
    const cs = new CompressionStream("deflate");
    const stream = new Blob([text]).stream().pipeThrough(cs);
    return (await new Response(stream).arrayBuffer()).byteLength;
  } catch {
    return null;
  }
}

export const marker = (name: string) => `<!--@file ${name}-->`;

export function insertMarker(index: string, name: string, place: "top" | "end"): string {
  const m = marker(name);
  if (index.includes(m)) return index;
  if (place === "top") return `${m}\n${index}`;
  return index.replace(/\s*$/, "") + `\n${m}\n`;
}

export function PhotoToSvg({ existing, onAdd, busy }: { existing: string[]; onAdd: (name: string, svg: string, place: "top" | "end" | "none") => void; busy?: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  const [fileName, setFileName] = useState("logo");
  const [colors, setColors] = useState(4);
  const [detail, setDetail] = useState(0.5);
  const [result, setResult] = useState<VectorResult | null>(null);
  const [zipped, setZipped] = useState<number | null>(null);
  const [name, setName] = useState("logo.svg");
  const [place, setPlace] = useState<"top" | "end" | "none">("end");
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!src) return;
    const t = setTimeout(() => {
      const img = imgRef.current;
      if (!img?.naturalWidth) return;
      const side = Math.round(40 + detail * 120);
      const scale = Math.min(1, (side * 2) / Math.max(img.naturalWidth, img.naturalHeight));
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(img.naturalWidth * scale));
      c.height = Math.max(1, Math.round(img.naturalHeight * scale));
      const ctx = c.getContext("2d", { willReadFrequently: true });
      if (!ctx) return setErr("This browser cannot read images on a canvas.");
      ctx.drawImage(img, 0, 0, c.width, c.height);
      const data = ctx.getImageData(0, 0, c.width, c.height);
      const r = vectorize(downscale({ width: c.width, height: c.height, data: data.data }, side), { colors, detail });
      setResult(r);
      void deflateSize(r.svg).then(setZipped);
    }, 120);
    return () => clearTimeout(t);
  }, [src, colors, detail]);

  const load = (f: File) => {
    setErr("");
    if (!/^image\/(png|jpeg|webp)$/.test(f.type)) return setErr("Use a PNG, JPEG or WebP image.");
    if (f.size > 8 * 1024 * 1024) return setErr("The image is over 8 MB.");
    const base = f.name.replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^[^a-z0-9]+/, "") || "image";
    setFileName(base);
    setName(`${base}.svg`);
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => { imgRef.current = img; setSrc(String(reader.result)); };
      img.onerror = () => setErr("The image could not be decoded.");
      img.src = String(reader.result);
    };
    reader.readAsDataURL(f);
  };

  const bytes = result ? utf8Bytes(result.svg) : 0;
  const nameProblem = !NAME_RE.test(name) ? "lowercase letters, digits, - _ . and .svg" : existing.includes(name) ? "a file with this name exists (it will be replaced)" : "";
  return (
    <div className="space-y-3">
      <label className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed px-4 py-5 text-center text-sm text-muted-foreground hover:bg-muted/40 focus-within:ring-2 focus-within:ring-ring">
        <ImageUp className="size-6" aria-hidden />
        <span><span className="font-medium text-foreground">Choose a photo or logo</span> (PNG, JPEG, WebP)</span>
        <span className="text-[11px]">Converted in this page; the image is never uploaded or sent anywhere.</span>
        <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) load(f); }} />
      </label>
      {err && <p role="alert" className="text-xs text-destructive">{err}</p>}
      {src && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Field label={<>Colours <span className="font-mono">{colors}</span></>}><Slider min={2} max={8} step={1} value={[colors]} onValueChange={([v]) => setColors(v)} aria-label="Colours" /></Field>
            <Field label={<>Detail <span className="font-mono">{Math.round(detail * 100)}%</span></>}><Slider min={0} max={1} step={0.05} value={[detail]} onValueChange={([v]) => setDetail(v)} aria-label="Detail" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <figure className="space-y-1">
              <div className="flex aspect-square items-center justify-center overflow-hidden rounded-lg bg-[repeating-conic-gradient(#f1f1f1_0_25%,#fff_0_50%)] bg-[length:16px_16px] ring-1 ring-border">
                <img src={src} alt={`Original ${fileName}`} className="max-h-full max-w-full object-contain" />
              </div>
              <figcaption className="text-center text-[11px] text-muted-foreground">Original</figcaption>
            </figure>
            <figure className="space-y-1">
              <div className="flex aspect-square items-center justify-center overflow-hidden rounded-lg bg-[repeating-conic-gradient(#f1f1f1_0_25%,#fff_0_50%)] bg-[length:16px_16px] ring-1 ring-border">
                {result ? <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(result.svg)}`} alt="Vector result" className="size-full object-contain" /> : <Loader2 className="size-5 animate-spin text-muted-foreground" />}
              </div>
              <figcaption className="text-center text-[11px] text-muted-foreground">SVG · {result ? `${result.paths} paths, ${result.points} points` : "…"}</figcaption>
            </figure>
          </div>
          {result && (
            <p className={cn("rounded-lg px-2.5 py-1.5 text-xs", bytes > ASSET_WARN ? "bg-amber-100 text-amber-950" : "bg-emerald-100 text-emerald-950")}>
              <span className="font-mono">{bytes.toLocaleString()} B</span> SVG{zipped != null && <> · <span className="font-mono">≈{zipped.toLocaleString()} B</span> compressed</>} of the 4,096 B widget budget.
              {bytes > ASSET_WARN ? " Heavy for one asset: lower colours or detail." : " Fits comfortably."}
            </p>
          )}
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <Field label="File name" htmlFor="svg-name" hint={nameProblem || undefined}>
              <Input id="svg-name" value={name} onChange={(e) => setName(e.target.value.trim().toLowerCase())} className="font-mono text-[13px]" aria-invalid={!!nameProblem && !existing.includes(name) || undefined} />
            </Field>
            <Field label="Put it in index.html">
              <EnumSelect value={place} onChange={(v) => setPlace(v as "top" | "end" | "none")} options={[
                { value: "end", label: "at the end" }, { value: "top", label: "at the top" }, { value: "none", label: "don't insert (copy the marker)" },
              ]} />
            </Field>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!result || !NAME_RE.test(name) || busy} onClick={() => result && onAdd(name, result.svg, place)}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : null} Add to widget
            </Button>
            <Button variant="outline" disabled={!NAME_RE.test(name)} onClick={async () => { if (await copyText(marker(name))) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />} Copy marker
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
