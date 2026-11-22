// node parity-cli.ts <project-root>: run every scenario through the TypeScript engine and
// print {scenarioId: parityView} as JSON. Used by tests/test_bot_ui_parity.py.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parityView, runScenario } from "./engine.ts";

const root = process.argv[2];
const read = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const project = read(join(root, "project.json"));
const screens: Record<string, any> = {};
for (const f of readdirSync(join(root, "screens"))) if (f.endsWith(".json")) { const d = read(join(root, "screens", f)); screens[d.id] = d; }
const out: Record<string, any> = {};
for (const f of readdirSync(join(root, "scenarios")).sort()) {
  const sc = read(join(root, "scenarios", f));
  out[sc.scenarioId] = parityView(runScenario({ project, screens }, sc));
}
process.stdout.write(JSON.stringify(out));
