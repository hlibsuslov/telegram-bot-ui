// Emoji page: import premium emoji packs by link, give emoji a meaning (the bot's icon map),
// see where they are used, and hand the placement to the agent.
import { AlertTriangle, Bot, Check, Copy, Download, FileJson, Library, Link2, Loader2, Plus, Search, Sparkles, Trash2, Wand2, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { CodeView } from "@/components/code-view";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, errorText } from "@/lib/api";
import { copyText, DEMO_SITE } from "@/lib/model";
import { go, href } from "@/lib/route";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { CustomEmoji } from "./CustomEmoji";
import { slotsForEmoji, tgEmojiHtml, useEmoji, type Entry } from "./context";

const ROUTES: Record<string, { ok: boolean; text: string }> = {
  fragment: { ok: true, text: "The bot has Fragment usernames: custom emoji work in every chat." },
  owner_premium: { ok: true, text: "The owner has Premium: custom emoji work in private chats and groups, not in channels." },
  none: { ok: false, text: "capabilities.customEmoji is 'none': Telegram silently drops custom emoji from this bot and users see the fallback. Set it in project.json when the bot has a Fragment username or a Premium owner." },
};
const SLOT_RE = /^[a-z0-9][a-z0-9_-]{0,47}$/;

function Section({ icon: Icon, title, hint, count, children, actions }: { icon: typeof Library; title: string; hint: string; count?: number; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="space-y-3 rounded-xl p-4 ring-1 ring-border">
      <div className="flex flex-wrap items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted"><Icon className="size-4" aria-hidden /></span>
        <div className="min-w-0 flex-1">
          <h3 className="flex items-baseline gap-2 text-[15px] font-semibold tracking-tight">{title}{count !== undefined && <span className="rounded-full bg-muted px-2 text-xs font-medium text-muted-foreground">{count}</span>}</h3>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** `preview`: the demo and the offline artifact show the form without a server behind it. */
function ImportCard({ preview }: { preview?: boolean }) {
  const { doc, call } = useEmoji();
  const { notify, loaded } = useStudio();
  const [link, setLink] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (body: Record<string, unknown>) => {
    setBusy(true);
    const res = await call("/api/emoji/import", body);
    setBusy(false);
    if (!res.ok) { notify(res.error ?? "import failed", "error"); return; }
    const d = res.data;
    notify(`${d.title}: ${d.count} emoji${d.source === "getStickerSet" ? `, ${d.previews} pictures${d.previewsFailed ? ` (${d.previewsFailed} without one)` : ""}` : " (ids only, no pictures)"}`, "success");
    setLink("");
  };
  return (
    <Section icon={Download} title="Add a pack" hint="Paste the link of an emoji pack (Telegram: the pack's menu, Share or Copy link).">
      {preview && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs">
          <span className="min-w-0 flex-1">{loaded.features.demo
            ? "Preview: in the demo nothing is imported. On your own bot the local Studio reads a pack from its link, and every emoji shows up in the editor, the previews and the simulator."
            : "Preview: this offline file cannot import. Run the local Studio (bot-ui studio) on the project to add packs."}</span>
          {loaded.features.demo && <a href={DEMO_SITE} target="_top" className="shrink-0 rounded-md border bg-background px-2 py-1 font-medium hover:bg-accent">Run it on your bot</a>}
        </div>
      )}
      <fieldset disabled={preview || busy} className="contents">
      <form className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]" onSubmit={(e) => { e.preventDefault(); if (link.trim()) void run({ link: link.trim(), token: token.trim() || undefined }); }}>
        <div className="relative">
          <Link2 className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://t.me/addemoji/…" className="pl-8" aria-label="Pack link" disabled={busy} />
        </div>
        <Button type="submit" disabled={preview || busy || !link.trim()}>{busy ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />} {busy ? "Reading the pack…" : "Import"}</Button>
        {doc.tokenEnv && !preview ? (
          <p className="text-xs text-muted-foreground sm:col-span-2">Uses the bot token from <span className="font-mono">{doc.tokenEnv}</span> for one read-only call (getStickerSet) and the pictures. Nothing is sent to a chat.</p>
        ) : (
          <div className="space-y-1 sm:col-span-2">
            <Input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Bot token (any bot of yours)" autoComplete="off" spellCheck={false} aria-label="Bot token" disabled={busy} />
            <p className="text-xs text-muted-foreground">Reading a pack needs any bot token: the Studio calls only the read-only getStickerSet and downloads the pictures. The token stays in this tab and is never saved. Or start the Studio with <span className="font-mono">TELEGRAM_TEST_BOT_TOKEN</span> set.</p>
          </div>
        )}
      </form>
      <label className={cn("flex items-center gap-2 text-xs text-muted-foreground", preview ? "opacity-60" : "cursor-pointer")}>
        <FileJson className="size-3.5" aria-hidden />
        <span className="underline">or load a saved getStickerSet response</span> (ids only, no pictures)
        <input type="file" accept="application/json,.json" className="sr-only" disabled={busy}
          onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (!f) return; try { await run({ stickerSet: JSON.parse(await f.text()) }); } catch (err) { notify((err as Error).message, "error"); } }} />
      </label>
      </fieldset>
    </Section>
  );
}

/** Give an emoji a meaning (slot) in the bot's icon map. */
function SlotDialog({ entry, onClose }: { entry: Entry | null; onClose: () => void }) {
  const { doc, call, slotOf, editable } = useEmoji();
  const { notify } = useStudio();
  const current = entry ? slotOf.get(entry.id) : undefined;
  const [slot, setSlot] = useState("");
  const [note, setNote] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!entry) return;
    const suggested = slotsForEmoji(doc.vocabulary, entry.fallback).find((v) => !doc.library.icons[v.slot]);
    setSlot(current ?? suggested?.slot ?? "");
    setNote((current && doc.library.icons[current]?.note) || "");
  }, [entry?.id]);
  if (!entry) return null;
  const vocab = doc.vocabulary.find((v) => v.slot === slot);
  const taken = slot && doc.library.icons[slot] && doc.library.icons[slot].id !== entry.id ? doc.library.icons[slot] : null;
  const fits = slotsForEmoji(doc.vocabulary, entry.fallback).slice(0, 6);
  const save = async () => {
    if (current && current !== slot) await call("/api/emoji/icon", { slot: current, id: null });
    const res = await call("/api/emoji/icon", { slot, id: entry.id, note });
    if (res.ok) { notify(`${slot}: added to the bot's icons`, "success"); onClose(); } else notify(res.error ?? "", "error");
  };
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3"><CustomEmoji id={entry.id} className="size-12" /> <span>{current ?? "Premium emoji"}</span></DialogTitle>
          <DialogDescription>Fallback {entry.fallback || "—"} · {entry.format}{entry.adaptive ? " · takes the text colour" : ""} · pack {entry.pack}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/50 p-2 font-mono text-xs">
          <span className="min-w-0 flex-1 truncate">{entry.id}</span>
          <Button type="button" size="sm" variant="ghost" className="h-7" onClick={async () => { if (await copyText(tgEmojiHtml(entry.id, entry.fallback))) { setCopied(true); setTimeout(() => setCopied(false), 1200); } }}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />} Copy HTML
          </Button>
        </div>
        {editable && (
          <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (SLOT_RE.test(slot) && !taken) void save(); }}>
            <label className="block text-sm font-medium" htmlFor="slot-input">What it means in this bot</label>
            <Input id="slot-input" list="slot-vocabulary" value={slot} onChange={(e) => setSlot(e.target.value.trim().toLowerCase())} placeholder="home, back, cart, paid…" autoFocus />
            <datalist id="slot-vocabulary">{doc.vocabulary.map((v) => <option key={v.slot} value={v.slot}>{v.label}</option>)}</datalist>
            {fits.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {fits.map((v) => <button key={v.slot} type="button" onClick={() => setSlot(v.slot)} className={cn("rounded-full border px-2 py-0.5 text-xs", v.slot === slot && "border-primary bg-primary/10")}>{v.slot}</button>)}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              {vocab ? <>{vocab.label} · {vocab.group}{vocab.use?.length ? ` · for ${vocab.use.join(", ")}` : ""}{vocab.note ? `. ${vocab.note}` : ""}</> : slot && SLOT_RE.test(slot) ? "Your own meaning (not in the skill's vocabulary): describe where to use it below." : "Lowercase letters, digits, _ and -."}
            </p>
            {taken && <p className="text-xs text-destructive">'{slot}' already has another emoji: clear it first under This bot's icons.</p>}
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Where to use it (optional, for the agent)" maxLength={200} aria-label="Note for the agent" />
            <div className="flex justify-end gap-2 pt-1">
              {current && <Button type="button" variant="ghost" onClick={async () => { await call("/api/emoji/icon", { slot: current, id: null }); onClose(); }}>Remove meaning</Button>}
              <Button type="submit" disabled={!SLOT_RE.test(slot) || !!taken}>{current ? "Save" : "Add to the bot's icons"}</Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Suggestions() {
  const { doc, call, editable } = useEmoji();
  const { notify } = useStudio();
  const [busy, setBusy] = useState(false);
  if (!editable || !doc.suggestions.length) return null;
  const add = async (list = doc.suggestions) => {
    setBusy(true);
    for (const s of list) await call("/api/emoji/icon", { slot: s.slot, id: s.id });
    setBusy(false);
    notify(`${list.length} icon${list.length === 1 ? "" : "s"} added`, "success");
  };
  return (
    <Section icon={Wand2} title="Suggested for your screens" count={doc.suggestions.length}
      hint="Your screens already use these ordinary emoji; the imported packs have a matching premium one."
      actions={<Button size="sm" variant="outline" disabled={busy} onClick={() => void add()}>{busy ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />} Add all</Button>}>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {doc.suggestions.map((s) => (
          <div key={s.slot} className="flex items-center gap-2 rounded-lg bg-muted/40 p-2">
            <span className="text-lg" aria-label="ordinary emoji">{s.fallback}</span>
            <span className="text-muted-foreground" aria-hidden>→</span>
            <CustomEmoji id={s.id} fallback={s.fallback} className="size-7" />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{s.slot}</span>
            <Button size="sm" variant="ghost" className="h-7" disabled={busy} onClick={() => void add([s])}>Add</Button>
          </div>
        ))}
      </div>
    </Section>
  );
}

function IconMap({ onOpen }: { onOpen: (e: Entry) => void }) {
  const { doc, index, editable, call } = useEmoji();
  const { addRequest, notify } = useStudio();
  const icons = Object.entries(doc.library.icons ?? {});
  const uses = (id: string) => doc.usage.filter((u) => u.id === id);
  const ask = () => {
    const list = icons.map(([slot, i]) => `${slot} ${i.fallback}`).join(", ");
    addRequest(null, `Place the premium emoji of the icon map (emoji/library.json: ${list}) where they fit by meaning: titles, key buttons and statuses, following \`bot-ui emoji brief\`. Keep ordinary emoji where no icon fits and check with bot-ui validate.`);
    notify("Request queued for the agent (Changes → Prompt)", "success");
  };
  return (
    <Section icon={Sparkles} title="This bot's icons" count={icons.length}
      hint="Each emoji gets one meaning. The pickers in the editor and the agent use these first, so one meaning keeps one icon everywhere."
      actions={icons.length > 0 && editable ? <Button size="sm" variant="outline" onClick={ask}><Bot className="size-4" /> Ask the agent to place them</Button> : undefined}>
      {!icons.length ? (
        <p className="text-sm text-muted-foreground">No icons yet. Open an emoji of a pack below and say what it means (home, back, cart…), or take the suggestions above.</p>
      ) : (
        <ul className="divide-y rounded-lg ring-1 ring-border">
          {icons.map(([slot, i]) => {
            const u = uses(i.id);
            const e = index.get(i.id);
            return (
              <li key={slot} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <button type="button" className="rounded-md p-0.5 hover:bg-accent" onClick={() => e && onOpen(e)} aria-label={`Edit ${slot}`}><CustomEmoji id={i.id} fallback={i.fallback} className="size-8" /></button>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{slot} <span className="font-normal text-muted-foreground">· fallback {i.fallback || "—"}{i.animated ? " · animated" : ""}</span></p>
                  <p className="truncate text-xs text-muted-foreground">{i.note || i.set || "—"} · <span className="font-mono">{i.id}</span></p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {u.length ? <>used on {[...new Set(u.map((x) => x.screenId))].map((sid, n) => <span key={sid}>{n ? ", " : ""}<a className="underline" href={href("map", sid)}>{sid}</a></span>)}</> : "not used yet"}
                </span>
                {editable && <Button size="icon" variant="ghost" className="size-8" aria-label={`Remove ${slot}`} onClick={() => void call("/api/emoji/icon", { slot, id: null }).then((r) => !r.ok && notify(r.error ?? "", "error"))}><X className="size-4" /></Button>}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function Packs({ onOpen }: { onOpen: (e: Entry) => void }) {
  const { doc, slotOf, editable, call } = useEmoji();
  const { notify } = useStudio();
  const [q, setQ] = useState("");
  const packs = Object.entries(doc.library.packs ?? {});
  if (!packs.length) return null;
  const query = q.trim().toLowerCase();
  return (
    <Section icon={Library} title="Packs" count={packs.length} hint="Every emoji of the imported packs. Open one to give it a meaning or copy its HTML."
      actions={
        <div className="relative w-48">
          <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Emoji, meaning or id" className="h-8 pl-7 text-xs" aria-label="Search the packs" />
        </div>
      }>
      {packs.map(([name, pack]) => {
        const list = pack.emoji.filter((e) => !query || e.fallback.includes(q.trim()) || (slotOf.get(e.id) ?? "").includes(query) || e.id.startsWith(query));
        return (
          <div key={name} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{pack.title}</span>
              <a href={pack.link} target="_blank" rel="noreferrer noopener" className="text-xs text-muted-foreground underline">{pack.link.replace(/^https?:\/\//, "")}</a>
              <span className="text-xs text-muted-foreground">{pack.emoji.length} emoji · {(pack.formats ?? []).join(", ")}{pack.source === "file" ? " · ids only" : ""}</span>
              {editable && (
                <Button size="sm" variant="ghost" className="ml-auto h-7 text-xs" onClick={async () => {
                  if (!confirm(`Remove ${pack.title} from the library? Icons that use it stay.`)) return;
                  const r = await call("/api/emoji/remove-pack", { pack: name });
                  notify(r.ok ? `${pack.title} removed` : r.error ?? "", r.ok ? "info" : "error");
                }}><Trash2 className="size-3.5" /> Remove</Button>
              )}
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(3.25rem,1fr))] gap-1">
              {list.map((e) => {
                const slot = slotOf.get(e.id);
                return (
                  <button key={e.id} type="button" onClick={() => onOpen({ ...e, pack: name })} title={`${slot ? `${slot} · ` : ""}${e.fallback} · ${e.id}`}
                    className={cn("flex flex-col items-center gap-0.5 rounded-lg p-1.5 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", slot && "bg-primary/5 ring-1 ring-primary/40")}>
                    <CustomEmoji id={e.id} fallback={e.fallback} className="size-8" title="" />
                    <span className="w-full truncate text-center text-[10px] text-muted-foreground">{slot ?? e.fallback}</span>
                  </button>
                );
              })}
              {!list.length && <p className="col-span-full text-xs text-muted-foreground">Nothing matches.</p>}
            </div>
          </div>
        );
      })}
    </Section>
  );
}

function AgentBrief() {
  const { loaded, store } = useStudio();
  const { doc } = useEmoji();
  const [md, setMd] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const n = Object.keys(doc.library.icons ?? {}).length + doc.usage.length;
  useEffect(() => {
    if (loaded.mode !== "studio" || !n) return;
    api("/api/emoji/brief", { screens: store.data.screens }).then((r) => { if (r.ok) setMd(r.data.markdown); else setErr(errorText(r.data)); });
  }, [doc, loaded.mode, n, store.version]);
  if (loaded.mode !== "studio" || !n) return null;
  return (
    <Section icon={Bot} title="What the agent gets" hint="The prompt on the Changes page includes the icon map; the agent can print this brief itself with `bot-ui emoji brief`."
      actions={<Button size="sm" variant="ghost" onClick={() => go("changes", "prompt")}>Open the prompt</Button>}>
      {err ? <p className="text-sm text-destructive">{err}</p> : md ? <CodeView maxHeight="40svh" tabs={[{ id: "brief", label: "emoji brief", code: md, lang: "text", filename: "emoji-brief.md", mime: "text/markdown" }]} /> : <Loader2 className="size-4 animate-spin" />}
    </Section>
  );
}

export function EmojiView() {
  const { loaded } = useStudio();
  const { doc, editable, loading } = useEmoji();
  const [open, setOpen] = useState<Entry | null>(null);
  const route = ROUTES[(loaded.project.capabilities ?? {}).customEmoji ?? "none"] ?? ROUTES.none;
  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 p-3 sm:p-5">
      <header className="space-y-1">
        <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">Premium emoji {loading && <Loader2 className="size-4 animate-spin text-muted-foreground" />}</h2>
        <p className="text-sm text-muted-foreground">Import your emoji packs, decide what each emoji means in this bot, then use them in texts and on buttons. The simulator and every preview show the real pictures.</p>
        <p className={cn("flex items-start gap-1.5 text-xs", route.ok ? "text-muted-foreground" : "text-amber-700 dark:text-amber-400")}>
          {!route.ok && <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden />}{route.text}
        </p>
        {doc.error && <p className="text-sm text-destructive">{doc.error.code}: {doc.error.message}</p>}
      </header>
      <ImportCard preview={!editable} />
      <Suggestions />
      <IconMap onOpen={setOpen} />
      <Packs onOpen={setOpen} />
      <AgentBrief />
      <SlotDialog entry={open} onClose={() => setOpen(null)} />
    </div>
  );
}
