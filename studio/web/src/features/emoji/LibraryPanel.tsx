// "Find a pack by tags" on the Emoji page: the emoji library's packs filtered by style, colour, theme fit and
// motion, and the pack picked for the slots this project's screens use. Studio: loading and picking ask the
// server (network only on these clicks, or none with --emoji-library-file). Snapshot: the embedded catalog
// and pick, filtered in the page.
import { Download, Filter, Loader2, RefreshCw, Tags, Wand2, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { useEmoji } from "./context";
import {
  FILTER_FACETS, facetOptions, facetValueLabel, filterPacks, filterPick, isFiltered, pickIsStale, toggleFilter,
  type Catalog, type CatalogPack, type FacetOption, type FilterFacet, type Filters, type PickRow,
} from "./library.ts";
import { Section } from "./Section";

const PAGE = 12;

function FilterBar({ options, onToggle }: { options: FacetOption[]; onToggle: (facet: FilterFacet, value: string) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {options.map((o) => {
        const values = o.values.filter((v) => v.count > 0 || v.active);
        return (
          <fieldset key={o.facet} className="min-w-0 space-y-1.5">
            <legend className="text-xs font-medium text-muted-foreground">{o.label}</legend>
            <div className="flex flex-wrap gap-1.5">
              {values.map((v) => (
                <button key={v.id} type="button" aria-pressed={v.active} onClick={() => onToggle(o.facet, v.id)}
                  className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    v.active && "border-primary bg-primary/10 font-medium text-foreground")}>
                  {o.facet === "color" && <span className="size-2.5 rounded-full ring-1 ring-border" style={{ background: v.id }} aria-hidden />}
                  {v.label}
                  <span className="text-muted-foreground tabular-nums">{v.count}</span>
                </button>
              ))}
              {!values.length && <span className="text-xs text-muted-foreground">No pack left with these filters.</span>}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}

function Description({ d }: { d?: { what?: string; for?: string; not_for?: string } | null }) {
  if (!d) return null;
  return (
    <div className="space-y-0.5 text-xs">
      {d.what && <p>{d.what}</p>}
      {d.for && <p className="text-muted-foreground"><span className="font-medium text-foreground">For:</span> {d.for}</p>}
      {d.not_for && <p className="text-muted-foreground"><span className="font-medium text-foreground">Not for:</span> {d.not_for}</p>}
    </div>
  );
}

function TagList({ catalog, pack }: { catalog: Catalog; pack: CatalogPack }) {
  const tags = FILTER_FACETS.flatMap((f) => (pack.tags[f] ?? []).slice(0, 2).map(([v]) => ({ f, v })));
  if (!tags.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map(({ f, v }) => <span key={`${f}:${v}`} className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{facetValueLabel(catalog, f, v)}</span>)}
    </div>
  );
}

function ImportButton({ name }: { name: string }) {
  const { doc, call, editable } = useEmoji();
  const { notify } = useStudio();
  const [busy, setBusy] = useState(false);
  if (!editable || doc.library.packs[name] || !(doc.resolver || doc.tokenEnv)) return null;
  const run = async () => {
    setBusy(true);
    const res = await call("/api/emoji/import", { link: `https://t.me/addemoji/${name}` });
    setBusy(false);
    if (!res.ok) notify(res.error ?? "import failed", "error");
    else notify(`${res.data.title}: ${res.data.count} emoji`, "success");
  };
  return (
    <Button size="xs" variant="outline" disabled={busy} onClick={() => void run()} aria-label={`Import ${name}`}>
      {busy ? <Loader2 className="animate-spin" /> : <Download />} Import
    </Button>
  );
}

function PickRowItem({ row, rank, slots, catalog }: { row: PickRow; rank: number; slots: number; catalog: Catalog }) {
  const pack = catalog.packs.find((p) => p.name === row.name);
  const covered = row.coverage != null ? Math.round(row.coverage * slots) : null;
  // The reason line already ends with "For: …" from the description; show that part once.
  const d = row.description;
  const description = d?.for && row.why.endsWith(`For: ${d.for}`) ? { ...d, for: undefined } : d;
  return (
    <li className="space-y-1.5 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="w-5 text-xs text-muted-foreground tabular-nums">{rank}.</span>
        <a href={row.link} target="_blank" rel="noreferrer noopener" className="min-w-0 truncate text-sm font-medium underline-offset-2 hover:underline">{row.title || row.name}</a>
        {covered != null && (
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", covered === slots ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
            covers {covered}/{slots}
          </span>
        )}
        <span className="ml-auto"><ImportButton name={row.name} /></span>
      </div>
      <p className="text-xs break-words text-muted-foreground">{row.why}</p>
      {!!row.missing?.length && <p className="text-xs text-muted-foreground">Missing: {row.missing.join(", ")}</p>}
      <Description d={description} />
      {pack && <TagList catalog={catalog} pack={pack} />}
    </li>
  );
}

function PickBlock({ catalog, filters }: { catalog: Catalog; filters: Filters }) {
  const { doc, editable, call } = useEmoji();
  const { notify } = useStudio();
  const [busy, setBusy] = useState(false);
  const slots = doc.screenSlots ?? [];
  const pick = doc.pick ?? null;
  const online = !!doc.resolver || !!doc.libraryFile;
  const stale = pickIsStale(pick, slots, catalog);
  const run = async () => {
    setBusy(true);
    const res = await call("/api/emoji/pick", {});
    setBusy(false);
    if (!res.ok) notify(res.error ?? "pick failed", "error");
    else notify(`${res.data.pick?.packs?.length ?? 0} packs ranked for ${slots.length} slots`, "success");
  };
  const shown = pick ? filterPick(pick, catalog, filters) : null;
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <h4 className="flex items-center gap-1.5 text-sm font-semibold"><Wand2 className="size-4" aria-hidden /> Pick a pack for this project's screens</h4>
          <p className="text-xs text-muted-foreground">
            {slots.length ? <>Your screens use {slots.length} icon meaning{slots.length === 1 ? "" : "s"}: <span className="text-foreground">{slots.join(", ")}</span>.</> : "Your screens use no emoji with a known meaning yet: packs are ranked for interface icons in general."}
          </p>
        </div>
        {editable && (
          <Button size="sm" disabled={busy || !online} onClick={() => void run()}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : pick ? <RefreshCw className="size-4" /> : <Wand2 className="size-4" />}
            {busy ? "Ranking packs…" : pick ? "Pick again" : "Pick a pack"}
          </Button>
        )}
      </div>
      {stale && <p className="text-xs text-amber-700 dark:text-amber-400">The screens or the library changed since this pick{editable ? ": pick again." : "."}</p>}
      {pick && shown ? (
        <>
          <p className="text-xs text-muted-foreground">
            {pick.mode === "coverage" ? "Each slot matched to every candidate pack by its emoji: coverage first, then style and theme fit." : "Ranked from the catalog by the roles of these slots (the offline catalog has no fallback emoji, so coverage is not checked)."}
            {shown.hidden > 0 && ` ${shown.hidden} ranked pack${shown.hidden === 1 ? " is" : "s are"} hidden by the filters.`}
          </p>
          {shown.rows.length ? (
            <ol className="divide-y rounded-lg bg-background ring-1 ring-border">
              {shown.rows.map((r) => <PickRowItem key={r.name} row={r} rank={pick.packs.indexOf(r) + 1} slots={pick.slots.length} catalog={catalog} />)}
            </ol>
          ) : <p className="text-xs text-muted-foreground">No ranked pack has these tags; the packs below do.</p>}
          {!!pick.notes?.length && <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">{pick.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
        </>
      ) : !editable && <p className="text-xs text-muted-foreground">This snapshot has no pick: pick in the local Studio, then export again.</p>}
    </div>
  );
}

function PackList({ catalog, packs }: { catalog: Catalog; packs: CatalogPack[] }) {
  const [limit, setLimit] = useState(PAGE);
  if (!packs.length) return <p className="text-sm text-muted-foreground">No pack carries every chosen tag. Clear a filter.</p>;
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">Packs with these tags</h4>
      <ul className="divide-y rounded-lg ring-1 ring-border">
        {packs.slice(0, limit).map((p) => (
          <li key={p.name} className="space-y-1 px-3 py-2">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <a href={`https://t.me/addemoji/${p.name}`} target="_blank" rel="noreferrer noopener" className="min-w-0 truncate text-sm font-medium underline-offset-2 hover:underline">{p.name}</a>
              <span className="text-xs text-muted-foreground">{[p.category, p.count != null ? `${p.count} emoji` : ""].filter(Boolean).join(" · ")}</span>
              <span className="ml-auto"><ImportButton name={p.name} /></span>
            </div>
            {p.description?.what && <p className="text-xs">{p.description.what}</p>}
            <TagList catalog={catalog} pack={p} />
          </li>
        ))}
      </ul>
      {packs.length > limit && <Button size="sm" variant="ghost" onClick={() => setLimit((n) => n + PAGE * 2)}>Show more ({packs.length - limit} left)</Button>}
    </div>
  );
}

export function LibraryPanel() {
  const { doc, editable, call } = useEmoji();
  const { notify } = useStudio();
  const [filters, setFilters] = useState<Filters>({});
  const [busy, setBusy] = useState(false);
  const catalog = doc.catalog ?? null;
  const hint = "Every pack of the telegram-bot-ui emoji library by its tags. Values in one group add up, groups narrow down.";
  if (!catalog) {
    const online = !!doc.resolver || !!doc.libraryFile;
    const load = async () => {
      setBusy(true);
      const res = await call("/api/emoji/library", {});
      setBusy(false);
      if (!res.ok) notify(res.error ?? "the library did not load", "error");
    };
    return (
      <Section icon={Tags} title="Find a pack by tags" hint={hint}>
        {editable ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 flex-1 text-xs text-muted-foreground">
              {doc.libraryFile ? "Reads the tags of every pack from the offline export this Studio was started with."
                : doc.resolver ? <>Reads the tags of every pack from {doc.resolver}. Nothing about your bot is sent.</>
                : <>The library is off here (<span className="font-mono">BOT_UI_EMOJI_RESOLVER=off</span>): start the Studio with <span className="font-mono">--emoji-library-file emoji-library.ndjson.gz</span>.</>}
            </p>
            <Button size="sm" disabled={busy || !online} onClick={() => void load()}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />} {busy ? "Loading…" : "Load the library"}
            </Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">This snapshot carries no library tags. Load the library on the Emoji page of the local Studio, or export with <span className="font-mono">--emoji-library-file</span>.</p>
        )}
      </Section>
    );
  }
  const packs = filterPacks(catalog, filters);
  const filtered = isFiltered(filters);
  return (
    <Section icon={Filter} title="Find a pack by tags" count={packs.length} hint={hint}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-[11px] text-muted-foreground">
          {catalog.packs.length} packs · library build {catalog.generated ?? "?"} · {catalog.source === "export" ? "from the offline export" : "from the online library"}
        </p>
        {filtered && <Button size="xs" variant="ghost" onClick={() => setFilters({})}><X /> Clear filters</Button>}
      </div>
      <FilterBar options={facetOptions(catalog, filters)} onToggle={(f, v) => setFilters((cur) => toggleFilter(cur, f, v))} />
      <PickBlock catalog={catalog} filters={filters} />
      <PackList catalog={catalog} packs={packs} />
    </Section>
  );
}
