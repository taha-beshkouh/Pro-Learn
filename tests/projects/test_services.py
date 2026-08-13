import pytest
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.profiles.models import TechnologyStack, UserSkill
from apps.projects.exceptions import ProjectConfigurationError
from apps.projects.models import ProjectRoleRequirement, ProjectVersion, StackPolicy
from apps.projects.services import (
    resolve_compatible_stacks,
    validate_role_requirement_configuration,
)


pytestmark = pytest.mark.django_db


def requirement_for(version, role_code):
    return version.role_requirements.prefetch_related(
        "allowed_stacks__technology_stack"
    ).get(role__code=role_code)


def test_allowlist_returns_all_configured_stacks_without_auto_selection(helpdesk_version):
    requirement = requirement_for(helpdesk_version, "BACKEND_DEVELOPER")

    result = resolve_compatible_stacks(requirement=requirement)

    assert {stack.code for stack in result.compatible_stacks} == {
        "django-drf",
        "aspnet-core-ef-core",
    }
    assert result.auto_selected_stack is None


def test_fixed_policy_auto_selects_the_only_stack(helpdesk_version):
    requirement = requirement_for(helpdesk_version, "FRONTEND_DEVELOPER")

    result = resolve_compatible_stacks(requirement=requirement)

    assert [stack.code for stack in result.compatible_stacks] == [
        "react-typescript-vite"
    ]
    assert result.auto_selected_stack.code == "react-typescript-vite"


def test_stackless_role_has_no_fake_stack(helpdesk_version):
    requirement = requirement_for(helpdesk_version, "PRODUCT_DESIGNER")

    result = resolve_compatible_stacks(requirement=requirement)

    assert result.compatible_stacks == ()
    assert result.auto_selected_stack is None


def test_open_policy_uses_only_registered_user_skills(
    helpdesk_version, backend_role, profile, django_stack, react_stack
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    requirement = ProjectRoleRequirement.objects.create(
        project_version=version,
        role=backend_role,
        requires_stack=True,
        stack_policy=StackPolicy.OPEN,
    )
    UserSkill.objects.create(profile=profile, technology_stack=django_stack)
    UserSkill.objects.create(profile=profile, technology_stack=react_stack)
    profile = type(profile).objects.prefetch_related(
        "skills__technology_stack"
    ).get(id=profile.id)

    result = resolve_compatible_stacks(requirement=requirement, profile=profile)

    assert [stack.code for stack in result.compatible_stacks] == ["django-drf"]
    assert result.auto_selected_stack == django_stack


def test_invalid_fixed_configuration_is_rejected(
    helpdesk_version, backend_role
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    with transaction.atomic():
        requirement = ProjectRoleRequirement.objects.create(
            project_version=version,
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.FIXED,
        )

        with pytest.raises(ValidationError):
            validate_role_requirement_configuration(requirement=requirement)
        with pytest.raises(ProjectConfigurationError):
            resolve_compatible_stacks(requirement=requirement)
        transaction.set_rollback(True)
