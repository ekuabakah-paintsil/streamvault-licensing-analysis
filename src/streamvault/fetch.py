"""Stage 2: acquisition.

Rules this module follows (Learning Path topic 7):
- fetch once and cache every raw response to data/raw/, one JSON file per id per endpoint;
- a re-run makes zero network calls for anything already cached;
- 404s are cached too (as a marker) so a dead id is never asked for twice;
- transient failures (429/5xx/connection) are retried with backoff and Retry-After honoured;
- permanent failures (401/403) stop the run loudly: a bad key should not burn 254 calls;
- every call is logged to a manifest with its timestamp, so every figure has an as-of date.

Looping here is over network requests, not over DataFrame rows.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

ENDPOINTS = {"movie": "/movie/{id}", "credits": "/movie/{id}/credits"}   # fetched for every candidate
EXTRA_ENDPOINTS = {"collection": "/collection/{id}"}                        # used by the bundle check only


# What the cache holds for one id at one endpoint. A fixed set of categories, so a typo such
# as "Found" or "200" cannot silently fail to match. The HTTP code is kept separately, as a number.
FETCH_STATE = pd.CategoricalDtype(["found", "not_found", "not_fetched"])


def fetch_state(http_status: pd.Series) -> pd.Series:
    """Nullable HTTP status codes -> FETCH_STATE: 200 found, 404 not_found, missing not_fetched."""
    return http_status.map({200: "found", 404: "not_found"}).fillna("not_fetched").astype(FETCH_STATE)


class AuthError(SystemExit):
    pass


def make_session() -> requests.Session:
    creds = config.api_credentials()
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json", **creds["headers"]})
    s.params = creds["params"]
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True, raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _cache_path(endpoint: str, key) -> Path:
    return config.RAW / endpoint / f"{key}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(session, url: str, params: dict | None = None) -> tuple[int, dict | None]:
    r = session.get(url, params=params, timeout=config.TIMEOUT)
    if r.status_code in (401, 403):
        raise AuthError(f"TMDb refused the key (HTTP {r.status_code}). Check TMDB_API_KEY in .env. "
                        "Stopping before making more requests.")
    if r.status_code == 404:
        return 404, None
    r.raise_for_status()
    return r.status_code, r.json()


def _write_atomic(path: Path, text: str) -> None:
    """Write a file so it is either complete or absent, never half-written.
    The text goes to a temporary file in the same folder, which is then renamed over the
    target in one step (os.replace is atomic on Windows and Linux). If the run is killed
    mid-write, only the temporary file is left, and the next run ignores and replaces it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def fetch_one(session, endpoint: str, tmdb_id: int, log: list) -> None:
    path = _cache_path(endpoint, tmdb_id)
    if path.exists():
        log.append({"endpoint": endpoint, "tmdb_id": tmdb_id, "source": "cache"})
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    url = config.API_BASE + {**ENDPOINTS, **EXTRA_ENDPOINTS}[endpoint].format(id=tmdb_id)
    fetched_at = _now()
    try:
        status, body = _get(session, url)
    except AuthError:
        raise
    except requests.RequestException as exc:
        # Not cached: a failed request should be retried on the next run, not remembered.
        log.append({"endpoint": endpoint, "tmdb_id": tmdb_id, "source": "network",
                    "http_status": None, "fetched_at": fetched_at, "error": str(exc)[:200]})
        return
    payload = {"_fetched_at": fetched_at, "_http_status": status, "_requested_id": int(tmdb_id),
               "body": body}
    _write_atomic(path, json.dumps(payload))
    log.append({"endpoint": endpoint, "tmdb_id": tmdb_id, "source": "network",
                "http_status": status, "fetched_at": fetched_at})
    time.sleep(config.THROTTLE_SECONDS)


def resolve_imdb_ids(session, imdb_ids: list[str], log: list) -> dict[str, int | None]:
    """Map IMDb ids (tt...) to TMDb movie ids via /find, cached like everything else."""
    out = {}
    for imdb in imdb_ids:
        path = _cache_path("find", imdb)
        if not path.exists():
            if session is None:
                out[imdb] = None
                continue
            fetched_at = _now()
            try:
                status, body = _get(session, f"{config.API_BASE}/find/{imdb}",
                                    params={"external_source": "imdb_id"})
            except AuthError:
                raise
            except requests.RequestException as exc:
                # Same rule as fetch_one: log it, leave it uncached, retry on the next run.
                # This run labels the line "excluded_imdb_unresolved" rather than crashing.
                log.append({"endpoint": "find", "tmdb_id": imdb, "source": "network",
                            "http_status": None, "fetched_at": fetched_at, "error": str(exc)[:200]})
                out[imdb] = None
                continue
            _write_atomic(path, json.dumps({"_fetched_at": fetched_at, "_http_status": status,
                                            "body": body}))
            log.append({"endpoint": "find", "tmdb_id": imdb, "source": "network",
                        "http_status": status, "fetched_at": fetched_at})
            time.sleep(config.THROTTLE_SECONDS)
        body = json.loads(path.read_text(encoding="utf-8"))["body"] or {}
        hits = body.get("movie_results") or []
        out[imdb] = int(hits[0]["id"]) if len(hits) == 1 else None
    return out


def read_cached(endpoint: str, key) -> dict | None:
    """Public accessor for one cached response: the stored payload ({"_fetched_at",
    "_http_status", "body"}), or None if that id has not been fetched for this endpoint.
    Other modules use this instead of building cache paths themselves."""
    path = _cache_path(endpoint, key)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def get_live(session, endpoint: str, key) -> dict | None:
    """Public accessor for one live response, bypassing the cache (used by the spot-check).
    Returns the response body, or None if TMDb answers 'not found'."""
    url = config.API_BASE + {**ENDPOINTS, **EXTRA_ENDPOINTS}[endpoint].format(id=key)
    return _get(session, url)[1]


def fetch_all(session, ids, log: list) -> None:
    ids = list(ids)
    for i, tmdb_id in enumerate(ids, 1):
        for endpoint in ENDPOINTS:
            fetch_one(session, endpoint, int(tmdb_id), log)
        if i % 25 == 0 or i == len(ids):
            made = sum(1 for e in log if e.get("source") == "network")
            print(f"  fetched {i}/{len(ids)} ids  (network calls so far: {made})")


def _bundle_path(endpoint: str):
    return config.RAW / f"bundle_{endpoint}.json"


def _slim(endpoint: str, payload: dict | None) -> dict | None:
    """Keep only the credit entries the analysis uses (config.CREW_JOBS_KEPT, config.CAST_BILLING_KEPT).
    Film details are small and kept whole. The per-film cache files are never changed."""
    if endpoint != "credits" or payload is None or payload.get("body") is None:
        return payload
    body = payload["body"]
    slim = dict(body,
                cast=[c for c in body.get("cast", []) if c.get("order", 999) < config.CAST_BILLING_KEPT],
                crew=[c for c in body.get("crew", []) if c.get("job") in config.CREW_JOBS_KEPT])
    return dict(payload, body=slim)


def build_bundles(ids) -> None:
    """Pack the per-id cache files into ONE file per endpoint, credits trimmed to what is used.

    Why (both measured, see ADR-005): opening 234 small files took 6.76 s on a cold run against
    0.18 s warm; and with full credits, the first run after idle at 500 titles took 6.0 s, over
    the 5 s budget. The per-id files stay complete as the source of truth; the bundle is a slim,
    read-optimised copy, rebuilt whenever the fetch adds anything new or the keep-rules change."""
    for endpoint in ENDPOINTS:
        bundle = {"_format": config.BUNDLE_FORMAT}
        for tmdb_id in ids:
            p = _cache_path(endpoint, int(tmdb_id))
            # None records "not fetched (yet)" so the bundle still covers every id
            bundle[str(int(tmdb_id))] = (_slim(endpoint, json.loads(p.read_text(encoding="utf-8")))
                                         if p.exists() else None)
        _write_atomic(_bundle_path(endpoint), json.dumps(bundle))


def _read_bundle(endpoint: str, ids) -> dict | None:
    """Return the bundle if it is the current format and covers every requested id,
    else None (the caller rebuilds it)."""
    path = _bundle_path(endpoint)
    if not path.exists():
        return None
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:          # damaged copy (e.g. written by an older version): rebuild
        return None
    if bundle.get("_format") != config.BUNDLE_FORMAT:
        return None
    return bundle if all(str(int(i)) in bundle for i in ids) else None


def load_cache(ids) -> tuple[list[dict], list[dict], pd.DataFrame]:
    """Read cached responses from the two bundle files. Returns movie bodies, credits bodies
    and a status table (grain: one row per requested id) recording what the cache holds:
    for each endpoint, the HTTP code as a nullable integer and the state as FETCH_STATE."""
    ids = [int(i) for i in ids]
    bundles = {e: _read_bundle(e, ids) for e in ENDPOINTS}
    if any(b is None for b in bundles.values()):           # missing or stale: rebuild once
        build_bundles(ids)
        bundles = {e: _read_bundle(e, ids) or {} for e in ENDPOINTS}
    movies, credits, rows = [], [], []
    for tmdb_id in ids:                                      # loop over ids in memory, not over files
        row = {"tmdb_id": tmdb_id}
        for endpoint, sink in (("movie", movies), ("credits", credits)):
            payload = bundles[endpoint].get(str(tmdb_id))
            if payload is None:
                continue                                     # absent -> http code missing -> not_fetched
            row[f"{endpoint}_http_status"] = int(payload["_http_status"])
            row[f"{endpoint}_fetched_at"] = payload["_fetched_at"]
            if payload["body"] is not None:
                body = dict(payload["body"])
                body["_requested_id"] = int(tmdb_id)
                body["_fetched_at"] = payload["_fetched_at"]
                sink.append(body)
        rows.append(row)
    status = pd.DataFrame(rows, columns=["tmdb_id", "movie_http_status", "movie_fetched_at",
                                         "credits_http_status", "credits_fetched_at"])
    for endpoint in ENDPOINTS:
        status[f"{endpoint}_http_status"] = status[f"{endpoint}_http_status"].astype("Int64")
        status[f"{endpoint}_status"] = fetch_state(status[f"{endpoint}_http_status"])
    return movies, credits, status
