// The telegram-bot-ui emoji library's catalog on the Emoji page: filter every pack by style, colour, theme fit
// and motion, and narrow the pack picked for the project's screens with the same filters.
// The catalog and the pick come from the server (bot_ui/emoji_catalog.py): in the Studio through /api/emoji,
// in the single-file snapshot from its `emoji` block, so filtering never needs a network.

export const FILTER_FACETS = ["style", "color", "fit", "motion"] as const;
export type FilterFacet = (typeof FILTER_FACETS)[number];
/** [taxonomy value, confidence 0..1] */
export type Tag = [string, number];
export type Filters = Partial<Record<FilterFacet, string[]>>;

export interface PackDescription { what?: string; for?: string; not_for?: string }
export interface CatalogPack {
  name: string; category?: string; count?: number | null; meanings?: number | null;
  tags: Partial<Record<FilterFacet, Tag[]>>; description?: PackDescription;
}
export interface FacetInfo { label: string; values: { id: string; label: string }[] }
export interface Catalog {
  generated?: string | null; taxonomy?: number | null; source?: string | null;
  /** The library's pack threshold: a tag below it counts for nothing. */
  threshold: number;
  facets: Partial<Record<FilterFacet, FacetInfo>>;
  packs: CatalogPack[];
}
export interface PickRow {
  name: string; title?: string | null; link: string; score: number; why: string;
  description?: PackDescription | null;
  /** coverage mode: share of the screens' slots the pack has, and the ones it lacks */
  coverage?: number | null; missing?: string[] | null;
}
export interface Pick {
  /** coverage: matched by fallback emoji online; tags: ranked from the catalog by the slots' interface roles */
  mode: "coverage" | "tags"; slots: string[]; generated?: string | null; source?: string | null;
  packs: PickRow[]; notes?: string[];
}

export function hasTag(pack: CatalogPack, facet: FilterFacet, value: string, threshold: number): boolean {
  return (pack.tags[facet] ?? []).some(([v, c]) => v === value && c >= threshold);
}

/** Values of one facet add up (any of them), facets narrow down (all of them). `except` leaves one facet out. */
export function matches(pack: CatalogPack, filters: Filters, threshold: number, except?: FilterFacet): boolean {
  return FILTER_FACETS.every((f) => {
    const wanted = filters[f];
    return f === except || !wanted?.length || wanted.some((v) => hasTag(pack, f, v, threshold));
  });
}

export function filterPacks(catalog: Catalog, filters: Filters): CatalogPack[] {
  return catalog.packs.filter((p) => matches(p, filters, catalog.threshold));
}

export function isFiltered(filters: Filters): boolean {
  return FILTER_FACETS.some((f) => !!filters[f]?.length);
}

export function toggleFilter(filters: Filters, facet: FilterFacet, value: string): Filters {
  const now = filters[facet] ?? [];
  const next = now.includes(value) ? now.filter((v) => v !== value) : [...now, value];
  const out: Filters = { ...filters };
  if (next.length) out[facet] = next;
  else delete out[facet];
  return out;
}

export interface FacetOption { facet: FilterFacet; label: string; values: { id: string; label: string; count: number; active: boolean }[] }

/** Every filter facet with its values and how many packs each would leave, given the other facets' filters. */
export function facetOptions(catalog: Catalog, filters: Filters): FacetOption[] {
  const out: FacetOption[] = [];
  for (const facet of FILTER_FACETS) {
    const info = catalog.facets[facet];
    if (!info) continue;
    const pool = catalog.packs.filter((p) => matches(p, filters, catalog.threshold, facet));
    out.push({
      facet, label: info.label,
      values: info.values.map((v) => ({
        id: v.id, label: v.label, active: !!filters[facet]?.includes(v.id),
        count: pool.filter((p) => hasTag(p, facet, v.id, catalog.threshold)).length,
      })),
    });
  }
  return out;
}

/** The pick in its own order, narrowed by the filters. A pack the catalog does not list has unknown tags, so
 * any filter hides it. `hidden`: how many ranked packs the filters hide. */
export function filterPick(pick: Pick, catalog: Catalog, filters: Filters): { rows: PickRow[]; hidden: number } {
  if (!isFiltered(filters)) return { rows: pick.packs, hidden: 0 };
  const byName = new Map(catalog.packs.map((p) => [p.name, p]));
  const rows = pick.packs.filter((r) => {
    const p = byName.get(r.name);
    return !!p && matches(p, filters, catalog.threshold);
  });
  return { rows, hidden: pick.packs.length - rows.length };
}

/** The pick was made for other screens (their slots changed) or from another catalog build. */
export function pickIsStale(pick: Pick | null | undefined, screenSlots: string[], catalog: Catalog | null | undefined): boolean {
  if (!pick) return false;
  const sameSlots = pick.slots.length === screenSlots.length && pick.slots.every((s, i) => s === screenSlots[i]);
  return !sameSlots || (!!catalog?.generated && !!pick.generated && pick.generated !== catalog.generated);
}

export function facetValueLabel(catalog: Catalog, facet: FilterFacet, id: string): string {
  return catalog.facets[facet]?.values.find((v) => v.id === id)?.label ?? id;
}
