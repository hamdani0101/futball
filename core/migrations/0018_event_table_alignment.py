from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_rename_stage_match_stage_name_match_stage_id_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_event_id", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("period", models.PositiveIntegerField(default=1)),
                ("minute", models.PositiveIntegerField(default=0)),
                ("second", models.PositiveIntegerField(default=0)),
                ("event_index", models.PositiveIntegerField(default=0)),
                ("possession", models.PositiveIntegerField(default=0)),
                ("timestamp", models.TimeField(blank=True, null=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("shot", "Shot"),
                            ("pass", "Pass"),
                            ("foul", "Foul"),
                            ("card", "Card"),
                            ("substitution", "Substitution"),
                            ("duel", "Duel"),
                            ("recovery", "Recovery"),
                            ("clearance", "Clearance"),
                        ],
                        max_length=20,
                    ),
                ),
                ("play_pattern", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="core.match")),
                ("player", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="core.player")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="core.team")),
            ],
            options={
                "ordering": ["match", "period", "minute", "second", "event_index", "id"],
            },
        ),
        migrations.AddField(
            model_name="pass",
            name="event",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pass_detail", to="core.event"),
        ),
        migrations.AddField(
            model_name="shot",
            name="event",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="shot_detail", to="core.event"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["match"], name="core_event_match_i_2a7f2f_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["match", "event_index"], name="core_event_match_i_36adca_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["minute", "second"], name="core_event_minute__7ac85c_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["period"], name="core_event_period_0ee0e2_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["type"], name="core_event_type_b221e4_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["team"], name="core_event_team_id_f3f48c_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["player"], name="core_event_player__33957a_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["possession"], name="core_event_possess_054ca1_idx"),
        ),
    ]
