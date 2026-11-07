#!/usr/bin/env python3
"""Featherless-driven experiment loop: cheap LLMs propose JSON specs, we run them, they see results.

    .venv/bin/python tools/fl_lab.py --rounds 4 --per-round 6 --workers 3

Safety: models never write code. A spec can only combine registry feature sets (each leak-checked)
with whitelisted options; every run goes through run_experiment (both folds, shared leaderboard).
State: experiments/lab/loop_state.jsonl (all specs + outcomes), experiments/lab/loop_log.md (summary).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import kimi  # noqa: E402  (Featherless client: keys, retries, data guard)
from experiments.lab.combo import REGISTRY  # noqa: E402

LAB = ROOT / "experiments/lab"
STATE, LOG, BOARD = LAB / "loop_state.jsonl", LAB / "loop_log.md", LAB / "leaderboard.csv"
CONTEXT = LAB / "loop_context.md"
CONTROL = LAB / "loop_control.json"   # edited live by the coordinator: per_round, workers, stop, steer


def control() -> dict:
    try:
        return json.loads(CONTROL.read_text())
    except Exception:  # noqa: BLE001
        return {}
PROPOSERS = [("deepseek-ai/DeepSeek-V4.1-Flash-1017", 3), ("zai-org/GLM-5.3", 0), ("moonshotai/Kimi-K3", 0),
             ("deepseek-ai/DeepSeek-V4.1-Flash-1017", 3)]
W = dict(MAE=30, pinball=20, brier_spike=20, brier_dir=10)
HGB_KEYS = {"max_iter": (50, 600), "learning_rate": (0.01, 0.3), "max_leaf_nodes": (4, 63),
            "min_samples_leaf": (20, 2000), "l2_regularization": (0.0, 10.0), "max_features": (0.2, 1.0)}


# ----------------------------------------------------------------------------- scoring
def scored_board() -> pd.DataFrame:
    b = pd.read_csv(BOARD)
    ref = b[b.name == "REF package mixture"].set_index("fold")
    rows = []
    for (agent, name), g in b.groupby(["agent", "name"], sort=False):
        g = g.drop_duplicates("fold", keep="last").set_index("fold")
        if not {"A", "B"} <= set(g.index):
            continue
        r = {"agent": agent, "name": name}
        both, score = True, 0.0
        for f in "AB":
            for m, w in W.items():
                rel = (ref.loc[f, m] - g.loc[f, m]) / ref.loc[f, m]
                r[f"{m}_{f}"] = g.loc[f, m]
                score += w * rel / 2
                both &= rel > -0.002
        r["score"], r["all_better_both"] = round(score, 3), both
        r["notes"] = str(g.iloc[-1].get("notes", ""))[:300]
        rows.append(r)
    return pd.DataFrame(rows).sort_values("score", ascending=False)


# ----------------------------------------------------------------------------- specs
def canon(spec: dict) -> str:
    s = {k: v for k, v in spec.items() if k not in ("name", "agent", "rationale")}
    s["features"] = sorted(set(s.get("features", [])) | {"package"})
    return hashlib.sha1(json.dumps(s, sort_keys=True).encode()).hexdigest()[:12]


def validate(spec: dict) -> dict:
    out = {"name": str(spec.get("name", "unnamed"))[:60].replace(",", ";"), "features": []}
    for f in spec.get("features", []):
        if f not in REGISTRY:
            raise ValueError(f"unknown feature set {f}")
        out["features"].append(f)
    out["model"] = spec.get("model", "mixture")
    assert out["model"] in ("mixture", "direct")
    out["target"] = spec.get("target", "gap")
    assert out["target"] in ("gap", "price")
    if spec.get("hgb"):
        h = {}
        for k, v in spec["hgb"].items():
            lo, hi = HGB_KEYS[k]
            h[k] = type(lo)(min(max(v, lo), hi)) if not isinstance(lo, float) else float(min(max(v, lo), hi))
        out["hgb"] = h
    if spec.get("bands"):
        bands = [[int(a), int(b)] for a, b in spec["bands"]]
        assert all(1 <= a <= b <= 40 for a, b in bands) and len(bands) <= 5
        out["bands"] = bands
    for k, lo, hi in (("hist_blend", 0.0, 0.9), ("causal", 0.0, 0.3), ("half_life_days", 20, 400)):
        if spec.get(k) not in (None, 0, False):
            out[k] = float(min(max(float(spec[k]), lo), hi))
    out["calibrate"] = bool(spec.get("calibrate", True))
    out["rationale"] = str(spec.get("rationale", ""))[:300]
    return out


def done_hashes() -> set:
    if not STATE.exists():
        return set()
    return {json.loads(l)["hash"] for l in STATE.read_text().splitlines() if l.strip()}


# ----------------------------------------------------------------------------- proposing
def build_prompt(n: int) -> str:
    sb = scored_board()
    top = sb.head(15)[["agent", "name", "score", "all_better_both", "MAE_A", "MAE_B", "pinball_A", "pinball_B",
                       "brier_spike_A", "brier_spike_B", "brier_dir_A", "brier_dir_B", "notes"]]
    recent = []
    if STATE.exists():
        for l in STATE.read_text().splitlines()[-12:]:
            d = json.loads(l)
            recent.append(f"- {d['spec']['name']}: {d.get('status')} score={d.get('score')} spec={json.dumps({k: v for k, v in d['spec'].items() if k not in ('name', 'rationale')})}")
    reg = "\n".join(f"- `{k}`: {v[2]}" for k, v in REGISTRY.items())
    return f"""{CONTEXT.read_text() if CONTEXT.exists() else ''}

## Feature sets you can combine (`features`; `package` is always added)
{reg}

## Spec options
`model` mixture|direct; `target` gap|price; `hgb` overrides among {list(HGB_KEYS)} (ranges enforced);
`bands` up to 5 step bands [[a,b],...] refit separately; `hist_blend` 0-0.9; `causal` 0-0.3;
`half_life_days` 20-400 or null; `calibrate` true/false.

## Leaderboard (score = points-weighted % improvement vs REF mixture, averaged over folds A and B; higher is better)
{top.to_csv(index=False)}

## Most recent loop experiments
{chr(10).join(recent) or '(none yet)'}

## Coordinator's current instructions
{control().get("steer", "(none)")}

## Your task
Propose exactly {n} NEW experiments that are most likely to raise the score while improving all four metrics on
BOTH folds. Mix exploitation (combine and tune the best components) and exploration (one or two untested
combinations). Don't repeat a spec that already ran. Each run costs ~10-15 CPU minutes, so make every one count.
Reply with ONLY a JSON array, no prose, e.g.
[{{"name": "short unique name", "features": ["rt_wind", "runs"], "model": "mixture", "hgb": {{"max_leaf_nodes": 15,
"min_samples_leaf": 400, "max_iter": 150}}, "bands": [[1,4],[5,8],[9,16]], "hist_blend": 0.6, "rationale": "one sentence"}}]
"""


def propose(n: int, rnd: int) -> list[dict]:
    model, key = PROPOSERS[rnd % len(PROPOSERS)]
    base, _, keys = kimi.get_config()
    prompt = build_prompt(n)
    kimi.guard(prompt, allow_data=True)
    text = kimi.call(key % len(keys), keys[key % len(keys)], base, model, prompt,
                     "You are a careful ML research lead. Output valid JSON only.", 8000, 0.7, f"loop-r{rnd}")
    m = re.search(r"\[.*\]", text, re.S)
    specs = json.loads(m.group(0)) if m else []
    print(f"[round {rnd}] {model} proposed {len(specs)} specs")
    return [dict(s, agent=f"fl-{model.split('/')[-1][:14]}") for s in specs]


# ----------------------------------------------------------------------------- running
def run_one(spec: dict, timeout_min: int) -> dict:
    t0 = time.time()
    env = dict(os.environ, OMP_NUM_THREADS="3", OPENBLAS_NUM_THREADS="3")
    payload = {k: v for k, v in spec.items() if k != "rationale"}
    try:
        r = subprocess.run([str(ROOT / ".venv/bin/python"), "-W", "ignore", "-m", "experiments.lab.combo", json.dumps(payload)],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout_min * 60)
        status = "ok" if r.returncode == 0 else "error"
        err = (r.stderr or "")[-600:] if r.returncode else ""
    except subprocess.TimeoutExpired:
        status, err = "timeout", ""
    score = None
    if status == "ok":
        sb = scored_board()
        hit = sb[(sb.name == spec["name"]) & (sb.agent == spec["agent"])]
        score = float(hit.score.iloc[0]) if len(hit) else None
    return dict(status=status, score=score, minutes=round((time.time() - t0) / 60, 1), error=err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--per-round", type=int, default=6)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout-min", type=int, default=45)
    ap.add_argument("--seed-file", help="JSON array of specs to run first (round 0)")
    a = ap.parse_args()
    LOG.touch(exist_ok=True)
    start_round = sum(1 for l in LOG.read_text().splitlines() if l.startswith("## Round"))
    for rnd in range(start_round, start_round + a.rounds):
        c = control()
        if c.get("stop"):
            print("stop flag set in loop_control.json"); break
        a.per_round, a.workers = int(c.get("per_round", a.per_round)), int(c.get("workers", a.workers))
        try:
            raw = json.loads(Path(a.seed_file).read_text()) if (a.seed_file and rnd == start_round) else propose(a.per_round, rnd)
        except Exception as e:  # noqa: BLE001
            print(f"[round {rnd}] proposal failed: {e}"); time.sleep(30); continue
        seen, specs = done_hashes(), []
        for s in raw:
            try:
                v = validate(s); v["agent"] = s.get("agent", "fl-seed")
                h = canon(v)
                if h not in seen:
                    seen.add(h); specs.append((h, v))
            except Exception as e:  # noqa: BLE001
                print(f"  rejected spec {s.get('name')}: {e}")
        print(f"[round {rnd}] running {len(specs)} specs on {a.workers} workers")
        with ThreadPoolExecutor(a.workers) as ex:
            results = list(ex.map(lambda hv: (hv, run_one(hv[1], a.timeout_min)), specs))
        with open(STATE, "a") as fh:
            for (h, v), res in results:
                fh.write(json.dumps({"hash": h, "round": rnd, "spec": v, **res}) + "\n")
        sb = scored_board()
        with open(LOG, "a") as fh:
            fh.write(f"\n## Round {rnd} ({time.strftime('%H:%M')})\n")
            for (h, v), res in results:
                fh.write(f"- **{v['name']}** [{v['agent']}] {res['status']} score={res['score']} ({res['minutes']} min): {v.get('rationale', '')}\n")
                if res["error"]:
                    fh.write(f"  - error: `{res['error'][-200:]}`\n")
            best = sb.iloc[0]
            fh.write(f"- leader after round: **{best['name']}** [{best['agent']}] score={best['score']} all-better-both={best['all_better_both']}\n")
        print(f"[round {rnd}] done. leader: {sb.iloc[0]['name']} score={sb.iloc[0]['score']}")


if __name__ == "__main__":
    main()
