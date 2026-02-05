import csv
import json
import os
from difflib import SequenceMatcher, get_close_matches

from django.core.management.base import BaseCommand

from futball.models import Team


def normalize(name):
    if not name:
        return ""
    cleaned = (
        name.replace(".", "")
        .replace(",", "")
        .replace("&", "and")
    )
    cleaned = " ".join(cleaned.split()).strip().lower()
    for suffix in (" fc", " afc", " cf", " sc"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    return cleaned


class Command(BaseCommand):
    help = "Generate team_map.csv by comparing DB teams vs StatsBomb matches.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "matches_json",
            type=str,
            help="Path to StatsBomb matches.json",
        )
        parser.add_argument(
            "--out",
            type=str,
            default="data/shots/team_map.csv",
            help="Output CSV path (default: data/shots/team_map.csv)",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.85,
            help="Similarity threshold for auto-matching (default: 0.85)",
        )

    def handle(self, *args, **options):
        matches_path = options["matches_json"]
        out_path = options["out"]
        threshold = options["threshold"]

        if not os.path.exists(matches_path):
            self.stderr.write(
                self.style.ERROR(f"matches.json not found: {matches_path}")
            )
            return

        with open(matches_path, encoding="utf-8") as f:
            matches = json.load(f)

        sb_names = set()
        for m in matches:
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            if home:
                sb_names.add(home)
            if away:
                sb_names.add(away)

        db_teams = list(Team.objects.values_list("name", flat=True))
        db_norm_map = {normalize(t): t for t in db_teams}

        rows = []
        for sb_name in sorted(sb_names):
            sb_norm = normalize(sb_name)

            # Exact match after normalization
            if sb_norm in db_norm_map:
                continue

            # Fuzzy suggestion
            candidates = list(db_norm_map.keys())
            suggestion = ""
            if candidates:
                close = get_close_matches(sb_norm, candidates, n=1, cutoff=threshold)
                if close:
                    suggestion = db_norm_map[close[0]]
                else:
                    # Try a best-effort similarity
                    best = max(
                        candidates,
                        key=lambda c: SequenceMatcher(None, sb_norm, c).ratio(),
                    )
                    if SequenceMatcher(None, sb_norm, best).ratio() >= threshold:
                        suggestion = db_norm_map[best]

            rows.append(
                {"statsbomb_name": sb_name, "csv_name": suggestion}
            )

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["statsbomb_name", "csv_name"])
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(rows)} rows to {out_path}. "
                "Review csv_name suggestions before use."
            )
        )
