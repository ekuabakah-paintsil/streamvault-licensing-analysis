"""Stage 3b: validate the pulled data against the data contract (data_contract.md).

Runs straight after flattening, before any film reaches the analysis. Three levels:

1. Structure. Every column the analysis relies on must exist. If TMDb changes its response
   format, the run stops here with a clear message instead of failing obscurely later.
2. Each record. Every film (and every credit) is checked against the contract's rules.
   A record that breaks a rule is QUARANTINED: removed from the analysis and written to
   outputs/quarantine.csv with the rule it broke. Nothing is deleted from the cache, and
   the ledger records the film as "excluded_failed_validation", so all lines still reconcile.
3. Threshold. If more than config.QUARANTINE_MAX_SHARE of films fail, the source itself is
   broken rather than a few records, so the run stops instead of analysing what is left.

Validation is about whether a record is well-formed and possible (a negative budget, a
rating of 14). Whether a valid record is plausible (a $5 budget, a 70x return) is a
different question, answered by the quality flags in quality.py.

Every rule is a whole-column expression; no row loops.
"""
from __future__ import annotations

import pandas as pd

from . import config


class ContractBroken(Exception):
    """The pulled data does not have the structure the analysis needs, or too many records
    failed validation. Nothing is written."""


KNOWN_STATUSES = {"Rumored", "Planned", "In Production", "Post Production", "Released", "Canceled"}

FILM_COLUMNS = {"tmdb_id", "returned_id", "title", "release_date", "release_status", "budget",
                "revenue", "runtime", "vote_average", "vote_count", "collection_id", "fetched_at"}
CAST_COLUMNS = {"tmdb_id", "person_id", "name", "order"}
CREW_COLUMNS = {"tmdb_id", "person_id", "name", "job"}


def _film_rules(f: pd.DataFrame) -> dict[str, pd.Series]:
    """Rule name -> boolean Series, True where the film PASSES the rule."""
    released = f["release_status"].eq("Released")
    return {
        "returned an id": f["returned_id"].notna(),
        "has a title": f["title"].fillna("").str.strip().ne(""),
        "release status is a known value": f["release_status"].isin(KNOWN_STATUSES),
        "released films have a release date": ~released | f["release_date"].notna(),
        "budget present and not negative": f["budget"].ge(0).fillna(False),
        "revenue present and not negative": f["revenue"].ge(0).fillna(False),
        "runtime not negative": f["runtime"].ge(0).fillna(True),
        "rating between 0 and 10": f["vote_average"].between(0, 10).fillna(False),
        "vote count not negative": f["vote_count"].ge(0).fillna(False),
        "franchise id positive if present": f["collection_id"].gt(0).fillna(True),
        "fetch time recorded": f["fetched_at"].notna(),
    }


def _credit_rules(cast: pd.DataFrame, crew: pd.DataFrame) -> tuple[dict, dict]:
    cast_rules = {
        "cast person id positive": cast["person_id"].gt(0),
        "cast billing order not negative": cast["order"].ge(0),
        "cast name present": cast["name"].fillna("").str.strip().ne(""),
    }
    crew_rules = {
        "crew person id positive": crew["person_id"].gt(0),
        "crew job present": crew["job"].fillna("").str.strip().ne(""),
        "crew name present": crew["name"].fillna("").str.strip().ne(""),
    }
    return cast_rules, crew_rules


def _require_columns(df: pd.DataFrame, needed: set[str], table: str) -> None:
    missing = needed - set(df.columns)
    if missing and len(df):
        raise ContractBroken(f"The {table} table is missing columns {sorted(missing)}. TMDb's response "
                             "format may have changed; see data_contract.md. Nothing was written.")


def _failures(df: pd.DataFrame, rules: dict[str, pd.Series], level: str) -> pd.DataFrame:
    """Grain: one row per record per broken rule."""
    frames = [df.loc[~passed.astype(bool), ["tmdb_id"]].assign(level=level, rule=name)
              for name, passed in rules.items()]
    frames = [x for x in frames if len(x)]
    if not frames:
        return pd.DataFrame(columns=["tmdb_id", "level", "rule"])
    return pd.concat(frames, ignore_index=True)


def validate(films: pd.DataFrame, cast: pd.DataFrame, crew: pd.DataFrame):
    """Returns (valid_films, valid_cast, valid_crew, quarantine, summary).

    quarantine grain: one row per record per broken rule (level 'film', 'cast' or 'crew').
    summary grain: one row per rule, with how many records were checked and how many failed."""
    _require_columns(films, FILM_COLUMNS, "film")
    _require_columns(cast, CAST_COLUMNS, "cast")
    _require_columns(crew, CREW_COLUMNS, "crew")

    film_rules = _film_rules(films)
    cast_rules, crew_rules = _credit_rules(cast, crew)
    quarantine = pd.concat([_failures(films, film_rules, "film"),
                            _failures(cast, cast_rules, "cast"),
                            _failures(crew, crew_rules, "crew")], ignore_index=True)

    film_ok = pd.concat(film_rules, axis=1).all(axis=1) if len(films) else pd.Series(dtype=bool)
    bad_films = films.loc[~film_ok, "tmdb_id"]
    share = len(bad_films) / len(films) if len(films) else 0.0
    if share > config.QUARANTINE_MAX_SHARE:
        raise ContractBroken(
            f"{len(bad_films)} of {len(films)} films ({share:.0%}) failed validation, more than the "
            f"{config.QUARANTINE_MAX_SHARE:.0%} allowed: the source looks broken, so the run stops "
            f"rather than analysing what is left.\n{quarantine.to_string(index=False)}")

    cast_ok = pd.concat(cast_rules, axis=1).all(axis=1) if len(cast) else pd.Series(dtype=bool)
    crew_ok = pd.concat(crew_rules, axis=1).all(axis=1) if len(crew) else pd.Series(dtype=bool)
    valid_films = films.loc[film_ok].reset_index(drop=True)
    # credits of a quarantined film go with it; a broken credit row is dropped on its own
    valid_cast = cast.loc[cast_ok & ~cast["tmdb_id"].isin(bad_films)].reset_index(drop=True)
    valid_crew = crew.loc[crew_ok & ~crew["tmdb_id"].isin(bad_films)].reset_index(drop=True)

    sizes = {"film": len(films), "cast": len(cast), "crew": len(crew)}
    summary = pd.DataFrame(
        [{"level": level, "rule": name, "checked": sizes[level], "failed": int((~passed.astype(bool)).sum())}
         for level, rules in (("film", film_rules), ("cast", cast_rules), ("crew", crew_rules))
         for name, passed in rules.items()])
    return valid_films, valid_cast, valid_crew, quarantine, summary


def quarantine_reasons(quarantine: pd.DataFrame) -> pd.Series:
    """tmdb_id -> '; '-joined rules a quarantined film broke (film level only)."""
    film_level = quarantine.loc[quarantine["level"].eq("film")]
    return film_level.groupby("tmdb_id")["rule"].agg("; ".join)
