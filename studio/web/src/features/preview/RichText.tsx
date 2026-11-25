// Rich Message preview (Bot API 10.1+, buttons 10.3), drawn locally from a safe tree: bot text never
// reaches the page as markup. Media, maps and documents are drawn stand-ins; links are not followed.
// Buttons that carry a screen action call onPress, the same path as the inline keyboard.
import { useState, type MouseEvent, type ReactNode } from "react";
import { ChevronDown, ExternalLink, FileText, Image as ImageIcon, MapPin, Music, Video } from "lucide-react";
import { type RichButton, type RichNode, richHtmlToSafe } from "@/core/rich.ts";
import { cn } from "@/lib/utils";
import { CustomEmoji } from "@/features/emoji/CustomEmoji";

interface Ctx { buttons: RichButton[]; onPress?: (actionId: string) => void; hlAction?: string; buttonSlot?: (actionId: string) => ReactNode }

const textOf = (nodes: RichNode[] | undefined): string => (nodes ?? []).map((n) => n.text ?? textOf(n.children)).join("");

function TgButton({ node, ctx, k, inRow }: { node: RichNode; ctx: Ctx; k: string; inRow: boolean }) {
  const a = node.attrs ?? {};
  const bound = a.type === "callback_data" ? ctx.buttons.find((b) => b.callbackData === a.data) : undefined;
  const actionId = bound?.actionId ?? null;
  const onPress = ctx.onPress;
  const click = actionId && onPress ? (e: MouseEvent) => { e.stopPropagation(); onPress(actionId); } : undefined;
  const title = a.type === "callback_data" ? `callback_data ${a.data ?? ""}`
    : a.url ? `${a.type}: ${a.url} (not followed)` : a.type === "copy_text" ? `copies “${a.text ?? ""}”` : a.type;
  const kids = render(node.children, ctx, k);
  if (a.style === "link") {
    return (
      <button type="button" data-action={actionId ?? undefined} data-hl={ctx.hlAction === actionId || undefined} title={title}
        className={cn("tg-link relative inline font-medium", !click && "cursor-default")} onClick={click}>{kids}{actionId && ctx.buttonSlot?.(actionId)}</button>
    );
  }
  return (
    <button type="button" data-action={actionId ?? undefined} data-style={a.style} data-hl={ctx.hlAction === actionId || undefined}
      title={title} disabled={a.type === "disabled"} onClick={click}
      className={cn("tg-inline-btn relative inline-flex min-h-[32px] items-center justify-center gap-1 px-3 py-1 align-middle text-[13.5px] font-medium disabled:opacity-50",
        inRow ? "min-w-0 flex-1" : "mx-0.5", !click && "cursor-default")}>
      <span className="truncate">{kids}</span>
      {actionId && ctx.buttonSlot?.(actionId)}
      {(a.type === "url" || a.type === "web_app" || a.type === "login_url") && <ExternalLink className="absolute top-1 right-1 size-2.5" aria-hidden />}
    </button>
  );
}

function Details({ open, summary, children }: { open: boolean; summary: ReactNode; children: ReactNode }) {
  const [isOpen, setOpen] = useState(open);
  return (
    <div className="my-1 rounded-lg bg-black/5 px-2 py-1 dark:bg-white/5">
      <button type="button" aria-expanded={isOpen} className="flex w-full items-center gap-1 text-left font-medium"
        onClick={(e) => { e.stopPropagation(); setOpen(!isOpen); }}>
        <ChevronDown className={cn("size-3.5 transition-transform", !isOpen && "-rotate-90")} aria-hidden />{summary}
      </button>
      {isOpen && <div className="pt-1">{children}</div>}
    </div>
  );
}

function ExpandableQuote({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <blockquote className="relative my-1">
      <div className={cn(!open && "line-clamp-3")}>{children}</div>
      <button type="button" aria-expanded={open} aria-label={open ? "Collapse quote" : "Expand quote"} className="absolute right-1 bottom-0.5"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}><ChevronDown className={cn("size-3.5", open && "rotate-180")} /></button>
    </blockquote>
  );
}

function MediaStandIn({ kind, src, spoiler }: { kind: string; src?: string; spoiler?: boolean }) {
  const Icon = kind === "video" ? Video : kind === "audio" ? Music : kind === "tg-document" ? FileText : kind === "tg-map" ? MapPin : ImageIcon;
  let host = "";
  try { host = src ? new URL(src).host : ""; } catch { host = src ?? ""; }
  return (
    <div data-media={kind}
      className="my-1 flex h-28 flex-col items-center justify-center gap-1 rounded-lg bg-gradient-to-br from-slate-300 to-slate-400 text-slate-700 dark:from-slate-600 dark:to-slate-700 dark:text-slate-100">
      <Icon className="size-6" aria-hidden />
      <span className="text-[11px] font-medium">{kind.replace("tg-", "")}{host ? ` · ${host}` : ""}{spoiler ? " · spoiler" : ""}</span>
    </div>
  );
}

const HEADING = ["", "text-[20px] font-bold", "text-[18px] font-bold", "text-[16.5px] font-semibold", "text-[15px] font-semibold",
  "text-[14.5px] font-semibold", "text-[13.5px] font-semibold uppercase"];

function render(nodes: RichNode[] | undefined, ctx: Ctx, key: string): ReactNode[] {
  return (nodes ?? []).map((n, i) => {
    const k = `${key}.${i}`;
    const a = n.attrs ?? {};
    const kids = () => render(n.children, ctx, k);
    switch (n.tag) {
      case "#text": return <span key={k}>{n.text}</span>;
      case "b": case "strong": return <b key={k} className="font-semibold">{kids()}</b>;
      case "i": case "em": return <i key={k}>{kids()}</i>;
      case "u": case "ins": return <u key={k}>{kids()}</u>;
      case "s": case "strike": case "del": return <s key={k}>{kids()}</s>;
      case "mark": return <mark key={k} className="rounded-sm bg-yellow-300/60 px-0.5 text-inherit">{kids()}</mark>;
      case "sub": return <sub key={k}>{kids()}</sub>;
      case "sup": return <sup key={k}>{kids()}</sup>;
      case "code": case "tg-math": return <code key={k} title={n.tag === "tg-math" ? "formula (LaTeX)" : undefined}>{kids()}</code>;
      case "pre": case "tg-math-block": return <pre key={k} className="my-1 whitespace-pre-wrap">{kids()}</pre>;
      case "tg-spoiler": return <span key={k} className="tg-spoiler" data-open="true">{kids()}</span>;
      case "tg-time": return <span key={k} title={`date-time ${a.unix ?? ""} (${a.format ?? ""})`} className="underline decoration-dotted">{kids()}</span>;
      case "tg-emoji": return a["emoji-id"] ? <CustomEmoji key={k} id={a["emoji-id"]} fallback={textOf(n.children)} /> : <span key={k}>{kids()}</span>;
      case "a": return <span key={k} className="tg-link" title={a.href ? `Link: ${a.href} (not followed)` : a.name ? `anchor #${a.name}` : undefined}>{kids()}</span>;
      case "tg-reference": return <span key={k} className="tg-link">{kids()}</span>;
      case "br": return <br key={k} />;
      case "hr": return <hr key={k} className="my-2 border-current opacity-20" />;
      case "h1": case "h2": case "h3": case "h4": case "h5": case "h6": {
        const level = Number(n.tag[1]);
        return <div key={k} role="heading" aria-level={level} className={cn("mt-1 mb-0.5 leading-tight", HEADING[level])}>{kids()}</div>;
      }
      case "p": return <p key={k} className="my-1">{kids()}</p>;
      case "footer": return <p key={k} className="tg-hint mt-1.5 text-[12.5px]">{kids()}</p>;
      case "ul": return <ul key={k} className="my-1 list-disc pl-5">{kids()}</ul>;
      case "ol": return <ol key={k} className="my-1 list-decimal pl-5" start={a.start ? Number(a.start) : undefined}>{kids()}</ol>;
      case "li": return <li key={k}>{kids()}</li>;
      case "input": return <input key={k} type="checkbox" readOnly checked={"checked" in a} className="mr-1 align-middle" aria-label="task" />;
      case "blockquote": return "expandable" in a ? <ExpandableQuote key={k}>{kids()}</ExpandableQuote> : <blockquote key={k} className="my-1">{kids()}</blockquote>;
      case "aside": return <div key={k} className="my-1.5 text-center text-[16px] font-medium italic">{kids()}</div>;
      case "cite": return <div key={k} className="tg-hint mt-0.5 text-[12px] not-italic">— {kids()}</div>;
      case "details": {
        const summary = (n.children ?? []).find((c) => c.tag === "summary");
        const rest = (n.children ?? []).filter((c) => c !== summary);
        return <Details key={k} open={"open" in a} summary={render(summary?.children, ctx, `${k}s`)}>{render(rest, ctx, `${k}r`)}</Details>;
      }
      case "summary": return <span key={k}>{kids()}</span>;
      case "table": {
        const compact = "compact" in a;
        return (
          <div key={k} className="my-1 overflow-x-auto">
            <table className={cn("w-full border-collapse text-left", compact ? "text-[12.5px]" : "text-[13.5px]")} data-compact={compact || undefined}>
              <tbody>{render((n.children ?? []).filter((c) => c.tag === "tr"), { ...ctx }, k)}</tbody>
            </table>
            {(n.children ?? []).filter((c) => c.tag === "caption").map((c, j) => <div key={j} className="tg-hint text-[11.5px]">{render(c.children, ctx, `${k}c`)}</div>)}
          </div>
        );
      }
      case "tr": return <tr key={k} className="border-b border-black/10 last:border-0 dark:border-white/10">{kids()}</tr>;
      case "th": case "td": {
        const Cell = n.tag;
        return (
          <Cell key={k} colSpan={a.colspan ? Number(a.colspan) : undefined} rowSpan={a.rowspan ? Number(a.rowspan) : undefined}
            className={cn("px-1.5 py-0.5", n.tag === "th" && "font-semibold", a.align === "right" && "text-right", a.align === "center" && "text-center")}>{kids()}</Cell>
        );
      }
      case "caption": return null;
      case "img": case "video": case "audio": case "tg-document": case "tg-map":
        return <MediaStandIn key={k} kind={n.tag} src={a.src} spoiler={"tg-spoiler" in a} />;
      case "figure": case "tg-collage": case "tg-slideshow": return <div key={k} className="my-1" data-group={n.tag}>{kids()}</div>;
      case "figcaption": return <div key={k} className="tg-hint text-[12px]">{kids()}</div>;
      case "tg-thinking": return <div key={k} className="tg-hint italic">{kids()}</div>;
      case "tg-button-row":
        return (
          <div key={k} role="group" aria-label="Buttons" className={cn("my-1.5 flex gap-1", a.align === "center" && "justify-center", a.align === "right" && "justify-end")}>
            {(n.children ?? []).filter((c) => c.tag === "tg-button").map((c, j) => <TgButton key={j} node={c} ctx={ctx} k={`${k}.${j}`} inRow />)}
          </div>
        );
      case "tg-button": return <TgButton key={k} node={n} ctx={ctx} k={k} inRow={false} />;
      default: return <span key={k}>{kids()}</span>;
    }
  });
}

export function RichText({ html, buttons, onPress, hlAction, buttonSlot, className }: {
  html: string; buttons: RichButton[]; onPress?: (actionId: string) => void; hlAction?: string;
  /** Extra content inside each bound button (map ports). */
  buttonSlot?: (actionId: string) => ReactNode; className?: string;
}) {
  return (
    <div className={cn("tg-rich text-[14.5px] leading-[1.38] break-words", className)} data-format="rich.html">
      {render(richHtmlToSafe(html), { buttons, onPress, hlAction, buttonSlot }, "r")}
    </div>
  );
}
