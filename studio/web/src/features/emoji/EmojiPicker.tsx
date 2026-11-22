// Pick a premium emoji from the project's library: the bot's icon map first (by meaning), then
// every imported pack. Used by the text fields (insert <tg-emoji>) and button icons.
import { Search, Smile } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { href } from "@/lib/route";
import { cn } from "@/lib/utils";
import { CustomEmoji } from "./CustomEmoji";
import { useEmoji } from "./context";

export interface Picked { id: string; fallback: string; slot?: string }

function Tile({ id, fallback, caption, selected, onPick }: { id: string; fallback: string; caption?: string; selected?: boolean; onPick: () => void }) {
  return (
    <button type="button" onClick={onPick} title={caption ? `${caption} · ${id}` : id}
      className={cn("flex flex-col items-center gap-0.5 rounded-md p-1 text-[10px] text-muted-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", selected && "bg-accent ring-1 ring-primary")}>
      <CustomEmoji id={id} fallback={fallback} className="size-7" title="" />
      {caption && <span className="w-full truncate text-center">{caption}</span>}
    </button>
  );
}

export function EmojiPicker({ onPick, selected, disabled, label = "Premium emoji", trigger, align = "end" }: {
  onPick: (p: Picked) => void; selected?: string | null; disabled?: boolean; label?: string; trigger?: ReactNode; align?: "start" | "end";
}) {
  const { doc, slotOf } = useEmoji();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const icons = Object.entries(doc.library.icons ?? {});
  const packs = Object.entries(doc.library.packs ?? {});
  const query = q.trim().toLowerCase();
  const match = (fallback: string, slot?: string, id?: string) =>
    !query || fallback.includes(q.trim()) || (slot ?? "").includes(query) || (id ?? "").startsWith(query);
  const shownIcons = useMemo(() => icons.filter(([slot, i]) => match(i.fallback, slot, i.id)), [icons, query]);
  const pick = (p: Picked) => { onPick(p); setOpen(false); };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        {trigger ?? (
          <Button type="button" size="sm" variant="ghost" className="h-6 px-1.5 text-[11px]" disabled={disabled}>
            <Smile className="size-3" /> {label}
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent align={align} className="w-80 p-2">
        {!icons.length && !packs.length ? (
          <div className="space-y-2 p-1 text-sm">
            <p>No premium emoji in this project yet.</p>
            <p className="text-xs text-muted-foreground">Import a pack by its link (t.me/addemoji/…) on the Emoji page; its emoji appear here.</p>
            <a href={href("emoji")} className="inline-block text-xs font-medium underline" onClick={() => setOpen(false)}>Open the Emoji page</a>
          </div>
        ) : (
          <>
            <div className="relative mb-2">
              <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Meaning, emoji or id" className="h-8 pl-7 text-xs" aria-label="Search premium emoji" autoFocus />
            </div>
            <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
              {shownIcons.length > 0 && (
                <section>
                  <h4 className="mb-1 text-[11px] font-medium text-muted-foreground">This bot's icons (by meaning)</h4>
                  <div className="grid grid-cols-5 gap-0.5">
                    {shownIcons.map(([slot, i]) => <Tile key={slot} id={i.id} fallback={i.fallback} caption={slot} selected={selected === i.id}
                      onPick={() => pick({ id: i.id, fallback: i.fallback, slot })} />)}
                  </div>
                </section>
              )}
              {packs.map(([name, pack]) => {
                const list = pack.emoji.filter((e) => match(e.fallback, slotOf.get(e.id), e.id));
                if (!list.length) return null;
                return (
                  <section key={name}>
                    <h4 className="mb-1 truncate text-[11px] font-medium text-muted-foreground" title={pack.link}>{pack.title} · {list.length}</h4>
                    <div className="grid grid-cols-7 gap-0.5">
                      {list.map((e) => <Tile key={e.id} id={e.id} fallback={e.fallback} selected={selected === e.id}
                        onPick={() => pick({ id: e.id, fallback: e.fallback, slot: slotOf.get(e.id) })} />)}
                    </div>
                  </section>
                );
              })}
            </div>
            <p className="mt-2 border-t pt-1.5 text-[10.5px] text-muted-foreground">Pick from the bot's icons when one fits the meaning: the same meaning keeps the same icon on every screen.</p>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
