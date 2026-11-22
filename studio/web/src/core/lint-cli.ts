// node lint-cli.ts <project-root> <cases.json>: apply each failure case to the project in
// memory and print {name: [{code, pointer}]} from lintScreen. Used by tests/test_bot_ui_parity.py.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { lintScreen } from "./lint.ts";

const [root, casesPath] = process.argv.slice(2);
const read = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const project = read(join(root, "project.json"));
const base: Record<string, any> = {};
for (const f of readdirSync(join(root, "screens"))) if (f.endsWith(".json")) { const d = read(join(root, "screens", f)); base[d.id] = d; }
const tokens = (p: string) => p.split("/").slice(1).map((t) => t.replace(/~1/g, "/").replace(/~0/g, "~"));
const out: Record<string, any> = {};
for (const c of read(casesPath).cases) {
  const screens = structuredClone(base);
  const doc = screens[c.screenId];
  for (const op of c.ops) {
    const t = tokens(op.path);
    let cur = doc;
    for (const k of t.slice(0, -1)) cur = cur[k] ??= {};
    if (op.op === "remove") delete cur[t[t.length - 1]]; else cur[t[t.length - 1]] = op.value;
  }
  out[c.name] = lintScreen({ project, screens }, c.screenId).map((d) => ({ code: d.code, pointer: d.pointer, severity: d.severity }));
}
process.stdout.write(JSON.stringify(out));
