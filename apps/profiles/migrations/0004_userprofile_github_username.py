import apps.profiles.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0003_roletechnologystack"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="github_username",
            field=models.CharField(
                blank=True,
                max_length=apps.profiles.validators.GITHUB_USERNAME_MAX_LENGTH,
                null=True,
                validators=[apps.profiles.validators.validate_github_username],
            ),
        ),
    ]
