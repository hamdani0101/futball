"""Admin registrations for futball app models."""

from django.contrib import admin
from futball.models.competition import Competition, CompetitionFormat
from futball.models.season import Season
from futball.models.match import Match
from futball.models.match_team_stat import MatchTeamStats
from futball.models.stadium import Stadium
from futball.models.team import Team
from futball.models.shots import Shot
from futball.models.player import Player
from futball.models.player_match import PlayerMatch
from futball.models.news import News
from futball.models.news_content_image import NewsContentImage

admin.site.register(Competition)
admin.site.register(CompetitionFormat)
admin.site.register(Season)
admin.site.register(Team)
admin.site.register(Match)
admin.site.register(MatchTeamStats)
admin.site.register(Shot)
admin.site.register(Player)
admin.site.register(PlayerMatch)
admin.site.register(News)
admin.site.register(NewsContentImage)
admin.site.register(Stadium)

