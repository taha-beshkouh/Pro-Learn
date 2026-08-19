from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.formations.models import ReadyCheck, ReadyCheckStatus, TeamFormation


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def set_formation_constraints_immediate():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "formations_exact_current_slots_constraint, "
            "formations_ready_check_slots_constraint, "
            "formations_ready_check_validity_constraint IMMEDIATE"
        )


def test_formation_requires_exactly_three_current_slots(
    facilitator, helpdesk_version
):
    with pytest.raises(IntegrityError), transaction.atomic():
        TeamFormation.objects.create(
            project_version=helpdesk_version,
            created_by=facilitator,
        )
        set_formation_constraints_immediate()


def test_database_rejects_non_staff_formation_creator(
    backend_user,
    helpdesk_version,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        TeamFormation.objects.create(
            project_version=helpdesk_version,
            created_by=backend_user,
        )
        set_formation_constraints_immediate()


def test_current_role_and_user_are_unique_per_formation(formation):
    existing = formation.ready_checks.filter(is_current=True).first()
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        ReadyCheck.objects.create(
            formation=formation,
            user=existing.user,
            role=existing.role,
            technology_stack=existing.technology_stack,
            proposed_by=formation.created_by,
            started_at=started_at,
            expires_at=started_at + timedelta(hours=48),
        )


def test_ready_check_expiry_must_be_exactly_48_hours(formation):
    existing = formation.ready_checks.filter(is_current=True).first()
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        existing.is_current = False
        existing.save(update_fields=["is_current"])
        ReadyCheck.objects.create(
            formation=formation,
            user=existing.user,
            role=existing.role,
            technology_stack=existing.technology_stack,
            proposed_by=formation.created_by,
            started_at=started_at,
            expires_at=started_at + timedelta(hours=47),
        )


def test_database_rejects_stack_for_stackless_role(formation, react_stack):
    designer = formation.ready_checks.get(role__code="PRODUCT_DESIGNER", is_current=True)
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        designer.status = ReadyCheckStatus.DECLINED
        designer.responded_at = started_at
        designer.is_current = False
        designer.save(update_fields=["status", "responded_at", "is_current"])
        ReadyCheck.objects.create(
            formation=formation,
            user=designer.user,
            role=designer.role,
            technology_stack=react_stack,
            proposed_by=formation.created_by,
            started_at=started_at,
            expires_at=started_at + timedelta(hours=48),
        )
        set_formation_constraints_immediate()


def test_database_rejects_role_that_differs_from_profile(
    formation,
    frontend_role,
    replacement_backend_user,
    django_stack,
    react_stack,
):
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)
    frontend = formation.ready_checks.get(role__code="FRONTEND_DEVELOPER", is_current=True)
    started_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        for current in (backend, frontend):
            current.status = ReadyCheckStatus.DECLINED
            current.responded_at = started_at
            current.is_current = False
            current.save(update_fields=["status", "responded_at", "is_current"])
        ReadyCheck.objects.create(
            formation=formation,
            user=replacement_backend_user,
            role=backend.role,
            technology_stack=django_stack,
            proposed_by=formation.created_by,
            started_at=started_at,
            expires_at=started_at + timedelta(hours=48),
        )
        ReadyCheck.objects.create(
            formation=formation,
            user=backend.user,
            role=frontend_role,
            technology_stack=react_stack,
            proposed_by=formation.created_by,
            started_at=started_at,
            expires_at=started_at + timedelta(hours=48),
        )
        set_formation_constraints_immediate()


def test_ready_confirmation_timestamp_requires_all_current_checks_confirmed(
    formation,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        formation.ready_confirmed_at = timezone.now()
        formation.save(update_fields=["ready_confirmed_at"])
        set_formation_constraints_immediate()


def test_confirmed_and_declined_statuses_require_response_timestamp(formation):
    ready_check = formation.ready_checks.filter(is_current=True).first()

    with pytest.raises(IntegrityError), transaction.atomic():
        ready_check.status = ReadyCheckStatus.CONFIRMED
        ready_check.responded_at = None
        ready_check.save(update_fields=["status", "responded_at"])


def test_ready_check_identity_snapshot_is_immutable(formation, react_stack):
    backend = formation.ready_checks.get(role__code="BACKEND_DEVELOPER", is_current=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        backend.technology_stack = react_stack
        backend.save(update_fields=["technology_stack"])
        with connection.cursor() as cursor:
            cursor.execute(
                "SET CONSTRAINTS formations_ready_check_validity_constraint IMMEDIATE"
            )


def test_only_declined_or_expired_ready_check_can_become_historical(formation):
    pending = formation.ready_checks.filter(is_current=True).first()

    with pytest.raises(IntegrityError), transaction.atomic():
        pending.is_current = False
        pending.save(update_fields=["is_current"])
        with connection.cursor() as cursor:
            cursor.execute(
                "SET CONSTRAINTS formations_ready_check_validity_constraint IMMEDIATE"
            )
