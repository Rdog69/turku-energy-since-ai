#!/usr/bin/env python3
"""Send tasks to Kimi (Featherless, OpenAI-compatible) using a pool of API keys.

Commands
  ping                         test every key with a tiny prompt
  ask   [-p TEXT | FILE | -]   one task; answer to stdout or --out
  batch DIR                    every DIR/*.md is one task, run in parallel,
                               answers written to DIR/out/<name>.md

Config comes from .env in the repo root (or the environment):
  FEATHERLESS_BASE_URL, FEATHERLESS_MODEL, FEATHERLESS_KEYS=key1,key2,...

Safety: prompts are scanned before sending. Anything that looks like licensed
Nord Pool spot data, or raw timestamped data rows, is refused (see guard()).
Keys are never printed; logs refer to keys by index only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = REPO / ".kimi"
USAGE_LOG = LOG_DIR / "usage.jsonl"
DEFAULT_SYSTEM = (
    "You are a careful senior engineer helping a hackathon team build a "
    "forecasting system for the Finnish imbalance price. Be concise and "
    "concrete. If you are unsure, say so instead of guessing."
)


# ---------------------------------------------------------------- config
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = REPO / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("FEATHERLESS_BASE_URL", "FEATHERLESS_MODEL", "FEATHERLESS_KEYS"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def get_config():
    env = load_env()
    keys = [k.strip() for k in env.get("FEATHERLESS_KEYS", "").split(",") if k.strip()]
    if not keys:
        sys.exit("No keys: set FEATHERLESS_KEYS=key1,key2,... in .env")
    base = env.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    model = env.get("FEATHERLESS_MODEL", "moonshotai/Kimi-K3.1-Pro")
    return base, model, keys


# ---------------------------------------------------------------- guard
# Files that must never be sent (licensed or raw organiser data).
BLOCKED_FILES = re.compile(
    r"(spot_nordpool|actuals_|inputs\.(csv|parquet)|forecast_backtest|\.parquet$|"
    r"(^|/)starter_package[^/]*/data/|TurkuEnergia_SinceAI2026/)",
    re.I,
)
# Text markers of spot data.
SPOT_MARKERS = re.compile(r"(fi_spot_price|spot_nordpool|nordpool,|\bspot_price\s*[,;])", re.I)
# A raw data row: ISO timestamp followed by a separator and a number.
DATA_ROW = re.compile(r"^\S*\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?Z?\S*[,;\t].*\d", re.M)


def guard(text: str, allow_data: bool) -> None:
    """Refuse to send licensed spot data; by default refuse raw data rows."""
    rows = len(DATA_ROW.findall(text))
    if SPOT_MARKERS.search(text) and rows:
        raise SystemExit("REFUSED: prompt looks like it contains Nord Pool spot data rows.")
    if rows >= 3 and not allow_data:
        raise SystemExit(
            f"REFUSED: prompt contains {rows} raw timestamped data rows. Send code, schemas "
            "or aggregates instead, or pass --allow-data for non-spot data."
        )


def read_context(paths: list[str]) -> str:
    parts = []
    for p in paths:
        rel = str(Path(p).resolve().relative_to(REPO)) if Path(p).resolve().is_relative_to(REPO) else p
        if BLOCKED_FILES.search(rel) or BLOCKED_FILES.search(Path(p).name):
            raise SystemExit(f"REFUSED: {p} is organiser/licensed data and is never sent.")
        text = Path(p).read_text(errors="replace")
        parts.append(f"<file path=\"{rel}\">\n{text}\n</file>")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- calling
def log_usage(rec: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    with _log_lock, USAGE_LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


_log_lock = threading.Lock()


def call(key_idx: int, key: str, base: str, model: str, prompt: str, system: str,
         max_tokens: int, temperature: float | None, task: str, retries: int = 6) -> str:
    from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError

    client = OpenAI(base_url=base, api_key=key, timeout=600, max_retries=0)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    kwargs = {"model": model, "messages": msgs, "max_tokens": max_tokens}
    if temperature is not None:
        kwargs["temperature"] = temperature
    delay = 5.0
    for attempt in range(1, retries + 1):
        t0 = time.time()
        try:
            r = client.chat.completions.create(**kwargs)
        except (APIStatusError, APIConnectionError, APITimeoutError) as e:
            status = getattr(e, "status_code", None)
            retryable = status is None or status == 429 or status >= 500
            msg = str(getattr(e, "message", e))[:300]
            log_usage({"ts": time.time(), "task": task, "key": key_idx, "ok": False,
                       "status": status, "error": msg, "attempt": attempt})
            if not retryable or attempt == retries:
                raise RuntimeError(f"key #{key_idx}: HTTP {status}: {msg}") from None
            print(f"  [key #{key_idx}] {task}: HTTP {status}, retry {attempt} in {delay:.0f}s",
                  file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        choice = r.choices[0]
        text = choice.message.content or ""
        u = r.usage
        log_usage({"ts": time.time(), "task": task, "key": key_idx, "ok": True,
                   "secs": round(time.time() - t0, 1), "finish": choice.finish_reason,
                   "prompt_tokens": getattr(u, "prompt_tokens", None),
                   "completion_tokens": getattr(u, "completion_tokens", None)})
        if choice.finish_reason == "length":
            text += "\n\n[kimi.py: output truncated at max_tokens]"
        return text
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- commands
def build_prompt(body: str, context: list[str], allow_data: bool) -> str:
    prompt = body if not context else f"{read_context(context)}\n\n{body}"
    guard(prompt, allow_data)
    return prompt


def cmd_ping(args, base, model, keys):
    ok = 0
    for i, k in enumerate(keys):
        t0 = time.time()
        try:
            out = call(i, k, base, model, "Reply with the single word: pong", "Be terse.",
                       2048, None, "ping", retries=1)
            print(f"key #{i}: OK  {time.time() - t0:5.1f}s  -> {out.strip()[:40]!r}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"key #{i}: FAIL {e}")
    print(f"{ok}/{len(keys)} keys working, model {model}")
    return 0 if ok == len(keys) else 1


def cmd_ask(args, base, model, keys):
    if args.p is not None:
        body = args.p
    elif args.file in (None, "-"):
        body = sys.stdin.read()
    else:
        body = Path(args.file).read_text()
    prompt = build_prompt(body, args.context, args.allow_data)
    system = Path(args.system).read_text() if args.system else DEFAULT_SYSTEM
    idx = args.key % len(keys)
    text = call(idx, keys[idx], base, model, prompt, system, args.max_tokens, args.temperature, "ask")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_batch(args, base, model, keys):
    src = Path(args.dir)
    tasks = sorted(p for p in src.glob("*.md") if p.is_file())
    if not tasks:
        sys.exit(f"No *.md tasks in {src}")
    out_dir = Path(args.out) if args.out else src / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    system = Path(args.system).read_text() if args.system else DEFAULT_SYSTEM

    # Build and guard every prompt before sending anything.
    prompts = {t: build_prompt(t.read_text(), args.context, args.allow_data) for t in tasks}
    todo = [t for t in tasks if args.force or not (out_dir / t.name).exists()]
    if not todo:
        print("All tasks already have outputs (use --force to redo).")
        return 0

    # One worker per key slot; each key handles one request at a time.
    per_key = max(1, args.per_key)
    pool: queue.Queue[int] = queue.Queue()
    for _ in range(per_key):
        for i in range(len(keys)):
            pool.put(i)

    def run(t: Path):
        i = pool.get()
        try:
            print(f"-> {t.name} on key #{i}", file=sys.stderr)
            text = call(i, keys[i], base, model, prompts[t], system,
                        args.max_tokens, args.temperature, t.name)
            (out_dir / t.name).write_text(text)
            return t.name, None
        except Exception as e:  # noqa: BLE001
            return t.name, str(e)
        finally:
            pool.put(i)

    failed = 0
    with cf.ThreadPoolExecutor(max_workers=len(keys) * per_key) as ex:
        for name, err in ex.map(run, todo):
            if err:
                failed += 1
                print(f"FAIL {name}: {err}", file=sys.stderr)
            else:
                print(f"done {name} -> {out_dir / name}", file=sys.stderr)
    print(f"{len(todo) - failed}/{len(todo)} tasks done, outputs in {out_dir}")
    return 1 if failed else 0


def cmd_usage(args, base, model, keys):
    if not USAGE_LOG.exists():
        print("No usage yet.")
        return 0
    agg: dict[int, dict] = {}
    for line in USAGE_LOG.read_text().splitlines():
        r = json.loads(line)
        a = agg.setdefault(r["key"], {"ok": 0, "err": 0, "in": 0, "out": 0})
        if r.get("ok"):
            a["ok"] += 1
            a["in"] += r.get("prompt_tokens") or 0
            a["out"] += r.get("completion_tokens") or 0
        else:
            a["err"] += 1
    print("key  calls  errors  prompt_tok  completion_tok")
    for k in sorted(agg):
        a = agg[k]
        print(f"#{k:<3} {a['ok']:5d}  {a['err']:6d}  {a['in']:10d}  {a['out']:14d}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--context", "-c", action="append", default=[],
                       help="file to include as context (repeatable)")
        p.add_argument("--system", help="file with a system prompt")
        p.add_argument("--max-tokens", type=int, default=16000)
        p.add_argument("--temperature", type=float, default=None)
        p.add_argument("--allow-data", action="store_true",
                       help="allow raw timestamped (non-spot) data rows in the prompt")

    sub.add_parser("ping", help="test every key")
    sub.add_parser("usage", help="calls and tokens per key")
    a = sub.add_parser("ask", help="one task")
    a.add_argument("file", nargs="?", help="prompt file, or - for stdin")
    a.add_argument("-p", help="prompt text")
    a.add_argument("--out", "-o", help="write the answer here")
    a.add_argument("--key", type=int, default=0, help="key index to use")
    common(a)
    b = sub.add_parser("batch", help="run DIR/*.md in parallel")
    b.add_argument("dir")
    b.add_argument("--out", "-o", help="output dir (default DIR/out)")
    b.add_argument("--per-key", type=int, default=1, help="parallel requests per key")
    b.add_argument("--force", action="store_true", help="redo tasks that already have output")
    common(b)

    args = ap.parse_args(argv)
    base, model, keys = get_config()
    return {"ping": cmd_ping, "ask": cmd_ask, "batch": cmd_batch, "usage": cmd_usage}[args.cmd](
        args, base, model, keys)


if __name__ == "__main__":
    sys.exit(main())
