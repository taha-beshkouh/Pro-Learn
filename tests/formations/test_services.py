from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.formations.exceptions import (
    InvalidFormationMembers,
    MemberHasActiveProjectRun,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
)
from apps.formations.models import (
    ProjectRun,
    ReadyCheck,
    ReadyCheckStatus,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.profiles.models import UserProfile, UserSkill
from apps.formations.services import (
    ProposedMember,
    confirm_ready_check,
    create_team_formation,
    decline_ready_check,
    replace_ready_check_member,
)


pytestmark = pytest.mark.django_db


def test_create_formation_has_exact_roles_stacks_and_48_hour_ready_checks(
    facilitator, helpdesk_version, proposed_members
):
    now = timezone.now()
    formation = create_team_formation(
        project_version=helpdesk_version,
        created_by=facilitator,
        members=proposed_members,
        now=now,
    )

    checks = {
        item.role.code: item
        for item in formation.ready_checks.select_related("role", "technology_stack")
    }
    assert set(checks) == {
        "BACKEND_DEVELOPER",
        "FRONTEND_DEVELOPER",
        "PRODUCT_DESIGNER",
    }
    assert checks["BACKEND_DEVELOPER"].technology_stack.code == "django-drf"
    assert checks["FRONTEND_DEVELOPER"].technology_stack.code == (
        "react-typescript-vite"
    )
    assert checks["PRODUCT_DESIGNER"].technology_stack is None
    assert all(item.expires_at - item.started_at == timedelta(hours=48) for item in checks.values())


def test_create_formation_rejects_duplicate_users(
    facilitator, helpdesk_version, proposed_members
):
    members = list(proposed_members)
    members[1] = ProposedMember(
        user=members[0].user,
        role=members[1].role,
        technology_stack=members[1].technology_stack,
    )

    with pytest.raises(InvalidFormationMembers):
        create_team_formation(
            project_version=helpdesk_version,
            created_by=facilitator,
            members=members,
        )
    assert TeamFormation.objects.count() == 0


def test_each_member_can_confirm_and_third_confirmation_marks_formation_ready(
    formation,
):
    checks = list(formation.ready_checks.order_by("role__code"))
    for check in checks:
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    formation.refresh_from_db()
    assert formation.ready_confirmed_at is not None
    assert formation.ready_checks.filter(
        is_current=True,
        status=ReadyCheckStatus.CONFIRMED,
    ).count() == 3
    team = Team.objects.get(formation=formation)
    project_run = ProjectRun.objects.get(team=team)
    assert project_run.project_version_id == formation.project_version_id
    assert project_run.started_at == formation.ready_confirmed_at
    assert project_run.ended_at is None
    assert project_run.members.count() == 3


def test_team_and_project_run_are_created_exactly_once(formation):
    checks = list(formation.ready_checks.order_by("role__code"))
    for check in checks:
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    with pytest.raises(ReadyCheckNotPending):
        confirm_ready_check(ready_check_id=checks[-1].id, user=checks[-1].user)

    assert Team.objects.filter(formation=formation).count() == 1
    assert ProjectRun.objects.filter(team__formation=formation).count() == 1
    assert TeamMember.objects.filter(
        project_run__team__formation=formation
    ).count() == 3


def test_team_members_snapshot_role_and_selected_stack(
    formation,
    backend_user,
    frontend_role,
):
    ready_check_snapshots = {
        check.user_id: (check.role_id, check.technology_stack_id)
        for check in formation.ready_checks.filter(is_current=True)
    }

    for check in formation.ready_checks.filter(is_current=True).order_by("role__code"):
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    members = {
        member.user_id: (member.role_id, member.technology_stack_id)
        for member in TeamMember.objects.filter(
            project_run__team__formation=formation
        )
    }
    assert members == ready_check_snapshots
    designer_ready_check = formation.ready_checks.get(
        role__code="PRODUCT_DESIGNER",
        is_current=True,
    )
    assert members[designer_ready_check.user_id][1] is None

    backend_profile = UserProfile.objects.get(user=backend_user)
    selected_stack_id = ready_check_snapshots[backend_user.id][1]
    skill = UserSkill.objects.create(
        profile=backend_profile,
        technology_stack_id=selected_stack_id,
    )
    skill.delete()
    UserProfile.objects.filter(user=backend_user).update(selected_role=frontend_role)
    backend_membership = TeamMember.objects.get(user=backend_user)
    assert backend_membership.role_id == ready_check_snapshots[backend_user.id][0]
    assert backend_membership.technology_stack_id == ready_check_snapshots[
        backend_user.id
    ][1]


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_changing_profile_role_after_confirmation_does_not_break_ready_check(
    formation,
    backend_user,
    frontend_role,
):
    """Regression: deferred ReadyCheck triggers must not revalidate against the
    user's mutable current UserProfile.selected_role. Historical snapshots are
    immutable (PROJECT_RULES §2/§14)."""
    for check in formation.ready_checks.filter(is_current=True).order_by("role__code"):
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    ready_check_role_id = formation.ready_checks.get(
        user=backend_user, is_current=True
    ).role_id

    # Mutate the user's current profile role after the ReadyCheck was already
    # created and confirmed. The deferred ReadyCheck trigger must still accept
    # the original snapshot role without raising.
    UserProfile.objects.filter(user=backend_user).update(selected_role=frontend_role)

    # Force any deferred constraint triggers to flush on the backend member's
    # ReadyCheck row. If the trigger still depended on the mutable profile role
    # this would raise 'Ready Check member and project role are incompatible.'
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    assert ready_check.role_id == ready_check_role_id
    assert ready_check.status == ReadyCheckStatus.CONFIRMED

    backend_membership = TeamMember.objects.get(user=backend_user)
    assert backend_membership.role_id == ready_check_role_id


def test_create_formation_rejects_member_with_mismatched_profile_role(
    facilitator,
    helpdesk_version,
    backend_role,
    frontend_role,
    designer_role,
    django_stack,
    frontend_user,
    designer_user,
    django_user_model,
    password,
):
    """Service-layer validation must reject a proposed member whose current
    UserProfile.selected_role does not match the proposed ReadyCheck role."""
    # A user whose current profile role is FRONTEND_DEVELOPER ...
    mismatched_user = django_user_model.objects.create_user(
        email="mismatched@example.com",
        password=password,
    )
    UserProfile.objects.create(user=mismatched_user, selected_role=frontend_role)

    # ... proposed in the BACKEND_DEVELOPER slot must be rejected, while the
    # other two members are valid for their slots.
    members = [
        ProposedMember(mismatched_user, backend_role, django_stack),
        ProposedMember(frontend_user, frontend_role, None),
        ProposedMember(designer_user, designer_role, None),
    ]

    with pytest.raises(InvalidFormationMembers):
        create_team_formation(
            project_version=helpdesk_version,
            created_by=facilitator,
            members=members,
        )
    assert TeamFormation.objects.count() == 0


def test_replace_ready_check_rejects_mismatched_profile_role(
    formation,
    backend_user,
    frontend_role,
    frontend_user,
    django_stack,
    facilitator,
):
    """Replacing a ReadyCheck member with a user whose current profile role does
    not match the slot role must be rejected at the service layer."""
    backend = formation.ready_checks.get(
        role__code="BACKEND_DEVELOPER", is_current=True
    )
    decline_ready_check(ready_check_id=backend.id, user=backend.user)

    # frontend_user.selected_role is FRONTEND_DEVELOPER, not BACKEND_DEVELOPER.
    with pytest.raises(InvalidFormationMembers):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=backend.id,
            replacement_user=frontend_user,
            technology_stack=django_stack,
            proposed_by=facilitator,
        )


def test_one_active_project_run_per_user_is_enforced_before_completion(
    formation,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    for check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    second_formation = create_team_formation(
        project_version=helpdesk_version,
        created_by=facilitator,
        members=proposed_members,
    )
    second_checks = list(second_formation.ready_checks.order_by("role__code"))
    for check in second_checks[:2]:
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    with pytest.raises(MemberHasActiveProjectRun):
        confirm_ready_check(
            ready_check_id=second_checks[2].id,
            user=second_checks[2].user,
        )

    second_checks[2].refresh_from_db()
    second_formation.refresh_from_db()
    assert second_checks[2].status == ReadyCheckStatus.PENDING
    assert second_formation.ready_confirmed_at is None
    assert not Team.objects.filter(formation=second_formation).exists()
    assert Team.objects.count() == 1
    assert ProjectRun.objects.count() == 1


def test_member_can_decline_only_pending_own_ready_check(formation):
    ready_check = formation.ready_checks.filter(is_current=True).first()

    declined = decline_ready_check(
        ready_check_id=ready_check.id,
        user=ready_check.user,
    )

    assert declined.status == ReadyCheckStatus.DECLINED
    assert declined.responded_at is not None
    with pytest.raises(ReadyCheckNotPending):
        decline_ready_check(ready_check_id=ready_check.id, user=ready_check.user)


def test_expired_ready_check_cannot_confirm_and_expiration_is_persisted(formation):
    ready_check = formation.ready_checks.filter(is_current=True).first()
    now = ready_check.expires_at

    with pytest.raises(ReadyCheckExpired):
        confirm_ready_check(
            ready_check_id=ready_check.id,
            user=ready_check.user,
            now=now,
        )

    ready_check.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.EXPIRED
    assert ready_check.responded_at is None


def test_replacement_preserves_role_and_other_members(
    formation,
    replacement_backend_user,
    django_stack,
    facilitator,
):
    original_ids = set(
        formation.ready_checks.filter(is_current=True).values_list("id", flat=True)
    )
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)
    decline_ready_check(ready_check_id=backend.id, user=backend.user)

    replacement = replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=backend.id,
        replacement_user=replacement_backend_user,
        technology_stack=django_stack,
        proposed_by=facilitator,
    )

    backend.refresh_from_db()
    assert backend.is_current is False
    assert replacement.role_id == backend.role_id
    assert replacement.user == replacement_backend_user
    current_ids = set(
        formation.ready_checks.filter(is_current=True).values_list("id", flat=True)
    )
    assert len(current_ids) == 3
    assert current_ids & original_ids == original_ids - {backend.id}
    assert formation.ready_checks.count() == 4


def test_pending_unexpired_member_cannot_be_replaced(
    formation, replacement_backend_user, django_stack, facilitator
):
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)

    with pytest.raises(ReadyCheckNotReplaceable):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=backend.id,
            replacement_user=replacement_backend_user,
            technology_stack=django_stack,
            proposed_by=facilitator,
            now=backend.expires_at - timedelta(seconds=1),
        )


def test_expired_member_can_be_replaced_in_the_same_role(
    formation, replacement_backend_user, django_stack, facilitator
):
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)

    replacement = replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=backend.id,
        replacement_user=replacement_backend_user,
        technology_stack=django_stack,
        proposed_by=facilitator,
        now=backend.expires_at,
    )

    backend.refresh_from_db()
    assert backend.status == ReadyCheckStatus.EXPIRED
    assert backend.is_current is False
    assert replacement.role_id == backend.role_id
    assert replacement.status == ReadyCheckStatus.PENDING


def test_declined_member_cannot_replace_themselves(
    formation, backend_user, django_stack, facilitator
):
    backend = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=backend.id, user=backend_user)

    with pytest.raises(InvalidFormationMembers):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=backend.id,
            replacement_user=backend_user,
            technology_stack=django_stack,
            proposed_by=facilitator,
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_concurrent_confirmations_mark_formation_ready_once(formation):
    checks = list(formation.ready_checks.order_by("id"))
    confirm_ready_check(ready_check_id=checks[0].id, user=checks[0].user)
    barrier = Barrier(2)

    def confirm(check_id, user_id):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            check = ReadyCheck.objects.select_related("user").get(id=check_id)
            confirm_ready_check(ready_check_id=check.id, user=check.user)
            return "confirmed"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: confirm(*args),
                [(checks[1].id, checks[1].user_id), (checks[2].id, checks[2].user_id)],
            )
        )

    assert results == ["confirmed", "confirmed"]
    formation.refresh_from_db()
    assert formation.ready_confirmed_at is not None
    assert formation.ready_checks.filter(status=ReadyCheckStatus.CONFIRMED).count() == 3
    assert Team.objects.filter(formation=formation).count() == 1
    assert ProjectRun.objects.filter(team__formation=formation).count() == 1
    assert TeamMember.objects.filter(
        project_run__team__formation=formation
    ).count() == 3


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_same_ready_check_cannot_be_confirmed_twice_concurrently(formation):
    check = formation.ready_checks.filter(is_current=True).first()
    barrier = Barrier(2)

    def confirm():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            user = type(check.user).objects.get(id=check.user_id)
            try:
                confirm_ready_check(ready_check_id=check.id, user=user)
            except ReadyCheckNotPending:
                return "rejected"
            return "confirmed"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: confirm(), range(2)))

    assert sorted(results) == ["confirmed", "rejected"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_concurrent_formations_cannot_create_two_active_runs_for_the_same_users(
    facilitator,
    helpdesk_version,
    proposed_members,
):
    formations = [
        create_team_formation(
            project_version=helpdesk_version,
            created_by=facilitator,
            members=proposed_members,
        )
        for _ in range(2)
    ]
    final_checks = []
    for candidate in formations:
        checks = list(candidate.ready_checks.order_by("role__code"))
        for check in checks[:2]:
            confirm_ready_check(ready_check_id=check.id, user=check.user)
        final_checks.append(checks[2])

    barrier = Barrier(2)

    def confirm_final(check_id, user_id):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            check = ReadyCheck.objects.get(id=check_id, user_id=user_id)
            try:
                confirm_ready_check(ready_check_id=check.id, user=check.user)
            except MemberHasActiveProjectRun:
                return "active-run-rejected"
            return "completed"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda args: confirm_final(*args),
                [(check.id, check.user_id) for check in final_checks],
            )
        )

    assert sorted(results) == ["active-run-rejected", "completed"]
    assert Team.objects.count() == 1
    assert ProjectRun.objects.count() == 1
    assert TeamMember.objects.filter(ended_at__isnull=True).count() == 3
