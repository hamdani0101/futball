from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_event_table_alignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="Substitution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("minute", models.PositiveIntegerField(default=0)),
                ("second", models.PositiveIntegerField(default=0)),
                ("period", models.PositiveIntegerField(default=1)),
                ("reason", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="substitution_detail", to="core.event")),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="substitutions", to="core.match")),
                ("player_in", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="substitutions_in", to="core.player")),
                ("player_out", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="substitutions_out", to="core.player")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="substitutions", to="core.team")),
            ],
            options={
                "ordering": ["minute", "second", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["match"], name="core_substi_match_i_6cafcb_idx"),
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["team"], name="core_substi_team_id_353dc7_idx"),
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["player_out"], name="core_substi_player__fb0f44_idx"),
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["player_in"], name="core_substi_player__3e620f_idx"),
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["period"], name="core_substi_period_250b15_idx"),
        ),
        migrations.AddIndex(
            model_name="substitution",
            index=models.Index(fields=["minute", "second"], name="core_substi_minute__732bd1_idx"),
        ),
    ]
