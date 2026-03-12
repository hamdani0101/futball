from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("futball", "0007_stadium_alter_competition_format_team_home_stadium"),
    ]

    operations = [
        migrations.AddField(
            model_name="shot",
            name="external_event_id",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
