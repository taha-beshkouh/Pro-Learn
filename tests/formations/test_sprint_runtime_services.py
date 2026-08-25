from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.formations.exceptions import (
    SprintAccessDenied,
    SprintSubmissionNotAllowed,
    SprintTransitionNotAllowed,
)
from apps.formations.models import SprintRunState, SprintSubmission
from apps.formations.services import (
    complete_sprint,
    initialize_sprint_runs,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
    submit_sprint,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence"))


def _complete_sprint(*, sprint_run, member, facilitator, now=None):
    open_sprint(
        sprint_run_id=sprint_run.id,
        designated_submitter_id=member.id,
        actor=facilitator,
        now=now,
    )
    submit_sprint(
        sprint_run_id=sprint_run.id,
        user=member.user,
        evidence="Initial evidence",
        now=now,
    )
    mark_sprint_under_review(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        now=now,
    )
    return complete_sprint(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        now=now,
    )


def test_project_run_initializes_locked_sprints_with_fixed_schedule(
    runtime_project_run,
    runtime_sprint_templates,
):
    sprint_runs = _ordered_sprints(runtime_project_run)

    assert len(sprint_runs) == len(runtime_sprint_templates) == 3
    assert all(item.state == SprintRunState.LOCKED for item in sprint_runs)
    for sprint_run, template in zip(sprint_runs, runtime_sprint_templates, strict=True):
        assert sprint_run.planned_start_at == (
            runtime_project_run.started_at
            + timedelta(days=template.planned_start_offset_days)
        )
        assert sprint_run.planned_end_at == (
            runtime_project_run.started_at
            + timedelta(days=template.planned_end_offset_days)
        )

    assert len(initialize_sprint_runs(project_run=runtime_project_run)) == 3
    assert runtime_project_run.sprint_runs.count() == 3


def test_next_sprint_cannot_open_until_previous_is_completed(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, _ = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
    )

    with pytest.raises(SprintTransitionNotAllowed):
        open_sprint(
            sprint_run_id=second.id,
            designated_submitter_id=backend.id,
            actor=facilitator,
        )


def test_submission_review_changes_resubmission_and_completion_flow(
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

    submitted, first_submission = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Version one",
    )
    assert submitted.state == SprintRunState.SUBMITTED
    assert submitted.completed_at is None
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    request_sprint_changes(sprint_run_id=first.id, actor=facilitator)
    resubmitted, second_submission = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Version two",
    )
    assert resubmitted.id == first.id
    assert first_submission.id != second_submission.id
    assert list(
        SprintSubmission.objects.filter(sprint_run=first).values_list(
            "evidence", flat=True
        )
    ) == ["Version one", "Version two"]
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    completed = complete_sprint(sprint_run_id=first.id, actor=facilitator)
    assert completed.state == SprintRunState.COMPLETED
    assert completed.completed_at is not None


def test_only_staff_manage_and_only_designated_current_member_submits(
    runtime_project_run,
    runtime_members,
    facilitator,
    outside_user,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]

    with pytest.raises(SprintAccessDenied):
        open_sprint(
            sprint_run_id=first.id,
            designated_submitter_id=backend.id,
            actor=backend.user,
        )
    open_sprint(
        sprint_run_id=first.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
    )
    with pytest.raises(SprintSubmissionNotAllowed):
        submit_sprint(sprint_run_id=first.id, user=frontend.user)
    with pytest.raises(SprintAccessDenied):
        submit_sprint(sprint_run_id=first.id, user=outside_user)


@pytest.mark.django_db(transaction=True)
def test_inactive_designated_member_cannot_submit(
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
    backend.user.is_active = False
    backend.user.save(update_fields=["is_active"])

    with pytest.raises(SprintAccessDenied):
        submit_sprint(sprint_run_id=first.id, user=backend.user)

    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE
    assert first.submissions.count() == 0


def test_early_or_late_completion_does_not_move_future_schedule(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, third = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    original_schedules = {
        item.id: (item.planned_start_at, item.planned_end_at)
        for item in (second, third)
    }
    early = first.planned_end_at - timedelta(days=2)
    _complete_sprint(
        sprint_run=first,
        member=backend,
        facilitator=facilitator,
        now=early,
    )
    open_sprint(
        sprint_run_id=second.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
        now=early,
    )
    late = second.planned_end_at + timedelta(days=3)
    submit_sprint(sprint_run_id=second.id, user=backend.user, now=late)
    mark_sprint_under_review(sprint_run_id=second.id, actor=facilitator, now=late)
    complete_sprint(sprint_run_id=second.id, actor=facilitator, now=late)
    open_sprint(
        sprint_run_id=third.id,
        designated_submitter_id=backend.id,
        actor=facilitator,
        now=late,
    )

    second.refresh_from_db()
    third.refresh_from_db()
    assert (second.planned_start_at, second.planned_end_at) == original_schedules[
        second.id
    ]
    assert (third.planned_start_at, third.planned_end_at) == original_schedules[
        third.id
    ]


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_submission_creates_one_history_row(
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
    barrier = Barrier(2)

    def submit_once():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            user = type(backend.user).objects.get(id=backend.user_id)
            try:
                submit_sprint(
                    sprint_run_id=first.id,
                    user=user,
                    evidence="Concurrent evidence",
                )
            except SprintTransitionNotAllowed:
                return "rejected"
            return "submitted"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit_once(), range(2)))

    assert sorted(results) == ["rejected", "submitted"]
    assert SprintSubmission.objects.filter(sprint_run=first).count() == 1
