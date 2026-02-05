#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


DEFAULT_LEAGUE_MAP = {
    "bundesliga": "1. Bundesliga",
    "la-liga": "La Liga",
    "ligue-1": "Ligue 1",
    "premier-league": "Premier League",
    "serie-a": "Serie A",
}


def list_datasets(data_match_dir: Path):
    if not data_match_dir.exists():
        return []
    return sorted(
        d.name for d in data_match_dir.iterdir() if d.is_dir()
    )


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build data/shots/matches.json from a local StatsBomb open-data repo"
        )
    )
    parser.add_argument(
        "--open-data-root",
        required=True,
        help="Path to the StatsBomb open-data repository root",
    )
    parser.add_argument(
        "--out",
        default="data/shots/matches.json",
        help="Output path for merged matches.json",
    )
    parser.add_argument(
        "--data-match-dir",
        default="data/match",
        help="Local datasets root (default: data/match)",
    )
    parser.add_argument(
        "--leagues",
        default="",
        help=(
            "Comma-separated league slugs to include "
            "(default: all folders in data/match)"
        ),
    )
    args = parser.parse_args()

    open_data_root = Path(args.open_data_root)
    competitions_path = open_data_root / "data" / "competitions.json"
    matches_root = open_data_root / "data" / "matches"

    if not competitions_path.exists():
        raise SystemExit(
            f"competitions.json not found: {competitions_path}"
        )

    competitions = load_json(competitions_path)

    if args.leagues:
        league_slugs = [s.strip() for s in args.leagues.split(",") if s.strip()]
    else:
        league_slugs = list_datasets(Path(args.data_match_dir))

    league_names = {}
    for slug in league_slugs:
        league_names[slug] = DEFAULT_LEAGUE_MAP.get(slug)

    matches = []
    missing_leagues = []

    for slug, league_name in league_names.items():
        if not league_name:
            missing_leagues.append(slug)
            continue

        for comp in competitions:
            if comp.get("competition_name") != league_name:
                continue

            comp_id = comp.get("competition_id")
            season_id = comp.get("season_id")
            if comp_id is None or season_id is None:
                continue

            match_file = matches_root / str(comp_id) / f"{season_id}.json"
            if not match_file.exists():
                continue

            matches.extend(load_json(match_file))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matches, f)

    print(f"Wrote {len(matches)} matches to {out_path}")

    if missing_leagues:
        print("No league mapping for:")
        for slug in missing_leagues:
            print(f"- {slug}")


if __name__ == "__main__":
    main()
