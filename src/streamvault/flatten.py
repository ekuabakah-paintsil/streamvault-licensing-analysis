"""Stage 3: turn nested JSON into tables. Each table states its grain."""
from __future__ import annotations

import pandas as pd

FILM_COLUMNS = {
    "_requested_id": "tmdb_id",
    "id": "returned_id",
    "title": "title",
    "original_title": "original_title",
    "release_date": "release_date",
    "status": "release_status",
    "budget": "budget",
    "revenue": "revenue",
    "runtime": "runtime",
    "vote_average": "vote_average",
    "vote_count": "vote_count",
    "popularity": "popularity",
    "original_language": "original_language",
    "imdb_id": "imdb_id",
    "adult": "adult",
    "video": "video",
    "belongs_to_collection_id": "collection_id",
    "belongs_to_collection_name": "collection_name",
    "_fetched_at": "fetched_at",
}
LEAD_BILLING = 3   # "lead actor" = billed in the top 3 (cast order 0, 1, 2)


def films_table(movies: list[dict]) -> pd.DataFrame:
    """Grain: one row per requested TMDb id that returned a film."""
    if not movies:
        return pd.DataFrame(columns=list(FILM_COLUMNS.values()))
    flat = pd.json_normalize(movies, sep="_", max_level=1)
    for col in FILM_COLUMNS:                      # a collection-less batch has no collection columns
        if col not in flat.columns:
            flat[col] = pd.NA
    films = flat[list(FILM_COLUMNS)].rename(columns=FILM_COLUMNS)

    genres = pd.json_normalize(movies, record_path="genres", meta=["_requested_id"], errors="ignore")
    if len(genres):
        genre_str = genres.groupby("_requested_id")["name"].agg(", ".join)
        films["genres"] = films["tmdb_id"].map(genre_str)
        films["genre_count"] = films["tmdb_id"].map(genres.groupby("_requested_id").size()).fillna(0)
    else:
        films["genres"], films["genre_count"] = pd.NA, 0

    films = films.astype({"tmdb_id": "int64", "returned_id": "int64", "budget": "Int64",
                          "revenue": "Int64", "runtime": "Float64", "vote_average": "Float64",
                          "vote_count": "Int64", "popularity": "Float64", "collection_id": "Int64",
                          "genre_count": "int64"})
    films["release_date"] = pd.to_datetime(films["release_date"].replace("", pd.NA), errors="coerce")
    films["release_year"] = films["release_date"].dt.year.astype("Int64")
    assert films["tmdb_id"].is_unique, "films table must have one row per id"
    return films


def cast_table(credits: list[dict]) -> pd.DataFrame:
    """Grain: one row per film per credited cast member."""
    cast = pd.json_normalize(credits, record_path="cast", meta=["_requested_id"], errors="ignore")
    if cast.empty:
        return pd.DataFrame(columns=["tmdb_id", "person_id", "name", "character", "order"])
    cast = cast.rename(columns={"_requested_id": "tmdb_id", "id": "person_id"})
    return cast[["tmdb_id", "person_id", "name", "character", "order"]].astype(
        {"tmdb_id": "int64", "person_id": "int64", "order": "int64"})


def crew_table(credits: list[dict]) -> pd.DataFrame:
    """Grain: one row per film per crew credit (a person can hold several jobs on one film)."""
    crew = pd.json_normalize(credits, record_path="crew", meta=["_requested_id"], errors="ignore")
    if crew.empty:
        return pd.DataFrame(columns=["tmdb_id", "person_id", "name", "job", "department"])
    crew = crew.rename(columns={"_requested_id": "tmdb_id", "id": "person_id"})
    return crew[["tmdb_id", "person_id", "name", "job", "department"]].astype(
        {"tmdb_id": "int64", "person_id": "int64"})


def talent_table(cast: pd.DataFrame, crew: pd.DataFrame) -> pd.DataFrame:
    """Grain: one row per film per (role, person) where role is 'director' or 'lead_actor'.
    Deduplicated so a person credited twice in the same role on one film counts once."""
    directors = crew.loc[crew["job"].eq("Director"), ["tmdb_id", "person_id", "name"]].assign(role="director")
    leads = cast.loc[cast["order"].lt(LEAD_BILLING), ["tmdb_id", "person_id", "name"]].assign(role="lead_actor")
    talent = pd.concat([directors, leads], ignore_index=True).drop_duplicates(["tmdb_id", "role", "person_id"])
    return talent.reset_index(drop=True)
