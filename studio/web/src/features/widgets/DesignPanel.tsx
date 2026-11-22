// Design tab of the widget workbench: edits widgets/<id>/design.json, a design profile the skill
// compiles to CSS at build time (skills/telegram-bot-ui/scripts/widget_design.py). Markup, script
// and texts are never touched, so the same controls restyle any kit widget.
import { Play, RotateCcw, Undo2 } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { clone, deepEqual } from "@/lib/model";
import { cn } from "@/lib/utils";

export interface DesignCatalog {
  version: number;
  slots: Record<string, string>;
  enums: Record<string, string[]>;
  ranges: Record<string, [number, number]>;
  motion: string[];
  presets: Record<string, { label: string; note: string; design: Doc }>;
  telegram: Record<"light" | "dark", Record<string, string>>;
}
export interface DesignInfo { css: string; bytes: number; contrast: { theme: string; pair: string; ratio: number; need: number; ok: boolean }[] }
type Theme = "light" | "dark";
/** Parts a widget has decide which sections are worth showing. */
export interface Parts { buttons: boolean; chips: boolean; counter: boolean; bars: boolean; image: boolean; title: boolean; meta: boolean }

export function widgetParts(files: Record<string, string>): Parts {
  const src = Object.entries(files).filter(([n]) => !n.endsWith(".json")).map(([, t]) => t).join("\n");
  const has = (c: string) => new RegExp(`(?<![\\w-])${c}(?![\\w-])`).test(src);
  return { buttons: /<button|"button"/.test(src), chips: has("ch"), counter: has("qt"), bars: has("br"), image: has("im"), title: has("tt"), meta: has("mt") };
}

const strip = (d: Doc) => { const { preset: _p, version: _v, ...rest } = d ?? {}; return rest; };
const COLOR_GROUPS: { title: string; slots: string[] }[] = [
  { title: "Block", slots: ["bg", "bg2", "border"] },
  { title: "Text", slots: ["text", "hint", "accent"] },
  { title: "Controls", slots: ["button", "buttonText", "surface", "separator"] },
  { title: "Status", slots: ["success", "warning", "danger"] },
];
const TG_FALLBACK: Record<string, string> = { bg2: "bg" };

function Section({ title, hint, children, aside }: { title: string; hint?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="space-y-3 rounded-xl border bg-card p-4">
      <header className="flex items-start gap-2">
        <div className="min-w-0 flex-1 space-y-0.5">
          <h3 id={id} className="text-sm font-semibold">{title}</h3>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Row({ label, children, note }: { label: string; children: ReactNode; note?: ReactNode }) {
  return (
    <div className="grid items-center gap-x-3 gap-y-1 sm:grid-cols-[7.5rem_minmax(0,1fr)]">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="min-w-0">{children}{note && <p className="mt-1 text-[11px] text-muted-foreground">{note}</p>}</div>
    </div>
  );
}

/** A segmented control; `undefined` is the "as Telegram / as designed" choice. */
function Seg<T extends string>({ label, value, options, onChange }: {
  label: string; value: T | undefined; options: { value: T | undefined; label: string }[]; onChange: (v: T | undefined) => void;
}) {
  return (
    <Row label={label}>
      <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-lg bg-muted p-1">
        {options.map((o) => {
          const on = value === o.value;
          return (
            <button key={o.label} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
              className={cn("rounded-md px-2.5 py-1 text-xs transition-colors", on ? "bg-background font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}>
              {o.label}
            </button>
          );
        })}
      </div>
    </Row>
  );
}

function Range({ label, value, range, fallback, unit = "px", onChange, disabled, fallbackLabel = "Telegram" }: {
  label: string; value: number | undefined; range: [number, number]; fallback: number; unit?: string;
  onChange: (v: number | undefined) => void; disabled?: boolean; fallbackLabel?: string;
}) {
  const id = useId();
  const set = value !== undefined;
  return (
    <div className={cn("space-y-1.5", disabled && "opacity-50")}>
      <div className="flex items-center justify-between gap-2 text-xs">
        <label htmlFor={id} className="text-muted-foreground">{label}</label>
        <span className="flex items-center gap-1 font-mono">
          {set ? `${value} ${unit}` : <span className="text-muted-foreground">{fallbackLabel}</span>}
          {set && !disabled && (
            <button type="button" onClick={() => onChange(undefined)} className="rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Reset ${label}`}>×</button>
          )}
        </span>
      </div>
      <input id={id} type="range" min={range[0]} max={range[1]} step={1} value={value ?? fallback} disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-primary" />
    </div>
  );
}

function Swatch({ value, auto, label, onChange, onReset }: { value?: string; auto: string; label: string; onChange: (v: string) => void; onReset: () => void }) {
  const id = useId();
  const [text, setText] = useState(value ?? "");
  const [prev, setPrev] = useState(value);
  if (prev !== value) { setPrev(value); setText(value ?? ""); }
  return (
    <div className="flex items-center gap-2 py-1">
      <label htmlFor={id} className={cn("relative size-8 shrink-0 cursor-pointer overflow-hidden rounded-full border", !value && "border-dashed")}
        style={{ background: value ?? auto }} title={value ? value : `Telegram's colour (${auto} in this theme)`}>
        <input id={id} type="color" value={value ?? auto} onChange={(e) => onChange(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0" aria-label={label} />
      </label>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium">{label}</p>
        <Input value={text} placeholder="Telegram" aria-label={`${label}, hex`} spellCheck={false}
          onChange={(e) => { setText(e.target.value); if (/^#[0-9a-fA-F]{6}$/.test(e.target.value)) onChange(e.target.value.toLowerCase()); }}
          className="mt-0.5 h-6 w-28 px-1.5 font-mono text-[11px]" />
      </div>
      {value && <Button type="button" size="xs" variant="ghost" onClick={onReset}>Reset</Button>}
    </div>
  );
}

function PresetTile({ name, label, note, design, active, tg, onPick }: {
  name: string; label: string; note: string; design: Doc; active: boolean; tg: DesignCatalog["telegram"]; onPick: () => void;
}) {
  const half = (theme: Theme) => {
    const c = design.colors ?? {};
    const own: Doc = (c.mode === "shared" ? c.shared : c[theme]) ?? {};
    const p = { ...tg[theme], ...own };
    const bg = own.bg2 ? `linear-gradient(160deg, ${own.bg ?? p.bg}, ${own.bg2})` : p.bg;
    const btn = design.button?.style ?? "native";
    const filled = btn === "native" || btn === "filled";
    return (
      <div className="flex flex-1 flex-col gap-1 p-1.5" style={{ background: bg, borderRadius: Math.min(design.block?.radius ?? 0, 8), border: design.block?.border ? `1px solid ${own.border ?? p.surface}` : undefined }}>
        <span className="h-1.5 w-3/4 rounded-full" style={{ background: p.text }} />
        <span className="h-1 w-1/2 rounded-full" style={{ background: p.hint }} />
        <span className="mt-auto h-2.5 w-full" style={{
          background: filled ? p.button : btn === "soft" ? p.surface : "transparent",
          boxShadow: btn === "outline" ? `inset 0 0 0 1px ${p.button}` : undefined,
          borderRadius: Math.min((design.button?.radius ?? 8) / 2, 6),
        }} />
      </div>
    );
  };
  return (
    <button type="button" onClick={onPick} aria-pressed={active} title={note}
      className={cn("group flex w-full flex-col gap-1.5 rounded-lg border bg-background p-1.5 text-left transition-colors hover:border-foreground/40",
        active && "border-primary ring-2 ring-primary/30")} data-preset={name}>
      <div className="flex h-12 overflow-hidden rounded-md" aria-hidden>
        <div className="flex flex-1 bg-white p-1">{half("light")}</div>
        <div className="flex flex-1 bg-[#0e1621] p-1">{half("dark")}</div>
      </div>
      <span className="px-0.5 text-xs font-medium">{label}</span>
    </button>
  );
}

export function DesignPanel({ design, catalog, parts, theme, onTheme, onChange, info, onReplay }: {
  design: Doc; catalog: DesignCatalog; parts: Parts; theme: Theme; onTheme: (t: Theme) => void;
  onChange: (next: Doc) => void; info?: DesignInfo | null; onReplay: () => void;
}) {
  const [before, setBefore] = useState<Doc | null>(null);
  const get = (g: string, k: string) => design[g]?.[k];
  const set = (g: string, k: string, v: any) => {
    const next = clone(design);
    next[g] = { ...(next[g] ?? {}) };
    if (v === undefined) delete next[g][k]; else next[g][k] = v;
    if (!Object.keys(next[g]).length) delete next[g];
    next.version = catalog.version;
    onChange(next);
  };
  const enumOpts = (path: string, labels: Record<string, string>, def = "As designed") =>
    [{ value: undefined, label: def }, ...(catalog.enums[path] ?? []).map((v) => ({ value: v, label: labels[v] ?? v }))];
  const range = (path: string) => catalog.ranges[path] ?? [0, 24];

  const colors: Doc = design.colors ?? {};
  const mode: "theme" | "shared" = colors.mode === "shared" ? "shared" : "theme";
  const part = mode === "shared" ? "shared" : theme;
  const palette: Doc = colors[part] ?? {};
  const setColor = (slot: string, v: string | undefined) => {
    const next = clone(design);
    const c = { mode, ...(next.colors ?? {}) };
    c[part] = { ...(c[part] ?? {}) };
    if (v === undefined) delete c[part][slot]; else c[part][slot] = v;
    if (!Object.keys(c[part]).length) delete c[part];
    next.colors = c;
    if (!c.light && !c.dark && !c.shared) delete next.colors;
    next.version = catalog.version;
    onChange(next);
  };
  const setMode = (m: "theme" | "shared") => {
    if (m === mode) return;
    const next = clone(design);
    const c: Doc = next.colors ?? {};
    next.colors = m === "shared" ? { mode: m, shared: { ...(c[theme] ?? {}) } } : { mode: m, light: { ...(c.shared ?? {}) }, dark: { ...(c.shared ?? {}) } };
    onChange(next);
  };
  const auto = (slot: string) => catalog.telegram[theme][slot] ?? catalog.telegram[theme][TG_FALLBACK[slot]] ?? "#888888";

  const activePreset = Object.entries(catalog.presets).find(([, p]) => deepEqual(strip(p.design), strip(design)))?.[0];
  const pick = (name: string) => {
    if (!activePreset && Object.keys(strip(design)).length) setBefore(design);
    onChange(clone(catalog.presets[name].design));
  };
  const lows = (info?.contrast ?? []).filter((r) => !r.ok);
  const bt = design.button ?? {};
  const buttonFull = bt.width === "full";

  return (
    <div className="space-y-3">
      <Section title="Ready-made looks" hint="Colour and shape only: texts, data and what the widget does stay the same. Each tile shows the light chat on the left and the dark one on the right."
        aside={before ? <Button type="button" size="xs" variant="outline" onClick={() => { onChange(before); setBefore(null); }}><Undo2 className="size-3" /> My design</Button> : undefined}>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(catalog.presets).map(([name, p]) => (
            <PresetTile key={name} name={name} label={p.label} note={p.note} design={p.design} active={activePreset === name} tg={catalog.telegram} onPick={() => pick(name)} />
          ))}
        </div>
        {activePreset && <p className="text-xs text-muted-foreground">{catalog.presets[activePreset].note}</p>}
      </Section>

      <Section title="Colours" hint="Telegram has a light and a dark theme and people see the widget in theirs. A colour you leave empty is Telegram's own, so the widget still matches the chat.">
        <Seg label="Style per theme" value={mode} onChange={(v) => setMode(v ?? "theme")}
          options={[{ value: "theme", label: "Own for each theme" }, { value: "shared", label: "Same in both" }]} />
        <Seg label={mode === "shared" ? "Preview in" : "Editing"} value={theme} onChange={(v) => onTheme(v ?? "light")}
          options={[{ value: "light", label: "Light theme" }, { value: "dark", label: "Dark theme" }]} />
        {mode === "shared" && <p className="text-[11px] text-muted-foreground">These colours apply in both themes; the switch only changes the preview chat.</p>}
        <div className="grid gap-x-4 sm:grid-cols-2">
          {COLOR_GROUPS.map((g) => (
            <fieldset key={g.title} className="min-w-0">
              <legend className="mb-0.5 text-[11px] font-medium tracking-wide text-muted-foreground">{g.title}</legend>
              {g.slots.map((slot) => (
                <Swatch key={`${part}-${slot}`} label={catalog.slots[slot] ?? slot} value={palette[slot]} auto={auto(slot)}
                  onChange={(v) => setColor(slot, v)} onReset={() => setColor(slot, undefined)} />
              ))}
            </fieldset>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="xs" variant="ghost" onClick={() => { const n = clone(design); delete n.colors; onChange(n); }} disabled={!design.colors}>
            <RotateCcw className="size-3" /> Reset all colours
          </Button>
          {info && (lows.length ? (
            <span role="status" className="text-xs text-amber-700 dark:text-amber-400">Low contrast: {lows.map((r) => `${r.theme} · ${r.pair.toLowerCase()} ${r.ratio}:1`).join("; ")}</span>
          ) : info.contrast.length ? <span role="status" className="text-xs text-emerald-700 dark:text-emerald-400">Contrast is fine in both themes.</span> : null)}
        </div>
      </Section>

      <Section title="Block" hint="The frame that holds everything: its corners, border, padding and where the content sits.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Range label="Corner radius" value={get("block", "radius")} range={range("block.radius")} fallback={0} onChange={(v) => set("block", "radius", v)} />
          <Range label="Border" value={get("block", "border")} range={range("block.border")} fallback={0} onChange={(v) => set("block", "border", v)} />
          <Range label="Padding" value={get("block", "padding")} range={range("block.padding")} fallback={12} onChange={(v) => set("block", "padding", v)} />
          <Range label="Gap to the bubble" value={get("block", "inset")} range={range("block.inset")} fallback={0} onChange={(v) => set("block", "inset", v)} fallbackLabel="none" />
        </div>
        <Seg label="Content" value={get("block", "align")} onChange={(v) => set("block", "align", v)}
          options={enumOpts("block.align", { start: "Left", center: "Centre", end: "Right" })} />
      </Section>

      <Section title="Motion" hint="The preview plays the entrance once after a change. Lively adds a glint that crosses the main button every few seconds."
        aside={<Button type="button" size="xs" variant="outline" onClick={onReplay}><Play className="size-3" /> Replay</Button>}>
        <Seg label="Motion" value={design.motion} onChange={(v) => { const n = clone(design); if (v && v !== "none") n.motion = v; else delete n.motion; onChange(n); }}
          options={[{ value: undefined, label: "None" }, { value: "calm", label: "Calm" }, { value: "lively", label: "Lively" }]} />
        <p className="text-[11px] text-muted-foreground">When a phone has Reduce motion on, the widget stays still. Motion never uses transparency or blur, which Telegram limits to 16 elements.</p>
      </Section>

      {parts.buttons && (
        <Section title="Button" hint="How the main button looks. Its label and action live in the widget's texts and code; buttons the widget draws itself (stars, list rows) keep their look.">
          <Seg label="Style" value={bt.style} onChange={(v) => set("button", "style", v)}
            options={enumOpts("button.style", { native: "Telegram", filled: "Filled", outline: "Outline", soft: "Soft", text: "Text" }, "Telegram").filter((o) => o.value !== "native")} />
          <Range label="Corner radius" value={bt.radius} range={range("button.radius")} fallback={8} onChange={(v) => set("button", "radius", v)} />
          <Seg label="Height" value={bt.height} onChange={(v) => set("button", "height", v)} options={enumOpts("button.height", { low: "Low", normal: "Normal", high: "High" }, "Telegram")} />
          <Seg label="Width" value={bt.width} onChange={(v) => set("button", "width", v)} options={enumOpts("button.width", { auto: "Fit text", half: "Half", full: "Full width" })} />
          <Seg label="Position" value={buttonFull ? undefined : bt.align} onChange={(v) => set("button", "align", v)}
            options={enumOpts("button.align", { start: "Left", center: "Centre", end: "Right" })} />
          {buttonFull && <p className="text-[11px] text-muted-foreground">A full-width button has no position.</p>}
        </Section>
      )}

      {(parts.title || parts.meta) && (
        <Section title="Title and texts" hint="Size and alignment. The words come from the bot and the widget's strings; colours are set above.">
          {parts.title && <>
            <Seg label="Title size" value={get("title", "size")} onChange={(v) => set("title", "size", v)} options={enumOpts("title.size", { s: "Small", m: "Medium", l: "Large", xl: "Huge" }, "Telegram")} />
            <Seg label="Title position" value={get("title", "align")} onChange={(v) => set("title", "align", v)} options={enumOpts("title.align", { start: "Left", center: "Centre", end: "Right" })} />
          </>}
          <Seg label="Main text" value={get("body", "size")} onChange={(v) => set("body", "size", v === "m" ? undefined : v)} options={[{ value: undefined, label: "Normal" }, { value: "s", label: "Small" }]} />
          {parts.meta && <>
            <Seg label="Secondary text" value={get("meta", "size")} onChange={(v) => set("meta", "size", v === "m" ? undefined : v)} options={[{ value: undefined, label: "Normal" }, { value: "s", label: "Small" }]} />
            <Seg label="Secondary position" value={get("meta", "align")} onChange={(v) => set("meta", "align", v)} options={enumOpts("meta.align", { start: "Left", center: "Centre", end: "Right" })} />
          </>}
        </Section>
      )}

      {(parts.chips || parts.counter || parts.bars) && (
        <Section title="Choices, counter and progress" hint="Chips are the small buttons for picking an option; their colours are the Chips and Button rows above.">
          <div className="grid gap-4 sm:grid-cols-2">
            {parts.chips && <Range label="Chip corners" value={get("chips", "radius")} range={range("chips.radius")} fallback={range("chips.radius")[1]} onChange={(v) => set("chips", "radius", v)} fallbackLabel="pill" />}
            <Range label="Card corners" value={get("surface", "radius")} range={range("surface.radius")} fallback={10} onChange={(v) => set("surface", "radius", v)} />
            {parts.counter && <Range label="Counter corners" value={get("counter", "radius")} range={range("counter.radius")} fallback={range("counter.radius")[1]} onChange={(v) => set("counter", "radius", v)} fallbackLabel="pill" />}
            {parts.bars && <Range label="Progress bar height" value={get("bar", "height")} range={range("bar.height")} fallback={6} onChange={(v) => set("bar", "height", v)} />}
            {parts.bars && <Range label="Progress bar corners" value={get("bar", "radius")} range={range("bar.radius")} fallback={3} onChange={(v) => set("bar", "radius", v)} />}
          </div>
          {parts.chips && <Seg label="Selected chip" value={get("chips", "selected")} onChange={(v) => set("chips", "selected", v === "filled" ? undefined : v)}
            options={[{ value: undefined, label: "Filled" }, { value: "outline", label: "Outlined" }]} />}
          {parts.counter && <Seg label="Counter" value={get("counter", "style")} onChange={(v) => set("counter", "style", v === "filled" ? undefined : v)}
            options={[{ value: undefined, label: "Filled" }, { value: "outline", label: "Outlined" }]} />}
        </Section>
      )}

      {parts.image && (
        <Section title="Picture" hint="The product picture or icon area at the top of the widget.">
          <Range label="Corner radius" value={get("image", "radius")} range={range("image.radius")} fallback={10} onChange={(v) => set("image", "radius", v)} />
          <Row label="Backdrop">
            <label className="flex items-center gap-2 text-xs">
              <Switch checked={get("image", "backdrop") !== false} onCheckedChange={(on) => set("image", "backdrop", on ? undefined : false)} aria-label="Backdrop behind the picture" />
              {get("image", "backdrop") === false ? "No backdrop: the picture sits on the block" : "A card behind the picture"}
            </label>
          </Row>
        </Section>
      )}

      <p className="px-1 text-xs text-muted-foreground" role="status">
        {info ? (info.bytes > 0 ? `This look adds ${info.bytes} B to the widget after compression; the meter above shows what is left of Telegram's 4096 B.` : "No design yet: the widget looks exactly like Telegram draws it.")
          : "Pick a look or change any option; the preview rebuilds as you go."}
      </p>
    </div>
  );
}
