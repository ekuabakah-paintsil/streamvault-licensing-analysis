"""Improvement beyond the brief: bundle completeness.

The candidate list mostly holds each franchise's best-known films, but studios sell the WHOLE
bundle. This module fetches every franchise's full film list, then the budget and revenue of
the films the candidate list left out, and compares what the list says a bundle returns with
what the complete bundle actually returned.

Network calls go through fetch.fetch_one, so the same rules apply: cached, throttled, retried,
404s remembered, a re-run costs nothing. All analysis is vectorised.
"""
from __future__ import annotations


import numpy as np
import pandas as pd

from . import config, fetch, flatten


def collection_ids(films: pd.DataFrame) -> list[int]:
    return sorted(films["collection_id"].dropna().astype("int64").unique().tolist())


def fetch_collections(session, coll_ids, log) -> None:
    for cid in coll_ids:                       # loop over network requests, not rows
        fetch.fetch_one(session, "collection", int(cid), log)


def load_members(coll_ids) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Grain: one row per franchise per member film, as the franchise list states it.
    Also returns a status table, one row per franchise, so a missing list is visible."""
    bodies, status = [], []
    for cid in coll_ids:
        payload = fetch.read_cached("collection", int(cid))
        if payload is None:
            status.append({"collection_id": int(cid), "collection_status": "not_fetched"})
            continue
        status.append({"collection_id": int(cid), "collection_status": str(payload["_http_status"]),
                       "collection_fetched_at": payload["_fetched_at"]})
        if payload["body"]:
            bodies.append(payload["body"])
    if not bodies:
        return pd.DataFrame(columns=["collection_id", "collection_name", "member_id", "member_title"]), \
            pd.DataFrame(status)
    members = pd.json_normalize(bodies, record_path="parts", meta=["id", "name"], meta_prefix="collection_")
    members = (members.rename(columns={"id": "member_id", "title": "member_title",
                                       "release_date": "listed_release_date"})
               [["collection_id", "collection_name", "member_id", "member_title"]]
               .astype({"collection_id": "int64", "member_id": "int64"}))
    assert not members.duplicated(["collection_id", "member_id"]).any(), "a franchise lists a film twice"
    return members, pd.DataFrame(status)


def fetch_member_details(session, member_ids, log) -> None:
    for mid in member_ids:                     # loop over network requests, not rows
        fetch.fetch_one(session, "movie", int(mid), log)


def load_member_details(member_ids) -> pd.DataFrame:
    """Grain: one row per member film with a cached details response."""
    bodies = []
    for mid in member_ids:
        payload = fetch.read_cached("movie", int(mid))
        if payload and payload["body"]:
            bodies.append(dict(payload["body"], _requested_id=int(mid), _fetched_at=payload["_fetched_at"]))
    return flatten.films_table(bodies)


def completeness(films: pd.DataFrame, members: pd.DataFrame, details: pd.DataFrame
                 ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (per_member, per_bundle).
    per_member grain: one row per franchise per member film.
    per_bundle grain: one row per franchise."""
    n = len(members)
    m = members.merge(details[["tmdb_id", "release_date", "release_year", "release_status",
                               "budget", "revenue", "vote_average", "vote_count"]],
                      left_on="member_id", right_on="tmdb_id", how="left", validate="many_to_one")
    assert len(m) == n, "member join changed the row count"
    today = pd.Timestamp.now().normalize()
    m["on_list"] = m["member_id"].isin(films["tmdb_id"])
    m["details_fetched"] = m["tmdb_id"].notna()
    m["released"] = m["release_status"].eq("Released").fillna(False) & m["release_date"].le(today).fillna(False)
    budget = m["budget"].astype("Float64").where(m["budget"].gt(0))
    revenue = m["revenue"].astype("Float64").where(m["revenue"].gt(0))
    m["usable"] = (m["released"] & budget.notna() & revenue.notna()).astype(bool)
    m["return_multiple"] = (revenue / budget).where(m["usable"])
    m["ub"], m["ur"] = budget.where(m["usable"]), revenue.where(m["usable"])
    m["list_ub"], m["list_ur"] = m["ub"].where(m["on_list"]), m["ur"].where(m["on_list"])
    m["missing_released"] = m["released"] & ~m["on_list"]
    m["missing_no_figures"] = m["missing_released"] & ~m["usable"]
    m["cancelled"] = m["release_status"].eq("Canceled").fillna(False).astype(bool)
    m["upcoming"] = ~m["released"] & ~m["cancelled"]       # announced or in production; may join the bundle

    missing_titles = (m.loc[m["missing_released"]].sort_values("release_date")
                      .assign(t=lambda d: d["member_title"] + " (" + d["release_year"].astype("string") + ")")
                      .groupby("collection_id")["t"].agg("; ".join))
    b = m.groupby(["collection_id", "collection_name"]).agg(
        films_in_franchise=("member_id", "size"),
        released=("released", "sum"),
        upcoming_not_released=("upcoming", "sum"),
        cancelled=("cancelled", "sum"),
        on_list=("on_list", "sum"),
        missing_released=("missing_released", "sum"),
        missing_without_figures=("missing_no_figures", "sum"),
        list_budget=("list_ub", "sum"), list_revenue=("list_ur", "sum"),
        full_budget=("ub", "sum"), full_revenue=("ur", "sum"),
        weakest_full=("return_multiple", "min"),
        first_year=("release_year", "min"), last_year=("release_year", "max"),
    ).reset_index()
    weakest_list = m.loc[m["on_list"]].groupby("collection_id")["return_multiple"].min()
    b["weakest_on_list"] = b["collection_id"].map(weakest_list)
    b["list_return"] = b["list_revenue"] / b["list_budget"].where(b["list_budget"].gt(0))
    b["full_return"] = b["full_revenue"] / b["full_budget"].where(b["full_budget"].gt(0))
    b["change_vs_list"] = b["full_return"] / b["list_return"] - 1
    b["complete_on_list"] = b["missing_released"].eq(0)
    b["all_released_2000_on"] = b["collection_id"].map(
        m.loc[m["released"]].groupby("collection_id")["release_year"].min().ge(config.WINDOW_CUTOFF_YEAR))
    b["missing_titles"] = b["collection_id"].map(missing_titles).fillna("")
    keep = ["collection_id", "collection_name", "films_in_franchise", "released", "upcoming_not_released", "cancelled",
            "on_list", "missing_released", "missing_without_figures", "first_year", "last_year",
            "all_released_2000_on", "list_return", "full_return", "change_vs_list", "weakest_on_list",
            "weakest_full", "complete_on_list", "list_budget", "full_budget", "missing_titles"]
    per_member = m.drop(columns=["tmdb_id", "ub", "ur", "list_ub", "list_ur"])
    return per_member, b[keep].sort_values("full_return", ascending=False, na_position="last")


def headline(films: pd.DataFrame, per_bundle: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per window. The franchise-vs-standalone comparison redone per WHOLE bundle."""
    rows = []
    usable = films.loc[films["in_scope"].astype(bool) & films["usable_financials"].astype(bool)]
    for w, bmask, fmask in (
        ("all_years", pd.Series(True, index=per_bundle.index), pd.Series(True, index=usable.index)),
        ("2000_on", per_bundle["all_released_2000_on"].fillna(False).astype(bool),
         usable["release_year"].ge(config.WINDOW_CUTOFF_YEAR)),
    ):
        pb = per_bundle.loc[bmask]
        st = usable.loc[fmask & usable["collection_id"].isna(), "return_multiple"]
        full = float(pb["full_return"].astype("float64").median())
        stand = float(st.astype("float64").median())
        winner = ("insufficient data" if np.isnan(full) or np.isnan(stand)
                  else "franchise" if full > stand else "standalone")
        rows.append({"window": w, "bundles": int(pb["full_return"].notna().sum()),
                     "median_bundle_return_list_only": float(pb["list_return"].astype("float64").median()),
                     "median_bundle_return_complete": full,
                     "standalones": len(st), "median_standalone_return": stand,
                     "winner_complete_bundles": winner})
    return pd.DataFrame(rows)
