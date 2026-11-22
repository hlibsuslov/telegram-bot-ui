import { GitCompareArrows, Sprout, Wrench, Info, LayoutGrid, Loader2, Map as MapIcon, MessagesSquare, Puzzle, Redo2, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { ApplicationShell1, type Crumb, type NavGroup } from "@/components/application-shell1";
import { Button } from "@/components/ui/button";
import { SidebarMenu, SidebarMenuItem } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { api, errorText } from "@/lib/api";
import { embeddedSnapshot, fromProjectDocument, fromSnapshot, shortRev, type Loaded } from "@/lib/model";
import { href, useRoute, type Section } from "@/lib/route";
import { StudioProvider, useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { AboutView, LoadSnapshot } from "@/features/artifact/AboutView";
import { ChangesView } from "@/features/changes/ChangesView";
import { ChangeTray, EditLocaleSelect } from "@/features/changes/Tray";
import { PendingBanner } from "@/features/changes/PendingBanner";
import { MapView } from "@/features/map/MapView";
import { ScreensView } from "@/features/screens/ScreensView";
import { SimulatorView } from "@/features/simulator/SimulatorView";
import { WidgetsView } from "@/features/widgets/WidgetsView";

const TITLES: Record<Section, string> = { map: "Map", screens: "Screens", simulator: "Simulator", widgets: "Widgets", changes: "Changes", task: "Task for the agent", about: "What works here" };

function Brand() {
  const { loaded, store } = useStudio();
  const n = store.count();
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <div className="flex items-center gap-2 rounded-md p-2 group-data-[collapsible=icon]:p-0">
          <div className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground" aria-hidden>
            {loaded.title.slice(0, 1).toUpperCase()}
          </div>
          <div className="grid min-w-0 flex-1 gap-1 leading-none group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-medium" title={loaded.title}>{loaded.title}</span>
            <span className="flex flex-wrap items-center gap-1">
              <span className="rounded border px-1 py-0.5 font-mono text-[10px] text-muted-foreground" title={loaded.revision}>rev {shortRev(loaded.revision)}</span>
              <a href={href("changes")} className={cn("rounded px-1 py-0.5 text-[10px]", n ? "bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-50" : "text-muted-foreground")}>
                {n ? `${n} draft change${n === 1 ? "" : "s"}` : "no drafts"}
              </a>
            </span>
          </div>
        </div>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

function Footer() {
  const { loaded } = useStudio();
  return (
    <div className="space-y-2 px-2 pb-1 text-[11px] text-muted-foreground group-data-[collapsible=icon]:hidden">
      {loaded.mode === "studio" ? (
        <p>Local Studio on this machine{loaded.rootLabel ? <> · <span className="font-mono">{loaded.rootLabel}</span></> : null}. Nothing is sent to Telegram.</p>
      ) : (
        <>
          <p>Offline artifact: a snapshot in one file. No network.</p>
          <LoadSnapshot />
        </>
      )}
    </div>
  );
}

/** Beginner hides code, JSON and advanced fields; Pro shows everything. Remembered per browser. */
function ModeSwitch() {
  const { pro, setPro } = useStudio();
  return (
    <div role="radiogroup" aria-label="Interface mode" className="hidden items-center rounded-lg bg-muted p-0.5 sm:flex">
      {[{ v: false, label: "Beginner", icon: Sprout }, { v: true, label: "Pro", icon: Wrench }].map(({ v, label, icon: Icon }) => (
        <button key={label} type="button" role="radio" aria-checked={pro === v} onClick={() => setPro(v)} title={v ? "Pro: code, JSON and every field" : "Beginner: plain forms, no code"}
          className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs text-muted-foreground aria-checked:bg-background aria-checked:text-foreground aria-checked:shadow-sm">
          <Icon className="size-3.5" aria-hidden />{label}
        </button>
      ))}
    </div>
  );
}

function Toasts() {
  const { toasts } = useStudio();
  return (
    <div className="pointer-events-none fixed right-3 bottom-3 z-50 flex w-[min(92vw,24rem)] flex-col gap-2" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={cn("pointer-events-auto rounded-md border bg-background px-3 py-2 text-sm shadow-lg",
          t.tone === "error" && "border-destructive text-destructive", t.tone === "success" && "border-emerald-600")}>{t.text}</div>
      ))}
    </div>
  );
}

function Shell() {
  const { loaded, store, validating, caps, working, requests } = useStudio();
  const route = useRoute();
  const n = store.count();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, [contenteditable=true]")) return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); store.undo(); }
      else if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); store.redo(); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [store]);

  useEffect(() => { document.title = `${TITLES[route.section]}${route.id ? ` · ${route.id}` : ""} · ${loaded.title} · bot-ui`; }, [route, loaded.title]);

  const widgetIds = Object.keys(loaded.widgets).sort();
  const navGroups: NavGroup[] = [{
    title: loaded.mode === "studio" ? "Studio" : "Artifact",
    items: [
      { key: "map", label: "Map", icon: MapIcon, href: href("map") },
      { key: "screens", label: "Screens", icon: LayoutGrid, href: href("screens"), badge: Object.keys(working.screens).length },
      { key: "simulator", label: "Simulator", icon: MessagesSquare, href: href("simulator") },
      { key: "widgets", label: "Widgets", icon: Puzzle, href: href("widgets"), children: caps.widgets && widgetIds.length > 1 ? widgetIds.map((w) => ({ key: w, label: w, href: href("widgets", w) })) : undefined },
      { key: "changes", label: "Changes", icon: GitCompareArrows, href: href("changes"), badge: n + requests.length || undefined },
      ...(loaded.mode === "artifact" ? [{ key: "about", label: "What works here", icon: Info, href: href("about") }] : []),
    ],
  }];
  const trail: Crumb[] = [{ label: loaded.title, href: href("map") }, { label: TITLES[route.section], href: href(route.section) }];
  if (route.id) trail.push({ label: route.id });
  const active = route.section === "widgets" && route.id ? `widgets:${route.id}` : route.section;

  const headerEnd = (
    <>
      <ModeSwitch />
      <ChangeTray />
      <EditLocaleSelect />
      {validating && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Checking the draft" />}
      <span className="hidden rounded border px-1.5 py-0.5 text-[11px] text-muted-foreground sm:inline">{loaded.mode === "studio" ? "Local Studio" : "Artifact · offline"}</span>
      <Button size="icon" variant="ghost" className="size-8" onClick={() => store.undo()} disabled={!store.past.length} aria-label="Undo (Ctrl+Z)" title="Undo (Ctrl+Z)"><Undo2 className="size-4" /></Button>
      <Button size="icon" variant="ghost" className="size-8" onClick={() => store.redo()} disabled={!store.future.length} aria-label="Redo (Ctrl+Y)" title="Redo (Ctrl+Y)"><Redo2 className="size-4" /></Button>
    </>
  );

  let body;
  switch (route.section) {
    case "screens": body = <ScreensView id={route.id} />; break;
    case "simulator": body = <SimulatorView />; break;
    case "widgets": body = <WidgetsView id={route.id} />; break;
    case "changes": case "task": body = <ChangesView anchor={route.section === "task" ? "prompt" : route.id} />; break;
    case "about": body = <AboutView />; break;
    default: body = <MapView id={route.id} />;
  }

  return (
    <ApplicationShell1 brand={<Brand />} navGroups={navGroups} footer={<Footer />} active={active} trail={trail}
      headerEnd={headerEnd} mobileTitle={`${TITLES[route.section]} · ${loaded.title}`}>
      <PendingBanner />
      {loaded.readOnly && <div className="border-b bg-muted px-4 py-2 text-sm">This project's schema version is not supported: it opens read-only.</div>}
      {!store.storageOk && <div className="border-b bg-muted px-4 py-2 text-sm">This browser does not keep drafts (storage is blocked); they last until the tab closes.</div>}
      {body}
      <Toasts />
    </ApplicationShell1>
  );
}

function Failure({ message, onLoad }: { message: string; onLoad: (l: Loaded) => void }) {
  return (
    <main className="mx-auto max-w-xl space-y-3 p-8">
      <h1 className="text-lg font-semibold">The Studio could not open the project</h1>
      <p className="font-mono text-sm break-words text-destructive">{message}</p>
      <p className="text-sm text-muted-foreground">Start it with <code className="font-mono">py -3 studio/bot-ui.py studio --project &lt;bot-ui folder&gt;</code> and open the printed URL, or load a snapshot JSON exported with <code className="font-mono">bot-ui export-snapshot --format json</code>.</p>
      <input type="file" accept="application/json,.json" aria-label="Load snapshot JSON" className="text-sm"
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { try { onLoad(fromSnapshot(JSON.parse(await f.text()))); } catch (ex) { alert((ex as Error).message); } } }} />
    </main>
  );
}

export default function App() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const snap = embeddedSnapshot();
    if (snap) {
      try { setLoaded(fromSnapshot(snap)); } catch (e) { setError((e as Error).message); }
      return;
    }
    api("/api/project").then((res) => {
      if (res.ok) setLoaded(fromProjectDocument(res.data));
      else setError(errorText(res.data));
    });
  }, []);
  if (error && !loaded) return <Failure message={error} onLoad={setLoaded} />;
  if (!loaded) return <div className="flex h-svh items-center justify-center text-sm text-muted-foreground"><Loader2 className="mr-2 size-4 animate-spin" /> Opening the project…</div>;
  return (
    <TooltipProvider delayDuration={300}>
      <StudioProvider initial={loaded}>
        <Shell />
      </StudioProvider>
    </TooltipProvider>
  );
}
