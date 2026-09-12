from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0009_remove_designated_submitter_authority"),
        ("profiles", "0004_userprofile_github_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectrun",
            name="repository_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
