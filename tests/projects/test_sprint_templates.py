import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

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
