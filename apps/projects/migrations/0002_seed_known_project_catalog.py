from django.db import migrations
from django.utils import timezone


LEVELS = (
    (1, "Level 1"),
    (2, "Level 2"),
    (3, "Level 3"),
)

PROJECTS = (
    ("helpdesk-lite", "Helpdesk Lite", 1),
    ("healthchecks-lite", "Healthchecks Lite", 2),
    ("event-ticketing-lite", "Event Ticketing Lite", 3),
)

HELPDESK_WORK_ITEMS = (
    "Authentication",
    "Ticket functionality",
    "Ticket claim",
    "Ticket status and priority",
    "Categories",
    "Comments",
    "History",
    "Search and filtering",
    "Pagination",
    "Validation",
    "Permission enforcement",
    "Swagger / OpenAPI",
    "Backend tests",
    "Responsive frontend",
    "README",
    "Deployment",
)


def seed_known_project_catalog(apps, schema_editor):
    Level = apps.get_model("projects", "Level")
    ProjectTemplate = apps.get_model("projects", "ProjectTemplate")
    ProjectVersion = apps.get_model("projects", "ProjectVersion")
    ProjectRoleRequirement = apps.get_model("projects", "ProjectRoleRequirement")
    ProjectRoleAllowedStack = apps.get_model("projects", "ProjectRoleAllowedStack")
    ProjectTaskTemplate = apps.get_model("projects", "ProjectTaskTemplate")
    Role = apps.get_model("profiles", "Role")
    TechnologyStack = apps.get_model("profiles", "TechnologyStack")

    levels = {}
    for number, name in LEVELS:
        levels[number], _ = Level.objects.update_or_create(
            number=number,
            defaults={"name": name},
        )

    templates = {}
    for slug, name, level_number in PROJECTS:
        templates[slug], _ = ProjectTemplate.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "level": levels[level_number]},
        )

    helpdesk_version, _ = ProjectVersion.objects.update_or_create(
        project_template=templates["helpdesk-lite"],
        version_number=1,
        defaults={
            "duration_weeks": 6,
            "sprint_count": 6,
            "weekly_effort_hours_min": 10,
            "weekly_effort_hours_max": 12,
            "participant_database": "MySQL 8 / InnoDB",
            "published_at": timezone.now(),
        },
    )

    roles = {role.code: role for role in Role.objects.all()}
    stacks = {stack.code: stack for stack in TechnologyStack.objects.all()}
    requirement_specs = (
        ("BACKEND_DEVELOPER", True, "ALLOWLIST"),
        ("FRONTEND_DEVELOPER", True, "FIXED"),
        ("PRODUCT_DESIGNER", False, None),
    )
    requirements = {}
    for role_code, requires_stack, stack_policy in requirement_specs:
        requirements[role_code], _ = ProjectRoleRequirement.objects.update_or_create(
            project_version=helpdesk_version,
            role=roles[role_code],
            defaults={
                "requires_stack": requires_stack,
                "stack_policy": stack_policy,
            },
        )

    for stack_code in ("django-drf", "aspnet-core-ef-core"):
        ProjectRoleAllowedStack.objects.get_or_create(
            role_requirement=requirements["BACKEND_DEVELOPER"],
            technology_stack=stacks[stack_code],
        )
    ProjectRoleAllowedStack.objects.get_or_create(
        role_requirement=requirements["FRONTEND_DEVELOPER"],
        technology_stack=stacks["react-typescript-vite"],
    )

    for position, title in enumerate(HELPDESK_WORK_ITEMS, start=1):
        ProjectTaskTemplate.objects.update_or_create(
            project_version=helpdesk_version,
            role=None,
            technology_stack=None,
            position=position,
            defaults={"title": title},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0002_seed_known_roles_and_stacks"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_known_project_catalog,
            reverse_code=migrations.RunPython.noop,
        )
    ]

