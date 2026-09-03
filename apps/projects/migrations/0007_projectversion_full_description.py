from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0006_populate_helpdesk_l1_canonical_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectversion",
            name="full_description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
