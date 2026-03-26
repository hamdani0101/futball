from django import forms

from core.models import Competition, Match, MatchTeamStats, Player, Season, Shot, Stadium, Team


class MaterializeFormMixin:
    def _apply_materialize_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{existing} admin-checkbox".strip()
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs["class"] = f"{existing} admin-select browser-default".strip()
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"{existing} admin-file-input".strip()
            else:
                widget.attrs["class"] = f"{existing} admin-input".strip()
                widget.attrs.setdefault("placeholder", field.label)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_materialize_classes()


class TeamForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Team
        fields = ["external_id", "name", "country", "logo", "home_stadium"]


class PlayerForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Player
        fields = [
            "external_id",
            "name",
            "team_now",
            "position",
            "country",
            "birth_date",
            "photo",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["external_id"].required = False
        self.fields["external_id"].help_text = "Optional. Leave blank for manually created players."


class MatchForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Match
        fields = ["external_id", "season", "home_team", "away_team", "match_date", "status"]
        widgets = {
            "match_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["season"].queryset = Season.objects.select_related("competition").order_by(
            "competition__name", "name"
        )

    def clean(self):
        cleaned_data = super().clean()
        home_team = cleaned_data.get("home_team")
        away_team = cleaned_data.get("away_team")
        if home_team and away_team and home_team == away_team:
            raise forms.ValidationError("Home team and away team must be different.")
        return cleaned_data


class MatchTeamStatsForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = MatchTeamStats
        fields = ["match", "team", "goals", "xg", "shots", "shots_on_target"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["match"].queryset = Match.objects.select_related(
            "home_team", "away_team"
        ).order_by("-match_date")
        self.fields["team"].queryset = Team.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        match = cleaned_data.get("match")
        team = cleaned_data.get("team")
        shots = cleaned_data.get("shots")
        shots_on_target = cleaned_data.get("shots_on_target")
        if match and team and team.id not in [match.home_team_id, match.away_team_id]:
            raise forms.ValidationError("Team must belong to the selected match.")
        if shots is not None and shots_on_target is not None and shots_on_target > shots:
            raise forms.ValidationError("Shots on target cannot exceed total shots.")
        return cleaned_data


class ShotForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Shot
        fields = [
            "external_event_id",
            "match",
            "team",
            "player",
            "minute",
            "second",
            "x",
            "y",
            "xg",
            "outcome",
            "body_part",
            "shot_type",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["external_event_id"].required = False
        self.fields["external_event_id"].help_text = "Optional external reference."
        self.fields["match"].queryset = Match.objects.select_related(
            "home_team", "away_team"
        ).order_by("-match_date")
        self.fields["team"].queryset = Team.objects.order_by("name")
        self.fields["player"].queryset = Player.objects.select_related("team_now").order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        match = cleaned_data.get("match")
        team = cleaned_data.get("team")
        player = cleaned_data.get("player")
        minute = cleaned_data.get("minute")
        second = cleaned_data.get("second")
        if match and team and team.id not in [match.home_team_id, match.away_team_id]:
            raise forms.ValidationError("Shot team must belong to the selected match.")
        if player and team and player.team_now_id != team.id:
            raise forms.ValidationError("Player must belong to the selected team.")
        if minute is not None and minute < 0:
            raise forms.ValidationError("Minute cannot be negative.")
        if second is not None and not 0 <= second <= 59:
            raise forms.ValidationError("Second must be between 0 and 59.")
        return cleaned_data


class StadiumForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Stadium
        fields = ["name", "city", "country", "capacity"]


class CompetitionForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Competition
        fields = [
            "name",
            "code",
            "country",
            "gender",
            "is_league",
            "format",
            "external_id",
            "logo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["format"].queryset = self.fields["format"].queryset.order_by("name")
        self.fields["external_id"].required = False
        self.fields["external_id"].help_text = (
            "Optional. Leave blank for competitions created directly in this admin."
        )
        self.fields["code"].help_text = "Short code such as EPL, UCL, or WC."
        self.fields["country"].help_text = "Optional for international competitions."
        self.fields["logo"].help_text = "Square logo works best in the admin cards."


class SeasonForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Season
        fields = ["competition", "name", "slug"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["competition"].queryset = Competition.objects.order_by("name")
