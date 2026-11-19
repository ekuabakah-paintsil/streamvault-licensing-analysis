"""StreamVault licensing analysis: one command, top to bottom.

    python run.py              # fetch anything not yet cached, then analyse
    python run.py --offline    # analyse from the cache only, no network (use in meetings)

Outputs land in outputs/. See README.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402

from streamvault import checks, config, fetch, ids, pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached responses only; make no API calls")
    args = ap.parse_args()

    timer = pipeline.Timer()
    log: list[dict] = []

    with timer.stage("acquisition (network, excluded from budget)", budgeted=False):
        session = None if args.offline else fetch.make_session()
        ledger = pipeline.build_ledger(session, log)
        candidates = ids.unique_candidates(ledger)
        print(f"Source lines: {len(ledger)} | unique candidate ids: {len(candidates)}")
        if session is not None:
            fetch.fetch_all(session, candidates, log)
        if any(e.get("source") == "network" for e in log):
            fetch.build_bundles(candidates)        # new data fetched: refresh the read-optimised copy

    with timer.stage("load_cache"):
        movies, credits, cache_status = fetch.load_cache(candidates)
        if not movies:
            raise SystemExit("No cached films found. Run without --offline first (needs TMDB_API_KEY).")

    out = pipeline.run_analysis(movies, credits, cache_status, ledger, timer)
    
    with timer.stage("quality_gate"):
        check_table = checks.check_before_write(out, cache_status)   # stops here, writing nothing, if any fails 
    
    with timer.stage("write_outputs"):
        config.OUTPUTS.mkdir(exist_ok=True)
        check_table.to_csv(config.OUTPUTS / "checks.csv", index=False)
        cache_status.to_csv(config.OUTPUTS / "fetch_record.csv", index=False)
        for name in ["ledger", "films", "quality", "flag_examples", "kpi_segments", "kpi_positions",
                     "kpi_collections", "standalone_ranking", "talent_kpis", "sensitivity", "method_sensitivity", "cast", "crew", "talent"]:
            out[name].to_csv(config.OUTPUTS / f"{name}.csv", index=False)
        if log:
            log_path = config.OUTPUTS / "fetch_log.csv"
            log_columns = ["run_at", "endpoint", "tmdb_id", "source", "http_status", "fetched_at", "error"]
            (pd.DataFrame(log)
               .assign(run_at=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"))
               .reindex(columns=log_columns)
               .to_csv(log_path, mode="a", header=not log_path.exists(), index=False))
        led = out["ledger"]
        summary = (led.groupby("final_status")
                    .agg(lines=("file_line", "size"),
                        file_lines=("file_line", lambda s: ", ".join(s.astype(str))))
                    .reset_index()
                    .sort_values("lines", ascending=False))
        total = pd.DataFrame([{"final_status": "TOTAL", "lines": summary["lines"].sum(), "file_lines": ""}])
        summary = pd.concat([summary, total], ignore_index=True)
        assert summary["lines"].iloc[-1] == len(led), "id counts do not reconcile"
        summary.to_csv(config.OUTPUTS / "id_reconciliation.csv", index=False)
            

    t = timer.table()
    t.to_csv(config.OUTPUTS / "timing.csv", index=False)
    analysis_seconds = t.loc[t["in_budget"], "seconds"].sum()

    # ---- console summary ----
    led = out["ledger"]
    print("\nWhere every source line went:")
    print(led["final_status"].value_counts().to_string())
    assert led["final_status"].value_counts().sum() == len(led), "counts do not reconcile"
    seg = out["kpi_segments"].set_index(["window", "segment"])
    print("\nFranchise vs standalone (median revenue/budget, usable n):")
    for w in ("all_years", "2000_on"):
        fr, st = seg.loc[(w, "franchise")], seg.loc[(w, "standalone")]
        print(f"  {w:9s}  franchise {fr['median_return']:.2f}x (n={fr['usable']:.0f})   "
              f"standalone {st['median_return']:.2f}x (n={st['usable']:.0f})")
    flips = out["sensitivity"].loc[out["sensitivity"]["flips_recommendation"]]
    print(f"\nCleaning-rule variants that flip the answer: {len(flips)}")
    if len(flips):
        print(flips[["variant", "window", "winner_by_median"]].to_string(index=False))
    calls = sum(1 for e in log if e.get("source") == "network")
    print(f"\nNetwork calls this run: {calls}")
    status = "WITHIN" if analysis_seconds <= config.TIME_BUDGET_SECONDS else "OVER"
    print(f"Analysis stage: {analysis_seconds:.3f}s ({status} the {config.TIME_BUDGET_SECONDS:.0f}s budget)")
    print(f"\nQuality gate: {int(check_table['passed'].sum())} of {len(check_table)} checks passed")
    print("\nPer stage:")
    print(t[["stage", "seconds"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()

    
