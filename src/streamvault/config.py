"""Paths and settings. Everything is relative to the repository root so the
pipeline runs from a fresh clone on any machine (Windows, macOS, Linux)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"                 # cached API responses, one JSON per id per endpoint
OUTPUTS = ROOT / "outputs"
ID_LIST = DATA / "id_list.csv"

API_BASE = "https://api.themoviedb.org/3"
USER_AGENT = "StreamVault-Licensing-Analysis/1.0 (DE02 lab; contact via repo owner)"
TIMEOUT = (3.05, 15)               # connect, read
THROTTLE_SECONDS = 0.1             # pause between live calls; ~10 req/s, well under TMDb limits

WINDOW_CUTOFF_YEAR = 2000          # Yaw's line: the "modern" window is release year >= this
TIME_BUDGET_SECONDS = 5.0          # analysis stage (from cache) must finish inside this at 500 titles
# What the read-optimised bundle keeps from each film's credits. The analysis uses directors and the
# top-3 billed cast; the per-film files in data/raw/credits/ keep everything TMDb sent. Measured reason:
# with full credits, the first run after idle at 500 titles took 6.0 s, over the 5 s budget (ADR-005).
# Widen these (e.g. add "Screenplay") if a future question needs more; no other change required.
CREW_JOBS_KEPT = ("Director",)
CAST_BILLING_KEPT = 10
BUNDLE_FORMAT = "slim-v1"          # change this whenever the keep-rules change, so old bundles are rebuilt

MIN_GROUP_SIZE = 3                 # talent / collection stats below this are reported but flagged


def load_env(path: Path | None = None) -> None:
    """Minimal .env reader so the project needs no extra dependency.
    Existing environment variables always win over the file."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_credentials() -> dict:
    """Return request params/headers for TMDb.

    Accepts either a v3 API key (TMDB_API_KEY) or a v4 read access token
    (TMDB_READ_TOKEN, or a TMDB_API_KEY value that is a JWT starting 'eyJ')."""
    load_env()
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if not token and key.startswith("eyJ"):
        token, key = key, ""
    if token:
        return {"params": {}, "headers": {"Authorization": f"Bearer {token}"}}
    if key:
        return {"params": {"api_key": key}, "headers": {}}
    raise SystemExit(
        "No TMDb credentials found. Put TMDB_API_KEY=<your key> in a .env file at the "
        "repository root (see .env.example) or set it as an environment variable."
    )