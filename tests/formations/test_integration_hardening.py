import pytest
from django.db import IntegrityError, connection, transaction

from apps.formations.models import SprintRun
from apps.projects.models import ProjectVersion, SprintTemplate


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _force_sprint_set_validation():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "formations_sprint_run_set_sprint_constraint IMMEDIATE"
        )


def test_referenced_project_version_fields_are_immutable(
    runtime_project_run,
    helpdesk_version,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        helpdesk_version.summary = "Retrospectively changed scope"
        helpdesk_version.save(update_fields=["summary"])


def test_pending_formation_already_freezes_its_project_definition(
    formation,
    helpdesk_version,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        helpdesk_version.duration_weeks += 1
        helpdesk_version.save(update_fields=["duration_weeks"])


def test_referenced_project_version_cannot_gain_a_new_final_sprint(
    runtime_project_run,
    helpdesk_version,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        SprintTemplate.objects.create(
            project_version=helpdesk_version,
            sequence=4,
            title="Late final Sprint",
            planned_start_offset_days=21,
            planned_duration_days=5,
        )


def test_referenced_project_requirements_and_work_content_are_immutable(
    runtime_project_run,
    helpdesk_version,
):
    requirement = helpdesk_version.role_requirements.order_by("id").first()
    work_item = helpdesk_version.work_items.order_by("id").first()
    assert requirement is not None
    assert work_item is not None

    with pytest.raises(IntegrityError), transaction.atomic():
        requirement.context = "Changed requirement"
        requirement.save(update_fields=["context"])

    with pytest.raises(IntegrityError), transaction.atomic():
        work_item.title = "Changed historical workspace content"
        work_item.save(update_fields=["title"])


def test_unreferenced_project_version_remains_editable(
    helpdesk_version,
):
    version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=helpdesk_version.version_number + 1,
        duration_weeks=4,
    )
    version.summary = "Still being authored"
    version.save(update_fields=["summary"])
    sprint = SprintTemplate.objects.create(
        project_version=version,
        sequence=1,
        title="Draft Sprint",
        planned_start_offset_days=0,
        planned_duration_days=5,
    )

    version.refresh_from_db()
    assert version.summary == "Still being authored"
    assert sprint.project_version_id == version.id


def test_project_run_must_keep_runtime_for_every_fixed_sprint(
    runtime_project_run,
):
    first = runtime_project_run.sprint_runs.order_by(
        "sprint_template__sequence", "id"
    ).first()
    assert first is not None

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=first.id).delete()
        _force_sprint_set_validation()
