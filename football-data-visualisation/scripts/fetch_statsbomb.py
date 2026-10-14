"""Fetch StatsBomb open data into ``data/cache`` (no API key required).

StatsBomb publishes a free open-data set as plain JSON in a GitHub repository.
This script mirrors only the slices this project needs:

    competitions.json             every competition + season
    matches/<comp>/<season>.json  the fixture list for one season
    events/<match_id>.json        the full event stream for one match
    three-sixty/<match_id>.json   360 freeze-frames (~1 frame per event)

Usage
-----
    python football-data-visualisation/scripts/fetch_statsbomb.py --list
    python football-data-visualisation/scripts/fetch_statsbomb.py --core
    python football-data-visualisation/scripts/fetch_statsbomb.py --matches 3857276 3857271
    python football-data-visualisation/scripts/fetch_statsbomb.py --season 43 106 --limit 8

Data licence: StatsBomb open data is free for research and public use under the
StatsBomb Public Data User Agreement. Attribution is required:

    "Data provided by StatsBomb" - https://statsbomb.com/what-we-do/hub/free-data/
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "cache"

#: Seasons used by the demo figures: (competition_id, season_id, short label)
CORE_SEASONS = [
    (43, 106, "FIFA World Cup 2022"),
    (72, 107, "Women's World Cup 2023"),
    (55, 282, "UEFA Euro 2024"),
    (11, 1, "La Liga 2017/2018"),
]


def fetch(rel: str, force: bool = False) -> Path | None:
    """Download ``rel`` under BASE into CACHE, returning the local path or None."""
    dest = CACHE / rel
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{rel}"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    dest.write_bytes(payload)
    return dest


def load_matches(competition_id: int, season_id: int, force: bool = False) -> list[dict]:
    """Return the fixture list for a season, downloading it if needed."""
    path = fetch(f"matches/{competition_id}/{season_id}.json", force=force)
    return json.loads(path.read_text()) if path else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--list", action="store_true", help="print available competitions and exit")
    ap.add_argument("--core", action="store_true", help="download fixture lists for CORE_SEASONS")
    ap.add_argument("--season", nargs=2, type=int, metavar=("COMP", "SEASON"),
                    help="download one season's fixtures")
    ap.add_argument("--matches", nargs="+", type=int, help="download events + 360 for these match ids")
    ap.add_argument("--limit", type=int, default=None, help="cap the number of matches pulled per season")
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args(argv)

    if args.list:
        path = fetch("competitions.json")
        for comp in json.loads(path.read_text()):
            print(f"{comp['competition_id']:>5} {comp['season_id']:>4}  "
                  f"{comp['competition_name']} - {comp['season_name']} ({comp['country_name']})")
        return 0

    # The competition index is small and everything else keys off it, so always
    # pull it - including for --core, which the data layer checks as its marker.
    fetch("competitions.json", force=args.force)

    seasons = [(args.season[0], args.season[1], "custom")] if args.season else (
        CORE_SEASONS if args.core else []
    )
    match_ids: list[int] = list(args.matches or [])

    for comp_id, season_id, label in seasons:
        matches = load_matches(comp_id, season_id, force=args.force)
        if args.limit:
            matches = matches[: args.limit]
        picked = [m["match_id"] for m in matches]
        match_ids.extend(picked)
        print(f"[{label}] {len(picked)} matches cached")

    if not match_ids and not seasons:
        ap.print_help()
        return 1

    unique = list(dict.fromkeys(match_ids))
    for i, mid in enumerate(unique, 1):
        ev = fetch(f"events/{mid}.json", force=args.force)
        fr = fetch(f"three-sixty/{mid}.json", force=args.force)
        print(f"  [{i}/{len(unique)}] {mid}: events={'ok' if ev else '-'} "
              f"360={'ok' if fr else 'none'}")

    print(f"\nCache: {CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
