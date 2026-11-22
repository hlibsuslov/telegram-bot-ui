// Telegram look, local only: bot text goes through telegramHtmlToSafe into React elements,
// never into innerHTML. Links are shown, not followed.
import { useState, type ReactNode } from "react";
import { ExternalLink, Pencil } from "lucide-react";
import { type Logical, telegramHtmlToSafe } from "@/core/render.ts";
import { cn } from "@/lib/utils";

type SafeNode = ReturnType<typeof telegramHtmlToSafe>[number];

function Spoiler({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      role="button"
      tabIndex={0}
      className="tg-spoiler"
      data-open={open}
      aria-label={open ? undefined : "Spoiler, press to reveal"}
      onClick={() => setOpen(true)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(true); } }}
    >
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
      case "b": case "strong": return <b key={k}>{kids}</b>;
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

export function MessageText({ text, format }: { text: string; format: string }) {
  return <div className="text-[15px] leading-snug break-words whitespace-pre-wrap">{renderNodes(telegramHtmlToSafe(text, format))}</div>;
}

export interface BubbleProps {
  logical: Logical;
  onPress?: (actionId: string) => void;
  edited?: boolean;
  label?: ReactNode;
  widget?: string | null;
  highlight?: boolean;
}

export function Bubble({ logical, onPress, edited, label, widget, highlight }: BubbleProps) {
  const inline = logical.keyboard.type === "inline" ? logical.keyboard.rows : [];
  return (
    <div className={cn("w-full max-w-[340px] transition-shadow", highlight && "rounded-xl ring-2 ring-sky-400")}>
      <div className="tg-bubble rounded-xl rounded-bl-sm px-3 py-2 shadow-sm">
        {widget && (
          <div className="mb-1 rounded-md border border-dashed border-current/30 px-2 py-1 text-xs tg-hint">
            Widget <span className="font-mono">{widget}</span> (see Widgets)
          </div>
        )}
        <MessageText text={logical.text} format={logical.format} />
        <div className="mt-1 flex items-center justify-end gap-1 text-[11px] tg-hint">
          {label}
          {edited && <span className="inline-flex items-center gap-0.5"><Pencil className="size-3" aria-hidden /> edited</span>}
          <span>10:00</span>
        </div>
      </div>
      {inline.length > 0 && (
        <div className="mt-1 flex flex-col gap-1" role="group" aria-label="Inline keyboard">
          {inline.map((row, r) => (
            <div key={r} className="flex gap-1">
              {row.map((b) => (
                <button
                  key={b.actionId}
                  type="button"
                  className={cn("tg-btn flex min-h-9 flex-1 items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium", !onPress && "cursor-default")}
                  data-style={b.style}
                  onClick={onPress ? () => onPress(b.actionId) : undefined}
                  aria-disabled={!onPress || undefined}
                  title={b.url ? `Opens ${b.url} (not followed)` : b.callbackData ? `callback_data ${b.callbackData}` : undefined}
                >
                  <span className="truncate">{b.text}</span>
                  {b.url && <ExternalLink className="size-3 shrink-0" aria-hidden />}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReplyKeyboard({ logical, onKey }: { logical: Logical; onKey?: (text: string) => void }) {
  return (
    <div className="flex flex-col gap-1 p-1.5" role="group" aria-label="Reply keyboard">
      {logical.keyboard.rows.map((row, r) => (
        <div key={r} className="flex gap-1">
          {row.map((b) => (
            <button
              key={b.actionId}
              type="button"
              className="tg-key min-h-10 flex-1 rounded-md px-2 text-sm shadow-sm"
              onClick={onKey ? () => onKey(b.text) : undefined}
              aria-disabled={!onKey || undefined}
            >
              {b.text}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function Composer({ placeholder, disabled, onSend }: { placeholder: string; disabled?: boolean; onSend?: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form
      className="flex items-center gap-2 border-t border-black/10 bg-[var(--tg-bubble)] px-2 py-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim() || !onSend) return;
        onSend(text);
        setText("");
      }}
    >
      <input
        className="min-w-0 flex-1 bg-transparent px-1 py-1.5 text-sm text-[var(--tg-text)] outline-none placeholder:text-[var(--tg-hint)] focus-visible:outline-none"
        placeholder={placeholder}
        aria-label="Message text"
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
      />
      <button type="submit" disabled={disabled || !text.trim()} className="rounded-full px-3 py-1 text-sm font-medium text-[var(--tg-link)] disabled:opacity-40">
        Send
      </button>
    </form>
  );
}

/** One screen as it would arrive: bubble, reply keyboard or ForceReply placeholder. */
export function ScreenPreview({ logical, theme, contextLabel, hideWidget }: { logical: Logical; theme: "light" | "dark"; contextLabel: string; hideWidget?: boolean }) {
  const kt = logical.keyboard.type;
  return (
    <figure className="overflow-hidden rounded-xl border">
      <div className="tg-chat flex min-h-56 flex-col" data-theme={theme}>
        <div className="flex flex-1 flex-col justify-end gap-2 p-3">
          <Bubble logical={logical} widget={hideWidget ? null : logical.widget} />
        </div>
        {(kt === "reply" || kt === "force_reply") && (
          <Composer placeholder={kt === "force_reply" ? logical.keyboard.placeholder || "Reply…" : "Message"} disabled />
        )}
        {kt === "reply" && <ReplyKeyboard logical={logical} />}
        {kt === "remove" && <p className="px-3 pb-2 text-xs tg-hint">This message removes the reply keyboard.</p>}
      </div>
      <PreviewCaption contextLabel={contextLabel} />
    </figure>
  );
}

export function PreviewCaption({ contextLabel }: { contextLabel: string }) {
  return (
    <figcaption className="flex flex-wrap items-center justify-between gap-1 border-t bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
      <span className="font-medium">Local preview, not Telegram</span>
      <span>{contextLabel}</span>
    </figcaption>
  );
}
