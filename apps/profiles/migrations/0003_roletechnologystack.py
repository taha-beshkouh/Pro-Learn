import uuid

import django.db.models.deletion
from django.db import migrations, models


KNOWN_ROLE_STACKS = (
    ("BACKEND_DEVELOPER", "django-drf"),
    ("BACKEND_DEVELOPER", "aspnet-core-ef-core"),
    ("FRONTEND_DEVELOPER", "react-typescript-vite"),
)


def seed_known_role_stack_compatibility(apps, schema_editor):
    Role = apps.get_model("profiles", "Role")
    RoleTechnologyStack = apps.get_model("profiles", "RoleTechnologyStack")
    TechnologyStack = apps.get_model("profiles", "TechnologyStack")

    roles = {role.code: role for role in Role.objects.all()}
    stacks = {stack.code: stack for stack in TechnologyStack.objects.all()}
    for role_code, stack_code in KNOWN_ROLE_STACKS:
        RoleTechnologyStack.objects.get_or_create(
            role=roles[role_code],
            technology_stack=stacks[stack_code],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0002_seed_known_roles_and_stacks"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoleTechnologyStack",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compatible_stack_links",
                        to="profiles.role",
                    ),
                ),
                (
                    "technology_stack",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="compatible_role_links",
                        to="profiles.technologystack",
                    ),
                ),
            ],
            options={
                "ordering": ["technology_stack__name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("role", "technology_stack"),
                        name="profiles_role_stack_unique",
                    )
                ],
            },
        ),
        migrations.RunPython(
            seed_known_role_stack_compatibility,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

