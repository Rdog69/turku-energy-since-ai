// pnpm bundle: put public/payload.json inside dist/index.html as <script id="payload" type="application/json">,
// so bundle.html works offline from a single file. Local only: it holds licensed Nord Pool spot prices.
import { readFileSync, writeFileSync } from "node:fs";
const html = readFileSync("dist/index.html", "utf8");
const data = readFileSync("public/payload.json", "utf8").replace(/</g, "\\u003c");
const tag = `<script id="payload" type="application/json">${data}</script>`;
writeFileSync("bundle.html", html.replace("</head>", `${tag}</head>`));
console.log(`bundle.html: ${(Buffer.byteLength(html) / 1e6).toFixed(1)} MB app + ${(data.length / 1e6).toFixed(1)} MB data`);
