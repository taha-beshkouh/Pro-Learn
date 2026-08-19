from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.formations.services import ProposedMember, create_team_formation
from apps.profiles.models import (
    Role,
    RoleCode,
    RoleTechnologyStack,
    TechnologyStack,
    UserProfile,
)
from apps.projects.models import (
    Level,
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTemplate,
    ProjectVersion,
    StackPolicy,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def csrf_client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def password():
    return "A-Strong-Password-739!"


@pytest.fixture
def facilitator(django_user_model, password):
    return django_user_model.objects.create_user(
        email="facilitator@example.com",
        password=password,
        is_staff=True,
    )


def create_member(django_user_model, *, email, password, role):
    user = django_user_model.objects.create_user(email=email, password=password)
    UserProfile.objects.create(user=user, selected_role=role)
    return user


@pytest.fixture
@transaction.atomic
def formation_catalog():
    """Build the complete, minimal catalog required by formation tests.

    Formation tests must not depend on data migrations having populated a reused
    or migration-disabled test database. Production seed migrations are tested
    separately by the projects app.
    """
    role_specs = {
        RoleCode.BACKEND_DEVELOPER: "Backend Developer",
        RoleCode.FRONTEND_DEVELOPER: "Frontend Developer",
        RoleCode.PRODUCT_DESIGNER: "Product Designer",
    }
    roles = {
        code: Role.objects.update_or_create(code=code, defaults={"name": name})[0]
        for code, name in role_specs.items()
    }

    stack_specs = {
        "django-drf": "Django + Django REST Framework",
        "aspnet-core-ef-core": (
            "ASP.NET Core Web API + Entity Framework Core"
        ),
        "react-typescript-vite": (
            "React + TypeScript + Vite + React Router"
        ),
    }
    stacks = {
        code: TechnologyStack.objects.update_or_create(
            code=code,
            defaults={"name": name},
        )[0]
        for code, name in stack_specs.items()
    }

    role_stack_specs = (
        (RoleCode.BACKEND_DEVELOPER, "django-drf"),
        (RoleCode.BACKEND_DEVELOPER, "aspnet-core-ef-core"),
        (RoleCode.FRONTEND_DEVELOPER, "react-typescript-vite"),
    )
    for role_code, stack_code in role_stack_specs:
        RoleTechnologyStack.objects.get_or_create(
            role=roles[role_code],
            technology_stack=stacks[stack_code],
        )

    level = Level.objects.update_or_create(
        number=1,
        defaults={"name": "Level 1"},
    )[0]
    project_template = ProjectTemplate.objects.update_or_create(
        slug="helpdesk-lite",
        defaults={"name": "Helpdesk Lite", "level": level},
    )[0]
    project_version = ProjectVersion.objects.update_or_create(
        project_template=project_template,
        version_number=1,
        defaults={
            "duration_weeks": 6,
            "sprint_count": 6,
            "weekly_effort_hours_min": 10,
            "weekly_effort_hours_max": 12,
            "participant_database": "MySQL 8 / InnoDB",
            "published_at": timezone.now(),
        },
    )[0]

    requirement_specs = {
        RoleCode.BACKEND_DEVELOPER: (True, StackPolicy.ALLOWLIST),
        RoleCode.FRONTEND_DEVELOPER: (True, StackPolicy.FIXED),
        RoleCode.PRODUCT_DESIGNER: (False, None),
    }
    requirements = {}
    for role_code, (requires_stack, stack_policy) in requirement_specs.items():
        requirements[role_code] = ProjectRoleRequirement.objects.update_or_create(
            project_version=project_version,
            role=roles[role_code],
            defaults={
                "requires_stack": requires_stack,
                "stack_policy": stack_policy,
            },
        )[0]

    for stack_code in ("django-drf", "aspnet-core-ef-core"):
        ProjectRoleAllowedStack.objects.get_or_create(
            role_requirement=requirements[RoleCode.BACKEND_DEVELOPER],
            technology_stack=stacks[stack_code],
        )
    ProjectRoleAllowedStack.objects.get_or_create(
        role_requirement=requirements[RoleCode.FRONTEND_DEVELOPER],
        technology_stack=stacks["react-typescript-vite"],
    )

    return {
        "roles": roles,
        "stacks": stacks,
        "level": level,
        "project_template": project_template,
        "project_version": project_version,
        "requirements": requirements,
    }


@pytest.fixture
def backend_role(formation_catalog):
    return formation_catalog["roles"][RoleCode.BACKEND_DEVELOPER]


@pytest.fixture
def frontend_role(formation_catalog):
    return formation_catalog["roles"][RoleCode.FRONTEND_DEVELOPER]


@pytest.fixture
def designer_role(formation_catalog):
    return formation_catalog["roles"][RoleCode.PRODUCT_DESIGNER]


@pytest.fixture
def django_stack(formation_catalog):
    return formation_catalog["stacks"]["django-drf"]


@pytest.fixture
def react_stack(formation_catalog):
    return formation_catalog["stacks"]["react-typescript-vite"]


@pytest.fixture
def backend_user(django_user_model, password, backend_role):
    return create_member(
        django_user_model,
        email="backend@example.com",
        password=password,
        role=backend_role,
    )


@pytest.fixture
def frontend_user(django_user_model, password, frontend_role):
    return create_member(
        django_user_model,
        email="frontend@example.com",
        password=password,
        role=frontend_role,
    )


@pytest.fixture
def designer_user(django_user_model, password, designer_role):
    return create_member(
        django_user_model,
        email="designer@example.com",
        password=password,
        role=designer_role,
    )


@pytest.fixture
def replacement_backend_user(django_user_model, password, backend_role):
    return create_member(
        django_user_model,
        email="replacement-backend@example.com",
        password=password,
        role=backend_role,
    )


@pytest.fixture
def helpdesk_version(formation_catalog):
    return formation_catalog["project_version"]


@pytest.fixture
def proposed_members(
    backend_user,
    frontend_user,
    designer_user,
    backend_role,
    frontend_role,
    designer_role,
    django_stack,
):
    return [
        ProposedMember(backend_user, backend_role, django_stack),
        ProposedMember(frontend_user, frontend_role, None),
        ProposedMember(designer_user, designer_role, None),
    ]


@pytest.fixture
def formation(facilitator, helpdesk_version, proposed_members):
    return create_team_formation(
        project_version=helpdesk_version,
        created_by=facilitator,
        members=proposed_members,
        now=timezone.now() - timedelta(hours=1),
    )
