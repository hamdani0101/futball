from rich.progress import Progress
from rich.console import Console
from django.utils.timezone import make_aware
import json
from pathlib import Path
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models.competition import Competition
from core.models.season import Season
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats
from core.models.team import Team
from core.models.stadium import Stadium


class Command(BaseCommand):
    help = "Import matches from StatsBomb directory (data/matches)"
    console = Console()

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-dir",
            type=str,
            required=True,
            help="Path to data/matches directory",
        )

    # =====================
    # ENTRY
    # =====================

    def handle(self, *args, **options):
        base_dir = Path(options["base_dir"])

        total_created = total_updated = total_skipped = 0

        with Progress() as progress:
            files = list(base_dir.rglob("*.json"))
            task = progress.add_task(
                "[cyan]Importing matches...",
                total=len(files)
            )

            for file in files:
                created, updated, skipped = self.import_file(file)
                
                total_created += created
                total_updated += updated
                total_skipped += skipped
                
                progress.advance(task)
                progress.update(
                    task,
                    description=f"[cyan]Importing: {file.name}"
                )
                

        self.console.log(
            f"[green]Created:[/green] {total_created} | "
            f"[blue]Updated:[/blue] {total_updated} | "
            f"[yellow]Skipped:[/yellow] {total_skipped}"
        )

    # =====================
    # IMPORT FILE
    # =====================

    @transaction.atomic
    def import_file(self, path):
        with open(path) as f:
            matches = json.load(f)

        team_cache = {}
        stadium_cache = {}

        return self.process_matches(matches, team_cache, stadium_cache)

    # =====================
    # PROCESS MATCH
    # =====================

    def process_matches(self, matches, team_cache, stadium_cache):
        created = 0
        updated = 0
        skipped = 0
        
        external_ids = [
            str(m.get("match_id"))
            for m in matches
            if m.get("match_id")
        ]

        existing_matches = {
            m.external_id: m
            for m in Match.objects.filter(external_id__in=external_ids)
        }

        to_create = []
        to_update = []
        raw_map = {}

        for m in matches:
            try:
                external_id = str(m["match_id"])

                # teams
                home_team_data = m.get("home_team") or {}
                home_name = home_team_data.get("home_team_name")
                home_id = home_team_data.get("home_team_id")
                home_team = self.get_team(home_name, home_id, None, team_cache)
                
                away_team_data = m.get("away_team") or {}
                away_name = away_team_data.get("away_team_name")
                away_id = away_team_data.get("away_team_id")
                away_team = self.get_team(away_name, away_id, None, team_cache)

                # stadium
                stadium = self.get_stadium(
                    m.get("stadium"),
                    m.get("stadium_country"),
                    stadium_cache,
                )

                # season
                season = self.get_or_create_season(m["competition"]["competition_id"], m["season"]["season_id"])

                # datetime
                match_date = self.parse_datetime(m["match_date"], m["kick_off"])
                status = self.map_status(m["match_status"])

                if external_id in existing_matches:
                    match = existing_matches[external_id]
                    match.season = season
                    match.home_team = home_team
                    match.away_team = away_team
                    match.match_date = match_date
                    match.status = status
                    match.stadium = stadium

                    to_update.append(match)
                    updated += 1
                else:
                    match = Match(
                        external_id=external_id,
                        season=season,
                        home_team=home_team,
                        away_team=away_team,
                        match_date=match_date,
                        status=status,
                        stadium=stadium,
                    )
                    to_create.append(match)
                    created += 1

                raw_map[external_id] = m
            except Exception as e:
                # self.console.log(
                #     f"[red]Error[/red] match_id={external_id} → {e}"
                # )
                pass
            
        Match.objects.bulk_create(to_create, ignore_conflicts=True)

        Match.objects.bulk_update(
            to_update,
            ["season", "home_team", "away_team", "match_date", "status", "stadium"],
        )
            
        all_matches = {
            m.external_id: m
            for m in Match.objects.filter(external_id__in=raw_map.keys())
        }
        
        existing_stats = {
            (s.match_id, s.team_id): s
            for s in MatchTeamStats.objects.filter(
                match__in=all_matches.values()
            )
        }
        
        stats_create = []
        stats_update = []

        for external_id, raw in raw_map.items():
            match = all_matches.get(external_id)

            if not match:
                skipped += 1
                continue

            for team, goals in [
                (match.home_team, raw.get("home_score") or 0),
                (match.away_team, raw.get("away_score") or 0),
            ]:
                key = (match.id, team.id)

                if key in existing_stats:
                    stat = existing_stats[key]
                    stat.goals = goals
                    stats_update.append(stat)
                else:
                    stats_create.append(
                        MatchTeamStats(
                            match=match,
                            team=team,
                            goals=goals,
                            xg=0.0,
                            shots=0,
                            shots_on_target=0,
                        )
                    )
        
        MatchTeamStats.objects.bulk_create(
            stats_create,
            ignore_conflicts=True
        )

        MatchTeamStats.objects.bulk_update(
            stats_update,
            ["goals"]
        )

        return created, updated, skipped
    # =====================
    # HELPERS
    # =====================

    def get_team(self, name, external_id, stadium, cache):
        key = external_id if external_id is not None else name.lower()

        if key not in cache:
            team, created = Team.objects.get_or_create(
                external_id=external_id,
                defaults={
                    "name": name.strip(),
                    "home_stadium": stadium,
                },
            )

            if not created:
                updated = False

                if name and not team.name:
                    team.name = name
                    updated = True

                if stadium and not team.home_stadium:
                    team.home_stadium = stadium
                    updated = True

                if updated:
                    team.save()

            cache[key] = team

        return cache[key]

    def get_stadium(self, stadium_data, country, cache):
        if not stadium_data:
            return None

        stadium_id = stadium_data.get("id")
        name = stadium_data.get("name")

        if not name:
            return None

        key = stadium_id or name.lower()

        if key not in cache:
            if stadium_id:
                stadium, _ = Stadium.objects.get_or_create(
                    external_id=stadium_id,
                    defaults={
                        "name": name,
                        "country": country,
                    },
                )
            else:
                stadium, _ = Stadium.objects.get_or_create(
                    name=name,
                    defaults={"country": country},
                )

            cache[key] = stadium

        return cache[key]

    def get_or_create_season(self, competition_id, season_id):
        competition = Competition.objects.filter(
            external_id=competition_id
        ).first()

        if not competition:
            raise ValueError(f"Competition not found: {competition_id}")
        
        season, created = Season.objects.get_or_create(
            external_id=season_id,
            competition=competition,
            defaults={
                "name": f"Season {season_id}",
            }
        )
        
        return season

    def parse_datetime(self, date_str, time_str=None):
        if time_str:
            try:
                dt = datetime.fromisoformat(f"{date_str}T{time_str}")
                return make_aware(dt)
            except Exception:
                pass
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return make_aware(dt)

    def map_status(self, status):
        return {
            "available": "finished",
            "scheduled": "scheduled",
            "deleted": "cancelled",
        }.get(status, "scheduled")