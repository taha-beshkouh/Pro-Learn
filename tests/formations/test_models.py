from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.formations.models import (
    ProjectRun,
    ReadyCheck,
    ReadyCheckStatus,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.formations.services import confirm_ready_check, create_team_formation
from apps.projects.models import ProjectVersion


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def set_formation_constraints_immediate():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "formations_exact_current_slots_constraint, "
            "formations_ready_check_slots_constraint, "
            "formations_ready_check_validity_constraint IMMEDIATE"
        )


def set_completion_constraints_immediate():
    with connection.cursor() as cursor:
        cursor.execute(
            "SET CONSTRAINTS "
            "formations_completion_formation_constraint, "
            "formations_completion_team_constraint, "
            "formations_completion_run_constraint, "
            "formations_completion_member_constraint IMMEDIATE"
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


def test_database_rejects_team_before_full_ready_check(formation):
    with pytest.raises(IntegrityError), transaction.atomic():
        Team.objects.create(formation=formation)
        set_completion_constraints_immediate()


def test_database_requires_exact_team_member_snapshots(formation, react_stack):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    backend_member = TeamMember.objects.get(
        project_run__team__formation=formation,
        role__code="BACKEND_DEVELOPER",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        backend_member.technology_stack = react_stack
        backend_member.save(update_fields=["technology_stack"])
        set_completion_constraints_immediate()


def test_database_requires_exactly_three_team_members(formation):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    member = TeamMember.objects.filter(
        project_run__team__formation=formation
    ).first()

    with pytest.raises(IntegrityError), transaction.atomic():
        member.delete()
        set_completion_constraints_immediate()


def test_database_keeps_project_run_on_formation_project_version(
    formation,
    helpdesk_version,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    project_run = ProjectRun.objects.get(team__formation=formation)
    another_version = ProjectVersion.objects.create(
        project_template=helpdesk_version.project_template,
        version_number=helpdesk_version.version_number + 1,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        project_run.project_version = another_version
        project_run.save(update_fields=["project_version"])
        set_completion_constraints_immediate()


def test_database_enforces_one_active_project_run_per_user(
    formation,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    active_member = TeamMember.objects.select_related("role").first()
    second_formation = create_team_formation(
        project_version=helpdesk_version,
        created_by=facilitator,
        members=proposed_members,
    )

    with pytest.raises(IntegrityError) as exc_info, transaction.atomic():
        second_team = Team.objects.create(formation=second_formation)
        second_run = ProjectRun.objects.create(
            team=second_team,
            project_version=helpdesk_version,
            started_at=timezone.now(),
        )
        TeamMember.objects.create(
            project_run=second_run,
            user=active_member.user,
            role=active_member.role,
            technology_stack=active_member.technology_stack,
        )

    assert "formations_active_run_user_unique" in str(exc_info.value)
