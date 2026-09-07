from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.formations.eligibility import ParticipationBlocker
from apps.formations.exceptions import (
    InvalidFormationMembers,
    InvalidProjectReadinessSelection,
)
from apps.formations.models import ProjectReadiness, ProjectRun, ProjectRunState
from apps.formations.services import (
    complete_sprint,
    confirm_ready_check,
    create_project_readiness,
    create_team_formation,
    decline_ready_check,
    mark_project_run_incomplete,
    mark_sprint_under_review,
    open_sprint,
    replace_ready_check_member,
    submit_sprint,
)
from apps.profiles.models import UserProfile
from apps.profiles.services import RoleChangeBlocked, select_profile_role


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

SELECT_ROLE_URL = "/api/v1/profile/select-role/"


def confirmed_selection(*, user, project_version, technology_stack):
    return {
        "project_stack_selection": {
            "user_id": str(user.id),
            "project_version_id": str(project_version.id),
            "selected_stack_id": (
                str(technology_stack.id) if technology_stack is not None else None
            ),
        }
    }


def readiness_ids(readinesses):
    return [readiness.id for readiness in readinesses]


def assert_blocked_change(*, user, requested_role, expected_reason):
    original_role_id = UserProfile.objects.get(user=user).selected_role_id
    with pytest.raises(RoleChangeBlocked) as caught:
        select_profile_role(user=user, role=requested_role)
    assert caught.value.reason == expected_reason
    assert UserProfile.objects.get(user=user).selected_role_id == original_role_id


def test_active_readiness_blocks_role_change_and_preserves_role(
    backend_user,
    frontend_role,
    proposed_members,
):
    assert ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).exists()

    assert_blocked_change(
        user=backend_user,
        requested_role=frontend_role,
        expected_reason=ParticipationBlocker.ACTIVE_READINESS,
    )


def test_same_role_remains_idempotent_while_lifecycle_is_active(
    backend_user,
    backend_role,
    proposed_members,
):
    selected = select_profile_role(user=backend_user, role=backend_role)

    assert selected.selected_role_id == backend_role.id


def test_consumed_historical_readiness_does_not_block_role_change(
    backend_user,
    frontend_role,
    proposed_members,
):
    readiness = next(
        item for item in proposed_members if item.user_id == backend_user.id
    )
    readiness.consumed_at = timezone.now()
    readiness.save(update_fields=["consumed_at"])

    changed = select_profile_role(user=backend_user, role=frontend_role)

    assert changed.selected_role_id == frontend_role.id


def test_current_unresolved_formation_blocks_role_change_and_preserves_role(
    formation,
    backend_user,
    frontend_role,
):
    assert formation.ready_confirmed_at is None

    assert_blocked_change(
        user=backend_user,
        requested_role=frontend_role,
        expected_reason=ParticipationBlocker.CURRENT_FORMATION_OR_READY_CHECK,
    )


@pytest.mark.django_db(transaction=True)
def test_replaced_user_may_change_role_when_no_other_blocker_remains(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    frontend_role,
    django_stack,
):
    current = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=current.id, user=backend_user)
    replacement_readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=backend_role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )
    replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=current.id,
        replacement_readiness_id=replacement_readiness.id,
        proposed_by=facilitator,
    )

    changed = select_profile_role(user=backend_user, role=frontend_role)

    assert changed.selected_role_id == frontend_role.id


def test_active_project_run_blocks_role_change_at_user_scope(
    runtime_project_run,
    backend_user,
    frontend_role,
):
    assert runtime_project_run.state == ProjectRunState.ACTIVE

    assert_blocked_change(
        user=backend_user,
        requested_role=frontend_role,
        expected_reason=ParticipationBlocker.ACTIVE_PROJECT_RUN,
    )


def test_active_run_block_has_no_project_template_scope(
    runtime_project_run,
    backend_user,
    frontend_role,
):
    assert runtime_project_run.project_version.project_template_id

    assert_blocked_change(
        user=backend_user,
        requested_role=frontend_role,
        expected_reason=ParticipationBlocker.ACTIVE_PROJECT_RUN,
    )


def test_active_run_block_has_no_project_version_scope(
    runtime_project_run,
    backend_user,
    frontend_role,
):
    assert runtime_project_run.project_version_id

    assert_blocked_change(
        user=backend_user,
        requested_role=frontend_role,
        expected_reason=ParticipationBlocker.ACTIVE_PROJECT_RUN,
    )


@pytest.mark.django_db(transaction=True)
def test_incomplete_project_run_does_not_block_role_change(
    overdue_runtime_project_run,
    facilitator,
    backend_user,
    frontend_role,
):
    ended = mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )
    assert ended.state == ProjectRunState.INCOMPLETE

    changed = select_profile_role(user=backend_user, role=frontend_role)

    assert changed.selected_role_id == frontend_role.id


@pytest.mark.django_db(transaction=True)
def test_completed_project_run_does_not_block_role_change(
    runtime_project_run,
    runtime_members,
    facilitator,
    backend_user,
    frontend_role,
):
    submitter = runtime_members["BACKEND_DEVELOPER"]
    transition_at = runtime_project_run.started_at + timedelta(days=1)
    for sprint_run in runtime_project_run.sprint_runs.order_by(
        "sprint_template__sequence",
        "id",
    ):
        open_sprint(
            sprint_run_id=sprint_run.id,
            designated_submitter_id=submitter.id,
            actor=facilitator,
            now=transition_at,
        )
        submit_sprint(
            sprint_run_id=sprint_run.id,
            user=backend_user,
            evidence="Role-change terminal-run regression",
            now=transition_at,
        )
        mark_sprint_under_review(
            sprint_run_id=sprint_run.id,
            actor=facilitator,
            now=transition_at,
        )
        complete_sprint(
            sprint_run_id=sprint_run.id,
            actor=facilitator,
            now=transition_at,
        )
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.COMPLETED

    changed = select_profile_role(user=backend_user, role=frontend_role)

    assert changed.selected_role_id == frontend_role.id


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason"),
    [
        ("proposed_members", ParticipationBlocker.ACTIVE_READINESS),
        ("formation", ParticipationBlocker.CURRENT_FORMATION_OR_READY_CHECK),
        ("runtime_project_run", ParticipationBlocker.ACTIVE_PROJECT_RUN),
    ],
)
def test_role_change_api_exposes_stable_blocker_reason(
    request,
    api_client,
    backend_user,
    frontend_role,
    fixture_name,
    expected_reason,
):
    lifecycle_state = request.getfixturevalue(fixture_name)
    if isinstance(lifecycle_state, list):
        project_version_id = lifecycle_state[0].project_version_id
    else:
        project_version_id = lifecycle_state.project_version_id
    continuation = {
        "selected_role_id": str(frontend_role.id),
        "project_version_id": str(project_version_id),
        "intended_action": "join_project",
        "return_path": f"/projects/{project_version_id}/stack-selection",
    }
    api_client.force_login(backend_user)
    session = api_client.session
    session["participation_context"] = continuation
    session.save()

    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(frontend_role.id)},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "role_change_blocked"
    assert response.data["reason"] == expected_reason.value
    assert response.data["detail"]
    assert UserProfile.objects.get(user=backend_user).selected_role_id != (
        frontend_role.id
    )
    assert api_client.session["participation_context"] == continuation


def test_successful_role_change_clears_stale_authenticated_stack_selection(
    api_client,
    backend_user,
    frontend_role,
):
    api_client.force_login(backend_user)
    session = api_client.session
    session["project_stack_selection"] = {
        "user_id": str(backend_user.id),
        "project_version_id": "00000000-0000-0000-0000-000000000001",
        "selected_stack_id": "00000000-0000-0000-0000-000000000002",
    }
    session.save()

    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(frontend_role.id)},
        format="json",
    )

    assert response.status_code == 200
    assert "project_stack_selection" not in api_client.session


def test_blocked_role_change_preserves_authenticated_stack_selection(
    api_client,
    backend_user,
    frontend_role,
    proposed_members,
):
    api_client.force_login(backend_user)
    selection = {
        "user_id": str(backend_user.id),
        "project_version_id": str(proposed_members[0].project_version_id),
        "selected_stack_id": str(proposed_members[0].technology_stack_id),
    }
    session = api_client.session
    session["project_stack_selection"] = selection
    session.save()

    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(frontend_role.id)},
        format="json",
    )

    assert response.status_code == 409
    assert api_client.session["project_stack_selection"] == selection


def test_blocked_conflict_approval_preserves_exact_continuation(
    api_client,
    backend_user,
    frontend_role,
    proposed_members,
):
    project_version_id = proposed_members[0].project_version_id
    continuation = {
        "selected_role_id": str(frontend_role.id),
        "project_version_id": str(project_version_id),
        "intended_action": "join_project",
        "return_path": f"/projects/{project_version_id}/stack-selection",
    }
    api_client.force_login(backend_user)
    session = api_client.session
    session["participation_context"] = continuation
    session.save()

    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(frontend_role.id)},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["reason"] == "active_readiness"
    assert api_client.session["participation_context"] == continuation


@pytest.mark.django_db(transaction=True)
def test_concurrent_role_change_and_readiness_creation_remain_coherent(
    backend_user,
    backend_role,
    frontend_role,
    helpdesk_version,
    django_stack,
):
    barrier = Barrier(2)

    def change_role():
        close_old_connections()
        try:
            thread_user = type(backend_user).objects.get(id=backend_user.id)
            thread_role = type(frontend_role).objects.get(id=frontend_role.id)
            barrier.wait(timeout=5)
            try:
                select_profile_role(user=thread_user, role=thread_role)
            except RoleChangeBlocked:
                return "role_blocked"
            return "role_changed"
        finally:
            close_old_connections()

    def create_readiness():
        close_old_connections()
        try:
            thread_user = type(backend_user).objects.get(id=backend_user.id)
            barrier.wait(timeout=5)
            try:
                create_project_readiness(
                    user=thread_user,
                    session=confirmed_selection(
                        user=thread_user,
                        project_version=helpdesk_version,
                        technology_stack=django_stack,
                    ),
                )
            except InvalidProjectReadinessSelection:
                return "readiness_rejected"
            return "readiness_created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        role_result = executor.submit(change_role)
        readiness_result = executor.submit(create_readiness)
        results = {role_result.result(), readiness_result.result()}

    profile = UserProfile.objects.get(user=backend_user)
    active = ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).first()
    assert results in (
        {"role_changed", "readiness_rejected"},
        {"role_blocked", "readiness_created"},
    )
    if active is None:
        assert profile.selected_role_id == frontend_role.id
    else:
        assert profile.selected_role_id == backend_role.id
        assert active.role_id == backend_role.id


@pytest.mark.django_db(transaction=True)
def test_concurrent_role_change_and_formation_consumption_remain_coherent(
    facilitator,
    proposed_members,
    backend_user,
    backend_role,
    frontend_role,
):
    barrier = Barrier(2)

    def change_role():
        close_old_connections()
        try:
            thread_user = type(backend_user).objects.get(id=backend_user.id)
            thread_role = type(frontend_role).objects.get(id=frontend_role.id)
            barrier.wait(timeout=5)
            try:
                select_profile_role(user=thread_user, role=thread_role)
            except RoleChangeBlocked:
                return "role_blocked"
            return "role_changed"
        finally:
            close_old_connections()

    def form_team():
        close_old_connections()
        try:
            actor = type(facilitator).objects.get(id=facilitator.id)
            barrier.wait(timeout=5)
            try:
                create_team_formation(
                    created_by=actor,
                    readiness_ids=readiness_ids(proposed_members),
                )
            except InvalidFormationMembers:
                return "formation_rejected"
            return "formation_created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        role_result = executor.submit(change_role)
        formation_result = executor.submit(form_team)
        results = {role_result.result(), formation_result.result()}

    profile = UserProfile.objects.get(user=backend_user)
    active = ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).first()
    assert results == {"role_blocked", "formation_created"}
    assert active is None
    assert profile.selected_role_id == backend_role.id


@pytest.mark.django_db(transaction=True)
def test_concurrent_role_change_and_project_run_activation_have_no_gap(
    facilitator,
    proposed_members,
    runtime_sprint_templates,
    runtime_work_items,
    backend_user,
    frontend_role,
):
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(proposed_members),
    )
    final_check = formation.ready_checks.get(user=backend_user, is_current=True)
    for ready_check in formation.ready_checks.exclude(id=final_check.id):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    barrier = Barrier(2)

    def change_role():
        close_old_connections()
        try:
            thread_user = type(backend_user).objects.get(id=backend_user.id)
            thread_role = type(frontend_role).objects.get(id=frontend_role.id)
            barrier.wait(timeout=5)
            try:
                select_profile_role(user=thread_user, role=thread_role)
            except RoleChangeBlocked:
                return "role_blocked"
            return "role_changed"
        finally:
            close_old_connections()

    def activate_run():
        close_old_connections()
        try:
            ready_check = type(final_check).objects.get(id=final_check.id)
            user = type(backend_user).objects.get(id=backend_user.id)
            barrier.wait(timeout=5)
            confirm_ready_check(ready_check_id=ready_check.id, user=user)
            return "run_activated"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        role_result = executor.submit(change_role)
        run_result = executor.submit(activate_run)
        results = {role_result.result(), run_result.result()}

    assert results == {"role_blocked", "run_activated"}
    assert UserProfile.objects.get(user=backend_user).selected_role_id == (
        final_check.role_id
    )
    assert ProjectRun.objects.filter(
        team__formation=formation,
        state=ProjectRunState.ACTIVE,
        members__user=backend_user,
        members__ended_at__isnull=True,
    ).exists()
