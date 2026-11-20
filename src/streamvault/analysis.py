"""Stage 5: KPIs. Every function takes a DataFrame and returns a new one (no mutation),
every computation is a whole-column or grouped expression (no row loops), and every
statistic sits beside the count it was computed over.

Cleaning RULES are parameters, so each one can be run both ways and its impact measured.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import config


@dataclass(frozen=True)
class Rules:
    zero_money_is_missing: bool = True      # TMDb uses 0 for "not entered"; False treats it as a real $0
    exclude_suspect_money: bool = True      # budgets/revenues < $1,000 treated as unit errors
    exclude_unreleased: bool = True         # films not yet released have no box office to judge
    exclude_shorts_and_video: bool = True   # shorts / direct-to-video are a different population

    def label(self) -> str:
        return ", ".join(f"{k}={'Y' if v else 'N'}" for k, v in asdict(self).items())


BASELINE = Rules()


def prepare(films: pd.DataFrame, rules: Rules = BASELINE) -> pd.DataFrame:
    """Derive the analysis columns. Returns a new frame; grain unchanged (one row per film)."""
    f = films.copy()
    in_scope = pd.Series(True, index=f.index)
    if rules.exclude_unreleased:
        in_scope &= ~f["flag_not_released"]
    if rules.exclude_shorts_and_video:
        in_scope &= ~(f["flag_short_runtime"] | f["flag_adult_or_video"])

    budget = f["budget"].astype("Float64")
    revenue = f["revenue"].astype("Float64")
    if rules.zero_money_is_missing:
        budget = budget.where(budget.gt(0))
        revenue = revenue.where(revenue.gt(0))
    if rules.exclude_suspect_money:
        budget = budget.where(~f["flag_budget_suspect"])
        revenue = revenue.where(~f["flag_revenue_suspect"])

    # Budget and revenue are deliberately treated differently:
    # - budget must be > 0, because it is the denominator; a $0 budget cannot give a return.
    # - revenue must only be present. Under the baseline rule a $0 revenue has already been
    #   set to missing above (TMDb uses 0 for "not entered"), so it is excluded here too.
    #   Only when that rule is switched off is $0 revenue kept, as a genuine total loss
    #   (return 0x), which is the point of testing that alternative.
    has_budget = budget.gt(0).fillna(False)
    has_revenue = revenue.notna()
    usable = in_scope & has_budget & has_revenue
    f["in_scope"] = in_scope
    f["usable_financials"] = usable
    f["return_multiple"] = (revenue / budget).where(usable)
    f["profit"] = (revenue - budget).where(usable)
    f["is_franchise"] = f["collection_id"].notna()
    f["segment"] = np.where(f["is_franchise"], "franchise", "standalone")
    f["window_2000_on"] = f["release_year"].ge(config.WINDOW_CUTOFF_YEAR).fillna(False)

    # Entry position inside its collection, among the collection's titles on THIS candidate list.
    grp = f.loc[f["is_franchise"] & in_scope].groupby("collection_id")["release_date"]
    pos = grp.rank(method="first")
    size = grp.transform("size")
    f["collection_titles_on_list"] = size.reindex(f.index)
    f["entry_position"] = pd.Series(
        np.select([pos.eq(1), pos.eq(size)], ["first", "last"], default="middle"), index=pos.index
    ).reindex(f.index)
    f.loc[f["collection_titles_on_list"].lt(3), "entry_position"] = pd.NA   # no middle with < 3 titles
    return f


def window(f: pd.DataFrame, which: str) -> pd.DataFrame:
    if which == "all_years":
        return f
    if which == "2000_on":
        return f.loc[f["window_2000_on"]]
    raise ValueError(which)


def segment_kpis(f: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per segment (franchise / standalone)."""
    s = f.loc[f["in_scope"]]
    s = s.assign(ub=s["budget"].where(s["usable_financials"]),
                 ur=s["revenue"].where(s["usable_financials"]),
                 losing=(s["return_multiple"] < 1).where(s["return_multiple"].notna()).astype("Float64"))
    g = s.groupby("segment")
    out = g.agg(
        titles=("tmdb_id", "size"),
        usable=("return_multiple", "count"),
        median_return=("return_multiple", "median"),
        mean_return=("return_multiple", "mean"),
        p25_return=("return_multiple", lambda x: x.quantile(0.25)),
        p75_return=("return_multiple", lambda x: x.quantile(0.75)),
        share_losing_money=("losing", "mean"),
        total_budget=("ub", "sum"),
        total_revenue=("ur", "sum"),
        median_rating=("vote_average", "median"),
        median_votes=("vote_count", "median"),
    )
    out["pooled_return"] = out["total_revenue"] / out["total_budget"]   # weighted by budget
    return out.reindex(["franchise", "standalone"])


def position_kpis(f: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per entry position within franchises that have >= 3 titles on the list.
    This is the direct test of the 'weak middle entries' claim."""
    s = f.loc[f["in_scope"] & f["entry_position"].notna()]
    return s.groupby("entry_position").agg(
        titles=("tmdb_id", "size"), usable=("return_multiple", "count"),
        median_return=("return_multiple", "median"), median_rating=("vote_average", "median"),
    ).reindex(["first", "middle", "last"])


def collection_kpis(f: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per franchise collection (a bundle)."""
    s = f.loc[f["in_scope"] & f["is_franchise"]]
    s = s.assign(ub=s["budget"].where(s["usable_financials"]), ur=s["revenue"].where(s["usable_financials"]))
    out = s.groupby(["collection_id", "collection_name"]).agg(
        titles_on_list=("tmdb_id", "size"),
        usable=("return_multiple", "count"),
        first_year=("release_year", "min"), last_year=("release_year", "max"),
        bundle_budget=("ub", "sum"), bundle_revenue=("ur", "sum"),
        median_return=("return_multiple", "median"),
        weakest_return=("return_multiple", "min"),
        median_rating=("vote_average", "median"), min_rating=("vote_average", "min"),
        median_votes=("vote_count", "median"),
    ).reset_index()
    out["bundle_return"] = out["bundle_revenue"] / out["bundle_budget"].where(out["bundle_budget"].gt(0))
    out["share_usable"] = out["usable"] / out["titles_on_list"]
    out["post_2000_share"] = out["collection_id"].map(
        s.groupby("collection_id")["window_2000_on"].mean())
    return out.sort_values("bundle_return", ascending=False, na_position="last")


def add_score(f: pd.DataFrame) -> pd.DataFrame:
    """A transparent licensing score: half financial return, half audience signal.
    Percentile ranks, so no single blockbuster dominates and units do not matter."""
    s = f.copy()
    # Rank as plain float64: pandas 2.2 ranks a masked <NA> (from .where on nullable columns)
    # as if it were the lowest value, which shifts every score. float64 NaN ranks correctly on
    # pandas 2.2 and 3.x alike, so results are identical across versions.
    pr = lambda col: col.astype("float64").rank(pct=True)
    s["score"] = (0.5 * pr(s["return_multiple"])
                  + 0.25 * pr(s["vote_average"].where(s["vote_count"].ge(50)))
                  + 0.25 * pr(np.log1p(s["vote_count"].astype("Float64"))))
    s.loc[~s["usable_financials"], "score"] = np.nan
    return s


def standalone_ranking(f: pd.DataFrame) -> pd.DataFrame:
    s = add_score(f.loc[f["in_scope"]])
    cols = ["tmdb_id", "title", "release_year", "budget", "revenue", "return_multiple",
            "vote_average", "vote_count", "genres", "score"]
    return s.loc[~s["is_franchise"], cols].sort_values("score", ascending=False, na_position="last")


def talent_kpis(f: pd.DataFrame, talent: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per (role, person). Join validated many-to-one onto the film table."""
    before = len(talent)
    t = talent.merge(f.loc[f["in_scope"], ["tmdb_id", "return_multiple", "vote_average", "is_franchise"]],
                     on="tmdb_id", how="inner", validate="many_to_one")
    assert len(t) <= before, "talent join fanned out"
    out = t.groupby(["role", "person_id", "name"]).agg(
        titles=("tmdb_id", "nunique"), usable=("return_multiple", "count"),
        median_return=("return_multiple", "median"), min_return=("return_multiple", "min"),
        median_rating=("vote_average", "median"), franchise_share=("is_franchise", "mean"),
    ).reset_index()
    out["meets_min_n"] = out["usable"].ge(config.MIN_GROUP_SIZE)
    return out.sort_values(["role", "meets_min_n", "median_return"], ascending=[True, False, False])


def verdict(seg: pd.DataFrame) -> str:
    fr, st = seg.loc["franchise", "median_return"], seg.loc["standalone", "median_return"]
    if pd.isna(fr) or pd.isna(st):
        return "insufficient data"
    return "franchise" if fr > st else "standalone"


def sensitivity(films_flagged: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per (cleaning-rule variant, window). Re-runs the headline comparison under
    each alternative so every cleaning decision has a measured impact and a flip check."""
    variants = {"baseline": BASELINE}
    for field in BASELINE.__dataclass_fields__:
        variants[f"flip:{field}"] = Rules(**{**asdict(BASELINE), field: not getattr(BASELINE, field)})
    rows = []
    for name, rules in variants.items():
        prepared = prepare(films_flagged, rules)
        for w in ("all_years", "2000_on"):
            seg = segment_kpis(window(prepared, w))
            rows.append({
                "variant": name, "window": w,
                "franchise_usable": seg.loc["franchise", "usable"],
                "franchise_median": seg.loc["franchise", "median_return"],
                "standalone_usable": seg.loc["standalone", "usable"],
                "standalone_median": seg.loc["standalone", "median_return"],
                "franchise_pooled": seg.loc["franchise", "pooled_return"],
                "standalone_pooled": seg.loc["standalone", "pooled_return"],
                "winner_by_median": verdict(seg),
            })
    out = pd.DataFrame(rows)
    base = out.loc[out["variant"].eq("baseline")].set_index("window")["winner_by_median"]
    out["flips_recommendation"] = out["winner_by_median"].ne(out["window"].map(base))
    return out


def method_sensitivity(f: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per (analytical alternative, window).

    Where `sensitivity()` flips the CLEANING rules, this flips the METHOD choices that
    actually move this data: which statistic, which films count as a bundle, whether one
    outlier carries the result, and whether we compare per film or per bundle.
    Each alternative is a whole-frame filter or a grouped statistic; no row loops."""
    rows = []
    for w in ("all_years", "2000_on"):
        base = window(f, w).loc[lambda d: d["in_scope"] & d["usable_financials"]]
        fr, st = base.loc[base["is_franchise"]], base.loc[~base["is_franchise"]]

        def add(name, f_val, s_val, f_n, s_n, note):
            rows.append({"alternative": name, "window": w,
                         "franchise_value": f_val, "franchise_n": f_n,
                         "standalone_value": s_val, "standalone_n": s_n,
                         "winner": "franchise" if f_val > s_val else "standalone", "what_it_tests": note})

        pooled = lambda d: d["revenue"].sum() / d["budget"].sum()
        add("baseline: median per film", fr["return_multiple"].median(), st["return_multiple"].median(),
            len(fr), len(st), "the headline method")
        add("mean per film", fr["return_multiple"].mean(), st["return_multiple"].mean(),
            len(fr), len(st), "average instead of median: sensitive to big hits")
        add("pooled (total revenue / total budget)", pooled(fr), pooled(st),
            len(fr), len(st), "weights each film by its budget")
        multi = fr.loc[fr["collection_id"].map(fr["collection_id"].value_counts()).ge(2)]
        add("franchises with 2+ titles on list only", multi["return_multiple"].median(),
            st["return_multiple"].median(), len(multi), len(st),
            "drops single-title 'franchises' that are not really bundles on this list")
        no_top_f = fr.drop(fr["return_multiple"].idxmax())
        no_top_s = st.drop(st["return_multiple"].idxmax())
        add("each group without its single best film", no_top_f["return_multiple"].median(),
            no_top_s["return_multiple"].median(), len(no_top_f), len(no_top_s),
            "is one outlier carrying either side?")
        bundles = fr.groupby("collection_id").agg(rev=("revenue", "sum"), bud=("budget", "sum"))
        bundle_ret = bundles["rev"] / bundles["bud"]
        add("per bundle (franchise) vs per film (standalone)", bundle_ret.median(),
            st["return_multiple"].median(), len(bundle_ret), len(st),
            "Kwame buys whole bundles, not single entries")
    out = pd.DataFrame(rows)
    base = out.loc[out["alternative"].str.startswith("baseline")].set_index("window")["winner"]
    out["flips_recommendation"] = out["winner"].ne(out["window"].map(base))
    return out
