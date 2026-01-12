from django.contrib import admin
from .models import Competition, Season, Team, Match, Shot

admin.site.register(Competition)
admin.site.register(Season)
admin.site.register(Team)
admin.site.register(Match)
admin.site.register(Shot)
