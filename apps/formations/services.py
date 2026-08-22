from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.formations.exceptions import (
    FormationAlreadyReady,
    FormationCompletionConflict,
    InvalidFormationMembers,
    InvalidFormationStack,
    MemberHasActiveProjectRun,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
    SprintAccessDenied,
    SprintRuntimeConfigurationError,
    SprintSubmissionNotAllowed,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    READY_CHECK_DURATION,
    ProjectRun,
    ReadyCheck,
    ReadyCheckStatus,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.profiles.models import Role, RoleCode, TechnologyStack, UserProfile
from apps.projects.exceptions import (
    InvalidProjectStackSelection,
    ProjectConfigurationError,
)
from apps.projects.models import ProjectRoleRequirement, ProjectVersion
from apps.projects.services import resolve_project_stack_selection


EXPECTED_ROLE_CODES = frozenset(RoleCode.values)

ALLOWED_SPRINT_TRANSITIONS = {
    SprintRunState.LOCKED: frozenset({SprintRunState.ACTIVE}),
    SprintRunState.ACTIVE: frozenset({SprintRunState.SUBMITTED}),
    SprintRunState.SUBMITTED: frozenset({SprintRunState.UNDER_REVIEW}),
    SprintRunState.UNDER_REVIEW: frozenset(
        {SprintRunState.CHANGES_REQUESTED, SprintRunState.COMPLETED}
    ),
    SprintRunState.CHANGES_REQUESTED: frozenset({SprintRunState.SUBMITTED}),
    SprintRunState.COMPLETED: frozenset(),
}


@dataclass(frozen=True)
class ProposedMember:
    user: User
    role: Role
    technology_stack: TechnologyStack | None = None


def validate_member_roles(*, role_codes) -> None:
    codes = tuple(role_codes)
    if len(codes) != 3 or len(set(codes)) != 3 or set(codes) != EXPECTED_ROLE_CODES:
        raise InvalidFormationMembers


def _profile_for_member(*, member: ProposedMember) -> UserProfile:
    try:
        profile = (
            UserProfile.objects.select_related("selected_role")
            .prefetch_related(
                "skills__technology_stack",
                "selected_role__compatible_stack_links__technology_stack",
            )
            .get(user=member.user)
        )
    except UserProfile.DoesNotExist as exc:
        raise InvalidFormationMembers from exc
    if not member.user.is_active or profile.selected_role_id != member.role.id:
        raise InvalidFormationMembers
    return profile


def _requirement_for_member(
    *, project_version: ProjectVersion, role: Role
) -> ProjectRoleRequirement:
    requirement = next(
        (
            item
            for item in project_version.role_requirements.all()
            if item.role_id == role.id
        ),
        None,
    )
    if requirement is None:
        raise InvalidFormationMembers
    return requirement


def _validated_stack_for_member(
    *,
    project_version: ProjectVersion,
    member: ProposedMember,
):
    profile = _profile_for_member(member=member)
    requirement = _requirement_for_member(
        project_version=project_version,
        role=member.role,
    )
    try:
        result = resolve_project_stack_selection(
            requirement=requirement,
            profile=profile,
            requested_stack=member.technology_stack,
            reject_invalid=True,
        )
    except InvalidProjectStackSelection as exc:
        raise InvalidFormationStack from exc
    if requirement.requires_stack and result.selected_stack is None:
        raise InvalidFormationStack
    if not requirement.requires_stack and result.selected_stack is not None:
        raise InvalidFormationStack
    return result.selected_stack


@transaction.atomic
def create_team_formation(
    *,
    project_version: ProjectVersion,
    created_by: User,
    members: list[ProposedMember],
    now=None,
) -> TeamFormation:
    now = now or timezone.now()
    if not created_by.is_active or not created_by.is_staff:
        raise InvalidFormationMembers
    validate_member_roles(role_codes=(member.role.code for member in members))
    if len({member.user.id for member in members}) != 3:
        raise InvalidFormationMembers

    project_version = (
        ProjectVersion.objects.select_for_update()
        .prefetch_related(
            "role_requirements__allowed_stacks__technology_stack",
            "role_requirements__role__compatible_stack_links__technology_stack",
        )
        .get(id=project_version.id)
    )
    if not project_version.is_published:
        raise InvalidFormationMembers
    validated_members = [
        (member, _validated_stack_for_member(project_version=project_version, member=member))
        for member in members
    ]
    formation = TeamFormation.objects.create(
        project_version=project_version,
        created_by=created_by,
        created_at=now,
    )
    ReadyCheck.objects.bulk_create(
        [
            ReadyCheck(
                formation=formation,
                user=member.user,
                role=member.role,
                technology_stack=selected_stack,
                proposed_by=created_by,
                started_at=now,
                expires_at=now + READY_CHECK_DURATION,
            )
            for member, selected_stack in validated_members
        ]
    )
    return formation


def validate_sprint_transition(*, current_state: str, target_state: str) -> None:
    if target_state not in ALLOWED_SPRINT_TRANSITIONS.get(current_state, frozenset()):
        raise SprintTransitionNotAllowed


def sprint_next_action(
    *,
    state: str | None,
    is_designated_submitter: bool,
    has_sprints: bool = True,
) -> str:
    if state is None:
        return "SPRINTS_COMPLETED" if has_sprints else "NO_SPRINT_AVAILABLE"
    if state == SprintRunState.LOCKED:
        return "WAIT_FOR_FACILITATOR"
    if state == SprintRunState.ACTIVE:
        return "SUBMIT_SPRINT" if is_designated_submitter else "COLLABORATE"
    if state in {SprintRunState.SUBMITTED, SprintRunState.UNDER_REVIEW}:
        return "WAIT_FOR_REVIEW"
    if state == SprintRunState.CHANGES_REQUESTED:
        return "RESUBMIT_SPRINT" if is_designated_submitter else "ADDRESS_CHANGES"
    return "SPRINTS_COMPLETED"


def _sprint_schedule(*, project_run: ProjectRun, sprint_template):
    planned_start_at = project_run.started_at + timedelta(
        days=sprint_template.planned_start_offset_days
    )
    planned_end_at = planned_start_at + timedelta(
        days=sprint_template.planned_duration_days
    )
    return planned_start_at, planned_end_at


def _ensure_sprint_runs_locked(*, project_run: ProjectRun) -> list[SprintRun]:
    sprint_templates = list(
        project_run.project_version.sprint_templates.order_by("sequence", "id")
    )
    existing = list(
        SprintRun.objects.select_for_update(of=("self",))
        .filter(project_run=project_run)
        .order_by("sprint_template__sequence", "id")
    )
    if existing:
        expected = {
            sprint_template.id: _sprint_schedule(
                project_run=project_run,
                sprint_template=sprint_template,
            )
            for sprint_template in sprint_templates
        }
        actual = {
            sprint_run.sprint_template_id: (
                sprint_run.planned_start_at,
                sprint_run.planned_end_at,
            )
            for sprint_run in existing
        }
        if actual != expected:
            raise SprintRuntimeConfigurationError
        return existing

    return SprintRun.objects.bulk_create(
        [
            SprintRun(
                project_run=project_run,
                sprint_template=sprint_template,
                planned_start_at=planned_start_at,
                planned_end_at=planned_end_at,
            )
            for sprint_template in sprint_templates
            for planned_start_at, planned_end_at in (
                _sprint_schedule(
                    project_run=project_run,
                    sprint_template=sprint_template,
                ),
            )
        ]
    )


@transaction.atomic
def initialize_sprint_runs(*, project_run: ProjectRun) -> list[SprintRun]:
    project_run = (
        ProjectRun.objects.select_for_update(of=("self",))
        .select_related("project_version")
        .get(id=project_run.id)
    )
    return _ensure_sprint_runs_locked(project_run=project_run)


def _ensure_team_and_project_run_locked(
    *,
    formation: TeamFormation,
    current_ready_checks: list[ReadyCheck],
    started_at,
) -> tuple[Team, ProjectRun]:
    """Complete a locked, fully confirmed formation idempotently."""

    if len(current_ready_checks) != 3 or any(
        ready_check.status != ReadyCheckStatus.CONFIRMED
        for ready_check in current_ready_checks
    ):
        raise FormationCompletionConflict

    team, _ = Team.objects.get_or_create(
        formation=formation,
        defaults={"created_at": started_at},
    )
    project_run, _ = ProjectRun.objects.get_or_create(
        team=team,
        defaults={
            "project_version_id": formation.project_version_id,
            "started_at": started_at,
        },
    )
    if (
        project_run.project_version_id != formation.project_version_id
        or project_run.started_at != started_at
        or project_run.ended_at is not None
    ):
        raise FormationCompletionConflict

    user_ids = [ready_check.user_id for ready_check in current_ready_checks]
    locked_users = list(
        User.objects.select_for_update()
        .filter(id__in=user_ids)
        .order_by("id")
        .values_list("id", "is_active")
    )
    if len(locked_users) != 3 or any(not is_active for _, is_active in locked_users):
        raise InvalidFormationMembers

    if (
        TeamMember.objects.filter(user_id__in=user_ids, ended_at__isnull=True)
        .exclude(project_run=project_run)
        .exists()
    ):
        raise MemberHasActiveProjectRun

    expected_snapshots = {
        ready_check.user_id: (
            ready_check.role_id,
            ready_check.technology_stack_id,
        )
        for ready_check in current_ready_checks
    }
    existing_members = list(
        TeamMember.objects.select_for_update()
        .filter(project_run=project_run)
        .order_by("role_id", "id")
    )
    if existing_members:
        existing_snapshots = {
            member.user_id: (member.role_id, member.technology_stack_id)
            for member in existing_members
            if member.ended_at is None
        }
        if len(existing_members) != 3 or existing_snapshots != expected_snapshots:
            raise FormationCompletionConflict
    else:
        TeamMember.objects.bulk_create(
            [
                TeamMember(
                    project_run=project_run,
                    user_id=ready_check.user_id,
                    role_id=ready_check.role_id,
                    technology_stack_id=ready_check.technology_stack_id,
                )
                for ready_check in current_ready_checks
            ]
        )
    _ensure_sprint_runs_locked(project_run=project_run)
    return team, project_run


def _respond_to_ready_check(*, ready_check_id, user: User, confirm: bool, now=None):
    now = now or timezone.now()
    expired = False
    with transaction.atomic():
        ready_check_ref = ReadyCheck.objects.only("formation_id").get(
            id=ready_check_id,
            user=user,
            is_current=True,
        )
        formation = TeamFormation.objects.select_for_update().get(
            id=ready_check_ref.formation_id
        )
        ready_check = (
            ReadyCheck.objects.select_for_update()
            .select_related("formation")
            .get(
                id=ready_check_id,
                formation=formation,
                user=user,
                is_current=True,
            )
        )
        if ready_check.status != ReadyCheckStatus.PENDING:
            raise ReadyCheckNotPending
        if now >= ready_check.expires_at:
            ready_check.status = ReadyCheckStatus.EXPIRED
            ready_check.save(update_fields=["status"])
            expired = True
        else:
            ready_check.status = (
                ReadyCheckStatus.CONFIRMED if confirm else ReadyCheckStatus.DECLINED
            )
            ready_check.responded_at = now
            ready_check.save(update_fields=["status", "responded_at"])
            if confirm:
                current_ready_checks = list(
                    ReadyCheck.objects.select_for_update()
                    .filter(formation=formation, is_current=True)
                    .order_by("role_id", "id")
                )
                if all(
                    current.status == ReadyCheckStatus.CONFIRMED
                    for current in current_ready_checks
                ):
                    if formation.ready_confirmed_at is None:
                        formation.ready_confirmed_at = now
                        formation.save(
                            update_fields=["ready_confirmed_at", "updated_at"]
                        )
                    _ensure_team_and_project_run_locked(
                        formation=formation,
                        current_ready_checks=current_ready_checks,
                        started_at=formation.ready_confirmed_at,
                    )
    if expired:
        raise ReadyCheckExpired
    return ready_check


def confirm_ready_check(*, ready_check_id, user: User, now=None) -> ReadyCheck:
    return _respond_to_ready_check(
        ready_check_id=ready_check_id,
        user=user,
        confirm=True,
        now=now,
    )


def decline_ready_check(*, ready_check_id, user: User, now=None) -> ReadyCheck:
    return _respond_to_ready_check(
        ready_check_id=ready_check_id,
        user=user,
        confirm=False,
        now=now,
    )


@transaction.atomic
def replace_ready_check_member(
    *,
    formation_id,
    ready_check_id,
    replacement_user: User,
    technology_stack,
    proposed_by: User,
    now=None,
) -> ReadyCheck:
    now = now or timezone.now()
    formation = TeamFormation.objects.select_for_update().get(id=formation_id)
    if not proposed_by.is_active or not proposed_by.is_staff:
        raise InvalidFormationMembers
    if formation.ready_confirmed_at is not None:
        raise FormationAlreadyReady
    current = (
        ReadyCheck.objects.select_for_update()
        .select_related("role", "user")
        .get(id=ready_check_id, formation=formation, is_current=True)
    )
    if current.status == ReadyCheckStatus.PENDING and now >= current.expires_at:
        current.status = ReadyCheckStatus.EXPIRED
        current.save(update_fields=["status"])
    if current.status not in {ReadyCheckStatus.DECLINED, ReadyCheckStatus.EXPIRED}:
        raise ReadyCheckNotReplaceable
    if replacement_user.id == current.user_id:
        raise InvalidFormationMembers
    if ReadyCheck.objects.filter(
        formation=formation,
        user=replacement_user,
        is_current=True,
    ).exclude(id=current.id).exists():
        raise InvalidFormationMembers

    project_version = (
        ProjectVersion.objects.select_for_update()
        .prefetch_related(
            "role_requirements__allowed_stacks__technology_stack",
            "role_requirements__role__compatible_stack_links__technology_stack",
        )
        .get(id=formation.project_version_id)
    )
    member = ProposedMember(
        user=replacement_user,
        role=current.role,
        technology_stack=technology_stack,
    )
    selected_stack = _validated_stack_for_member(
        project_version=project_version,
        member=member,
    )
    current.is_current = False
    current.save(update_fields=["is_current"])
    return ReadyCheck.objects.create(
        formation=formation,
        user=replacement_user,
        role=current.role,
        technology_stack=selected_stack,
        proposed_by=proposed_by,
        started_at=now,
        expires_at=now + READY_CHECK_DURATION,
    )


def _locked_sprint_run(*, sprint_run_id, project_run_id=None):
    sprint_ref = SprintRun.objects.only("project_run_id").get(id=sprint_run_id)
    if project_run_id is not None and sprint_ref.project_run_id != project_run_id:
        raise SprintRun.DoesNotExist
    # Lock parent then child; nullable response relations must stay outside this query.
    project_run = ProjectRun.objects.select_for_update(of=("self",)).get(
        id=sprint_ref.project_run_id
    )
    sprint_run = (
        SprintRun.objects.select_for_update(of=("self",))
        .select_related("sprint_template")
        .get(id=sprint_run_id, project_run=project_run)
    )
    if project_run.ended_at is not None:
        raise SprintTransitionNotAllowed
    return project_run, sprint_run


def _require_active_staff(*, actor: User) -> None:
    if not actor.is_active or not actor.is_staff:
        raise SprintAccessDenied


@transaction.atomic
def open_sprint(
    *,
    sprint_run_id,
    designated_submitter_id,
    actor: User,
    project_run_id=None,
    now=None,
) -> SprintRun:
    _require_active_staff(actor=actor)
    now = now or timezone.now()
    project_run, sprint_run = _locked_sprint_run(
        sprint_run_id=sprint_run_id,
        project_run_id=project_run_id,
    )
    validate_sprint_transition(
        current_state=sprint_run.state,
        target_state=SprintRunState.ACTIVE,
    )
    if SprintRun.objects.filter(
        project_run=project_run,
        sprint_template__sequence__lt=sprint_run.sprint_template.sequence,
    ).exclude(state=SprintRunState.COMPLETED).exists():
        raise SprintTransitionNotAllowed
    try:
        designated_submitter = TeamMember.objects.select_for_update(of=("self",)).get(
            id=designated_submitter_id,
            project_run=project_run,
            ended_at__isnull=True,
        )
    except TeamMember.DoesNotExist as exc:
        raise SprintSubmissionNotAllowed from exc
    sprint_run.state = SprintRunState.ACTIVE
    sprint_run.designated_submitter = designated_submitter
    sprint_run.opened_at = now
    sprint_run.save(
        update_fields=["state", "designated_submitter", "opened_at", "updated_at"]
    )
    return sprint_run


@transaction.atomic
def submit_sprint(
    *,
    sprint_run_id,
    user: User,
    evidence: str = "",
    project_run_id=None,
    now=None,
) -> tuple[SprintRun, SprintSubmission]:
    now = now or timezone.now()
    project_run, sprint_run = _locked_sprint_run(
        sprint_run_id=sprint_run_id,
        project_run_id=project_run_id,
    )
    try:
        member = TeamMember.objects.select_for_update(of=("self",)).get(
            project_run=project_run,
            user=user,
            ended_at__isnull=True,
        )
    except TeamMember.DoesNotExist as exc:
        raise SprintAccessDenied from exc
    if sprint_run.designated_submitter_id != member.id:
        raise SprintSubmissionNotAllowed
    validate_sprint_transition(
        current_state=sprint_run.state,
        target_state=SprintRunState.SUBMITTED,
    )
    submission = SprintSubmission.objects.create(
        sprint_run=sprint_run,
        submitted_by=member,
        evidence=evidence,
        submitted_at=now,
    )
    sprint_run.state = SprintRunState.SUBMITTED
    sprint_run.save(update_fields=["state", "updated_at"])
    return sprint_run, submission


def _staff_transition_sprint(
    *,
    sprint_run_id,
    target_state: str,
    actor: User,
    project_run_id=None,
    now=None,
) -> SprintRun:
    _require_active_staff(actor=actor)
    now = now or timezone.now()
    _, sprint_run = _locked_sprint_run(
        sprint_run_id=sprint_run_id,
        project_run_id=project_run_id,
    )
    validate_sprint_transition(
        current_state=sprint_run.state,
        target_state=target_state,
    )
    sprint_run.state = target_state
    update_fields = ["state", "updated_at"]
    if target_state == SprintRunState.COMPLETED:
        sprint_run.completed_at = now
        update_fields.append("completed_at")
    sprint_run.save(update_fields=update_fields)
    return sprint_run


@transaction.atomic
def mark_sprint_under_review(**kwargs) -> SprintRun:
    return _staff_transition_sprint(
        target_state=SprintRunState.UNDER_REVIEW,
        **kwargs,
    )


@transaction.atomic
def request_sprint_changes(**kwargs) -> SprintRun:
    return _staff_transition_sprint(
        target_state=SprintRunState.CHANGES_REQUESTED,
        **kwargs,
    )


@transaction.atomic
def complete_sprint(**kwargs) -> SprintRun:
    return _staff_transition_sprint(
        target_state=SprintRunState.COMPLETED,
        **kwargs,
    )
