"""Improvement beyond the brief: is each franchise bundle as good as the list makes it look?

    python improvement/bundle_check.py             # after run.py; fetches what is not cached yet
    python improvement/bundle_check.py --offline   # cached data only, no network

The candidate list mostly holds each franchise's best-known films, but a bundle is sold whole.
This fetches every franchise's complete film list, then the figures for the films the list left
out, and writes:
    outputs/bundle_completeness.csv   one row per franchise: on the list vs the complete bundle
    outputs/bundle_members.csv        one row per franchise per film, flagged on/off the list
    outputs/bundle_headline.csv       franchise vs standalone, redone with complete bundles
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from streamvault import bundles, config, fetch  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="cached data only; make no API calls")
    args = ap.parse_args()

    films_path = config.OUTPUTS / "films.csv"
    if not films_path.exists():
        raise SystemExit("outputs/films.csv not found: run `python run.py` first.")
    films = pd.read_csv(films_path, parse_dates=["release_date"])
    films["collection_id"] = films["collection_id"].astype("Int64")

    session = None if args.offline else fetch.make_session()
    log: list[dict] = []
    coll_ids = bundles.collection_ids(films)
    if session is not None:
        bundles.fetch_collections(session, coll_ids, log)
    members, coll_status = bundles.load_members(coll_ids)

    member_ids = sorted(members["member_id"].unique().tolist())
    if session is not None:
        bundles.fetch_member_details(session, member_ids, log)
    details = bundles.load_member_details(member_ids)

    per_member, per_bundle = bundles.completeness(films, members, details)
    head = bundles.headline(films, per_bundle, per_member)

    config.OUTPUTS.mkdir(exist_ok=True)
    per_bundle.to_csv(config.OUTPUTS / "bundle_completeness.csv", index=False)
    per_member.to_csv(config.OUTPUTS / "bundle_members.csv", index=False)
    head.to_csv(config.OUTPUTS / "bundle_headline.csv", index=False)

    calls = sum(1 for e in log if e.get("source") == "network")
    not_fetched = coll_status["collection_status"].ne("200").sum()
    print(f"Franchises checked: {len(coll_ids)} (lists missing: {not_fetched}) | "
          f"films across them: {len(members)} | not on the candidate list: "
          f"{int((~per_member['on_list']).sum())} | network calls this run: {calls}")
    print(f"Bundles complete on the list: {int(per_bundle['complete_on_list'].sum())} of {len(per_bundle)}; "
          f"released films missing from the list: {int(per_bundle['missing_released'].sum())} "
          f"({int(per_bundle['missing_without_figures'].sum())} of them with no budget or revenue)\n")
    pd.set_option("display.width", 250)
    cols = ["collection_name", "films_in_franchise", "on_list", "missing_released", "list_return",
            "full_return", "change_vs_list", "weakest_on_list", "weakest_full"]
    print(per_bundle[cols].round(2).to_string(index=False))
    print("\nFranchise vs standalone, per WHOLE bundle:")
    print(head.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
