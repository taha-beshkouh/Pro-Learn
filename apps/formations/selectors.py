from django.db.models import Prefetch

from apps.accounts.models import User
from apps.formations.models import ReadyCheck, TeamFormation


def _ready_checks_queryset():
    return ReadyCheck.objects.select_related(
        "user",
        "role",
        "technology_stack",
        "proposed_by",
    ).order_by("role__name", "started_at", "id")


def formation_list():
    return (
        TeamFormation.objects.select_related(
            "project_version",
            "project_version__project_template",
            "created_by",
            "team__project_run",
        )
        .prefetch_related(
            Prefetch("ready_checks", queryset=_ready_checks_queryset())
        )
        .order_by("-created_at", "id")
    )


def formation_detail(*, formation_id):
    return formation_list().get(id=formation_id)


def current_ready_checks_for_user(*, user: User):
    return (
        _ready_checks_queryset()
        .select_related(
            "formation",
            "formation__project_version",
            "formation__project_version__project_template",
        )
        .filter(user=user, is_current=True)
    )


def ready_check_detail(*, ready_check_id):
    return (
        _ready_checks_queryset()
        .select_related(
            "formation",
            "formation__project_version",
            "formation__project_version__project_template",
        )
        .get(id=ready_check_id)
    )
