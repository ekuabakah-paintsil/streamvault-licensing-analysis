"""Reconcile pipeline output against LIVE TMDb values (Learning Path topic 7, 2nd continuation).

    python spot_check.py          # run after run.py

Picks ~12 films deliberately (four slices, fixed seed), re-fetches them live (never from cache),
and compares three versions of each field:
    table  = what outputs/films.csv says (our pipeline's output)
    cache  = the raw response we stored when we fetched
    live   = what TMDb says right now
That three-way split classifies every discrepancy automatically:
    table != cache          -> our_bug         (parsing/cleaning changed a value)
    cache != live           -> source_changed  (TMDb was edited since our snapshot)
    both differ             -> both
Tolerance, decided before looking: exact for ids, titles, dates and money (TMDb stores money
as whole dollars, so any difference is a real difference, not float noise).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402

from streamvault import config, fetch  # noqa: E402

SEED = 42
FIELDS = ["title", "release_date", "budget", "revenue", "collection_id", "director", "lead_actor"]


def pick_sample(films: pd.DataFrame, ledger: pd.DataFrame, talent: pd.DataFrame,
                collections: pd.DataFrame) -> pd.DataFrame:
    """Five deliberate slices (Learning Path topic 7.2), each chosen for a stated reason.
    Fixed seed, so the same run picks the same films and the check cannot be accused of
    being chosen to pass."""
    f = films.loc[films["usable_financials"].astype(bool)].copy()
    picks = []
    # 1. Random: repeatable, unbiased baseline.
    picks.append(f.sample(4, random_state=SEED).assign(slice="random"))
    # 2. Extremes: the films with the most leverage on any average.
    picks.append(f.nlargest(2, "return_multiple").assign(slice="extreme_high"))
    picks.append(f.nsmallest(1, "return_multiple").assign(slice="extreme_low"))
    # 3. Most handled: ids that were repeated or IMDb-resolved in the source list, and films
    #    whose director field had to be built from several crew entries.
    handled_ids = set(ledger.loc[ledger["final_status"].eq("excluded_duplicate"), "tmdb_id"].dropna().astype(int))
    dirs = talent.loc[talent["role"].eq("director")].groupby("tmdb_id")["person_id"].nunique()
    multi_dir = set(dirs[dirs.gt(1)].index)
    handled = f.loc[f["tmdb_id"].isin(handled_ids | multi_dir)]
    picks.append(handled.sample(min(3, len(handled)), random_state=SEED).assign(slice="most_handled"))
    # 4. Boundary: films sitting on a rule (the 2000 window line, single-title collections).
    boundary = f.loc[f["release_year"].isin([1999, 2000]) | f["collection_titles_on_list"].eq(1)]
    picks.append(boundary.sample(min(2, len(boundary)), random_state=SEED).assign(slice="boundary"))
    # 5. Decision-critical: every film in the top franchise bundle (2000 on, 3+ titles) and
    #    the top standalone by score - the numbers the memo leans on hardest.
    top = collections.loc[collections["window"].eq("2000_on") & collections["titles_on_list"].ge(3)]
    if len(top):
        top_id = top.sort_values("bundle_return", ascending=False)["collection_id"].iloc[0]
        picks.append(f.loc[f["collection_id"].eq(top_id)].assign(slice="decision_critical"))
    picks.append(f.loc[~f["collection_id"].notna()].nlargest(1, "return_multiple").assign(slice="decision_critical"))
    return pd.concat(picks).drop_duplicates("tmdb_id")


def extract(movie: dict | None, credits: dict | None) -> dict:
    movie, credits = movie or {}, credits or {}
    coll = movie.get("belongs_to_collection") or {}
    directors = sorted(c["name"] for c in credits.get("crew", []) if c.get("job") == "Director")
    lead = [c["name"] for c in credits.get("cast", []) if c.get("order") == 0]
    return {"title": movie.get("title"), "release_date": movie.get("release_date") or None,
            "budget": movie.get("budget"), "revenue": movie.get("revenue"),
            "collection_id": coll.get("id"), "director": "; ".join(directors) or None,
            "lead_actor": lead[0] if lead else None}


def norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return str(v)[:10] if isinstance(v, pd.Timestamp) else v


def main() -> None:
    films = pd.read_csv(config.OUTPUTS / "films.csv", parse_dates=["release_date"])
    ledger = pd.read_csv(config.OUTPUTS / "ledger.csv")
    talent = pd.read_csv(config.OUTPUTS / "talent.csv")
    cast = pd.read_csv(config.OUTPUTS / "cast.csv")
    collections = pd.read_csv(config.OUTPUTS / "kpi_collections.csv")
    sample = pick_sample(films, ledger, talent, collections)

    # Our pipeline's own director / lead-actor values (NOT re-parsed from the cache).
    our_dir = (talent.loc[talent["role"].eq("director")].groupby("tmdb_id")["name"]
               .agg(lambda s: "; ".join(sorted(s))))
    our_lead = cast.loc[cast["order"].eq(0)].drop_duplicates("tmdb_id").set_index("tmdb_id")["name"]

    session = fetch.make_session()
    rows = []
    for _, film in sample.iterrows():       # loop over ~12 network calls, not over analysis rows
        fid = int(film["tmdb_id"])
        cache = extract(json.loads((config.RAW / "movie" / f"{fid}.json").read_text(encoding="utf-8"))["body"],
                        json.loads((config.RAW / "credits" / f"{fid}.json").read_text(encoding="utf-8"))["body"])
        _, live_movie = fetch._get(session, f"{config.API_BASE}/movie/{fid}")
        _, live_credits = fetch._get(session, f"{config.API_BASE}/movie/{fid}/credits")
        live = extract(live_movie, live_credits)
        table = {"title": film["title"], "release_date": film["release_date"],
                 "budget": film["budget"], "revenue": film["revenue"], "collection_id": film["collection_id"],
                 "director": our_dir.get(fid), "lead_actor": our_lead.get(fid)}
        for field in FIELDS:
            t, c, l = norm(table[field]), norm(cache[field]), norm(live[field])
            t = str(t)[:10] if field == "release_date" and t else t
            cls = ("match" if t == c == l else "our_bug" if t != c and c == l
                   else "source_changed" if t == c and c != l else "both")
            rows.append({"tmdb_id": fid, "title": film["title"], "slice": film["slice"], "field": field,
                         "our_value": t, "cached_value": c, "live_value": l, "class": cls,
                         "action": "" if cls == "match" else "TODO: investigate and record the resolution"})
    out = pd.DataFrame(rows)
    out.to_csv(config.OUTPUTS / "spot_check.csv", index=False)
    n_films, n_fields = out["tmdb_id"].nunique(), len(out)
    print(f"Checked {n_films} films x {len(FIELDS)} fields = {n_fields} comparisons, live at "
          f"{pd.Timestamp.now(tz='UTC').isoformat(timespec='seconds')}.")
    print(sample.groupby("slice", sort=False)["title"].agg(", ".join).to_string())
    print()
    print(out["class"].value_counts().to_string())
    diffs = out.loc[out["class"].ne("match")]
    if len(diffs):
        print("\nDiscrepancies to resolve:")
        print(diffs[["tmdb_id", "title", "field", "our_value", "cached_value", "live_value", "class"]].to_string(index=False))


if __name__ == "__main__":
    main()
    