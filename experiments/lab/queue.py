"""Local job queue: keeps N experiments running (one process per fold), skips finished jobs on restart.

    LAB_HISTORY=1 nohup .venv/bin/python -m experiments.lab.queue lumi/queue_hist.jsonl --jobs 4 --threads 2 &

Each line of the queue file is one job:
    {"spec": {...combo spec...}}                          -> lab run, one process per fold (A, B, C in history mode)
    {"spec": {...}, "folds": ["A"]}                       -> only these folds
    {"spec": {...}, "mode": "test", "tag": "h_x"}         -> submit.py test file submissions/forecast_backtest_<tag>.csv
Lines can be appended while the queue runs; it re-reads the file between launches. Done jobs are recorded in
<queue file>.done, so a restart continues where it stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .data import FOLDS

ROOT = Path(__file__).resolve().parents[2]
LOGS = Path(__file__).resolve().parent / "_logs"


def jobs_from(qfile: Path) -> list[dict]:
    out = []
    for line in qfile.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        j = json.loads(line)
        if j.get("mode") == "test":
            out.append({"key": f"test:{j['tag']}", "cmd": ["-m", "experiments.lab.submit", "--mode", "test", "--spec",
                                                          json.dumps(j["spec"]), "--tag", j["tag"]]})
        else:
            for f in j.get("folds") or list(FOLDS):
                spec = dict(j["spec"], folds=[f])
                out.append({"key": f"lab:{spec['name']}:{f}", "cmd": ["-m", "experiments.lab.combo", json.dumps(spec)]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queue")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--one", type=int, help="run only job number ONE (0-based, e.g. a Slurm array task) and exit")
    a = ap.parse_args()
    qfile = Path(a.queue)
    if a.one is not None:                      # LUMI: lumi/hist.sbatch runs one job per array task
        j = jobs_from(qfile)[a.one]
        print("job", a.one, j["key"], flush=True)
        sys.exit(subprocess.call([sys.executable, "-u", "-W", "ignore"] + j["cmd"], cwd=ROOT))
    donef = qfile.with_suffix(qfile.suffix + ".done")
    done = set(donef.read_text().splitlines()) if donef.exists() else set()
    running: dict[str, subprocess.Popen] = {}
    failed: set[str] = set()
    LOGS.mkdir(exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS=str(a.threads), PYTHONWARNINGS="ignore")
    while True:
        for k, p in list(running.items()):
            if p.poll() is not None:
                running.pop(k)
                status = "ok" if p.returncode == 0 else f"FAILED rc={p.returncode}"
                print(time.strftime("%H:%M"), status, k, flush=True)
                if p.returncode == 0:
                    done.add(k)
                    with open(donef, "a") as fh:
                        fh.write(k + "\n")
                else:
                    failed.add(k)            # not retried in this run; see its log
        todo = [j for j in jobs_from(qfile) if j["key"] not in done | failed and j["key"] not in running]
        while todo and len(running) < a.jobs:
            j = todo.pop(0)
            log = LOGS / ("q_" + j["key"].replace(":", "_").replace(" ", "_").replace("/", "-")[:110] + ".log")
            running[j["key"]] = subprocess.Popen([sys.executable, "-u", "-W", "ignore"] + j["cmd"], cwd=ROOT, env=env,
                                                 stdout=open(log, "w"), stderr=subprocess.STDOUT)
            print(time.strftime("%H:%M"), "start", j["key"], flush=True)
        if not running and not todo:
            print(time.strftime("%H:%M"), "queue empty", flush=True)
            break
        time.sleep(20)


if __name__ == "__main__":
    main()
