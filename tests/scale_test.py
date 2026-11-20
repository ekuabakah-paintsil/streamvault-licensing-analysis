"""Scale test and benchmark on REAL data shape: python tests/scale_test.py

Copies the real cached films (full-sized cast and crew lists) under new ids until the list
reaches 500, 1,000 and 2,000 titles, then times loading and the analysis stage. Each copy
gets its own film id and collection id, so franchise sizes stay realistic instead of one
collection growing to hundreds of films. Needs one normal `python run.py` first (uses the
bundles in data/raw/, which hold the slim credits the analysis actually reads). Makes no network calls and writes only to a temporary folder.

The copies are not new information: this measures SPEED at a size, not findings.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamvault import config, pipeline  # noqa: E402

SIZES = [112, 500, 1000, 2000]
REPEATS = 10
OFFSET = 10_000_000          # copy k of film 155 becomes 155 + k * OFFSET


def real_bodies():
    movies, credits = [], []
    for endpoint, sink in (("movie", movies), ("credits", credits)):
        bundle = json.loads((config.RAW / f"bundle_{endpoint}.json").read_text(encoding="utf-8"))
        for key, payload in bundle.items():
            if key.startswith("_"):
                continue
            if payload and payload["body"]:
                sink.append(payload["body"])
    if not movies:
        raise SystemExit("No cached data: run `python run.py` once first.")
    return movies, credits


def replicate(movies, credits, n):
    out_m, out_c = [], []
    copy = 0
    while len(out_m) < n:
        for m, c in zip(movies, credits):
            if len(out_m) == n:
                break
            new_id = m["id"] + copy * OFFSET
            mm = dict(m, id=new_id, _requested_id=new_id, _fetched_at="scale-test")
            if m.get("belongs_to_collection"):
                coll = m["belongs_to_collection"]
                mm["belongs_to_collection"] = dict(coll, id=coll["id"] + copy * OFFSET)
            out_m.append(mm)
            out_c.append(dict(c, id=new_id, _requested_id=new_id))
        copy += 1
    return out_m, out_c


def main():
    import argparse
    import os
    import platform

    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=SIZES, help="list sizes to time, e.g. --sizes 500")
    ap.add_argument("--repeats", type=int, default=REPEATS, help="runs per size")
    args = ap.parse_args()
    sizes, repeats = args.sizes, args.repeats

    import numpy as np
    import pandas as pd

    movies, credits = real_bodies()
    credits_by_id = {c["id"]: c for c in credits}
    credits = [credits_by_id[m["id"]] for m in movies]          # align order
    print(f"Machine: {platform.platform()} | {platform.processor() or platform.machine()} | "
          f"{os.cpu_count()} logical CPUs | Python {platform.python_version()} | pandas {pd.__version__}")
    print(f"Base: {len(movies)} real films, "
          f"{sum(len(c['cast']) for c in credits) / len(credits):.0f} cast and "
          f"{sum(len(c['crew']) for c in credits) / len(credits):.0f} crew per film on average")
    print(f"Timed: reading the two cache files + the whole analysis stage (flatten, flag, KPIs in both "
          f"windows, sensitivity). {repeats} runs per size; run 1 is the first of the session.\n")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in sizes:
            m, c = replicate(movies, credits, n)
            pm, pc = Path(tmp) / "m.json", Path(tmp) / "c.json"
            pm.write_text(json.dumps({str(x["id"]): {"body": x} for x in m}), encoding="utf-8")
            pc.write_text(json.dumps({str(x["id"]): {"body": x} for x in c}), encoding="utf-8")
            totals = []
            for _ in range(repeats):
                t0 = time.perf_counter()
                json.loads(pm.read_text(encoding="utf-8"))
                json.loads(pc.read_text(encoding="utf-8"))
                timer = pipeline.Timer()
                pipeline.run_analysis(m, c, None, None, timer)
                totals.append(time.perf_counter() - t0)
            t = np.array(totals)
            rows.append({"titles": n, "runs": repeats, "first_run_s": t[0], "median_s": np.median(t),
                         "p95_s": np.percentile(t, 95), "worst_s": t.max(), "best_s": t.min(),
                         "bundle_mb": (pm.stat().st_size + pc.stat().st_size) / 1e6,
                         "target_met": bool(t.max() <= config.TIME_BUDGET_SECONDS)})
    out = pd.DataFrame(rows)
    out["median_vs_112"] = out["median_s"] / out["median_s"].iloc[0]
    config.OUTPUTS.mkdir(exist_ok=True)
    name = "benchmark.csv" if sizes == SIZES and repeats == REPEATS else "benchmark_custom.csv"
    out.to_csv(config.OUTPUTS / name, index=False)
    print(out.round(3).to_string(index=False))
    print(f"\nTarget: every run within {config.TIME_BUDGET_SECONDS:.0f} s. "
          f"Written to outputs/{name}. After the laptop has been idle, expect the first run "
          "to be slower (measured up to about 3x at 112 titles).")


if __name__ == "__main__":
    main()
