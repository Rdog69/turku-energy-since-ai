#!/bin/bash
# Run LOCALLY in the background: wait until LUMI accepts ssh again, sync the repo, submit the history queue.
cd "$(dirname "$0")/.."
until ssh -o ConnectTimeout=10 -o BatchMode=yes amojahid@lumi.csc.fi true 2>/dev/null; do sleep 300; done
echo "$(date) LUMI is back"
./lumi/sync.sh
N=$(LAB_HISTORY=1 .venv/bin/python -c "from pathlib import Path; from experiments.lab.queue import jobs_from; print(len(jobs_from(Path('lumi/queue_lumi.jsonl'))))")
ssh amojahid@lumi.csc.fi "cd ~/te && mkdir -p lumi/logs lumi/results && sbatch --array=0-$((N-1))%40 --export=ALL,QUEUE=lumi/queue_lumi.jsonl lumi/hist.sbatch" | tee lumi/hist_jobid.txt
