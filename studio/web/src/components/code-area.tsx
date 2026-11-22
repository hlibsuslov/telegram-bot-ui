// Plain textarea with a line-number gutter (no editor library). Tab keeps moving focus.
import { useRef } from "react";
import { cn } from "@/lib/utils";

export function CodeArea({ id, value, onChange, className, label }: { id: string; value: string; onChange: (v: string) => void; className?: string; label: string }) {
  const gutter = useRef<HTMLDivElement>(null);
  const lines = value.split("\n").length;
  return (
    <div className={cn("flex min-h-0 overflow-hidden rounded-lg bg-muted/30 font-mono text-[12.5px] leading-[1.65] ring-1 ring-border focus-within:ring-2 focus-within:ring-ring", className)}>
      <div ref={gutter} aria-hidden className="w-11 shrink-0 overflow-hidden bg-muted/60 py-2.5 pr-2 text-right text-[11px] leading-[1.65] text-muted-foreground/70 select-none">
        {Array.from({ length: lines }, (_, i) => <div key={i} className="h-[1.65em] text-[12.5px] leading-[1.65]"><span className="text-[11px]">{i + 1}</span></div>)}
      </div>
      <textarea id={id} aria-label={label} value={value} spellCheck={false} wrap="off" autoCapitalize="off" autoCorrect="off"
        className="min-h-0 flex-1 resize-none bg-transparent px-3 py-2.5 whitespace-pre outline-none"
        onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop; }}
        onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
