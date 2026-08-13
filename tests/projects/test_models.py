import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

from apps.projects.models import (
    Level,
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTaskTemplate,
    ProjectTemplate,
    ProjectVersion,
    StackPolicy,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def test_known_catalog_is_seeded_without_inventing_unresolved_versions():
    assert list(Level.objects.values_list("number", "name")) == [
        (1, "Level 1"),
        (2, "Level 2"),
        (3, "Level 3"),
    ]
    assert set(ProjectTemplate.objects.values_list("slug", flat=True)) == {
        "helpdesk-lite",
        "healthchecks-lite",
        "event-ticketing-lite",
    }
    assert ProjectVersion.objects.count() == 1
    assert ProjectVersion.objects.get().project_template.slug == "helpdesk-lite"


def test_external_catalog_entities_use_uuid_primary_keys(helpdesk_template, helpdesk_version):
    assert isinstance(helpdesk_template.id, uuid.UUID)
    assert isinstance(helpdesk_version.id, uuid.UUID)


def test_helpdesk_known_version_data_is_seeded(helpdesk_version):
    assert helpdesk_version.duration_weeks == 6
    assert helpdesk_version.sprint_count == 6
    assert helpdesk_version.weekly_effort_hours_min == 10
    assert helpdesk_version.weekly_effort_hours_max == 12
    assert helpdesk_version.participant_database == "MySQL 8 / InnoDB"
    assert helpdesk_version.is_published is True
    assert helpdesk_version.work_items.count() == 16


def test_helpdesk_role_stack_policies_are_seeded(helpdesk_version):
    requirements = {
        item.role.code: item
        for item in helpdesk_version.role_requirements.select_related("role")
    }
    assert requirements["BACKEND_DEVELOPER"].stack_policy == StackPolicy.ALLOWLIST
    assert requirements["BACKEND_DEVELOPER"].allowed_stacks.count() == 2
    assert requirements["FRONTEND_DEVELOPER"].stack_policy == StackPolicy.FIXED
    assert requirements["FRONTEND_DEVELOPER"].allowed_stacks.count() == 1
    assert requirements["PRODUCT_DESIGNER"].requires_stack is False
    assert requirements["PRODUCT_DESIGNER"].stack_policy is None


def test_level_database_constraint_rejects_unknown_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Level.objects.create(number=4, name="Level 4")


def test_version_effort_range_database_constraint(helpdesk_template):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectVersion.objects.create(
            project_template=helpdesk_template,
            version_number=2,
            weekly_effort_hours_min=12,
            weekly_effort_hours_max=10,
        )


def test_requirement_policy_database_constraint(helpdesk_version, backend_role):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectRoleRequirement.objects.create(
            project_version=version,
            role=backend_role,
            requires_stack=False,
            stack_policy=StackPolicy.OPEN,
        )


def test_work_item_stack_requires_role(helpdesk_version, django_stack):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            role=None,
            technology_stack=django_stack,
            position=100,
            title="Invalid stack-scoped shared item",
        )


def test_definition_foreign_keys_have_deliberate_protection(
    helpdesk_version, django_stack
):
    allowance = ProjectRoleAllowedStack.objects.filter(
        role_requirement__project_version=helpdesk_version,
        technology_stack=django_stack,
    ).first()
    assert allowance is not None
    with pytest.raises(ProtectedError):
        django_stack.delete()
    with pytest.raises(ProtectedError):
        helpdesk_version.project_template.delete()


def set_stack_policy_constraints_immediate():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "projects_role_requirement_stack_policy_constraint, "
            "projects_allowed_stack_policy_constraint IMMEDIATE"
        )


def test_fixed_policy_cardinality_is_enforced_by_database(
    helpdesk_version, backend_role
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectRoleRequirement.objects.create(
            project_version=version,
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.FIXED,
        )
        set_stack_policy_constraints_immediate()


def test_allowlist_requires_an_allowed_stack_in_database(
    helpdesk_version, backend_role
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectRoleRequirement.objects.create(
            project_version=version,
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.ALLOWLIST,
        )
        set_stack_policy_constraints_immediate()


def test_open_policy_rejects_configured_stacks_in_database(
    helpdesk_version, backend_role, django_stack
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        requirement = ProjectRoleRequirement.objects.create(
            project_version=version,
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.OPEN,
        )
        ProjectRoleAllowedStack.objects.create(
            role_requirement=requirement,
            technology_stack=django_stack,
        )
        set_stack_policy_constraints_immediate()


def test_stackless_role_rejects_configured_stacks_in_database(
    helpdesk_version, designer_role, django_stack
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        requirement = ProjectRoleRequirement.objects.create(
            project_version=version,
            role=designer_role,
            requires_stack=False,
            stack_policy=None,
        )
        ProjectRoleAllowedStack.objects.create(
            role_requirement=requirement,
            technology_stack=django_stack,
        )
        set_stack_policy_constraints_immediate()


def test_valid_stack_policy_paths_satisfy_database_constraints(
    helpdesk_version, backend_role, designer_role, django_stack
):
    template = helpdesk_version.project_template

    with transaction.atomic():
        fixed = ProjectRoleRequirement.objects.create(
            project_version=ProjectVersion.objects.create(
                project_template=template,
                version_number=2,
            ),
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.FIXED,
        )
        ProjectRoleAllowedStack.objects.create(
            role_requirement=fixed,
            technology_stack=django_stack,
        )

        allowlist = ProjectRoleRequirement.objects.create(
            project_version=ProjectVersion.objects.create(
                project_template=template,
                version_number=3,
            ),
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.ALLOWLIST,
        )
        ProjectRoleAllowedStack.objects.create(
            role_requirement=allowlist,
            technology_stack=django_stack,
        )

        ProjectRoleRequirement.objects.create(
            project_version=ProjectVersion.objects.create(
                project_template=template,
                version_number=4,
            ),
            role=backend_role,
            requires_stack=True,
            stack_policy=StackPolicy.OPEN,
        )
        ProjectRoleRequirement.objects.create(
            project_version=ProjectVersion.objects.create(
                project_template=template,
                version_number=5,
            ),
            role=designer_role,
            requires_stack=False,
            stack_policy=None,
        )

        set_stack_policy_constraints_immediate()
