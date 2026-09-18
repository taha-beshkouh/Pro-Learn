from enum import StrEnum

from django.db.models import Q
from django.utils import timezone

from apps.formations.models import (
    ProjectReadiness,
    ProjectRunState,
    ReadyCheck,
    ReadyCheckStatus,
    TeamMember,
)


class ParticipationBlocker(StrEnum):
    ACTIVE_READINESS = "active_readiness"
    CURRENT_FORMATION_OR_READY_CHECK = "current_formation_or_ready_check"
    ACTIVE_PROJECT_RUN = "active_project_run"


def active_project_readinesses():
    return ProjectReadiness.objects.filter(consumed_at__isnull=True)


def current_unresolved_ready_checks():
    return ReadyCheck.objects.filter(
        is_current=True,
        formation__ready_confirmed_at__isnull=True,
    ).filter(
        Q(status=ReadyCheckStatus.CONFIRMED)
        | Q(status=ReadyCheckStatus.PENDING, expires_at__gt=timezone.now())
    )


def active_project_run_memberships():
    return TeamMember.objects.filter(
        ended_at__isnull=True,
        project_run__state=ProjectRunState.ACTIVE,
        project_run__ended_at__isnull=True,
    )


def participation_blocker_for_user(*, user_id) -> ParticipationBlocker | None:
    """Return the first canonical current-participation blocker for one user."""

    if active_project_readinesses().filter(user_id=user_id).exists():
        return ParticipationBlocker.ACTIVE_READINESS
    if current_unresolved_ready_checks().filter(user_id=user_id).exists():
        return ParticipationBlocker.CURRENT_FORMATION_OR_READY_CHECK
    if active_project_run_memberships().filter(user_id=user_id).exists():
        return ParticipationBlocker.ACTIVE_PROJECT_RUN
    return None
