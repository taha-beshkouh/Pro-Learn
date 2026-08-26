from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_project_definition_integrity_triggers"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="projecttasktemplate",
            name="projects_work_item_scope_position_unique",
        ),
        migrations.AddConstraint(
            model_name="projecttasktemplate",
            constraint=models.UniqueConstraint(
                fields=(
                    "project_version",
                    "sprint_template",
                    "role",
                    "technology_stack",
                    "position",
                ),
                name="projects_work_item_scope_position_unique",
                nulls_distinct=False,
            ),
        ),
    ]
