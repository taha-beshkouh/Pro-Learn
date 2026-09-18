from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from time import sleep
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from django.utils.dateparse import parse_datetime

from apps.formations.exceptions import (
    ProjectRunDeadlineNotReached,
    ProjectRunTransitionNotAllowed,
    SprintAccessDenied,
    SprintDeadlinePassed,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ProjectRunState,
    SprintRunState,
)
from apps.formations.services import (
    complete_sprint,
    confirm_ready_check,
    create_team_formation,
    mark_project_run_incomplete,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
)
from tests.formations.structured_submission import submit_structured_sprint as submit_sprint


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence", "id"))


def _complete_sprint(*, sprint_run, member, facilitator, now):
    sprint_run.refresh_from_db()
    if sprint_run.state == SprintRunState.LOCKED:
        open_sprint(
            sprint_run_id=sprint_run.id,
            actor=facilitator,
            now=now,
        )
    submit_sprint(
        sprint_run_id=sprint_run.id,
        user=member.user,
        evidence=f"Evidence for {sprint_run.sprint_template.sequence}",
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


def test_ready_check_completion_sets_authoritative_run_deadline(
    runtime_project_run,
    helpdesk_version,
):
    assert runtime_project_run.state == ProjectRunState.ACTIVE
    assert runtime_project_run.deadline_at == (
        runtime_project_run.started_at
        + timedelta(weeks=helpdesk_version.duration_weeks)
    )
    assert runtime_project_run.ended_at is None


def test_submission_at_deadline_is_rejected_without_history(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(SprintDeadlinePassed):
        submit_sprint(
            sprint_run_id=first.id,
            user=backend.user,
            now=runtime_project_run.deadline_at,
        )

    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE
    assert first.submissions.count() == 0


def test_pre_deadline_submission_can_be_reviewed_after_deadline(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    before_deadline = runtime_project_run.deadline_at - timedelta(microseconds=1)
    after_deadline = runtime_project_run.deadline_at + timedelta(hours=1)
    submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Submitted before cutoff",
        now=before_deadline,
    )

    mark_sprint_under_review(
        sprint_run_id=first.id,
        actor=facilitator,
        now=after_deadline,
    )
    completed = complete_sprint(
        sprint_run_id=first.id,
        actor=facilitator,
        now=after_deadline,
    )

    runtime_project_run.refresh_from_db()
    assert completed.state == SprintRunState.COMPLETED
    assert runtime_project_run.state == ProjectRunState.ACTIVE


def test_resubmission_after_deadline_is_rejected_in_same_sprint(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    before_deadline = runtime_project_run.deadline_at - timedelta(seconds=1)
    after_deadline = runtime_project_run.deadline_at + timedelta(seconds=1)
    submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Version one",
        now=before_deadline,
    )
    mark_sprint_under_review(
        sprint_run_id=first.id,
        actor=facilitator,
        now=after_deadline,
    )
    request_sprint_changes(
        sprint_run_id=first.id,
        actor=facilitator,
        feedback="Address the requested corrections.",
        now=after_deadline,
    )

    with pytest.raises(SprintDeadlinePassed):
        submit_sprint(
            sprint_run_id=first.id,
            user=backend.user,
            evidence="Too late",
            now=after_deadline,
        )

    first.refresh_from_db()
    assert first.state == SprintRunState.CHANGES_REQUESTED
    assert list(first.submissions.values_list("evidence", flat=True)) == [
        "Version one"
    ]


def test_highest_sequence_sprint_completion_atomically_completes_run(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, final = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    transition_at = runtime_project_run.deadline_at - timedelta(days=2)
    _complete_sprint(
        sprint_run=first,
        member=backend,
        facilitator=facilitator,
        now=transition_at,
    )
    _complete_sprint(
        sprint_run=second,
        member=backend,
        facilitator=facilitator,
        now=transition_at,
    )
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.ACTIVE

    open_sprint(
        sprint_run_id=final.id,
        actor=facilitator,
        now=transition_at,
    )
    submit_sprint(
        sprint_run_id=final.id,
        user=backend.user,
        evidence="Final evidence",
        now=transition_at,
    )
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.ACTIVE

    completed_at = runtime_project_run.deadline_at + timedelta(hours=2)
    mark_sprint_under_review(
        sprint_run_id=final.id,
        actor=facilitator,
        now=completed_at,
    )
    complete_sprint(
        sprint_run_id=final.id,
        actor=facilitator,
        now=completed_at,
    )

    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.COMPLETED
    assert runtime_project_run.ended_at == completed_at
    assert set(
        runtime_project_run.members.values_list("ended_at", flat=True)
    ) == {completed_at}


def test_manual_incomplete_is_staff_only_after_deadline_and_blocks_runtime(
    overdue_runtime_project_run,
    overdue_runtime_members,
    facilitator,
):
    first = _ordered_sprints(overdue_runtime_project_run)[0]
    backend = overdue_runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(SprintAccessDenied):
        mark_project_run_incomplete(
            project_run_id=overdue_runtime_project_run.id,
            actor=backend.user,
        )

    ended = mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )
    assert ended.state == ProjectRunState.INCOMPLETE
    assert ended.ended_at >= ended.deadline_at

    with pytest.raises(SprintTransitionNotAllowed):
        open_sprint(
            sprint_run_id=first.id,
            actor=facilitator,
        )


def test_manual_incomplete_before_deadline_is_rejected(
    runtime_project_run,
    facilitator,
):
    with pytest.raises(ProjectRunDeadlineNotReached):
        mark_project_run_incomplete(
            project_run_id=runtime_project_run.id,
            actor=facilitator,
            now=runtime_project_run.deadline_at - timedelta(microseconds=1),
        )


# Commit valid submission/review history before the real database deadline;
# a historical service `now` cannot override the PostgreSQL clock_timestamp() guard.
@pytest.mark.django_db(transaction=True)
def test_staff_incomplete_api_exposes_server_eligibility_and_preserves_history(
    api_client,
    facilitator,
    helpdesk_version,
    proposed_members,
    runtime_sprint_templates,
    runtime_work_items,
):
    # The fixed ProjectVersion duration determines the deadline. Start this
    # test's own run so its deadline is briefly in the future, then let actual
    # PostgreSQL time pass; never rewrite an immutable ProjectRun deadline.
    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        database_now = cursor.fetchone()[0]
    target_deadline = database_now + timedelta(seconds=10)
    startup_at = target_deadline - timedelta(weeks=helpdesk_version.duration_weeks)
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in proposed_members],
        now=startup_at - timedelta(hours=1),
    )
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(
            ready_check_id=ready_check.id,
            user=ready_check.user,
            now=startup_at,
        )
    project_run = ProjectRun.objects.get(team__formation=formation)
    assert project_run.state == ProjectRunState.ACTIVE
    assert project_run.deadline_at == target_deadline
    first = _ordered_sprints(project_run)[0]
    assert first.state == SprintRunState.ACTIVE
    assert first.opened_at == project_run.started_at
    backend = project_run.members.get(role__code="BACKEND_DEVELOPER")

    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        assert cursor.fetchone()[0] < project_run.deadline_at
    submitted_at = project_run.started_at + timedelta(days=1)
    _complete_sprint(
        sprint_run=first,
        member=backend,
        facilitator=facilitator,
        now=submitted_at,
    )
    first.refresh_from_db()
    submission = first.submissions.get()
    assert submission.submitted_at < project_run.deadline_at
    decision_id = submission.review_decision.id
    sprint_state = first.state

    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        database_now = cursor.fetchone()[0]
    sleep(max(0, (project_run.deadline_at - database_now).total_seconds()) + 0.05)

    api_client.force_login(facilitator)
    listed = api_client.get("/api/v1/project-runs/")
    assert listed.status_code == 200
    item = next(row for row in listed.data if row["id"] == str(project_run.id))
    assert item["deadline_at"] is not None
    assert item["can_mark_incomplete"] is True

    url = f"/api/v1/project-runs/{project_run.id}/incomplete/"
    marked = api_client.post(url, {}, format="json")
    assert marked.status_code == 200
    assert marked.data["state"] == ProjectRunState.INCOMPLETE
    assert marked.data["ended_at"] is not None
    assert api_client.post(url, {}, format="json").status_code == 409
    assert not any(
        row["id"] == str(project_run.id)
        for row in api_client.get("/api/v1/project-runs/").data
    )

    first.refresh_from_db()
    assert first.state == sprint_state
    assert first.submissions.get().id == submission.id
    assert first.submissions.get().review_decision.id == decision_id
    historical = api_client.get(
        f"/api/v1/project-runs/{project_run.id}/sprints/{first.id}/"
    )
    assert historical.status_code == 200
    assert historical.data["submissions"][0]["id"] == str(submission.id)
    assert historical.data["submissions"][0]["review_decision"]["id"] == str(decision_id)
    with pytest.raises(SprintTransitionNotAllowed):
        open_sprint(sprint_run_id=first.id, actor=facilitator)


def test_staff_incomplete_api_rejects_early_nonstaff_inactive_and_unknown_run(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
    django_user_model,
):
    url = f"/api/v1/project-runs/{runtime_project_run.id}/incomplete/"
    api_client.force_login(facilitator)
    listed = api_client.get("/api/v1/project-runs/")
    item = next(row for row in listed.data if row["id"] == str(runtime_project_run.id))
    assert parse_datetime(item["deadline_at"]) == runtime_project_run.deadline_at
    assert item["can_mark_incomplete"] is False
    assert api_client.post(url, {}, format="json").status_code == 409
    assert api_client.post(f"/api/v1/project-runs/{uuid4()}/incomplete/", {}, format="json").status_code == 404

    api_client.force_login(runtime_members["BACKEND_DEVELOPER"].user)
    assert api_client.post(url, {}, format="json").status_code == 403
    api_client.logout()
    assert api_client.post(url, {}, format="json").status_code in {401, 403}

    inactive_staff = django_user_model.objects.create_user(
        email="inactive-incomplete-staff@example.test",
        password="test-password-84731",
        is_staff=True,
        is_active=False,
    )
    api_client.force_login(inactive_staff)
    assert api_client.post(url, {}, format="json").status_code in {401, 403}
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.ACTIVE


# Final-Sprint history must commit through the real lifecycle before this API attempt.
@pytest.mark.django_db(transaction=True)
def test_staff_incomplete_api_rejects_a_completed_run(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    transition_at = runtime_project_run.deadline_at - timedelta(days=2)
    for sprint_run in _ordered_sprints(runtime_project_run):
        _complete_sprint(
            sprint_run=sprint_run,
            member=backend,
            facilitator=facilitator,
            now=transition_at,
        )
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.COMPLETED

    api_client.force_login(facilitator)
    response = api_client.post(
        f"/api/v1/project-runs/{runtime_project_run.id}/incomplete/",
        {},
        format="json",
    )
    assert response.status_code == 409
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.COMPLETED


def test_overdue_project_run_does_not_auto_transition(overdue_runtime_project_run):
    overdue_runtime_project_run.refresh_from_db()

    assert overdue_runtime_project_run.state == ProjectRunState.ACTIVE
    assert overdue_runtime_project_run.ended_at is None


def test_terminal_run_releases_users_for_a_new_active_run(
    overdue_runtime_project_run,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )
    replacement_readinesses = [
        ProjectReadiness.objects.create(
            user=readiness.user,
            role=readiness.role,
            project_version=readiness.project_version,
            technology_stack=readiness.technology_stack,
        )
        for readiness in proposed_members
    ]
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in replacement_readinesses],
    )
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)

    new_run = ProjectRun.objects.get(team__formation=formation)
    assert new_run.state == ProjectRunState.ACTIVE
    assert new_run.members.filter(ended_at__isnull=True).count() == 3


@pytest.mark.django_db(transaction=True)
def test_concurrent_incomplete_requests_terminalize_once(
    overdue_runtime_project_run,
    facilitator,
):
    barrier = Barrier(2)

    def mark_once():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            actor = type(facilitator).objects.get(id=facilitator.id)
            try:
                mark_project_run_incomplete(
                    project_run_id=overdue_runtime_project_run.id,
                    actor=actor,
                )
            except ProjectRunTransitionNotAllowed:
                return "rejected"
            return "incomplete"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: mark_once(), range(2)))

    assert sorted(results) == ["incomplete", "rejected"]
    run = ProjectRun.objects.get(id=overdue_runtime_project_run.id)
    assert run.state == ProjectRunState.INCOMPLETE
    assert run.members.filter(ended_at=run.ended_at).count() == 3


@pytest.mark.django_db(transaction=True)
def test_concurrent_final_completion_completes_project_run_once(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, final = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    transition_at = runtime_project_run.started_at + timedelta(days=1)
    _complete_sprint(
        sprint_run=first,
        member=backend,
        facilitator=facilitator,
        now=transition_at,
    )
    _complete_sprint(
        sprint_run=second,
        member=backend,
        facilitator=facilitator,
        now=transition_at,
    )
    open_sprint(
        sprint_run_id=final.id,
        actor=facilitator,
        now=transition_at,
    )
    submit_sprint(
        sprint_run_id=final.id,
        user=backend.user,
        now=transition_at,
    )
    mark_sprint_under_review(
        sprint_run_id=final.id,
        actor=facilitator,
        now=transition_at,
    )
    barrier = Barrier(2)

    def complete_once():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            actor = type(facilitator).objects.get(id=facilitator.id)
            try:
                complete_sprint(
                    sprint_run_id=final.id,
                    actor=actor,
                    now=transition_at,
                )
            except (ProjectRunTransitionNotAllowed, SprintTransitionNotAllowed):
                return "rejected"
            return "completed"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: complete_once(), range(2)))

    assert sorted(results) == ["completed", "rejected"]
    run = ProjectRun.objects.get(id=runtime_project_run.id)
    assert run.state == ProjectRunState.COMPLETED
    assert run.members.filter(ended_at=run.ended_at).count() == 3
