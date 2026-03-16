from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_rename_core_pass_match_i_eb66d7_idx_core_pass_match_i_ae4a12_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="match",
            name="match_id",
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name="pass",
            name="external_event_id",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="player",
            name="external_id",
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
