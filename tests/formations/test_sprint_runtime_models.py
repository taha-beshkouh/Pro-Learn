from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.formations.models import SprintRun, SprintRunState, SprintSubmission
from apps.formations.services import open_sprint, submit_sprint
from apps.projects.models import ProjectVersion, SprintTemplate


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence"))


def test_sprint_run_rejects_template_from_another_project_version(
    runtime_project_run,
    helpdesk_version,
):
    other_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=helpdesk_version.version_number + 1,
        sprint_count=1,
    )
    other_template = SprintTemplate.objects.create(
        project_version=other_version,
        sequence=1,
        title="Other Sprint",
        planned_start_offset_days=0,
        planned_duration_days=5,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.create(
            project_run=runtime_project_run,
            sprint_template=other_template,
            planned_start_at=runtime_project_run.started_at,
            planned_end_at=runtime_project_run.started_at + timedelta(days=5),
        )


def test_database_rejects_opening_a_later_sprint_first(
    runtime_project_run,
    runtime_members,
):
    _, second, _ = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=second.id).update(
            state=SprintRunState.ACTIVE,
            designated_submitter=backend,
            opened_at=timezone.now(),
        )


def test_database_rejects_invalid_state_transition(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(
            state=SprintRunState.COMPLETED,
            completed_at=timezone.now(),
        )


def test_database_rejects_submission_by_non_designated_member(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.create(
            sprint_run=first,
            submitted_by=frontend,
            evidence="Not allowed",
        )


def test_sprint_submission_history_is_database_append_only(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
    )
    _, submission = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Original evidence",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.filter(id=submission.id).update(evidence="Changed")
    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.filter(id=submission.id).delete()

