"""Stage 1: audit the candidate list.

Produces the id LEDGER: one row per data line of id_list.csv (grain: one row
per line in the file, blank lines included), so every one of the original
entries can be traced to where it ended up. Nothing is dropped here; rows are
only labelled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

IMDB_PATTERN = r"^tt\d{7,8}$"


def read_raw(path) -> pd.DataFrame:
    """Read every line as text. No type guessing, no blank-line skipping,
    because both would silently hide faults in the source list."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    if list(raw.columns) != ["tmdb_id"]:
        raise ValueError(f"Expected one column 'tmdb_id', found {list(raw.columns)}")
    raw = raw.rename(columns={"tmdb_id": "raw_value"})
    raw.insert(0, "file_line", np.arange(2, len(raw) + 2))   # line 1 is the header
    return raw


def parse(raw: pd.DataFrame) -> pd.DataFrame:
    """Label each line. Vectorised: every rule is a whole-column mask."""
    led = raw.copy()
    v = led["raw_value"].str.strip()
    numeric = pd.to_numeric(v.where(v.str.fullmatch(r"-?\d+")), errors="coerce")

    is_blank = v.eq("")
    is_imdb = v.str.fullmatch(IMDB_PATTERN)
    is_number = numeric.notna()
    is_positive = is_number & numeric.gt(0)

    led["id_status"] = np.select(
        [is_blank, is_imdb, is_number & ~is_positive, is_positive],
        ["excluded_blank_line", "imdb_id_needs_resolving", "excluded_invalid_number", "candidate"],
        default="excluded_not_an_id",
    )
    led["tmdb_id"] = numeric.where(is_positive).astype("Int64")
    led["note"] = np.select(
        [is_blank, is_imdb, is_number & ~is_positive, ~is_number & ~is_blank & ~is_imdb],
        ["empty line in source file",
         "IMDb-format id; resolved via TMDb /find before deduplication",
         "non-positive number; TMDb ids start at 1",
         "placeholder text, not an identifier"],
        default="",
    )
    return led


def apply_imdb_resolution(led: pd.DataFrame, resolved: dict[str, int | None]) -> pd.DataFrame:
    """Fill in TMDb ids for IMDb-format lines using a {imdb_id: tmdb_id or None} map."""
    led = led.copy()
    imdb_lines = led["id_status"].eq("imdb_id_needs_resolving")
    mapped = led.loc[imdb_lines, "raw_value"].str.strip().map(resolved)
    resolved_idx = mapped.index[mapped.notna()]      # IMDb lines with exactly one TMDb match
    unresolved_idx = mapped.index[mapped.isna()]     # IMDb lines with no single match
    led.loc[resolved_idx, "tmdb_id"] = mapped[resolved_idx].astype("int64")
    led.loc[resolved_idx, "id_status"] = "candidate"
    led.loc[resolved_idx, "note"] = "resolved from IMDb id " + led.loc[resolved_idx, "raw_value"].str.strip()
    led.loc[unresolved_idx, "id_status"] = "excluded_imdb_unresolved"
    return led


def mark_duplicates(led: pd.DataFrame) -> pd.DataFrame:
    """Keep the first occurrence of each id; label later ones with the line they repeat."""
    led = led.copy()
    cand = led["id_status"].eq("candidate")
    first_line = led.loc[cand].groupby("tmdb_id")["file_line"].transform("min")
    dup = cand & led["file_line"].ne(first_line.reindex(led.index))
    led.loc[dup, "id_status"] = "excluded_duplicate"
    led.loc[dup, "note"] = ("same TMDb id as line " +
                            first_line[dup[cand]].astype(str) +
                            led.loc[dup, "note"].where(led.loc[dup, "note"].eq(""),
                                                       "; " + led.loc[dup, "note"]))
    return led


def unique_candidates(led: pd.DataFrame) -> pd.Series:
    ids = led.loc[led["id_status"].eq("candidate"), "tmdb_id"].astype("int64")
    assert ids.is_unique, "candidate ids must be unique after deduplication"
    return ids