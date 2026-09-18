from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.formations.exceptions import (
    SprintAccessDenied,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ProjectRunState,
    SprintRunState,
    SprintSubmission,
)
from apps.formations.services import (
    complete_sprint,
    confirm_ready_check,
    create_team_formation,
    initialize_sprint_runs,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
)
from apps.profiles.models import RoleCode, UserProfile
from tests.formations.structured_submission import (
    configure_submission_runtime,
    submit_structured_sprint as submit_sprint,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence"))


def _create_other_project_run(
    *,
    django_user_model,
    project_run,
    runtime_members,
    facilitator,
):
    readinesses = []
    for member in runtime_members.values():
        user = django_user_model.objects.create_user(
            email=f"other-{member.role.code.lower()}@example.com"
        )
        UserProfile.objects.create(
            user=user,
            selected_role=member.role,
            github_username=(
                f"other-{user.id.hex[:12]}"
                if member.role.code in {
                    RoleCode.BACKEND_DEVELOPER,
                    RoleCode.FRONTEND_DEVELOPER,
                }
                else None
            ),
        )
        readinesses.append(
            ProjectReadiness.objects.create(
                user=user,
                role=member.role,
                project_version=project_run.project_version,
                technology_stack=member.technology_stack,
            )
        )

    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in readinesses],
    )
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    return ProjectRun.objects.get(team__formation=formation)


def _complete_sprint(*, sprint_run, member, facilitator, now=None):
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


def test_project_run_starts_first_sprint_and_keeps_later_sprints_locked(
    runtime_project_run,
    runtime_sprint_templates,
):
    sprint_runs = _ordered_sprints(runtime_project_run)

    assert runtime_project_run.state == ProjectRunState.ACTIVE
    assert len(sprint_runs) == len(runtime_sprint_templates) == 3
    first, *later = sprint_runs
    assert first.sprint_template.sequence == 1
    assert first.state == SprintRunState.ACTIVE
    assert first.opened_at == runtime_project_run.started_at
    assert all(item.state == SprintRunState.LOCKED for item in later)
    assert all(item.opened_at is None for item in later)
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
    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE
    assert first.opened_at == runtime_project_run.started_at


def test_later_sprint_requires_prior_completion_and_explicit_staff_open(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, _ = _ordered_sprints(runtime_project_run)
    assert first.state == SprintRunState.ACTIVE

    with pytest.raises(SprintTransitionNotAllowed):
        open_sprint(
            sprint_run_id=second.id,
            actor=facilitator,
        )

    _complete_sprint(
        sprint_run=first,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    second.refresh_from_db()
    assert second.state == SprintRunState.LOCKED
    assert second.opened_at is None

    opened = open_sprint(sprint_run_id=second.id, actor=facilitator)
    assert opened.state == SprintRunState.ACTIVE
    assert opened.opened_at is not None


def test_submission_review_changes_resubmission_and_completion_flow(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]

    submitted, first_submission = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Version one",
    )
    assert submitted.state == SprintRunState.SUBMITTED
    assert submitted.completed_at is None
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    request_sprint_changes(
        sprint_run_id=first.id,
        actor=facilitator,
        feedback="Correct the first submission.",
    )
    resubmitted, second_submission = submit_sprint(
        sprint_run_id=first.id,
        user=frontend.user,
        evidence="Version two",
    )
    assert resubmitted.id == first.id
    assert first_submission.id != second_submission.id
    assert first_submission.submitted_by_id == backend.id
    assert second_submission.submitted_by_id == frontend.id
    assert list(
        SprintSubmission.objects.filter(sprint_run=first).values_list(
            "submitted_by_id", "evidence"
        )
    ) == [(backend.id, "Version one"), (frontend.id, "Version two")]
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    completed = complete_sprint(sprint_run_id=first.id, actor=facilitator)
    assert completed.state == SprintRunState.COMPLETED
    assert completed.completed_at is not None


def test_submitted_sprint_accepts_append_only_pre_review_replacement(
    runtime_project_run,
    runtime_members,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    initial_time = first.opened_at + timedelta(hours=1)
    replacement_time = initial_time + timedelta(minutes=30)

    submitted, initial = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Initial review candidate",
        now=initial_time,
    )
    sprint_updated_at = submitted.updated_at
    initial_snapshot = {
        "submitted_by_id": initial.submitted_by_id,
        "evidence": initial.evidence,
        "submitted_at": initial.submitted_at,
    }

    replaced, replacement = submit_sprint(
        sprint_run_id=first.id,
        user=frontend.user,
        evidence="New pre-review candidate",
        now=replacement_time,
    )

    assert replaced.state == SprintRunState.SUBMITTED
    assert replaced.updated_at == sprint_updated_at
    assert replaced.designated_submitter_id is None
    assert replacement.id != initial.id
    assert replacement.submitted_by_id == frontend.id
    initial.refresh_from_db()
    assert {
        "submitted_by_id": initial.submitted_by_id,
        "evidence": initial.evidence,
        "submitted_at": initial.submitted_at,
    } == initial_snapshot
    history = list(SprintSubmission.objects.filter(sprint_run=first))
    assert history == [initial, replacement]
    assert history[-1].evidence == "New pre-review candidate"


def test_submission_rejects_locked_under_review_and_completed_sprints(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, locked, _ = _ordered_sprints(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(SprintTransitionNotAllowed):
        submit_sprint(sprint_run_id=locked.id, user=backend.user)

    submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Only valid submission",
    )
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    with pytest.raises(SprintTransitionNotAllowed):
        submit_sprint(sprint_run_id=first.id, user=backend.user)

    complete_sprint(sprint_run_id=first.id, actor=facilitator)
    with pytest.raises(SprintTransitionNotAllowed):
        submit_sprint(sprint_run_id=first.id, user=backend.user)

    first.refresh_from_db()
    locked.refresh_from_db()
    assert first.state == SprintRunState.COMPLETED
    assert list(first.submissions.values_list("evidence", flat=True)) == [
        "Only valid submission"
    ]
    assert locked.state == SprintRunState.LOCKED
    assert locked.submissions.count() == 0


def test_only_staff_manage_and_only_current_members_submit(
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
            actor=backend.user,
        )
    with pytest.raises(SprintAccessDenied):
        submit_sprint(sprint_run_id=first.id, user=outside_user)
    submitted, submission = submit_sprint(sprint_run_id=first.id, user=frontend.user)
    assert submitted.state == SprintRunState.SUBMITTED
    assert submission.submitted_by_id == frontend.id


@pytest.mark.parametrize(
    "role_code",
    ["BACKEND_DEVELOPER", "FRONTEND_DEVELOPER", "PRODUCT_DESIGNER"],
)
def test_each_current_team_member_can_submit_without_designation(
    runtime_project_run,
    runtime_members,
    facilitator,
    role_code,
):
    first = _ordered_sprints(runtime_project_run)[0]
    member = runtime_members[role_code]

    submitted, submission = submit_sprint(
        sprint_run_id=first.id,
        user=member.user,
        evidence=f"Evidence from {role_code}",
    )

    assert first.designated_submitter_id is None
    assert submitted.state == SprintRunState.SUBMITTED
    assert submission.submitted_by_id == member.id


def test_member_of_another_project_run_cannot_submit(
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    other_run = _create_other_project_run(
        django_user_model=django_user_model,
        project_run=runtime_project_run,
        runtime_members=runtime_members,
        facilitator=facilitator,
    )
    other_member = other_run.members.select_related("user").order_by("id").first()
    assert other_member is not None

    with pytest.raises(SprintAccessDenied):
        submit_sprint(sprint_run_id=first.id, user=other_member.user)

    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE
    assert first.submissions.count() == 0


@pytest.mark.django_db(transaction=True)
def test_inactive_current_member_cannot_submit(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    backend.user.is_active = False
    backend.user.save(update_fields=["is_active"])

    with pytest.raises(SprintAccessDenied):
        submit_sprint(sprint_run_id=first.id, user=backend.user)

    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE
    assert first.submissions.count() == 0


def test_ended_team_member_cannot_submit(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(SprintAccessDenied), transaction.atomic():
        type(backend).objects.filter(id=backend.id).update(ended_at=timezone.now())
        submit_sprint(sprint_run_id=first.id, user=backend.user)

    first.refresh_from_db()
    backend.refresh_from_db()
    assert backend.ended_at is None
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
        actor=facilitator,
        now=early,
    )
    late = second.planned_end_at + timedelta(days=3)
    submit_sprint(sprint_run_id=second.id, user=backend.user, now=late)
    mark_sprint_under_review(sprint_run_id=second.id, actor=facilitator, now=late)
    complete_sprint(sprint_run_id=second.id, actor=facilitator, now=late)
    open_sprint(
        sprint_run_id=third.id,
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
def test_concurrent_submission_by_two_current_members_preserves_both_snapshots(
    runtime_project_run,
    runtime_members,
):
    configure_submission_runtime(runtime_project_run)
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    barrier = Barrier(2)

    def submit_once(user_id):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            user = type(backend.user).objects.get(id=user_id)
            submit_sprint(
                sprint_run_id=first.id,
                user=user,
                evidence=f"Concurrent evidence from {user_id}",
            )
            return "submitted"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit_once, (backend.user_id, frontend.user_id)))

    assert results == ["submitted", "submitted"]
    submissions = SprintSubmission.objects.filter(sprint_run=first)
    assert submissions.count() == 2
    assert set(submissions.values_list("submitted_by_id", flat=True)) == {
        backend.id,
        frontend.id,
    }
    first.refresh_from_db()
    assert first.state == SprintRunState.SUBMITTED


@pytest.mark.django_db(transaction=True)
def test_pre_review_replacement_races_safely_with_staff_start_review(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    configure_submission_runtime(runtime_project_run)
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Initial review candidate",
    )
    barrier = Barrier(2)

    def replace_submission():
        close_old_connections()
        try:
            user = type(frontend.user).objects.get(id=frontend.user_id)
            barrier.wait(timeout=5)
            try:
                submit_sprint(
                    sprint_run_id=first.id,
                    user=user,
                    evidence="Concurrent replacement candidate",
                )
            except SprintTransitionNotAllowed:
                return "rejected-after-review"
            return "replacement-created"
        finally:
            close_old_connections()

    def start_review():
        close_old_connections()
        try:
            actor = type(facilitator).objects.get(id=facilitator.id)
            barrier.wait(timeout=5)
            mark_sprint_under_review(sprint_run_id=first.id, actor=actor)
            return "review-started"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        replacement_future = executor.submit(replace_submission)
        review_future = executor.submit(start_review)
        replacement_result = replacement_future.result()
        review_result = review_future.result()

    assert review_result == "review-started"
    assert replacement_result in {"replacement-created", "rejected-after-review"}
    first.refresh_from_db()
    assert first.state == SprintRunState.UNDER_REVIEW
    history = list(SprintSubmission.objects.filter(sprint_run=first))
    if replacement_result == "replacement-created":
        assert len(history) == 2
        assert history[-1].evidence == "Concurrent replacement candidate"
    else:
        assert len(history) == 1
        assert history[-1].evidence == "Initial review candidate"
