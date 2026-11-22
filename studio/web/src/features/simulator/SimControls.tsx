// Toolbar pieces of the simulator: a tooltip wrapper, the searchable "Start from" picker,
// the language chip and the chat-type switch.
import {
  AlertTriangle, Bell, Check, ChevronsUpDown, Circle, CircleCheck, FileText, Hourglass, Inbox, LayoutList, ListChecks, Loader, Menu,
  Play, Terminal, User, Users, Zap, type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Doc } from "@/core/render.ts";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { defaultLocale } from "@/lib/model";
import { useStudio } from "@/lib/studio";
import { cn } from "@/lib/utils";
import { firstLine } from "../inspector/fields";

/** Tooltip for icon controls; the child keeps its own aria-label. */
export function Tip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}

export const KIND_ICON: Record<string, LucideIcon> = {
  entry: Play, menu: Menu, form: FileText, confirmation: CircleCheck, result: Check, error: AlertTriangle,
  empty: Inbox, loading: Loader, notification: Bell, status: Hourglass,
};

/** Start value: cmd:<command> | ev:<eventKey> | scenario:<id> | screen:<id> */
export function startLabel(start: string): { icon: LucideIcon; text: string } {
  const [kind, rest] = [start.slice(0, start.indexOf(":")), start.slice(start.indexOf(":") + 1)];
  if (kind === "cmd") return { icon: Terminal, text: `/${rest}` };
  if (kind === "ev") return { icon: Zap, text: rest };
  if (kind === "scenario") return { icon: ListChecks, text: rest };
  return { icon: LayoutList, text: rest };
}

export function StartPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { loaded, working, editLocale } = useStudio();
  const [open, setOpen] = useState(false);
  const def = defaultLocale(loaded.project);
  const eps: Doc[] = loaded.project.entryPoints ?? [];
  const commands = eps.filter((e) => e.type === "command");
  const events = eps.filter((e) => e.type === "event");
  const scenarios = Object.values<Doc>(loaded.scenarios ?? {});
  const screens = Object.keys(working.screens).sort();
  const cur = startLabel(value);
  const pick = (v: string) => { onChange(v); setOpen(false); };
  const item = (v: string, Icon: LucideIcon, main: ReactNode, sub: string, search: string) => (
    <CommandItem key={v} value={`${v} ${search}`} onSelect={() => pick(v)} className="items-start gap-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px]">{main}</span>
        {sub && <span className="block truncate text-[11px] text-muted-foreground">{sub}</span>}
      </span>
      {v === value && <Check className="mt-0.5 size-4 shrink-0" />}
    </CommandItem>
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tip label="Where the chat starts">
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" role="combobox" aria-expanded={open} aria-label={`Start from ${cur.text}`} className="h-8 max-w-[15rem] justify-between gap-2 px-2.5">
            <cur.icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 truncate font-mono text-[12.5px]">{cur.text}</span>
            <ChevronsUpDown className="size-3.5 shrink-0 opacity-50" aria-hidden />
          </Button>
        </PopoverTrigger>
      </Tip>
      <PopoverContent align="start" className="w-[min(94vw,26rem)] p-0">
        <Command filter={(v, s) => (v.toLowerCase().includes(s.toLowerCase()) ? 1 : 0)}>
          <CommandInput placeholder="Search commands, events, scenarios, screens…" />
          <CommandList className="max-h-[60svh]">
            <CommandEmpty>Nothing matches.</CommandEmpty>
            {commands.length > 0 && (
              <CommandGroup heading="Commands">
                {commands.map((c) => item(`cmd:${c.command}`, Terminal, <span className="font-mono">/{c.command}</span>, `opens ${c.screen}`, `/${c.command} ${c.screen}`))}
              </CommandGroup>
            )}
            {events.length > 0 && (
              <CommandGroup heading="Events from your server">
                {events.map((e) => item(`ev:${e.eventKey}`, Zap, <span className="font-mono">{e.eventKey}</span>, `sends ${e.screen}`, `${e.eventKey} ${e.screen}`))}
              </CommandGroup>
            )}
            {scenarios.length > 0 && (
              <CommandGroup heading="Scenarios (recorded runs)">
                {scenarios.map((x) => item(`scenario:${x.scenarioId}`, ListChecks, <span className="font-mono">{x.scenarioId}</span>, x.title ?? "", `${x.scenarioId} ${x.title ?? ""}`))}
              </CommandGroup>
            )}
            <CommandGroup heading="Open a screen directly">
              {screens.map((sid) => {
                const s = working.screens[sid];
                const line = firstLine(s, editLocale, def);
                return item(`screen:${sid}`, KIND_ICON[s.kind] ?? Circle,
                  <span><span className="font-mono">{sid}</span> <span className="text-muted-foreground">· {s.title}</span></span>, line, `${sid} ${s.title ?? ""} ${s.kind ?? ""} ${line}`);
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function LocaleChip({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  if (options.length < 2) return null;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tip label="Language of the user">
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 w-12 px-0 font-mono text-xs uppercase" aria-label={`User language: ${value}`}>{value}</Button>
        </PopoverTrigger>
      </Tip>
      <PopoverContent align="start" className="w-28 p-1">
        <div role="listbox" aria-label="User language">
          {options.map((l) => (
            <button key={l} type="button" role="option" aria-selected={l === value} onClick={() => { onChange(l); setOpen(false); }}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 font-mono text-xs uppercase hover:bg-muted aria-selected:bg-muted">
              {l}{l === value && <Check className="size-3.5" />}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function ChatTypeSwitch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const opts = [{ v: "private", icon: User, label: "Private chat" }, { v: "group", icon: Users, label: "Group chat" }];
  return (
    <div role="radiogroup" aria-label="Chat type" className="inline-flex h-8 items-center rounded-lg bg-muted p-0.5">
      {opts.map(({ v, icon: Icon, label }) => (
        <Tip key={v} label={label}>
          <button type="button" role="radio" aria-checked={value === v} aria-label={label} onClick={() => onChange(v)}
            className={cn("flex h-7 w-8 items-center justify-center rounded-md text-muted-foreground aria-checked:bg-background aria-checked:text-foreground aria-checked:shadow-sm")}>
            <Icon className="size-4" aria-hidden />
          </button>
        </Tip>
      ))}
    </div>
  );
}

