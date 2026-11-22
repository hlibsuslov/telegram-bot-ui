import { useEffect, useState } from "react";

export type Section = "map" | "screens" | "simulator" | "widgets" | "changes" | "about";
export interface Route { section: Section; id: string | null }

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").map((p) => decodeURIComponent(p));
  const [head, id] = parts;
  if (head === "screen" || head === "screens") return { section: "screens", id: id || null };
  if (head === "widgets" || head === "widget") return { section: "widgets", id: id || null };
  if (head === "simulator" || head === "changes" || head === "about" || head === "map") return { section: head, id: id || null };
  return { section: "map", id: null };
}

export function href(section: Section, id?: string | null): string {
  if (section === "screens" && id) return `#/screen/${encodeURIComponent(id)}`;
  if (section === "widgets" && id) return `#/widgets/${encodeURIComponent(id)}`;
  return `#/${section}`;
}

export function go(section: Section, id?: string | null) {
  const next = href(section, id);
  if (location.hash !== next) location.hash = next;
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(location.hash));
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  return route;
}
