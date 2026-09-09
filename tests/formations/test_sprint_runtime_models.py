from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    TeamMember,
)
from apps.formations.services import (
    complete_sprint,
    confirm_ready_check,
    create_team_formation,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
    submit_sprint,
)
from apps.profiles.models import UserProfile
from apps.projects.models import ProjectVersion, SprintTemplate


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence"))


def _create_other_project_run(
    *,
    facilitator,
    django_user_model,
    password,
    project_version,
    source_members,
):
    readiness_ids = []
    for index, source_member in enumerate(
        sorted(source_members.values(), key=lambda member: str(member.id))
    ):
        user = django_user_model.objects.create_user(
            email=f"cross-run-member-{index}@example.com",
            password=password,
        )
        UserProfile.objects.create(user=user, selected_role=source_member.role)
        readiness = ProjectReadiness.objects.create(
            user=user,
            role=source_member.role,
            project_version=project_version,
            technology_stack=source_member.technology_stack,
        )
        readiness_ids.append(readiness.id)

    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids,
    )
    for ready_check in formation.ready_checks.select_related("user").order_by("id"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    return ProjectRun.objects.get(team__formation=formation)


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
):
    _, second, _ = _ordered_sprints(runtime_project_run)

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=second.id).update(
            state=SprintRunState.ACTIVE,
            opened_at=timezone.now(),
        )


def test_database_rejects_invalid_state_transition(
    runtime_project_run,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    open_sprint(
        sprint_run_id=first.id,
        actor=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(
            state=SprintRunState.COMPLETED,
            completed_at=timezone.now(),
        )


def test_database_accepts_full_valid_state_flow_without_designation(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    opened = open_sprint(
        sprint_run_id=first.id,
        actor=facilitator,
    )
    assert opened.state == SprintRunState.ACTIVE
    assert opened.designated_submitter_id is None

    submitted, first_submission = submit_sprint(
        sprint_run_id=first.id,
        user=backend.user,
        evidence="Initial evidence",
    )
    assert submitted.state == SprintRunState.SUBMITTED
    assert submitted.designated_submitter_id is None
    assert first_submission.submitted_by_id == backend.id

    reviewing = mark_sprint_under_review(
        sprint_run_id=first.id,
        actor=facilitator,
    )
    assert reviewing.state == SprintRunState.UNDER_REVIEW
    assert reviewing.designated_submitter_id is None

    changes_requested = request_sprint_changes(
        sprint_run_id=first.id,
        actor=facilitator,
    )
    assert changes_requested.state == SprintRunState.CHANGES_REQUESTED
    assert changes_requested.designated_submitter_id is None

    resubmitted, second_submission = submit_sprint(
        sprint_run_id=first.id,
        user=frontend.user,
        evidence="Revised evidence",
    )
    assert resubmitted.state == SprintRunState.SUBMITTED
    assert resubmitted.designated_submitter_id is None
    assert second_submission.submitted_by_id == frontend.id

    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    completed = complete_sprint(sprint_run_id=first.id, actor=facilitator)
    assert completed.state == SprintRunState.COMPLETED
    assert completed.designated_submitter_id is None


def test_database_keeps_sprint_timestamp_invariants_without_designation(
    runtime_project_run,
):
    first = _ordered_sprints(runtime_project_run)[0]

    with pytest.raises(IntegrityError) as missing_opened_at, transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(state=SprintRunState.ACTIVE)
    assert "formations_sprint_state_timestamps_valid" in str(missing_opened_at.value)

    opened_at = timezone.now()
    SprintRun.objects.filter(id=first.id).update(
        state=SprintRunState.ACTIVE,
        opened_at=opened_at,
    )
    SprintRun.objects.filter(id=first.id).update(state=SprintRunState.SUBMITTED)
    SprintRun.objects.filter(id=first.id).update(state=SprintRunState.UNDER_REVIEW)

    with pytest.raises(IntegrityError) as missing_completed_at, transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(state=SprintRunState.COMPLETED)
    assert "formations_sprint_state_timestamps_valid" in str(
        missing_completed_at.value
    )

    with pytest.raises(IntegrityError) as completion_before_open, transaction.atomic():
        SprintRun.objects.filter(id=first.id).update(
            state=SprintRunState.COMPLETED,
            completed_at=opened_at - timedelta(microseconds=1),
        )
    assert "formations_sprint_state_timestamps_valid" in str(
        completion_before_open.value
    )


def test_database_rejects_submission_by_member_of_another_project_run(
    runtime_project_run,
    runtime_members,
    facilitator,
    django_user_model,
    password,
):
    first = _ordered_sprints(runtime_project_run)[0]
    other_run = _create_other_project_run(
        facilitator=facilitator,
        django_user_model=django_user_model,
        password=password,
        project_version=runtime_project_run.project_version,
        source_members=runtime_members,
    )
    other_member = other_run.members.order_by("id").first()
    open_sprint(sprint_run_id=first.id, actor=facilitator)

    with pytest.raises(IntegrityError, match="Invalid Sprint submission"):
        with transaction.atomic():
            SprintSubmission.objects.create(
                sprint_run=first,
                submitted_by=other_member,
                evidence="Cross-run evidence",
            )


def test_database_rejects_cross_project_run_legacy_designation(
    runtime_project_run,
    runtime_members,
    facilitator,
    django_user_model,
    password,
):
    first = _ordered_sprints(runtime_project_run)[0]
    other_run = _create_other_project_run(
        facilitator=facilitator,
        django_user_model=django_user_model,
        password=password,
        project_version=runtime_project_run.project_version,
        source_members=runtime_members,
    )
    other_member = other_run.members.order_by("id").first()

    with pytest.raises(IntegrityError, match="Legacy Sprint designation"):
        with transaction.atomic():
            SprintRun.objects.filter(id=first.id).update(
                state=SprintRunState.ACTIVE,
                designated_submitter_id=other_member.id,
                opened_at=timezone.now(),
            )


def test_database_rejects_submission_by_non_current_member(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    open_sprint(sprint_run_id=first.id, actor=facilitator)

    with pytest.raises(IntegrityError, match="Invalid Sprint submission"):
        with transaction.atomic():
            TeamMember.objects.filter(id=backend.id).update(ended_at=timezone.now())
            SprintSubmission.objects.create(
                sprint_run=first,
                submitted_by=backend,
                evidence="Ended membership evidence",
            )


def test_historical_designation_remains_valid_but_is_not_submission_authority(
    runtime_project_run,
    runtime_members,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    opened_at = timezone.now()

    # Simulate a row opened before designation stopped being written by current flows.
    SprintRun.objects.filter(id=first.id).update(
        state=SprintRunState.ACTIVE,
        designated_submitter=backend,
        opened_at=opened_at,
    )

    submitted, submission = submit_sprint(
        sprint_run_id=first.id,
        user=frontend.user,
        evidence="Submitted by another current member",
    )

    assert submitted.state == SprintRunState.SUBMITTED
    assert submitted.designated_submitter_id == backend.id
    assert submission.submitted_by_id == frontend.id


def test_sprint_submission_history_is_database_append_only(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    open_sprint(
        sprint_run_id=first.id,
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
