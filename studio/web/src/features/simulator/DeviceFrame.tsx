// A resizable device for the simulator chat: Phone / Tablet / Desktop presets, free resizing by
// drag (right edge, bottom edge, corner) or keyboard, scaled down to fit the pane, remembered.
import { Monitor, Smartphone, Tablet, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Tip } from "./SimControls";

export type DeviceKind = "phone" | "tablet" | "desktop" | "custom";
export interface Device { kind: DeviceKind; w: number; h: number }

export const PRESETS: Record<Exclude<DeviceKind, "custom">, { w: number; h: number; icon: LucideIcon; label: string }> = {
  phone: { w: 390, h: 844, icon: Smartphone, label: "Phone (390 × 844)" },
  tablet: { w: 820, h: 1180, icon: Tablet, label: "Tablet (820 × 1180)" },
  desktop: { w: 1100, h: 760, icon: Monitor, label: "Telegram Desktop / Web (1100 × 760)" },
};
const KEY = "bot-ui-studio:sim-device";
const MIN_W = 320, MAX_W = 1600, MIN_H = 480, MAX_H = 1400;

/** How Telegram lays the chat out at a width: a centred column on wide windows, narrower bubbles. */
export function chatLayout(w: number): { column: number; bubble: string; pad: number; wide: boolean } {
  if (w >= 1000) return { column: 720, bubble: "min(70%, 480px)", pad: 24, wide: true };
  if (w >= 700) return { column: Math.min(w, 680), bubble: "min(72%, 500px)", pad: 20, wide: false };
  return { column: w, bubble: "86%", pad: 12, wide: false };
}

export function useDevice(): [Device, (d: Device) => void] {
  const [dev, setDev] = useState<Device>(() => {
    try { const v = JSON.parse(localStorage.getItem(KEY) ?? "null"); if (v && v.w && v.h) return v; } catch { /* storage blocked */ }
    return { kind: "phone", ...PRESETS.phone };
  });
  const set = (d: Device) => {
    const next = { ...d, w: Math.round(Math.max(MIN_W, Math.min(MAX_W, d.w))), h: Math.round(Math.max(MIN_H, Math.min(MAX_H, d.h))) };
    setDev(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage blocked */ }
  };
  return [dev, set];
}

export function DevicePresets({ device, onChange, scale }: { device: Device; onChange: (d: Device) => void; scale: number }) {
  return (
    <div className="flex items-center gap-2">
      <div role="radiogroup" aria-label="Device size" className="inline-flex h-8 items-center rounded-lg bg-muted p-0.5">
        {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((k) => {
          const P = PRESETS[k];
          return (
            <Tip key={k} label={P.label}>
              <button type="button" role="radio" aria-checked={device.kind === k} aria-label={P.label} onClick={() => onChange({ kind: k, w: P.w, h: P.h })}
                className="flex h-7 w-8 items-center justify-center rounded-md text-muted-foreground aria-checked:bg-background aria-checked:text-foreground aria-checked:shadow-sm">
                <P.icon className="size-4" aria-hidden />
              </button>
            </Tip>
          );
        })}
      </div>
      <span className="font-mono text-[11px] text-muted-foreground tabular-nums" aria-live="polite">
        {device.w}×{device.h}{scale < 0.995 ? ` · ${Math.round(scale * 100)}%` : ""}
      </span>
    </div>
  );
}

/** Fits the device into the available area and lets the user drag its size. */
export function DeviceStage({ device, onChange, onScale, children }: { device: Device; onChange: (d: Device) => void; onScale: (s: number) => void; children: ReactNode }) {
  const stage = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState({ w: 800, h: 700 });
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    // The height that is really visible: banners above the page can push the stage below the
    // window edge, so the box height alone would let the bottom bar (START, composer) fall off.
    const measure = () => {
      const r = el.getBoundingClientRect();
      const visible = window.innerHeight - Math.max(0, r.top) - 8;
      setAvail({ w: r.width, h: Math.max(160, Math.min(r.height, visible)) });
    };
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    measure();
    return () => { ro.disconnect(); window.removeEventListener("resize", measure); };
  }, []);
  const scale = Math.min(1, (avail.w - 28) / device.w, (avail.h - 28) / device.h);
  useEffect(() => { onScale(scale); }, [scale, onScale]);

  const drag = (axis: "x" | "y" | "xy") => (e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    const x0 = e.clientX, y0 = e.clientY, w0 = device.w, h0 = device.h, s = scale;
    // The frame is centred horizontally, so a right-edge drag grows it on both sides.
    const move = (ev: PointerEvent) => onChange({
      kind: "custom",
      w: axis === "y" ? w0 : w0 + ((ev.clientX - x0) * 2) / s,
      h: axis === "x" ? h0 : h0 + (ev.clientY - y0) / s,
    });
    const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  };
  const keys = (axis: "x" | "y") => (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 50 : 10;
    if (axis === "x" && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { e.preventDefault(); onChange({ kind: "custom", w: device.w + (e.key === "ArrowRight" ? step : -step), h: device.h }); }
    if (axis === "y" && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); onChange({ kind: "custom", w: device.w, h: device.h + (e.key === "ArrowDown" ? step : -step) }); }
  };
  const handle = "absolute z-10 flex items-center justify-center rounded-full bg-background/90 shadow ring-1 ring-border hover:bg-background focus-visible:ring-2 focus-visible:ring-ring";
  return (
    <div ref={stage} className="relative flex min-h-0 flex-1 items-start justify-center overflow-hidden p-3.5">
      <div className="relative" style={{ width: device.w * scale, height: device.h * scale }}>
        <div className="absolute top-0 left-0 origin-top-left" style={{ width: device.w, height: device.h, transform: `scale(${scale})` }}>{children}</div>
        <div role="separator" aria-orientation="vertical" aria-label="Chat width" aria-valuenow={device.w} aria-valuemin={MIN_W} aria-valuemax={MAX_W} tabIndex={0}
          title="Drag to change the width (arrow keys, Shift for bigger steps)"
          className={cn(handle, "top-1/2 -right-3 h-12 w-2.5 -translate-y-1/2 cursor-ew-resize")} onPointerDown={drag("x")} onKeyDown={keys("x")}>
          <span className="h-6 w-0.5 rounded-full bg-muted-foreground/50" />
        </div>
        <div role="separator" aria-orientation="horizontal" aria-label="Chat height" aria-valuenow={device.h} aria-valuemin={MIN_H} aria-valuemax={MAX_H} tabIndex={0}
          title="Drag to change the height (arrow keys, Shift for bigger steps)"
          className={cn(handle, "-bottom-3 left-1/2 h-2.5 w-12 -translate-x-1/2 cursor-ns-resize")} onPointerDown={drag("y")} onKeyDown={keys("y")}>
          <span className="h-0.5 w-6 rounded-full bg-muted-foreground/50" />
        </div>
        <div aria-hidden title="Drag to resize" className={cn(handle, "-right-3 -bottom-3 size-4 cursor-nwse-resize")} onPointerDown={drag("xy")} />
      </div>
    </div>
  );
}
