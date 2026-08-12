from django.db import migrations


KNOWN_ROLES = (
    ("BACKEND_DEVELOPER", "Backend Developer"),
    ("FRONTEND_DEVELOPER", "Frontend Developer"),
    ("PRODUCT_DESIGNER", "Product Designer"),
)

KNOWN_STACKS = (
    ("django-drf", "Django + Django REST Framework"),
    ("aspnet-core-ef-core", "ASP.NET Core Web API + Entity Framework Core"),
    ("react-typescript-vite", "React + TypeScript + Vite + React Router"),
)


def seed_known_roles_stacks_and_profiles(apps, schema_editor):
    Role = apps.get_model("profiles", "Role")
    TechnologyStack = apps.get_model("profiles", "TechnologyStack")
    UserProfile = apps.get_model("profiles", "UserProfile")
    User = apps.get_model("accounts", "User")

    for code, name in KNOWN_ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name})

    for code, name in KNOWN_STACKS:
        TechnologyStack.objects.update_or_create(code=code, defaults={"name": name})

    for user_id in User.objects.values_list("id", flat=True).iterator():
        UserProfile.objects.get_or_create(user_id=user_id)


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_known_roles_stacks_and_profiles,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

