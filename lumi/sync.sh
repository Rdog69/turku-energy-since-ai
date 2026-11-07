#!/bin/bash
# Run LOCALLY: copy the repo to LUMI ~/te (private home), without venvs, git objects or local caches.
set -euo pipefail
cd "$(dirname "$0")/.."
rsync -az --delete --exclude .venv/ --exclude .git/ --exclude .venv-lumi/ --exclude 'experiments/lab/_cache/' \
  --exclude 'external_data/_cache/' --exclude '.kimi/' --exclude 'TurkuEnergia_SinceAI2026/' --exclude '.env' \
  --exclude 'lumi/logs/' --exclude 'lumi/results/' ./ amojahid@lumi.csc.fi:te/
ssh amojahid@lumi.csc.fi 'chmod 700 ~/te'
echo synced
