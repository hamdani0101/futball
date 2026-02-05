#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def normalize_team(name):
    return (name or "").strip()


def load_team_map(path):
    if not path:
        return {}

    team_map = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sb = normalize_team(row.get("statsbomb_name"))
            csv_name = normalize_team(row.get("csv_name"))
            if sb and csv_name:
                team_map[sb] = csv_name
    return team_map


def format_match_id(match_date, home, away):
    date_str = datetime.strptime(match_date, "%Y-%m-%d").strftime("%d/%m/%y")
    return f"{date_str}-{home}-{away}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate match_map.csv from StatsBomb matches.json"
    )
    parser.add_argument(
        "matches_json",
        help="Path to StatsBomb matches.json",
    )
    parser.add_argument(
        "--out",
        default="match_map.csv",
        help="Output CSV path (default: match_map.csv)",
    )
    parser.add_argument(
        "--team-map",
        default="",
        help="Optional CSV map with headers `statsbomb_name,csv_name`",
    )
    args = parser.parse_args()

    matches_path = Path(args.matches_json)
    if not matches_path.exists():
        raise SystemExit(f"matches.json not found: {matches_path}")
    if matches_path.stat().st_size == 0:
        raise SystemExit(f"matches.json is empty: {matches_path}")

    team_map = load_team_map(args.team_map)

    try:
        with open(matches_path, encoding="utf-8") as f:
            matches = json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"matches.json is not valid JSON: {matches_path}"
        ) from exc

    rows = []
    for m in matches:
        match_id = str(m.get("match_id") or "").strip()
        match_date = m.get("match_date")
        home = (m.get("home_team") or {}).get("home_team_name")
        away = (m.get("away_team") or {}).get("away_team_name")

        if not (match_id and match_date and home and away):
            continue

        home = team_map.get(normalize_team(home), normalize_team(home))
        away = team_map.get(normalize_team(away), normalize_team(away))

        rows.append(
            {
                "statsbomb_match_id": match_id,
                "match_id": format_match_id(match_date, home, away),
            }
        )

    out_path = Path(args.out)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["statsbomb_match_id", "match_id"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
