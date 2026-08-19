from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.formations.exceptions import (
    InvalidFormationMembers,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
)
from apps.formations.models import ReadyCheck, ReadyCheckStatus, TeamFormation
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
