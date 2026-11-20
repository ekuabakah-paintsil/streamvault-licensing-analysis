"""Offline self-test: builds a FAKE cache (no network, no key needed), runs the whole
analysis stage, checks the reconciliation, then times the analysis at 127, 500 and 5,000
titles to show how it scales.  Run:  python tests/test_pipeline.py

The fake data is invented and only exercises the code paths. It says nothing about films.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamvault import config, fetch, ids, pipeline  # noqa: E402

rng = np.random.default_rng(7)


def fake_movie(i: int, n_collections: int) -> dict:
    coll = int(rng.integers(0, n_collections)) if rng.random() < 0.45 else None
    budget = int(rng.choice([0, 5, int(rng.lognormal(17, 1))], p=[0.12, 0.03, 0.85]))
    revenue = int(rng.choice([0, int(rng.lognormal(18, 1.3))], p=[0.15, 0.85]))
    year = int(rng.integers(1970, 2025))
    return {
        "id": i, "title": f"Film {i % (n_collections * 7)}", "original_title": f"Film {i}",
        "release_date": f"{year}-0{int(rng.integers(1, 9))}-15", "status": "Released",
        "budget": budget, "revenue": revenue, "runtime": int(rng.choice([25, 110], p=[0.03, 0.97])),
        "vote_average": round(float(rng.uniform(4, 9)), 1), "vote_count": int(rng.integers(10, 30000)),
        "popularity": float(rng.uniform(1, 100)), "original_language": "en", "imdb_id": f"tt{i:07d}",
        "adult": False, "video": False,
        "belongs_to_collection": None if coll is None else {"id": 9000 + coll, "name": f"Saga {coll}"},
        "genres": [{"id": 1, "name": "Drama"}, {"id": 2, "name": "Action"}][: int(rng.integers(0, 3))],
    }


def fake_credits(i: int) -> dict:
    return {"id": i,
            "cast": [{"id": 100 + int(rng.integers(0, 40)) + k, "name": f"Actor {k}", "character": "x", "order": k}
                     for k in range(int(rng.integers(0, 6)))],
            "crew": [{"id": 5000 + int(rng.integers(0, 30)), "name": "Director X", "job": "Director",
                      "department": "Directing"}]}


def write(path: Path, body, status=200):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"_fetched_at": "2026-11-18T00:00:00+00:00", "_http_status": status,
                                "_requested_id": 0, "body": body}))


FIXTURE = Path(__file__).resolve().parent / "fixture_id_list.csv"


def test_real_id_list_reconciles(tmp: Path):
    """Runs on a FROZEN copy of the 2026 list (tests/fixture_id_list.csv), not on
    data/id_list.csv, so replacing the live list next year never breaks this test."""
    config.RAW = tmp / "raw"
    config.ID_LIST = FIXTURE
    # tt0468569 resolves to 155 (already on the list); huge ids 404; everything else is a fake film.
    write(config.RAW / "find" / "tt0468569.json", {"movie_results": [{"id": 155}]})
    ledger = pipeline.build_ledger(None, [])
    cands = ids.unique_candidates(ledger)
    for c in cands:
        if c > 5_000_000:
            write(config.RAW / "movie" / f"{c}.json", None, 404)
            write(config.RAW / "credits" / f"{c}.json", None, 404)
        else:
            write(config.RAW / "movie" / f"{c}.json", fake_movie(int(c), 12))
            write(config.RAW / "credits" / f"{c}.json", fake_credits(int(c)))
    movies, credits, status = fetch.load_cache(cands)
    timer = pipeline.Timer()
    out = pipeline.run_analysis(movies, credits, status, ledger, timer)
    led = out["ledger"]
    assert len(led) == 127, len(led)
    counts = led["final_status"].value_counts()
    assert counts.sum() == 127
    assert counts["excluded_duplicate"] == 7, counts   # 6 repeated ids + the IMDb id that resolves to 155
    assert counts["excluded_blank_line"] == 1
    print("Reconciliation on the frozen 2026 id list (fake API data):")
    print(counts.to_string(), "\n")


NOTEBOOK = ROOT / "explore" / "profile_candidates.ipynb"


def test_notebook_has_no_saved_outputs():
    """The profiling notebook is committed without outputs, so no data enters version control.
    Run `jupyter nbconvert --clear-output --inplace explore/profile_candidates.ipynb` to fix."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    dirty = [i for i, c in enumerate(nb["cells"])
             if c["cell_type"] == "code" and (c.get("outputs") or c.get("execution_count"))]
    assert not dirty, f"notebook cells with saved outputs: {dirty}; clear them before committing"
    print(f"Notebook {NOTEBOOK.name}: {len(nb['cells'])} cells, none with saved outputs.\n")


def time_at(n: int, tmp: Path) -> float:
    movies = [dict(fake_movie(i, max(5, n // 12)), _requested_id=i, _fetched_at="x") for i in range(1, n + 1)]
    credits = [dict(fake_credits(i), _requested_id=i) for i in range(1, n + 1)]
    timer = pipeline.Timer()
    pipeline.run_analysis(movies, credits, None, None, timer)
    return timer.table()["seconds"].sum()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        test_real_id_list_reconciles(Path(d))
        test_notebook_has_no_saved_outputs()
        print("Analysis-stage timing on synthetic data (seconds):")
        base = None
        for n in (127, 500, 5000):
            s = min(time_at(n, Path(d)) for _ in range(3))
            base = base or s
            print(f"  {n:>5} titles: {s:.3f}s  ({s / base:.1f}x the 127-title time)")
    print("\nAll checks passed.")
