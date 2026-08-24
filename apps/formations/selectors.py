from django.db.models import Prefetch

from apps.accounts.models import User
from apps.formations.models import (
    ProjectRun,
    ProjectRunState,
    ReadyCheck,
    SprintRun,
    SprintSubmission,
    TeamFormation,
    TeamMember,
)
from apps.projects.models import ProjectTaskTemplate


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


def _team_members_queryset():
    return TeamMember.objects.select_related(
        "user",
        "role",
        "technology_stack",
    ).order_by("role__name", "id")


def _sprint_runs_queryset():
    submissions = SprintSubmission.objects.select_related(
        "submitted_by",
        "submitted_by__user",
        "submitted_by__role",
        "submitted_by__technology_stack",
    ).order_by("submitted_at", "id")
    return (
        SprintRun.objects.select_related(
            "sprint_template",
            "designated_submitter",
            "designated_submitter__user",
            "designated_submitter__role",
            "designated_submitter__technology_stack",
        )
        .prefetch_related(Prefetch("submissions", queryset=submissions))
        .order_by("sprint_template__sequence", "id")
    )


def _project_runs_queryset():
    work_items = ProjectTaskTemplate.objects.select_related(
        "role",
        "technology_stack",
        "sprint_template",
    ).order_by("position", "id")
    return (
        ProjectRun.objects.select_related(
            "team",
            "team__formation",
            "project_version",
            "project_version__project_template",
            "project_version__project_template__level",
        )
        .prefetch_related(
            Prefetch("members", queryset=_team_members_queryset()),
            Prefetch("sprint_runs", queryset=_sprint_runs_queryset()),
            Prefetch("project_version__work_items", queryset=work_items),
        )
    )


def active_project_run_for_user(*, user: User) -> ProjectRun:
    project_run = _project_runs_queryset().get(
        state=ProjectRunState.ACTIVE,
        ended_at__isnull=True,
        members__user=user,
        members__ended_at__isnull=True,
    )
    project_run.requesting_member = next(
        member for member in project_run.members.all() if member.user_id == user.id
    )
    return project_run


def active_sprint_run_for_user(*, user: User, sprint_run_id) -> SprintRun:
    project_run = active_project_run_for_user(user=user)
    try:
        sprint_run = next(
            item for item in project_run.sprint_runs.all() if item.id == sprint_run_id
        )
    except StopIteration as exc:
        raise SprintRun.DoesNotExist from exc
    sprint_run.requesting_member = project_run.requesting_member
    sprint_run.workspace_project_run = project_run
    return sprint_run
