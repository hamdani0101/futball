# Consolidates in-progress model changes: event links, goal/save types,
# system-calculated xG default, and the Save detail table.

from django.db import migrations, models
import django.db.models.deletion


def _column_exists(schema_editor, table, column):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            [table, column],
        )
        return cursor.fetchone()[0] > 0


def _fk_exists(schema_editor, table, constraint):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "AND CONSTRAINT_NAME = %s",
            [table, constraint],
        )
        return cursor.fetchone()[0] > 0


def add_related_event_column(apps, schema_editor):
    # Online DDL: a plain ALTER copies the 1.2M-row core_event table, so use
    # INPLACE (instant for a nullable column). Idempotent for DBs where the
    # column was already added manually.
    if _column_exists(schema_editor, "core_event", "related_event_id"):
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE core_event ADD COLUMN related_event_id bigint NULL, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )


def add_related_event_fk(apps, schema_editor):
    constraint = "core_event_related_event_id_0d127df0_fk_core_event_id"
    if _fk_exists(schema_editor, "core_event", constraint):
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SET foreign_key_checks=OFF")
        try:
            cursor.execute(
                "ALTER TABLE core_event ADD CONSTRAINT "
                + constraint
                + " FOREIGN KEY (related_event_id) REFERENCES core_event (id), "
                "ALGORITHM=INPLACE"
            )
        finally:
            cursor.execute("SET foreign_key_checks=ON")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_remove_matchstate_core_matchs_status_8dba4c_idx_and_more"),
    ]

    operations = [
        # NOTE: online DDL via RunPython (ALGORITHM=INPLACE) because a default
        # ALTER copies the 1.2M-row core_event table. Idempotent: fresh DBs
        # (tests, new deploys) get the column; the existing DB is untouched.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="event",
                    name="related_event",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="related_events",
                        to="core.event",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_related_event_column,
                    reverse_code=migrations.RunPython.noop,
                ),
                migrations.RunPython(
                    add_related_event_fk,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
        ),
        migrations.AlterField(
            model_name="event",
            name="type",
            field=models.CharField(
                choices=[
                    ("shot", "Shot"),
                    ("pass", "Pass"),
                    ("foul", "Foul"),
                    ("card", "Card"),
                    ("substitution", "Substitution"),
                    ("duel", "Duel"),
                    ("goal", "Goal"),
                    ("save", "Save"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="shot",
            name="xg",
            field=models.FloatField(default=0.0),
        ),
        migrations.CreateModel(
            name="Save",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("minute", models.PositiveIntegerField()),
                ("second", models.PositiveIntegerField()),
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="save_detail",
                        to="core.event",
                    ),
                ),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="core.match"
                    ),
                ),
                (
                    "originating_shot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="saves",
                        to="core.shot",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="core.player"
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="core.team"
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["match", "minute", "second"],
                        name="core_save_match_i_969fcb_idx",
                    )
                ],
            },
        ),
    ]
