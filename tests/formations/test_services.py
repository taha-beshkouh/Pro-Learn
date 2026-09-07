from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.formations.exceptions import (
    InvalidFormationMembers,
    InvalidFormationReadiness,
    MemberHasActiveProjectRun,
    MemberHasUnresolvedFormation,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ReadyCheck,
    ReadyCheckStatus,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.profiles.models import UserProfile, UserSkill
from apps.formations.services import (
    confirm_ready_check,
    create_team_formation,
    decline_ready_check,
    replace_ready_check_member,
)


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("response_service", [confirm_ready_check, decline_ready_check])
@pytest.mark.django_db(transaction=True)
def test_inactive_member_cannot_respond_to_ready_check(
    formation,
    backend_user,
    response_service,
):
    ready_check = formation.ready_checks.get(user=backend_user)
    backend_user.is_active = False
    backend_user.save(update_fields=["is_active"])

    with pytest.raises(InvalidFormationMembers):
        response_service(ready_check_id=ready_check.id, user=backend_user)

    ready_check.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.PENDING
    assert ready_check.responded_at is None


def test_create_formation_has_exact_roles_stacks_and_48_hour_ready_checks(
    facilitator, helpdesk_version, proposed_members
):
    now = timezone.now()
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in proposed_members],
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


def test_create_formation_rejects_duplicate_readiness_ids(
    facilitator, helpdesk_version, proposed_members
):
    readiness_ids = [readiness.id for readiness in proposed_members]
    readiness_ids[1] = readiness_ids[0]

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids,
        )
    assert TeamFormation.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_create_formation_rechecks_locked_project_version_publication(
    facilitator,
    helpdesk_version,
    proposed_members,
):
    type(helpdesk_version).objects.filter(id=helpdesk_version.id).update(
        published_at=None
    )

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=[readiness.id for readiness in proposed_members],
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_team_members_snapshot_role_and_selected_stack(
    formation,
    backend_user,
    frontend_role,
):
    ready_check_snapshots = {
        check.user_id: (check.role_id, check.technology_stack_id)
        for check in formation.ready_checks.filter(is_current=True)
    }

    for check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    members = {
        member.user_id: (member.role_id, member.technology_stack_id)
        for member in TeamMember.objects.filter(
            project_run__team__formation=formation
        )
    }
    assert members == ready_check_snapshots
    assert members[
        formation.ready_checks.get(role__code="PRODUCT_DESIGNER").user_id
    ][1] is None

    backend_profile = UserProfile.objects.get(user=backend_user)
    selected_stack_id = ready_check_snapshots[backend_user.id][1]
    skill = UserSkill.objects.create(
        profile=backend_profile,
        technology_stack_id=selected_stack_id,
    )
    skill.delete()
    UserProfile.objects.filter(user=backend_user).update(selected_role=frontend_role)
    backend_ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    backend_membership = TeamMember.objects.get(user=backend_user)
    assert backend_ready_check.role_id == ready_check_snapshots[backend_user.id][0]
    assert backend_membership.role_id == ready_check_snapshots[backend_user.id][0]
    assert backend_membership.technology_stack_id == ready_check_snapshots[
        backend_user.id
    ][1]


def test_active_project_run_users_cannot_enter_a_new_formation(
    formation,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    for check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=check.id, user=check.user)

    second_readinesses = [
        ProjectReadiness.objects.create(
            user=readiness.user,
            role=readiness.role,
            project_version=readiness.project_version,
            technology_stack=readiness.technology_stack,
        )
        for readiness in proposed_members
    ]

    with pytest.raises(MemberHasActiveProjectRun):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=[readiness.id for readiness in second_readinesses],
        )

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
    readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=backend.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    replacement = replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=backend.id,
        replacement_readiness_id=readiness.id,
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
    readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=backend.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    with pytest.raises(ReadyCheckNotReplaceable):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=backend.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
            now=backend.expires_at - timedelta(seconds=1),
        )


def test_expired_member_can_be_replaced_in_the_same_role(
    formation, replacement_backend_user, django_stack, facilitator
):
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)
    readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=backend.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    replacement = replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=backend.id,
        replacement_readiness_id=readiness.id,
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
    readiness = ProjectReadiness.objects.create(
        user=backend_user,
        role=backend.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    with pytest.raises(MemberHasUnresolvedFormation):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=backend.id,
            replacement_readiness_id=readiness.id,
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
def test_concurrent_formations_cannot_consume_the_same_readinesses_twice(
    facilitator,
    helpdesk_version,
    proposed_members,
):
    barrier = Barrier(2)
    readiness_ids = [readiness.id for readiness in proposed_members]

    def create_once():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            actor = type(facilitator).objects.get(id=facilitator.id)
            try:
                create_team_formation(
                    created_by=actor,
                    readiness_ids=readiness_ids,
                )
            except (InvalidFormationReadiness, MemberHasUnresolvedFormation):
                return "rejected"
            return "created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create_once(), range(2)))

    assert sorted(results) == ["created", "rejected"]
    assert TeamFormation.objects.count() == 1
    assert ReadyCheck.objects.filter(is_current=True).count() == 3
    assert ProjectReadiness.objects.filter(consumed_at__isnull=False).count() == 3
