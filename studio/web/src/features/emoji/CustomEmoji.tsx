// One custom emoji as Telegram would draw it: the pack's picture when the library has a preview,
// otherwise the fallback emoji with a violet dot ("custom emoji here, picture not available").
// Adaptive emoji (needs_repainting) take the text colour, like in Telegram: the picture is a mask.
import { cn } from "@/lib/utils";
import { useEmojiMaybe } from "./context";

export function CustomEmoji({ id, fallback, className, title }: { id: string; fallback?: string | null; className?: string; title?: string }) {
  const ctx = useEmojiMaybe();
  const entry = ctx?.index.get(id);
  const url = ctx?.src(id) ?? null;
  const fb = (fallback ?? entry?.fallback) || "⭐";
  const slot = ctx?.slotOf.get(id);
  const label = title ?? `Custom emoji ${id}${slot ? ` (${slot})` : ""}; without it users see ${fb}`;
  const box = cn("inline-block size-[1.2em] shrink-0 align-[-0.2em]", className);
  if (!url) {
    return (
      <span className="relative" title={`${label}. No picture in the library: import its pack on the Emoji page.`}>
        {fb}<span className="absolute -top-0.5 -right-1 size-1.5 rounded-full bg-violet-500" aria-hidden />
      </span>
    );
  }
  if (url.endsWith(".webm") || entry?.format === "video") {
    return <video src={url} className={cn(box, "object-contain")} autoPlay loop muted playsInline aria-label={fb} title={label} />;
  }
  if (entry?.adaptive) {
    return (
      <span role="img" aria-label={fb} title={label} className={box}
        style={{ backgroundColor: "currentColor", WebkitMaskImage: `url("${url}")`, maskImage: `url("${url}")`, WebkitMaskSize: "contain", maskSize: "contain", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat", WebkitMaskPosition: "center", maskPosition: "center" }} />
    );
  }
  return <img src={url} alt={fb} title={label} className={cn(box, "object-contain")} draggable={false} />;
}
