from django.contrib import admin
from futball.models.competition import Competition
from futball.models.season import Season
from futball.models.match import Match
from futball.models.team import Team
from futball.models.shots import Shot

admin.site.register(Competition)
admin.site.register(Season)
admin.site.register(Team)
admin.site.register(Match)
admin.site.register(Shot)
