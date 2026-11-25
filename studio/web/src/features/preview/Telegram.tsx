// Telegram look, drawn locally (no Telegram assets): bot text goes through telegramHtmlToSafe into
// React elements, never into innerHTML. Links are shown, not followed.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  CheckCheck, Clapperboard, CornerUpLeft, ExternalLink, EyeOff, Film, Image as ImageIcon, Mic, Music, Play, Puzzle, Send, SquareSlash, Sticker, Video,
} from "lucide-react";
import { type Logical, type Media, telegramHtmlToSafe } from "@/core/render.ts";
import { cn } from "@/lib/utils";
import { CustomEmoji } from "@/features/emoji/CustomEmoji";
import { RichText } from "./RichText";

type SafeNode = ReturnType<typeof telegramHtmlToSafe>[number];

function Spoiler({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span role="button" tabIndex={0} className="tg-spoiler" data-open={open} aria-label={open ? undefined : "Spoiler, press to reveal"}
      onClick={(e) => { e.stopPropagation(); setOpen(true); }}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(true); } }}>
      <span style={{ visibility: open ? "visible" : "hidden" }}>{children}</span>
    </span>
  );
}

function renderNodes(nodes: SafeNode[] | undefined, key = "n"): ReactNode[] {
  return (nodes ?? []).map((n, i) => {
    const k = `${key}.${i}`;
    const kids = renderNodes(n.children, k);
    switch (n.tag) {
      case "#text": return <span key={k}>{n.text}</span>;
      case "b": case "strong": return <b key={k} className="font-semibold">{kids}</b>;
      case "i": case "em": return <i key={k}>{kids}</i>;
      case "u": case "ins": return <u key={k}>{kids}</u>;
      case "s": case "strike": case "del": return <s key={k}>{kids}</s>;
      case "code": return <code key={k}>{kids}</code>;
      case "pre": return <pre key={k}>{kids}</pre>;
      case "blockquote": return <blockquote key={k}>{kids}</blockquote>;
      case "tg-spoiler": return <Spoiler key={k}>{kids}</Spoiler>;
      case "tg-emoji": return n.emojiId
        ? <CustomEmoji key={k} id={n.emojiId} fallback={(n.children ?? []).map((c) => c.text ?? "").join("")} />
        : <span key={k} className="relative" title="Custom emoji without a valid emoji-id: users see this emoji">{kids}<span className="absolute -top-0.5 -right-1 size-1.5 rounded-full bg-violet-500" aria-hidden /></span>;
      case "a": return <span key={k} className="tg-link" title={n.href ? `Link: ${n.href} (not followed in the preview)` : undefined}>{kids}</span>;
      default: return <span key={k}>{kids}</span>;
    }
  });
}

export function MessageText({ text, format, className }: { text: string; format: string; className?: string }) {
  return <div className={cn("text-[14.5px] leading-[1.38] break-words whitespace-pre-wrap", className)}>{renderNodes(telegramHtmlToSafe(text, format))}</div>;
}

export interface Hl { text?: boolean; actionId?: string; keyboard?: boolean; input?: boolean }

export interface BubbleProps {
  logical: Logical;
  onPress?: (actionId: string) => void;
  edited?: boolean;
  meta?: ReactNode;
  widget?: string | null;
  hl?: Hl;
  clampText?: boolean;
  /** Extra content inside each inline button (map ports). */
  buttonSlot?: (actionId: string) => ReactNode;
  tail?: boolean;
  time?: string;
}

export function InlineKeyboard({ logical, onPress, hl, buttonSlot }: Pick<BubbleProps, "logical" | "onPress" | "hl" | "buttonSlot">) {
  const rows = logical.keyboard.type === "inline" ? logical.keyboard.rows : [];
  if (!rows.length) return null;
  return (
    <div className="mt-1 flex flex-col gap-1" role="group" aria-label="Inline keyboard" data-hl={hl?.keyboard || undefined}>
      {rows.map((row, r) => (
        <div key={r} className="flex gap-1">
          {row.map((b) => (
            <button key={b.actionId} type="button" data-action={b.actionId}
              className={cn("tg-inline-btn relative flex min-h-[34px] min-w-0 flex-1 items-center justify-center gap-1 px-2 py-1 text-[13.5px] font-medium", !onPress && "cursor-default")}
              data-style={b.style} data-hl={hl?.actionId === b.actionId || undefined}
              onClick={onPress ? (e) => { e.stopPropagation(); onPress(b.actionId); } : undefined}
              title={b.url ? `Opens ${b.url} (not followed)` : b.callbackData ? `callback_data ${b.callbackData}` : undefined}>
              {b.icon && <CustomEmoji id={b.icon} className="size-[1.15em]" />}
              <span className="truncate">{b.text}</span>
              {b.url && <ExternalLink className="absolute top-1 right-1 size-2.5 shrink-0" aria-hidden />}
              {buttonSlot?.(b.actionId)}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

/** The message body: Rich HTML (with its in-document buttons) or regular text. */
function Body({ logical, onPress, hl, buttonSlot }: Pick<BubbleProps, "logical" | "onPress" | "hl" | "buttonSlot">) {
  return logical.format === "rich.html"
    ? <RichText html={logical.text} buttons={logical.richButtons} onPress={onPress} hlAction={hl?.actionId} buttonSlot={buttonSlot} />
    : <MessageText text={logical.text} format={logical.format} />;
}

/** Six lines and an ellipsis; "more" opens the full text over the bubble without changing its size. */
function ClampedText({ logical, onPress, hl }: Pick<BubbleProps, "logical" | "onPress" | "hl">) {
  const { text, format } = logical;
  const ref = useRef<HTMLDivElement>(null);
  const [over, setOver] = useState(false);
  const [open, setOpen] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el) setOver(el.scrollHeight > el.clientHeight + 1);
  }, [text, format]);
  return (
    <div className="relative">
      <div ref={ref} className="overflow-hidden [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:6]">
        <Body logical={logical} onPress={onPress} hl={hl} />
      </div>
      {over && (
        <button type="button" className="nodrag mt-0.5 text-[12px] font-medium text-[var(--tg-theme-link-color)]" aria-expanded={open}
          onClick={(e) => { e.stopPropagation(); setOpen(true); }}>more</button>
      )}
      {open && (
        <div className="nodrag nowheel absolute -inset-x-1.5 -top-1 z-20 max-h-80 overflow-y-auto rounded-xl bg-[var(--tg-theme-bg-color)] p-2 shadow-xl ring-1 ring-black/10"
          onClick={(e) => e.stopPropagation()}>
          <Body logical={logical} onPress={onPress} hl={hl} />
          <button type="button" className="mt-1 text-[12px] font-medium text-[var(--tg-theme-link-color)]" onClick={() => setOpen(false)} autoFocus>less</button>
        </div>
      )}
    </div>
  );
}

const MEDIA_ICON: Record<string, typeof Puzzle> = { photo: ImageIcon, video: Film, animation: Clapperboard, audio: Music, voice: Mic, video_note: Video, sticker: Sticker };

function mediaLabel(m: Media): string {
  if (m.source === "missing" || m.file === null) return m.source === "field" ? "field: no value in this run" : "no file";
  if (m.source === "fileId") return `file_id ${m.file.length > 14 ? `${m.file.slice(0, 12)}…` : m.file}`;
  if (m.source === "url") { try { return `URL ${new URL(m.file).host}`; } catch { return "URL"; } }
  return `field value ${m.file.length > 18 ? `${m.file.slice(0, 16)}…` : m.file}`;
}

/** A drawn stand-in for the media (nothing is downloaded): type icon, source label, spoiler blur. */
export function MediaCard({ media, compact }: { media: Media; compact?: boolean }) {
  return <div data-media={media.type} className="contents"><MediaInner media={media} compact={compact} /></div>;
}

function MediaInner({ media, compact }: { media: Media; compact?: boolean }) {
  const Icon = MEDIA_ICON[media.type] ?? ImageIcon;
  const label = mediaLabel(media);
  if (media.type === "sticker") {
    return <div className="flex flex-col items-start gap-0.5"><span className={compact ? "text-5xl" : "text-7xl"} role="img" aria-label={`sticker ${media.emoji ?? ""}`}>{media.emoji ?? "🙂"}</span><span className="tg-service rounded-full px-2 py-0.5 text-[10.5px]">sticker · {label}</span></div>;
  }
  if (media.type === "video_note") {
    return (
      <div className="flex flex-col items-start gap-1">
        <div className={cn("flex items-center justify-center rounded-full bg-gradient-to-br from-slate-500 to-slate-700 text-white shadow", compact ? "size-28" : "size-40")} aria-label="round video message"><Video className="size-8" /></div>
        <span className="tg-service rounded-full px-2 py-0.5 text-[10.5px]">video message · {label}</span>
      </div>
    );
  }
  if (media.type === "voice" || media.type === "audio") {
    return (
      <div className="mb-1 flex items-center gap-2.5">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--tg-theme-button-color)] text-white">{media.type === "voice" ? <Play className="size-4" /> : <Music className="size-4" />}</span>
        <span className="min-w-0 flex-1">
          {media.type === "voice"
            ? <span className="flex h-5 items-end gap-0.5" aria-label="voice message">{[3, 6, 9, 5, 11, 7, 4, 8, 12, 6, 3, 7, 10, 5].map((h, i) => <span key={i} className="w-0.5 rounded-full bg-[var(--tg-theme-button-color)]" style={{ height: h + 4 }} />)}</span>
            : <span className="block text-[13.5px] font-medium">Audio</span>}
          <span className="tg-hint block truncate text-[11px]">{label}</span>
        </span>
      </div>
    );
  }
  return (
    <div className={cn("relative -mx-2.5 -mt-1.5 mb-1.5 flex flex-col items-center justify-center gap-1 overflow-hidden rounded-t-[14px] bg-gradient-to-br from-slate-300 to-slate-400 text-slate-700 dark:from-slate-600 dark:to-slate-700 dark:text-slate-100", compact ? "h-28" : "h-40")}>
      <Icon className="size-8" aria-hidden />
      <span className="text-[11px] font-medium">{media.type}</span>
      <span className="rounded-full bg-black/40 px-2 py-0.5 text-[10.5px] text-white">{label}</span>
      {media.spoiler && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/30 backdrop-blur-md" aria-label="spoiler: blurred until tapped">
          <span className="flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[11px] text-white"><EyeOff className="size-3" /> spoiler</span>
        </div>
      )}
    </div>
  );
}

export function Bubble({ logical, onPress, edited, meta, widget, hl, clampText, buttonSlot, tail = true, time = "10:00" }: BubbleProps) {
  const media = logical.media;
  if (media && (media.type === "sticker" || media.type === "video_note")) {
    return (
      <div className="w-full">
        <div className="flex items-end gap-2"><MediaCard media={media} compact={clampText} /><span className="tg-service mb-1 rounded-full px-1.5 py-0.5 text-[10.5px]">{edited ? "edited · " : ""}{time}</span></div>
        <InlineKeyboard logical={logical} onPress={onPress} hl={hl} buttonSlot={buttonSlot} />
      </div>
    );
  }
  return (
    <div className="w-full">
      <div className="tg-bubble overflow-hidden px-2.5 pt-1.5 pb-1" data-tail={tail}>
        {media && <MediaCard media={media} compact={clampText} />}
        {widget && (
          <div className="mb-1.5 flex items-center gap-2 rounded-lg bg-[color-mix(in_srgb,var(--tg-theme-button-color)_12%,transparent)] px-2 py-1.5 text-[12.5px]">
            <Puzzle className="size-4 shrink-0 text-[var(--tg-theme-button-color)]" aria-hidden />
            <span className="min-w-0"><span className="block font-medium">Widget</span><span className="tg-hint block truncate font-mono text-[11px]">{widget}</span></span>
          </div>
        )}
        <div data-hl={hl?.text || undefined} className="rounded">
          {/* A rich document is not clamped: its buttons carry map ports that must stay visible. */}
          {clampText && logical.format !== "rich.html" ? <ClampedText logical={logical} onPress={onPress} hl={hl} />
            : <Body logical={logical} onPress={onPress} hl={hl} buttonSlot={buttonSlot} />}
        </div>
        <div className="tg-meta float-right -mb-0.5 ml-2 flex translate-y-0.5 items-center gap-1 pt-0.5 text-[11px]">
          {meta}
          {edited && <span>edited</span>}
          <span>{time}</span>
        </div>
        <div className="clear-both" />
      </div>
      <InlineKeyboard logical={logical} onPress={onPress} hl={hl} buttonSlot={buttonSlot} />
    </div>
  );
}

export function OutgoingBubble({ text, time = "10:00" }: { text: string; time?: string }) {
  return (
    <div className="tg-bubble ml-auto max-w-[80%] px-2.5 pt-1.5 pb-1" data-out="true" data-tail="true">
      <span className="text-[14.5px] leading-[1.38] break-words whitespace-pre-wrap">{text}</span>
      <span className="tg-meta float-right ml-2 flex translate-y-1 items-center gap-0.5 text-[11px]">{time}<CheckCheck className="size-3.5" aria-label="read" /></span>
      <div className="clear-both" />
    </div>
  );
}

export function ReplyKeyboard({ logical, onKey, hl, buttonSlot }: { logical: Logical; onKey?: (text: string) => void; hl?: Hl; buttonSlot?: (actionId: string) => ReactNode }) {
  return (
    <div className="tg-panel flex flex-col gap-1.5 p-1.5" role="group" aria-label="Reply keyboard" data-hl={hl?.keyboard || undefined}>
      {logical.keyboard.rows.map((row, r) => (
        <div key={r} className="flex gap-1.5">
          {row.map((b) => (
            <button key={b.actionId} type="button" className="tg-key relative min-h-10 min-w-0 flex-1 truncate px-2 text-[14px]"
              data-hl={hl?.actionId === b.actionId || undefined}
              onClick={onKey ? (e) => { e.stopPropagation(); onKey(b.text); } : undefined}>
              {b.icon && <CustomEmoji id={b.icon} className="mr-1 size-[1.15em]" />}
              {b.text}
              {buttonSlot?.(b.actionId)}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function ForceReplyBar({ placeholder, hl }: { placeholder: string; hl?: boolean }) {
  return (
    <div className="tg-panel flex items-center gap-2 px-3 py-1.5 text-[12.5px]" data-hl={hl || undefined}>
      <CornerUpLeft className="size-4 text-[var(--tg-theme-button-color)]" aria-hidden />
      <span className="min-w-0"><span className="block font-medium text-[var(--tg-theme-button-color)]">Reply to the bot</span><span className="tg-hint block truncate">{placeholder}</span></span>
    </div>
  );
}

export function Composer({ placeholder, disabled, onSend, onMenu }: { placeholder: string; disabled?: boolean; onSend?: (text: string) => void; onMenu?: () => void }) {
  const [text, setText] = useState("");
  return (
    <form className="flex items-center gap-1.5 bg-[var(--tg-theme-bg-color)] px-2 py-1.5"
      onSubmit={(e) => { e.preventDefault(); if (!text.trim() || !onSend) return; onSend(text); setText(""); }}>
      <button type="button" onClick={onMenu} disabled={disabled || !onMenu} aria-label="Bot menu: commands"
        className="flex h-8 items-center gap-1 rounded-full bg-[var(--tg-theme-button-color)] px-2.5 text-[13px] font-medium text-[var(--tg-theme-button-text-color)] disabled:opacity-50">
        <SquareSlash className="size-4" aria-hidden /> Menu
      </button>
      <input className="min-w-0 flex-1 bg-transparent px-1.5 py-1.5 text-[14.5px] text-[var(--tg-theme-text-color)] outline-none placeholder:text-[var(--tg-theme-hint-color)] focus-visible:outline-none"
        placeholder={placeholder} aria-label="Message text" value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} />
      <button type="submit" disabled={disabled || !text.trim()} aria-label="Send" className="flex size-8 items-center justify-center rounded-full text-[var(--tg-theme-button-color)] disabled:opacity-40">
        <Send className="size-5" />
      </button>
    </form>
  );
}

/** One screen as it arrives in a chat: bubble, inline or reply keyboard, ForceReply bar. */
export function ScreenPreview({ logical, theme, contextLabel, hideWidget, hl, className }: {
  logical: Logical; theme: "light" | "dark"; contextLabel: string; hideWidget?: boolean; hl?: Hl; className?: string;
}) {
  const kt = logical.keyboard.type;
  return (
    <figure className={cn("overflow-hidden rounded-xl border", className)}>
      <div className="tg tg-wallpaper flex flex-col" data-theme={theme}>
        <div className="flex flex-col justify-end gap-2 py-3 pr-6 pl-4">
          <div className="max-w-[340px]"><Bubble logical={logical} widget={hideWidget ? null : logical.widget} hl={hl} /></div>
        </div>
        {kt === "force_reply" && <ForceReplyBar placeholder={logical.keyboard.placeholder || "Reply…"} hl={hl?.input} />}
        {kt === "reply" && <ReplyKeyboard logical={logical} hl={hl} />}
        {kt === "remove" && <p className="tg-service mx-auto mb-2 rounded-full px-2.5 py-0.5 text-[11px]">removes the reply keyboard</p>}
      </div>
      <PreviewCaption contextLabel={contextLabel} />
    </figure>
  );
}

export function PreviewCaption({ contextLabel }: { contextLabel: string }) {
  return (
    <figcaption className="flex flex-wrap items-center justify-between gap-1 border-t bg-muted/40 px-3 py-1.5 text-[11px] text-muted-foreground">
      <span className="font-medium">Local preview, not Telegram</span>
      <span>{contextLabel}</span>
    </figcaption>
  );
}
