// Folds dist-artifact/ into one self-contained dist-artifact/index.html: the built JS and CSS
// go inline, a meta CSP forbids all network, and the snapshot placeholder that
// studio/bot_ui/artifact.py fills (first occurrence of the mark) sits before the script.
import { readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dir = join(import.meta.dirname, "..", "dist-artifact");
const MARK = "__BOT_UI_SNAPSHOT__";
const CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'";

let html = readFileSync(join(dir, "index.html"), "utf8");
const assets = join(dir, "assets");
const files = readdirSync(assets);
const js = files.filter((f) => f.endsWith(".js"));
const css = files.filter((f) => f.endsWith(".css"));
const other = files.filter((f) => !f.endsWith(".js") && !f.endsWith(".css"));
if (js.length !== 1 || css.length > 1 || other.length) {
  throw new Error(`expected one JS and at most one CSS asset, got ${files.join(", ")}`);
}

const read = (f) => readFileSync(join(assets, f), "utf8");
const script = read(js[0]).replace(/<\/script/gi, "<\\/script");
const style = css.length ? read(css[0]).replace(/<\/style/gi, "<\\/style") : "";
for (const src of [script, style]) {
  if (src.includes(MARK)) throw new Error(`the bundle contains ${MARK}; artifact.py would replace it instead of the snapshot`);
  if (/https?:\/\/[^\s"'`)]*\.(woff2?|ttf|otf|css)\b/.test(src)) throw new Error("the bundle references a remote font or stylesheet");
}

const scriptTag = new RegExp(`<script[^>]*src="\\./assets/${js[0].replace(/\./g, "\\.")}"[^>]*></script>\\s*`);
const linkTag = css.length ? new RegExp(`<link[^>]*href="\\./assets/${css[0].replace(/\./g, "\\.")}"[^>]*>\\s*`) : null;
if (!scriptTag.test(html) || (linkTag && !linkTag.test(html))) throw new Error("could not find the built asset tags in index.html");

// Replacement callbacks, so `$` sequences in the bundle are kept literally.
html = html.replace(scriptTag, () => "");
if (linkTag) html = html.replace(linkTag, () => "");
html = html.replace(/<meta name="bot-ui-token"[^>]*>\s*/, () => "");
html = html.replace(/<meta name="bot-ui-mode"[^>]*>\s*/, () => "");
html = html.replace("<meta charset=\"utf-8\" />", () => `<meta charset="utf-8" />\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`);
html = html.replace("</head>", () => `    <style>${style}</style>\n    <script id="bot-ui-snapshot" type="application/json">${MARK}</script>\n  </head>`);
html = html.replace("</body>", () => `    <script type="module">${script}</script>\n  </body>`);

if (html.indexOf(MARK) !== html.lastIndexOf(MARK)) throw new Error("the snapshot mark appears more than once");
if (!html.includes(CSP)) throw new Error("CSP meta missing");

rmSync(assets, { recursive: true });
writeFileSync(join(dir, "index.html"), html);
console.log(`dist-artifact/index.html: ${(Buffer.byteLength(html) / 1024).toFixed(0)} KiB, one file, inline JS + CSS, CSP: ${CSP}`);
