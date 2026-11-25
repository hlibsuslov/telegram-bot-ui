// builder/v1 schema types (studio/docs/widget-builder.md). The Studio renders whatever
// /api/widget/builder-schema returns (skills/telegram-bot-ui/scripts/bot_ui/builder.py owns the content).
import type { Doc } from "@/core/render.ts";

export interface BField {
  key: string; label: string; type: "text" | "number" | "toggle" | "choice" | "color" | "datetime" | "list" | "action" | "image";
  help?: string; default?: any; localized?: boolean; max?: number; min?: number; step?: number; multiline?: boolean;
  options?: { value: any; label: string }[]; when?: { key: string; eq?: any; in?: any[] }; item?: { fields: BField[] };
  minItems?: number; maxItems?: number; toggle?: string; unit?: string;
}
export interface BSection { id: string; title: string; help?: string; fields: BField[] }
export interface BType { title: string; summary: string; icon?: string; sections: BSection[]; states: { id: string; title: string }[]; defaults: Doc }
export interface BPreset { id: string; title: string; values: Doc }
export interface BSchema {
  version: number;
  types: Record<string, BType>;
  style: { sections: BSection[]; presets: BPreset[]; colorSlots: Record<string, { key: string; label: string }[]> };
}
