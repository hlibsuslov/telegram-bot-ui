// Telegram look, drawn locally (no Telegram assets): bot text goes through telegramHtmlToSafe into
// React elements, never into innerHTML. Links are shown, not followed.
import { useState, type ReactNode } from "react";
import { CheckCheck, CornerUpLeft, ExternalLink, Puzzle, Send, SquareSlash } from "lucide-react";
import { type Logical, telegramHtmlToSafe } from "@/core/render.ts";
import { cn } from "@/lib/utils";

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

export function Bubble({ logical, onPress, edited, meta, widget, hl, clampText, buttonSlot, tail = true, time = "10:00" }: BubbleProps) {
  return (
    <div className="w-full">
      <div className="tg-bubble px-2.5 pt-1.5 pb-1" data-tail={tail}>
        {widget && (
          <div className="mb-1.5 flex items-center gap-2 rounded-lg bg-[color-mix(in_srgb,var(--tg-theme-button-color)_12%,transparent)] px-2 py-1.5 text-[12.5px]">
            <Puzzle className="size-4 shrink-0 text-[var(--tg-theme-button-color)]" aria-hidden />
            <span className="min-w-0"><span className="block font-medium">Widget</span><span className="tg-hint block truncate font-mono text-[11px]">{widget}</span></span>
          </div>
        )}
        <div data-hl={hl?.text || undefined} className={cn("rounded", clampText && "relative max-h-[176px] overflow-hidden")}>
          <MessageText text={logical.text} format={logical.format} />
          {clampText && <div className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-[var(--tg-theme-bg-color)] to-transparent" />}
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
