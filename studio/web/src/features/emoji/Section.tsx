import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** One block of the Emoji page: icon, title with a count, a hint, actions on the right. */
export function Section({ icon: Icon, title, hint, count, children, actions }: { icon: LucideIcon; title: string; hint: string; count?: number; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="space-y-3 rounded-xl p-4 ring-1 ring-border">
      <div className="flex flex-wrap items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted"><Icon className="size-4" aria-hidden /></span>
        <div className="min-w-0 flex-1">
          <h3 className="flex items-baseline gap-2 text-[15px] font-semibold tracking-tight">{title}{count !== undefined && <span className="rounded-full bg-muted px-2 text-xs font-medium text-muted-foreground">{count}</span>}</h3>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
