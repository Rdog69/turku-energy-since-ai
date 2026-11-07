#!/usr/bin/env python3
"""FAST loop: Featherless models design blends + post-processing over SAVED predictions (seconds per test).

    .venv/bin/python tools/fl_post.py --threads 2 --hours 8

Anti-overfitting design: proposers only ever see fold B (Aug) scores. Fold A (Sep, the organisers' window)
is computed but hidden from them, and used to judge whether a recipe generalises.
Results: experiments/lab/post_board.csv (both folds), experiments/lab/post_log.md.
Stop: experiments/lab/post_control.json {"stop": true}.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import random
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import kimi  # noqa: E402
from experiments.lab import ensemble as E  # noqa: E402
from experiments.lab.models import metrics  # noqa: E402

LAB = ROOT / "experiments/lab"
BOARD, LOG, CTRL = LAB / "post_board.csv", LAB / "post_log.md", LAB / "post_control.json"
W = dict(MAE=30, pinball=20, brier_spike=20, brier_dir=10)
PROPOSERS = ["deepseek-ai/DeepSeek-V4.1-Flash-1017", "zai-org/GLM-5.3", "deepseek-ai/DeepSeek-V4.1-Flash-1017",
             "moonshotai/Kimi-K3", "zai-org/GLM-5.2", "deepseek-ai/DeepSeek-V4-Flash"]
LOCK = threading.Lock()

RUNS = E.load()
TAGS = sorted(RUNS)
IDX = {f: RUNS[TAGS[0]][f]["idx"] for f in "AB"}
TGT = {f: E.targets(IDX[f]) for f in "AB"}
BASE = E.base
TRAIN_RATE = {}
for f in "AB":
    tr = BASE[(BASE[f"fold{f}"] == "train") & BASE.gap.notna()]
    TRAIN_RATE[f] = ((tr.gap > 50).mean(), (tr.gap < -50).mean(), (tr.dir == 1).mean())


def fold_score(m, f):
    return sum(w * (E.REF[f][k] - m[k]) / E.REF[f][k] for k, w in W.items())


def single_metrics():
    rows = []
    for t in TAGS:
        y, s, d, st = TGT["B"]
        m = metrics(RUNS[t]["B"], y, s, d, st)
        rows.append(dict(tag=t, scoreB=round(fold_score(m, "B"), 3), **{k: round(m[k], 4) for k in W}))
    return pd.DataFrame(rows).sort_values("scoreB", ascending=False)


SINGLES = single_metrics()


def logit(p):
    p = np.clip(p, 1e-5, 1 - 1e-5); return np.log(p / (1 - p))


def sig(z):
    return 1 / (1 + np.exp(-z))


def apply(recipe: dict, f: str) -> dict:
    out = {}
    for g, keys in E.GROUPS.items():
        mem = recipe["members"].get(g) or recipe["members"].get("all")
        tags = [m[0] for m in mem]; w = np.array([max(float(m[1]), 0) for m in mem]); w = w / w.sum()
        for k in keys:
            out[k] = np.tensordot(w, np.stack([RUNS[t][f][k] for t in tags]), 1)
    p = recipe.get("post", {})
    st = TGT[f][3]
    if p.get("q_width"):            # scale interval half-widths around p50
        s = float(p["q_width"])
        out["p10"] = out["p50"] - s * (out["p50"] - out["p10"]); out["p90"] = out["p50"] + s * (out["p90"] - out["p50"])
    if p.get("q_width_short") and p.get("q_width_short") != 1:   # steps 1-8 only
        s, m = float(p["q_width_short"]), st <= 8
        out["p10"][m] = out["p50"][m] - s * (out["p50"][m] - out["p10"][m]); out["p90"][m] = out["p50"][m] + s * (out["p90"][m] - out["p50"][m])
    if p.get("p50_shift"):
        out["p50"] = out["p50"] + float(p["p50_shift"])
    if p.get("dir_temp"):           # temperature on logit P(up | not none)
        pn = out["p_none"]; q = out["p_up"] / np.maximum(out["p_up"] + out["p_down"], 1e-9)
        q = sig(logit(q) / float(p["dir_temp"])); out["p_up"], out["p_down"] = (1 - pn) * q, (1 - pn) * (1 - q)
    if p.get("spike_temp"):
        for k in ("p_hi", "p_lo"):
            out[k] = sig(logit(out[k]) / float(p["spike_temp"]))
    if p.get("spike_shrink"):       # shrink toward the fold's TRAINING base rates (no validation info)
        a = float(p["spike_shrink"]); hi, lo, _ = TRAIN_RATE[f]
        out["p_hi"] = (1 - a) * out["p_hi"] + a * hi; out["p_lo"] = (1 - a) * out["p_lo"] + a * lo
    return E.fix(out)


def evaluate(recipe: dict) -> dict:
    res = {}
    for f in "AB":
        y, s, d, st = TGT[f]
        m = metrics(apply(recipe, f), y, s, d, st)
        res[f] = dict(score=round(fold_score(m, f), 3), **{k: round(float(m[k]), 4) for k in W})
    return res


def validate(r: dict) -> dict:
    mem = r.get("members", {})
    assert isinstance(mem, dict) and mem
    clean = {}
    for g, lst in mem.items():
        assert g in ("all", *E.GROUPS)
        lst = [(str(t), float(w)) for t, w in lst][:6]
        for t, _ in lst:
            if t not in RUNS:
                raise ValueError(f"unknown run {t}")
        clean[g] = lst
    if "all" not in clean:
        assert all(g in clean for g in E.GROUPS), "give 'all' or all four groups"
    post = {}
    rng = dict(q_width=(0.7, 1.4), q_width_short=(0.7, 1.4), p50_shift=(-5, 5), dir_temp=(0.6, 1.6),
               spike_temp=(0.6, 1.6), spike_shrink=(0, 0.5))
    for k, v in (r.get("post") or {}).items():
        if k in rng and v is not None:
            lo, hi = rng[k]; post[k] = float(min(max(float(v), lo), hi))
    return dict(name=str(r.get("name", "r"))[:60], members=clean, post=post, rationale=str(r.get("rationale", ""))[:200])


def board() -> pd.DataFrame:
    return pd.read_csv(BOARD) if BOARD.exists() else pd.DataFrame()


def record(rows: list[dict]):
    with LOCK:
        df = pd.DataFrame(rows)
        new = not BOARD.exists()
        with open(BOARD, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX); df.to_csv(fh, header=new, index=False); fcntl.flock(fh, fcntl.LOCK_UN)


def prompt(n: int) -> str:
    b = board()
    top = "" if b.empty else b.sort_values("scoreB", ascending=False).drop_duplicates("recipe").head(12)[
        ["name", "scoreB", "MAE_B", "pinball_B", "brier_spike_B", "brier_dir_B", "recipe"]].to_csv(index=False)
    singles = SINGLES.head(45).to_csv(index=False)
    return f"""We forecast the Finnish imbalance price. Each saved RUN below is a model's predictions on the AUGUST validation
fold (fold B). You design ENSEMBLE + POST-PROCESSING recipes over these runs. Metrics (lower is better), weights 30/20/20/10:
MAE of p50, pinball of p10/p90, spike Brier (p_hi/p_lo), direction Brier (p_up/p_down/p_none). scoreB = weighted % gain
over the reference model on fold B (higher is better). Lesson so far: blending DIVERSE runs (e.g. weather 'W6' runs with
'INT' runs) beats averaging near-identical top runs; each column group can use different members/weights.

## Single runs (fold B)
{singles}
## Best recipes so far (fold B)
{top or '(none yet)'}
## Recipe format
{{"name": "...", "members": {{"p50": [["tag", weight], ...], "q": [...], "spike": [...], "dir": [...]}},  (or "all": [...] for every group; max 6 members per group)
 "post": {{"q_width": 0.7-1.4, "q_width_short": 0.7-1.4 (steps 1-8), "p50_shift": -5..5, "dir_temp": 0.6-1.6,
          "spike_temp": 0.6-1.6, "spike_shrink": 0-0.5}},  (all optional)
 "rationale": "one sentence"}}
Use exact tags from the list. Propose {n} NEW recipes that beat the best scoreB, mixing refinement and exploration.
Reply with ONLY a JSON array."""


def parse_objects(text: str) -> list[dict]:
    """Parse a JSON array; if truncated, salvage every complete top-level object."""
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            pass
    out, dec, i = [], json.JSONDecoder(), text.find("{")
    while 0 <= i < len(text):
        try:
            obj, end = dec.raw_decode(text, i)
            if isinstance(obj, dict) and "members" in obj:
                out.append(obj)
            i = text.find("{", end)
        except ValueError:
            i = text.find("{", i + 1)
    return out


def worker(tid: int, hours: float, n: int):
    base, _, keys = kimi.get_config()
    end = time.time() + hours * 3600
    i = tid
    while time.time() < end:
        try:
            if json.loads(CTRL.read_text()).get("stop"):
                return
        except Exception:  # noqa: BLE001
            pass
        model = PROPOSERS[i % len(PROPOSERS)]; i += 2
        key_i = [0, 3][tid % 2] % len(keys)
        try:
            p = prompt(n); kimi.guard(p, allow_data=True)
            text = kimi.call(key_i, keys[key_i], base, model, p, "Output valid JSON only.", 24000, 0.8, f"post-t{tid}")
            recs = parse_objects(text)
        except Exception as e:  # noqa: BLE001
            print(f"[t{tid}] {model}: proposal failed: {str(e)[:120]}"); time.sleep(10); continue
        rows = []
        for r in recs:
            try:
                v = validate(r); res = evaluate(v)
                rows.append(dict(time=time.strftime("%H:%M:%S"), model=model.split("/")[-1], name=v["name"],
                                 scoreB=res["B"]["score"], scoreA_hidden=res["A"]["score"],
                                 **{f"{k}_B": res["B"][k] for k in W}, **{f"{k}_A": res["A"][k] for k in W},
                                 recipe=json.dumps({"members": v["members"], "post": v["post"]}, sort_keys=True),
                                 rationale=v["rationale"]))
            except Exception as e:  # noqa: BLE001
                print(f"[t{tid}] rejected {r.get('name') if isinstance(r, dict) else r}: {str(e)[:80]}")
        if rows:
            record(rows)
            b = board().sort_values("scoreB", ascending=False).iloc[0]
            print(f"[t{tid}] {model.split('/')[-1]}: {len(rows)} recipes; best B {b.scoreB} (its A {b.scoreA_hidden}) {b['name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--hours", type=float, default=8)
    ap.add_argument("--per-call", type=int, default=8)
    a = ap.parse_args()
    CTRL.write_text(json.dumps({"stop": False}))
    print(f"{len(RUNS)} saved runs loaded")
    ts = [threading.Thread(target=worker, args=(t, a.hours, a.per_call)) for t in range(a.threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


if __name__ == "__main__":
    main()
