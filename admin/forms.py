from django import forms

from core.models import Competition, Match, Player, Season, Stadium, Team


class MaterializeFormMixin:
    def _apply_materialize_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} browser-default".strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_materialize_classes()


class TeamForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "country", "logo", "home_stadium"]


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


class MatchForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Match
        fields = ["match_id", "season", "home_team", "away_team", "match_date", "status"]
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


class StadiumForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Stadium
        fields = ["name", "city", "country", "capacity"]


class CompetitionForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Competition
        fields = ["name", "code", "logo", "is_league", "format", "country"]


class SeasonForm(MaterializeFormMixin, forms.ModelForm):
    class Meta:
        model = Season
        fields = ["competition", "name", "slug", "is_league"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["competition"].queryset = Competition.objects.order_by("name")
