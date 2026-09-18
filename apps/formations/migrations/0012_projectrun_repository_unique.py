from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("formations", "0011_allow_submitted_sprint_replacement")]

    operations = [
        migrations.AddConstraint(
            model_name="projectrun",
            constraint=models.UniqueConstraint(
                fields=("repository_url",),
                condition=models.Q(repository_url__isnull=False),
                name="formations_run_repository_unique",
            ),
        ),
    ]
