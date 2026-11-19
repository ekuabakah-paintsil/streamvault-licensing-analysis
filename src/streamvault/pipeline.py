"""Orchestration. Acquisition (network) and analysis (from cache) are separate stages;
only the analysis stage counts against the time budget, because network time measures
TMDb and your internet connection, not this code."""
from __future__ import annotations

import time
from contextlib import contextmanager

import numpy as np
import pandas as pd

from . import analysis, config, fetch, flatten, ids, quality


class Timer:
    def __init__(self):
        self.rows = []

    @contextmanager
    def stage(self, name: str, budgeted: bool = True):
        t0 = time.perf_counter()
        yield
        self.rows.append({"stage": name, "seconds": time.perf_counter() - t0, "in_budget": budgeted})

    def table(self) -> pd.DataFrame:
        t = pd.DataFrame(self.rows)
        b = t["in_budget"]
        t["share_of_analysis"] = (t["seconds"] / t.loc[b, "seconds"].sum()).where(b)
        return t


def build_ledger(session=None, fetch_log=None) -> pd.DataFrame:
    led = ids.parse(ids.read_raw(config.ID_LIST))
    imdb = led.loc[led["id_status"].eq("imdb_id_needs_resolving"), "raw_value"].str.strip().tolist()
    led = ids.apply_imdb_resolution(led, fetch.resolve_imdb_ids(session, imdb, fetch_log if fetch_log is not None else []))
    return ids.mark_duplicates(led)


def finalise_ledger(led: pd.DataFrame, cache_status: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """Attach what happened to every candidate after fetching and scoping. Grain stays
    one row per line of the source file; the merges are validated so no line is lost or doubled."""
    n = len(led)
    out = led.merge(cache_status, on="tmdb_id", how="left", validate="many_to_one")
    out = out.merge(f[["tmdb_id", "title", "release_year", "in_scope", "usable_financials", "segment",
                       "flag_not_released", "flag_short_runtime", "flag_adult_or_video", "flag_id_redirected",
                       "returned_id"]],
                    on="tmdb_id", how="left", validate="many_to_one")
    assert len(out) == n, "ledger row count changed during merge"

    b = lambda s: s.fillna(False).astype(bool).to_numpy()      # nullable -> plain bool for np.select
    cand = out["id_status"].eq("candidate").to_numpy()
    ms = out["movie_status"].astype("string")
    in_scope = out["in_scope"].astype("boolean")
    usable = out["usable_financials"].astype("boolean")
    out["final_status"] = np.select(
        [~cand,
         cand & b(ms.eq("404")),
         cand & b(ms.isna() | ms.eq("not_fetched")),
         cand & b(in_scope.eq(False)),
         cand & b(usable.eq(True)),
         cand & b(usable.eq(False))],
        [out["id_status"],
         "excluded_not_found_on_tmdb",
         "excluded_fetch_failed",
         "excluded_out_of_scope",
         "analysed_full",
         "analysed_no_usable_financials"],
        default="unexplained",
    )
    scope_reason = np.select(
        [b(out["flag_not_released"].astype("boolean")), b(out["flag_short_runtime"].astype("boolean")),
         b(out["flag_adult_or_video"].astype("boolean"))],
        ["not released", "short (<40 min)", "adult/video release"], default="")
    out["note"] = np.select(
        [out["final_status"].eq("excluded_out_of_scope").to_numpy(),
         out["final_status"].eq("excluded_not_found_on_tmdb").to_numpy(),
         out["final_status"].eq("excluded_fetch_failed").to_numpy(),
         b(out["flag_id_redirected"].astype("boolean"))],
        [scope_reason,
         "TMDb returned 404: id does not exist (or was deleted)",
         "request failed after retries; re-run to retry",
         "TMDb returned a different id: " + out["returned_id"].astype("string").fillna("")],
        default=out["note"].fillna(""))
    bad = out.loc[out["final_status"].eq("unexplained")]
    assert bad.empty, f"every line must have an explained outcome:\n{bad.to_string()}"
    return out


def run_analysis(movies, credits, cache_status, ledger, timer: Timer) -> dict:
    with timer.stage("flatten"):
        films = flatten.films_table(movies)
        cast = flatten.cast_table(credits)
        crew = flatten.crew_table(credits)
        talent = flatten.talent_table(cast, crew)
    with timer.stage("flag_and_check"):
        flagged = quality.add_flags(films)
        q = quality.quality_report(flagged, "after_flagging")   # one stage: every check, once
        examples = quality.flag_examples(flagged)
    with timer.stage("prepare"):
        f = analysis.prepare(flagged)
    with timer.stage("reconcile_ledger"):
        final_ledger = finalise_ledger(ledger, cache_status, f) if ledger is not None else None
    with timer.stage("kpis_both_windows"):
        seg, pos, coll, stand, tal = [], [], [], [], []
        for w in ("all_years", "2000_on"):
            fw = analysis.window(f, w)
            seg.append(analysis.segment_kpis(fw).assign(window=w))
            pos.append(analysis.position_kpis(fw).assign(window=w))
            coll.append(analysis.collection_kpis(fw).assign(window=w))
            stand.append(analysis.standalone_ranking(fw).assign(window=w))
            tal.append(analysis.talent_kpis(fw, talent).assign(window=w))
    with timer.stage("sensitivity"):
        sens = analysis.sensitivity(flagged)
        method_sens = analysis.method_sensitivity(f)
    return {
        "films": f, "cast": cast, "crew": crew, "talent": talent, "quality": q, "flag_examples": examples,
        "ledger": final_ledger,
        "kpi_segments": pd.concat(seg).reset_index(),
        "kpi_positions": pd.concat(pos).reset_index(),
        "kpi_collections": pd.concat(coll),
        "standalone_ranking": pd.concat(stand),
        "talent_kpis": pd.concat(tal),
        "sensitivity": sens,
        "method_sensitivity": method_sens,
    }