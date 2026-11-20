"""Quality gate: named checks that must all pass before any output is written.

The same idea as a pre-load gate in a production pipeline: if the analysis has lost a
film, doubled one, or computed a statistic over the wrong rows, the run stops loudly and
writes nothing, so a half-wrong set of files can never reach a meeting. Every check is
recorded in outputs/checks.csv, so passing is evidence, not just the absence of an error.
"""
from __future__ import annotations

import pandas as pd

from . import config


class ChecksFailed(Exception):
    """One or more quality checks failed; outputs were not written."""


def _results(out: dict, cache_status: pd.DataFrame) -> list[tuple[str, bool, str]]:
    led, films, cast, crew, talent = (out[k] for k in ("ledger", "films", "cast", "crew", "talent"))
    seg = out["kpi_segments"]
    found = int(cache_status["movie_status"].eq("found").sum())
    quarantined = int(out["quarantine"].loc[out["quarantine"]["level"].eq("film"), "tmdb_id"].nunique())
    counts = led["final_status"].value_counts()
    in_scope = films.loc[films["in_scope"]]
    per_window = {"all_years": len(in_scope), "2000_on": int(in_scope["window_2000_on"].sum())}
    seg_totals = seg.groupby("window")["titles"].sum()
    money_cols = {"budget", "revenue", "return_multiple", "profit"}
    return [
        ("every line of the list has exactly one outcome",
         int(counts.sum()) == len(led) and not led["final_status"].isna().any(),
         f"{int(counts.sum())} outcomes for {len(led)} lines"),
        ("one row per film",
         bool(films["tmdb_id"].is_unique), f"{len(films)} rows, {films['tmdb_id'].nunique()} distinct films"),
        ("every film TMDb returned is analysed or quarantined",
         found == len(films) + quarantined, f"{found} found = {len(films)} in table + {quarantined} quarantined"),
        ("ledger and film table agree on films analysed",
         int(led["final_status"].str.startswith("analysed").sum()) == len(in_scope),
         f"{int(led['final_status'].str.startswith('analysed').sum())} in ledger, {len(in_scope)} in scope"),
        ("cast, crew and talent only reference known films",
         bool(cast["tmdb_id"].isin(films["tmdb_id"]).all() and crew["tmdb_id"].isin(films["tmdb_id"]).all()
              and talent["tmdb_id"].isin(films["tmdb_id"]).all()),
         f"{cast['tmdb_id'].nunique()} / {crew['tmdb_id'].nunique()} / {talent['tmdb_id'].nunique()} films referenced"),
        ("money lives only on the film table",
         not (money_cols & (set(cast.columns) | set(crew.columns) | set(talent.columns))),
         "no budget or revenue column on cast, crew or talent"),
        ("both time windows computed",
         set(seg["window"]) == {"all_years", "2000_on"}, ", ".join(sorted(set(seg["window"])))),
        ("franchise + standalone add up to the films in each window",
         all(int(seg_totals.get(w, -1)) == n for w, n in per_window.items()),
         "; ".join(f"{w}: {int(seg_totals.get(w, -1))} of {n}" for w, n in per_window.items())),
        ("every statistic has its group size beside it",
         bool(seg["usable"].notna().all() and out["talent_kpis"]["usable"].notna().all()),
         "usable-film counts present in segment and talent tables"),
        ("window cut-off is the configured year",
         bool((in_scope.loc[in_scope["window_2000_on"], "release_year"] >= config.WINDOW_CUTOFF_YEAR).all()),
         f"2000-on window starts at {config.WINDOW_CUTOFF_YEAR}"),
    ]


def check_before_write(out: dict, cache_status: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per check. Raises ChecksFailed (and writes nothing) if any fails."""
    table = pd.DataFrame(_results(out, cache_status), columns=["check", "passed", "evidence"])
    failed = table.loc[~table["passed"], "check"].tolist()
    if failed:
        raise ChecksFailed("Quality checks failed, no outputs written: " + "; ".join(failed) +
                           "\n" + table.to_string(index=False))
    return table
