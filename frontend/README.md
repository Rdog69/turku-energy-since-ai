# Tasehinta: imbalance price outlook

The situation view for the Turku Energia imbalance-price forecast (Level 2 of the challenge). It replays every hourly forecast of a period exactly as it was known at that hour:

- **Next 10 hours:** a fan chart of the forecast (10–90 % band, median) against spot and the ±50 €/MWh spike lines, with the balancing direction and the high/low spike risk per quarter-hour.
- **Worth checking:** high- or low-price risk, likely up-regulation, forecasts that moved materially since the previous hour, the two models disagreeing, very wide uncertainty. Each item has its drivers and what to check.
- **Hindsight:** how the forecasts made before the review time did, scored only against prices published by then.
- **Time travel:** a slider over every forecast hour, arrow keys (Shift for a day), Play. English and Finnish.

## Run it

Needs Node.js 20.19 or newer (Vite 8) and pnpm 9 (`npx -y pnpm@9.15.9 ...` works without installing it).
Install with the Node version you will build with: pnpm skips Vite's native bundler module on older Node.

```bash
# 1. data (needs the starter package and the forecast files; writes public/payload.json, git-ignored)
python frontend/scripts/build_data.py          # run from the repo root with the project's Python env

# 2. app
cd frontend
pnpm install --frozen-lockfile
pnpm dev                                       # http://localhost:5173

# 3. one offline file for the demo (bundle.html, git-ignored)
pnpm bundle                                    # macOS / Linux
```

On Windows, `pnpm bundle` fails on its `rm`; run its three steps instead:

```bash
pnpm exec vite build --mode single
rm -f dist/payload.json                        # Git Bash; PowerShell: Remove-Item dist/payload.json -ErrorAction Ignore
node scripts/inline_payload.mjs
```

`payload.json` and `bundle.html` contain Nord Pool spot prices, licensed to Turku Energia for the hackathon only: keep them on your machine, don't host or publish them, and delete them after the event.

Stack: React + TypeScript + Vite + Tailwind + shadcn/ui (Radix), d3-scale/d3-shape for the charts, Source Sans 3 (SIL OFL) embedded.
