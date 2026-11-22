// The project's premium emoji library (emoji/library.json) for every surface: previews, the
// simulator, the inspector's pickers, the Emoji page and the agent prompt.
// Studio: loaded from /api/emoji, pictures from the local cache (/emoji-preview/<file>).
// Artifact: the snapshot's `emoji` block, pictures inlined as data: URLs.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorText } from "@/lib/api";
import type { Loaded } from "@/lib/model";

export type EmojiFormat = "static" | "animated" | "video";
export interface PackEmoji { id: string; fallback: string; format: EmojiFormat; adaptive: boolean }
export interface Pack { title: string; link: string; importedAt?: string; formats?: string[]; source?: string; emoji: PackEmoji[] }
export interface Icon { id: string; set: string; fallback: string; animated: boolean; adaptive: boolean; note?: string }
export interface Library { format: string; bot?: string; packs: Record<string, Pack>; icons: Record<string, Icon> }
export interface Slot { slot: string; group?: string; label?: string; unicode?: string[]; use?: string[]; note?: string }
export interface Use { screenId: string; pointer: string; id: string; fallback: string | null; where: "text" | "button" }
export interface Suggestion { slot: string; id: string; set: string; fallback: string }
export interface EmojiDoc {
  library: Library; previews: Record<string, string>; usage: Use[]; vocabulary: Slot[];
  suggestions: Suggestion[]; tokenEnv: string | null; error?: { code: string; message: string } | null;
}
export interface Entry extends PackEmoji { pack: string }

const EMPTY: EmojiDoc = { library: { format: "bot-ui-emoji/v1", packs: {}, icons: {} }, previews: {}, usage: [], vocabulary: [], suggestions: [], tokenEnv: null };

interface Ctx {
  doc: EmojiDoc;
  /** Studio: import, map and remove go to the server. Artifact: read-only. */
  editable: boolean;
  loading: boolean;
  index: Map<string, Entry>;
  /** id -> slot of the icon map */
  slotOf: Map<string, string>;
  src: (id: string) => string | null;
  refresh: () => Promise<void>;
  /** POST to an /api/emoji* endpoint; the answer carries the new library. */
  call: (path: string, body: unknown) => Promise<{ ok: boolean; data: any; error?: string }>;
}

const EmojiContext = createContext<Ctx | null>(null);

export function useEmoji(): Ctx {
  const ctx = useContext(EmojiContext);
  if (!ctx) throw new Error("useEmoji outside EmojiProvider");
  return ctx;
}

/** Optional variant for components that also render outside the provider (tests, isolated previews). */
export function useEmojiMaybe(): Ctx | null {
  return useContext(EmojiContext);
}

function buildIndex(lib: Library): Map<string, Entry> {
  const out = new Map<string, Entry>();
  for (const [name, pack] of Object.entries(lib.packs ?? {})) {
    for (const e of pack.emoji ?? []) if (!out.has(e.id)) out.set(e.id, { ...e, pack: name });
  }
  for (const icon of Object.values(lib.icons ?? {})) {
    if (!out.has(icon.id)) out.set(icon.id, { id: icon.id, fallback: icon.fallback, format: icon.animated ? "animated" : "static", adaptive: icon.adaptive, pack: icon.set });
  }
  return out;
}

export function EmojiProvider({ loaded, children }: { loaded: Loaded; children: ReactNode }) {
  const studio = loaded.mode === "studio";
  const [doc, setDoc] = useState<EmojiDoc>(() => ({ ...EMPTY, ...(loaded.emoji ?? {}) }));
  const [loading, setLoading] = useState(studio);

  const refresh = useCallback(async () => {
    if (!studio) return;
    setLoading(true);
    const res = await api<EmojiDoc>("/api/emoji");
    if (res.ok) setDoc({ ...EMPTY, ...res.data });
    setLoading(false);
  }, [studio]);

  useEffect(() => { void refresh(); }, [refresh, loaded.revision]);

  const call = useCallback(async (path: string, body: unknown) => {
    const res = await api(path, body);
    if (res.ok && res.data?.library) setDoc((d) => ({ ...d, ...res.data }));
    return { ok: res.ok, data: res.data, error: res.ok ? undefined : errorText(res.data) };
  }, []);

  const value = useMemo<Ctx>(() => {
    const index = buildIndex(doc.library);
    const slotOf = new Map(Object.entries(doc.library.icons ?? {}).map(([slot, i]) => [i.id, slot]));
    const src = (id: string) => {
      const p = doc.previews[id];
      if (!p) return null;
      return p.startsWith("data:") ? p : `/emoji-preview/${encodeURIComponent(p)}`;
    };
    return { doc, editable: studio, loading, index, slotOf, src, refresh, call };
  }, [doc, studio, loading, refresh, call]);

  return <EmojiContext.Provider value={value}>{children}</EmojiContext.Provider>;
}

export const tgEmojiHtml = (id: string, fallback: string) => `<tg-emoji emoji-id="${id}">${fallback || "⭐"}</tg-emoji>`;

/** Slots of the vocabulary that accept this ordinary emoji (variation selectors ignored). */
export function slotsForEmoji(vocab: Slot[], emoji: string): Slot[] {
  const key = (s: string) => s.replace(/[︎️]/g, "");
  const k = key(emoji);
  if (!k) return [];
  const first = vocab.filter((v) => v.unicode?.[0] && key(v.unicode[0]) === k);
  const rest = vocab.filter((v) => !first.includes(v) && v.unicode?.some((u) => key(u) === k));
  return [...first, ...rest];
}
