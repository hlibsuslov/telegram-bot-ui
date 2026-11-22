import { ChevronDown, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** One numbered, collapsible step of the flow. */
export function Step({ n, icon: Icon, title, hint, open, onToggle, children, right }: { n: number; icon: LucideIcon; title: string; hint: string; open: boolean; onToggle: () => void; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="rounded-2xl bg-card ring-1 ring-border" aria-labelledby={`wstep-${n}`}>
      <div className="flex items-start gap-3 p-4">
        <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={`wstep-${n}-body`} className="flex min-w-0 flex-1 items-start gap-3 text-left">
          <span className={cn("relative flex size-8 shrink-0 items-center justify-center rounded-xl", open ? "bg-foreground text-background" : "bg-muted text-muted-foreground")}>
            <Icon className="size-4" aria-hidden />
            <span className="absolute -top-1.5 -right-1.5 flex size-4 items-center justify-center rounded-full bg-background font-mono text-[9.5px] font-semibold text-foreground ring-1 ring-border">{n}</span>
          </span>
          <span className="min-w-0 flex-1">
            <span id={`wstep-${n}`} className="block text-[15px] font-semibold tracking-tight">{title}</span>
            <span className="block text-xs text-muted-foreground">{hint}</span>
          </span>
          <ChevronDown className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
        </button>
        {right}
      </div>
      {open && <div id={`wstep-${n}-body`} className="space-y-4 px-4 pb-5 sm:pl-14">{children}</div>}
    </section>
  );
}

