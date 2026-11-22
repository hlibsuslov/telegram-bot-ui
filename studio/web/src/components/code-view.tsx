// Read-only code viewer: line numbers, a small own highlighter (JSON, HTML, diff, CSS/JS
// comments and strings), copy and download. Output is React text nodes, never HTML strings.
import { Check, Copy, Download, WrapText } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { copyText, download } from "@/lib/model";
import { cn } from "@/lib/utils";

export type Lang = "json" | "html" | "diff" | "css" | "js" | "text";
export interface CodeTab { id: string; label: string; code: string; lang: Lang; filename?: string; mime?: string }

type Tok = [string, string | null];

const RULES: Record<Exclude<Lang, "diff" | "text">, [RegExp, string | ((m: RegExpExecArray, rest: string) => string)][]> = {
  json: [
    [/^"(?:[^"\\]|\\.)*"(?=\s*:)/, "key"],
    [/^"(?:[^"\\]|\\.)*"/, "str"],
    [/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/, "num"],
    [/^(?:true|false|null)\b/, "kw"],
    [/^[{}[\],:]/, "punc"],
  ],
  html: [
    [/^<!--[\s\S]*?(?:-->|$)/, "com"],
    [/^<\/?[a-zA-Z][\w:-]*/, "tag"],
    [/^\/?>/, "tag"],
    [/^[a-zA-Z_:][\w:.-]*(?==)/, "attr"],
    [/^"[^"]*"|^'[^']*'/, "str"],
    [/^&[#\w]+;/, "kw"],
  ],
  css: [
    [/^\/\*[\s\S]*?(?:\*\/|$)/, "com"],
    [/^"(?:[^"\\]|\\.)*"|^'(?:[^'\\]|\\.)*'/, "str"],
    [/^#[0-9a-fA-F]{3,8}\b/, "num"],
    [/^-?\d+(?:\.\d+)?(?:px|em|rem|%|s|ms|vw|vh)?/, "num"],
    [/^[a-z-]+(?=\s*:)/, "attr"],
    [/^[{}();:,]/, "punc"],
  ],
  js: [
    [/^\/\/.*/, "com"],
    [/^\/\*[\s\S]*?(?:\*\/|$)/, "com"],
    [/^"(?:[^"\\]|\\.)*"|^'(?:[^'\\]|\\.)*'|^`(?:[^`\\]|\\.)*`/, "str"],
    [/^\d+(?:\.\d+)?/, "num"],
    [/^(?:const|let|var|function|return|if|else|for|while|new|true|false|null|undefined|typeof|this|async|await|try|catch)\b/, "kw"],
    [/^[{}()[\];,.]/, "punc"],
  ],
};

function tokenizeLine(line: string, lang: Lang): Tok[] {
  if (lang === "text" || lang === "diff") return [[line, null]];
  const rules = RULES[lang];
  const out: Tok[] = [];
  let rest = line, plain = "";
  while (rest) {
    let hit = false;
    for (const [rx, cls] of rules) {
      const m = rx.exec(rest);
      if (m && m[0]) {
        if (plain) { out.push([plain, null]); plain = ""; }
        out.push([m[0], typeof cls === "string" ? cls : cls(m, rest)]);
        rest = rest.slice(m[0].length);
        hit = true;
        break;
      }
    }
    if (!hit) { plain += rest[0]; rest = rest.slice(1); }
  }
  if (plain) out.push([plain, null]);
  return out;
}

const TOKEN_CLASS: Record<string, string> = {
  key: "text-sky-800 dark:text-sky-300",
  str: "text-emerald-800 dark:text-emerald-300",
  num: "text-amber-800 dark:text-amber-300",
  kw: "text-violet-700 dark:text-violet-300",
  punc: "text-muted-foreground",
  tag: "text-rose-700 dark:text-rose-300",
  attr: "text-sky-800 dark:text-sky-300",
  com: "text-muted-foreground italic",
};

function diffClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-muted-foreground font-semibold";
  if (line.startsWith("+")) return "bg-emerald-500/12 text-emerald-900 dark:text-emerald-200";
  if (line.startsWith("-")) return "bg-red-500/12 text-red-900 dark:text-red-200";
  if (line.startsWith("@@")) return "bg-sky-500/8 text-sky-800 dark:text-sky-300";
  return "";
}

export function CodeBlock({ code, lang, maxHeight = "60svh", wrap }: { code: string; lang: Lang; maxHeight?: string; wrap?: boolean }) {
  const lines = useMemo(() => code.replace(/\n$/, "").split("\n"), [code]);
  const big = code.length > 400_000;
  return (
    <div className="overflow-auto rounded-b-lg bg-muted/30 font-mono text-[12px] leading-[1.6]" style={{ maxHeight }}>
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((l, i) => (
            <tr key={i} className={lang === "diff" ? diffClass(l) : undefined}>
              <td className="sticky left-0 w-px bg-muted/60 px-2 text-right align-top text-[11px] text-muted-foreground/70 select-none" aria-hidden>{i + 1}</td>
              <td className={cn("px-3 align-top", wrap ? "break-all whitespace-pre-wrap" : "whitespace-pre")}>
                {big ? l : tokenizeLine(l, lang).map(([t, c], j) => (c ? <span key={j} className={TOKEN_CLASS[c]}>{t}</span> : <span key={j}>{t}</span>)) as ReactNode}
                {!l && " "}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CodeView({ tabs, maxHeight, className, empty }: { tabs: CodeTab[]; maxHeight?: string; className?: string; empty?: ReactNode }) {
  const [active, setActive] = useState(tabs[0]?.id);
  const [copied, setCopied] = useState(false);
  const [wrap, setWrap] = useState(false);
  const tab = tabs.find((t) => t.id === active) ?? tabs[0];
  if (!tab) return <>{empty}</>;
  return (
    <div className={cn("overflow-hidden rounded-lg border bg-background", className)}>
      <div className="flex items-center gap-1 border-b bg-muted/40 px-1.5">
        <div role="tablist" aria-label="Code" className="flex min-w-0 flex-1 gap-0.5 overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={t.id === tab.id} onClick={() => setActive(t.id)}
              className="relative px-2.5 py-2 text-xs font-medium whitespace-nowrap text-muted-foreground aria-selected:text-foreground">
              {t.label}
              {t.id === tab.id && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-foreground" aria-hidden />}
            </button>
          ))}
        </div>
        <span className="hidden font-mono text-[10.5px] text-muted-foreground sm:inline">{tab.code.split("\n").length} lines</span>
        <button type="button" onClick={() => setWrap(!wrap)} aria-pressed={wrap} aria-label="Wrap long lines" title="Wrap long lines"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted aria-pressed:text-foreground"><WrapText className="size-3.5" /></button>
        <button type="button" aria-label={`Copy ${tab.label}`} title="Copy"
          onClick={async () => { if (await copyText(tab.code)) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}
          className="rounded p-1.5 text-muted-foreground hover:bg-muted">{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}</button>
        {tab.filename && (
          <button type="button" aria-label={`Download ${tab.filename}`} title={`Download ${tab.filename}`} onClick={() => download(tab.filename!, tab.code, tab.mime)}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted"><Download className="size-3.5" /></button>
        )}
      </div>
      <CodeBlock code={tab.code} lang={tab.lang} maxHeight={maxHeight} wrap={wrap} />
    </div>
  );
}
