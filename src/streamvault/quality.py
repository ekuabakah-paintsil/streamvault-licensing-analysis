"""Stage 4: data-quality checks. These FLAG rows; they never delete them.
Whether a flagged row is excluded, and from which metric, is a cleaning rule
in analysis.py, so its impact can be measured both ways."""
from __future__ import annotations

import pandas as pd

SUSPECT_MONEY = 1_000          # budgets/revenues under $1,000 are almost certainly unit errors (e.g. "7" meaning $7M)
SHORT_RUNTIME = 40             # minutes; under this TMDb/AMPAS treat a film as a short
EXTREME_MULTIPLE = 50          # revenue/budget above this is real for a few films but worth eyeballing


def norm_title(s: pd.Series) -> pd.Series:
    return s.fillna("").str.casefold().str.replace(r"[^0-9a-z]+", " ", regex=True).str.strip()


def as_of_dates(fetched_at: pd.Series) -> pd.Series:
    """The day each response was fetched (timezone-naive), used as the as-of date.
    Falls back to today only for a row with no fetch time, which a cached film always has."""
    stamp = pd.to_datetime(fetched_at, utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    return stamp.fillna(pd.Timestamp.now().normalize())


def add_flags(films: pd.DataFrame) -> pd.DataFrame:
    f = films.copy()
    # Judge "released" as of the date each film was fetched, not today's date, so the same
    # cache always gives the same flags whenever and wherever it is rerun.
    as_of = as_of_dates(f["fetched_at"])
    f["flag_id_redirected"] = f["returned_id"].ne(f["tmdb_id"])
    f["flag_budget_zero"] = f["budget"].fillna(0).eq(0)
    f["flag_revenue_zero"] = f["revenue"].fillna(0).eq(0)
    f["flag_budget_suspect"] = f["budget"].between(1, SUSPECT_MONEY - 1).fillna(False)
    f["flag_revenue_suspect"] = f["revenue"].between(1, SUSPECT_MONEY - 1).fillna(False)
    f["flag_no_release_date"] = f["release_date"].isna()
    f["flag_not_released"] = f["release_status"].ne("Released") | f["release_date"].gt(as_of).fillna(False)
    f["flag_short_runtime"] = f["runtime"].lt(SHORT_RUNTIME).fillna(False)
    f["flag_adult_or_video"] = f["adult"].fillna(False).astype(bool) | f["video"].fillna(False).astype(bool)
    f["flag_low_votes"] = f["vote_count"].fillna(0).lt(50)
    multiple = f["revenue"].astype("Float64") / f["budget"].where(f["budget"].gt(0)).astype("Float64")
    f["flag_extreme_multiple"] = multiple.gt(EXTREME_MULTIPLE).fillna(False)

    # Semantic duplicates: different TMDb ids, same normalised title AND year, or same IMDb id.
    key = norm_title(f["title"]) + "|" + f["release_year"].astype("string").fillna("?")
    f["flag_same_title_year"] = key.duplicated(keep=False)
    imdb = f["imdb_id"].replace("", pd.NA)
    f["flag_same_imdb_id"] = imdb.notna() & imdb.duplicated(keep=False)
    # Same title, different year: almost always a remake or re-release. Flagged for review, NOT a duplicate.
    t = norm_title(f["title"])
    f["flag_same_title_other_year"] = t.duplicated(keep=False) & ~f["flag_same_title_year"]
    return f


def quality_report(films: pd.DataFrame, stage: str) -> pd.DataFrame:
    """Grain: one row per check; `count` is always a whole number (films affected), so the
    table can be summed and compared without converting text back to numbers."""
    checks = {
        "rows": len(films),
        "duplicate_tmdb_ids": int(films["tmdb_id"].duplicated().sum()),
        "null_title": int(films["title"].isna().sum()),
    }
    for col in [c for c in films.columns if c.startswith("flag_")]:
        checks[col] = int(films[col].sum())
    out = pd.DataFrame({"check": list(checks), "count": pd.Series(list(checks.values()), dtype="int64")})
    out.insert(0, "stage", stage)
    return out


def flag_examples(films: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per film per raised flag, with the values that raised it, for the diagnosis."""
    flag_cols = [c for c in films.columns if c.startswith("flag_")]
    long = films.melt(id_vars=["tmdb_id", "title", "release_year", "budget", "revenue",
                               "runtime", "vote_count", "collection_name", "release_status"],
                      value_vars=flag_cols, var_name="flag", value_name="raised")
    return long.loc[long["raised"]].drop(columns="raised").sort_values(["flag", "tmdb_id"])
