import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

from apps.profiles.models import TechnologyStack
from apps.projects.models import ProjectTaskTemplate, ProjectVersion, SprintTemplate


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def make_sprint(version, *, sequence=1, start=0, duration=5, title="Sprint"):
    return SprintTemplate.objects.create(
        project_version=version,
        sequence=sequence,
        title=title,
        planned_start_offset_days=start,
        planned_duration_days=duration,
    )


def test_sprint_template_uses_uuid_and_relative_schedule(helpdesk_version):
    sprint = make_sprint(helpdesk_version)

    assert isinstance(sprint.id, uuid.UUID)
    assert sprint.planned_start_offset_days == 0
    assert sprint.planned_duration_days == 5
    assert sprint.planned_end_offset_days == 5


def test_sprint_sequence_is_unique_per_project_version(helpdesk_version):
    make_sprint(helpdesk_version, sequence=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_sprint(helpdesk_version, sequence=1, start=5)


def test_sprint_duration_database_constraint_rejects_zero(helpdesk_version):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_sprint(helpdesk_version, duration=0)


def test_same_sprint_sequence_is_allowed_in_different_versions(
    helpdesk_version,
):
    second_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )

    make_sprint(helpdesk_version, sequence=1)
    make_sprint(second_version, sequence=1)

    assert SprintTemplate.objects.filter(sequence=1).count() == 2


def test_work_content_can_be_scheduled_or_unscheduled(helpdesk_version):
    sprint = make_sprint(helpdesk_version)
    scheduled = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="Scheduled static work",
        position=100,
    )
    unscheduled = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        title="Unscheduled static work",
        position=101,
    )

    assert scheduled.sprint_template == sprint
    assert unscheduled.sprint_template is None


def test_duplicate_shared_position_in_same_sprint_is_rejected(helpdesk_version):
    sprint = make_sprint(helpdesk_version)
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="First shared Sprint item",
        position=200,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            sprint_template=sprint,
            title="Duplicate shared Sprint item",
            position=200,
        )


def test_duplicate_unscheduled_position_in_same_scope_is_rejected(helpdesk_version):
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        title="First unscheduled shared item",
        position=201,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            title="Duplicate unscheduled shared item",
            position=201,
        )


def test_same_scope_position_is_allowed_in_different_sprints(
    helpdesk_version,
    backend_role,
):
    first_sprint = make_sprint(helpdesk_version, sequence=1)
    second_sprint = make_sprint(helpdesk_version, sequence=2, start=5)

    first = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=first_sprint,
        role=backend_role,
        title="First Sprint backend item",
        position=202,
    )
    second = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=second_sprint,
        role=backend_role,
        title="Second Sprint backend item",
        position=202,
    )

    assert first.sprint_template_id != second.sprint_template_id


def test_duplicate_role_stack_position_in_same_sprint_is_rejected(
    helpdesk_version,
    backend_role,
    django_stack,
):
    sprint = make_sprint(helpdesk_version)
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        technology_stack=django_stack,
        title="First Django backend item",
        position=203,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            sprint_template=sprint,
            role=backend_role,
            technology_stack=django_stack,
            title="Duplicate Django backend item",
            position=203,
        )


def test_different_roles_in_same_sprint_may_reuse_position(
    helpdesk_version,
    backend_role,
    frontend_role,
):
    sprint = make_sprint(helpdesk_version)

    backend_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        title="Backend item",
        position=204,
    )
    frontend_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=frontend_role,
        title="Frontend item",
        position=204,
    )

    assert backend_item.role_id != frontend_item.role_id


def test_shared_and_role_item_in_same_sprint_may_reuse_position(
    helpdesk_version,
    backend_role,
):
    sprint = make_sprint(helpdesk_version)

    shared_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="Shared item",
        position=205,
    )
    backend_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        title="Backend item",
        position=205,
    )

    assert shared_item.role_id is None
    assert backend_item.role_id == backend_role.id


def test_same_role_with_different_stacks_in_same_sprint_may_reuse_position(
    helpdesk_version,
    backend_role,
    django_stack,
):
    aspnet_stack = TechnologyStack.objects.get(code="aspnet-core-ef-core")
    sprint = make_sprint(helpdesk_version)

    django_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        technology_stack=django_stack,
        title="Django backend item",
        position=206,
    )
    aspnet_item = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        technology_stack=aspnet_stack,
        title="ASP.NET backend item",
        position=206,
    )

    assert django_item.technology_stack_id != aspnet_item.technology_stack_id


def test_scheduled_and_unscheduled_items_may_reuse_scope_position(
    helpdesk_version,
    backend_role,
):
    sprint = make_sprint(helpdesk_version)

    scheduled = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        role=backend_role,
        title="Scheduled backend item",
        position=207,
    )
    unscheduled = ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        role=backend_role,
        title="Unscheduled backend item",
        position=207,
    )

    assert scheduled.sprint_template_id == sprint.id
    assert unscheduled.sprint_template_id is None


def test_sprint_cannot_be_deleted_while_static_work_references_it(helpdesk_version):
    sprint = make_sprint(helpdesk_version)
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="Protected static work",
        position=100,
    )

    with pytest.raises(ProtectedError):
        sprint.delete()


def test_cross_version_work_assignment_fails_model_validation(helpdesk_version):
    second_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    sprint = make_sprint(second_version)
    work_item = ProjectTaskTemplate(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="Invalid cross-version work",
        position=100,
    )

    with pytest.raises(ValidationError):
        work_item.full_clean()


def set_work_item_version_constraints_immediate():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "projects_work_item_sprint_version_constraint, "
            "projects_sprint_work_item_version_constraint IMMEDIATE"
        )


def test_cross_version_work_assignment_is_rejected_by_database(helpdesk_version):
    second_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    sprint = make_sprint(second_version)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectTaskTemplate.objects.create(
            project_version=helpdesk_version,
            sprint_template=sprint,
            title="Invalid cross-version work",
            position=100,
        )
        set_work_item_version_constraints_immediate()


def test_moving_referenced_sprint_to_another_version_is_rejected_by_database(
    helpdesk_version,
):
    second_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=2,
    )
    sprint = make_sprint(helpdesk_version)
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        sprint_template=sprint,
        title="Version-bound work",
        position=100,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintTemplate.objects.filter(id=sprint.id).update(
            project_version=second_version
        )
        set_work_item_version_constraints_immediate()


def test_helpdesk_sprint_distribution_is_not_seeded(helpdesk_version):
    assert helpdesk_version.sprint_templates.count() == 0
