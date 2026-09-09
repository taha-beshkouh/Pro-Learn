from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.formations.models import (
    ProjectRun,
    ProjectRunState,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    Team,
)
from apps.formations.services import (
    complete_sprint,
    create_team_formation,
    mark_project_run_incomplete,
    mark_sprint_under_review,
    open_sprint,
    submit_sprint,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence", "id"))


def _complete_sprint(*, sprint_run, member, facilitator, now):
    open_sprint(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        now=now,
    )
    submit_sprint(
        sprint_run_id=sprint_run.id,
        user=member.user,
        now=now,
    )
    mark_sprint_under_review(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        now=now,
    )
    complete_sprint(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        now=now,
    )


def test_database_enforces_fixed_immutable_project_run_deadline(runtime_project_run):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectRun.objects.filter(id=runtime_project_run.id).update(
            deadline_at=runtime_project_run.deadline_at + timedelta(days=1)
        )


def test_database_rejects_initial_deadline_not_matching_version_duration(
    facilitator,
    helpdesk_version,
    proposed_members,
):
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in proposed_members],
    )
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        team = Team.objects.create(formation=formation)
        ProjectRun.objects.create(
            team=team,
            project_version=helpdesk_version,
            started_at=started_at,
            deadline_at=started_at + timedelta(days=1),
        )


def test_database_rejects_incomplete_before_deadline(runtime_project_run):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectRun.objects.filter(id=runtime_project_run.id).update(
            state=ProjectRunState.INCOMPLETE,
            ended_at=runtime_project_run.deadline_at - timedelta(microseconds=1),
        )


def test_database_submission_trigger_rejects_overdue_history(
    overdue_runtime_project_run,
    overdue_runtime_members,
    facilitator,
):
    first = _ordered_sprints(overdue_runtime_project_run)[0]
    backend = overdue_runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.create(
            sprint_run=first,
            submitted_by=backend,
            submitted_at=timezone.now(),
        )


def test_database_requires_final_sprint_and_run_completion_in_same_transaction(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, final = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    now = timezone.now()
    _complete_sprint(
        sprint_run=first,
        member=backend,
        facilitator=facilitator,
        now=now,
    )
    _complete_sprint(
        sprint_run=second,
        member=backend,
        facilitator=facilitator,
        now=now,
    )
    open_sprint(
        sprint_run_id=final.id,
        actor=facilitator,
        now=now,
    )
    submit_sprint(sprint_run_id=final.id, user=backend.user, now=now)
    mark_sprint_under_review(
        sprint_run_id=final.id,
        actor=facilitator,
        now=now,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=final.id).update(
            state=SprintRunState.COMPLETED,
            completed_at=now,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SET CONSTRAINTS "
                "formations_final_sprint_completion_constraint IMMEDIATE"
            )


def test_database_blocks_sprint_state_changes_after_terminal_run(
    overdue_runtime_project_run,
    overdue_runtime_members,
    facilitator,
):
    first = _ordered_sprints(overdue_runtime_project_run)[0]
    backend = overdue_runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        actor=facilitator,
    )
    mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(state=SprintRunState.SUBMITTED)


def test_database_preserves_sprint_history_after_terminal_run(
    overdue_runtime_project_run,
    facilitator,
):
    first = _ordered_sprints(overdue_runtime_project_run)[0]
    mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=first.id).delete()
