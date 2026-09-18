from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.accounts.models import User
from apps.formations.eligibility import (
    active_project_readinesses,
    active_project_run_memberships,
    current_unresolved_ready_checks,
)
from apps.formations.exceptions import (
    ActiveProjectReadinessExists,
    DesignWorkspaceAccessDenied,
    DesignWorkspaceRequired,
    FormationAlreadyReady,
    FormationCompletionConflict,
    InvalidFormationMembers,
    InvalidFormationReadiness,
    InvalidFormationStack,
    InvalidGithubUsername,
    InvalidDesignWorkspaceUrl,
    InvalidDeploymentUrl,
    InvalidFinalCommitUrl,
    InvalidReviewFeedback,
    InvalidProjectReadinessSelection,
    InvalidRepositoryUrl,
    MemberHasActiveProjectRun,
    MemberHasUnresolvedFormation,
    ProjectRunDeadlineNotReached,
    ProjectRunRepositoryRequired,
    ProjectRunTransitionNotAllowed,
    ReadyCheckExpired,
    GithubUsernameRequired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
    RepositoryAlreadyAssigned,
    SprintAccessDenied,
    SprintDeadlinePassed,
    SprintRuntimeConfigurationError,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    READY_CHECK_DURATION,
    ProjectReadiness,
    ProjectRun,
    ProjectRunState,
    ReadyCheck,
    ReadyCheckStatus,
    ReviewDecision,
    ReviewDecisionType,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.profiles.models import (
    Role,
    RoleCode,
    TechnologyStack,
    UserProfile,
    UserSkill,
)
from apps.profiles.validators import validate_github_username
from apps.projects.exceptions import (
    InvalidProjectStackSelection,
    ProjectConfigurationError,
)
from apps.projects.models import ProjectRoleRequirement, ProjectVersion, SprintTemplate
from apps.projects.services import (
    authenticated_stack_selection_from_session,
    resolve_project_stack_selection,
)


EXPECTED_ROLE_CODES = frozenset(RoleCode.values)
GITHUB_REQUIRED_ROLE_CODES = frozenset(
    {RoleCode.BACKEND_DEVELOPER, RoleCode.FRONTEND_DEVELOPER}
)

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

SPRINT_SUBMISSION_SOURCE_STATES = frozenset(
    {
        SprintRunState.ACTIVE,
        SprintRunState.SUBMITTED,
        SprintRunState.CHANGES_REQUESTED,
    }
)


def _selection_uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidProjectReadinessSelection from exc


def _locked_readiness_profile(*, user: User) -> UserProfile:
    try:
        return (
            UserProfile.objects.select_for_update(of=("self",))
            .select_related("selected_role")
            .prefetch_related(
                Prefetch(
                    "skills",
                    queryset=UserSkill.objects.select_for_update(
                        of=("self",)
                    )
                    .select_related("technology_stack")
                    .order_by("technology_stack__name"),
                )
            )
            .get(user=user)
        )
    except UserProfile.DoesNotExist as exc:
        raise InvalidProjectReadinessSelection from exc


def _confirmed_readiness_selection_ids(
    *, user: User, session
) -> tuple[UUID, UUID | None]:
    selection = authenticated_stack_selection_from_session(session=session)
    required_keys = {"user_id", "project_version_id", "selected_stack_id"}
    if not required_keys.issubset(selection):
        raise InvalidProjectReadinessSelection
    if _selection_uuid(selection["user_id"]) != user.id:
        raise InvalidProjectReadinessSelection

    project_version_id = _selection_uuid(selection["project_version_id"])
    raw_stack_id = selection["selected_stack_id"]
    selected_stack_id = (
        _selection_uuid(raw_stack_id) if raw_stack_id is not None else None
    )
    return project_version_id, selected_stack_id


def _validated_readiness_snapshot(
    *,
    profile: UserProfile,
    project_version: ProjectVersion,
    selected_stack_id: UUID | None,
) -> tuple[Role, TechnologyStack | None]:
    role = profile.selected_role
    if role is None:
        raise InvalidProjectReadinessSelection
    try:
        requirement = (
            ProjectRoleRequirement.objects.select_related("role")
            .prefetch_related(
                "allowed_stacks__technology_stack",
                "role__compatible_stack_links__technology_stack",
            )
            .get(project_version=project_version, role=role)
        )
    except ProjectRoleRequirement.DoesNotExist as exc:
        raise InvalidProjectReadinessSelection from exc

    selected_stack = None
    if selected_stack_id is not None:
        try:
            selected_stack = TechnologyStack.objects.get(id=selected_stack_id)
        except TechnologyStack.DoesNotExist as exc:
            raise InvalidProjectReadinessSelection from exc

    try:
        result = resolve_project_stack_selection(
            requirement=requirement,
            profile=profile,
            requested_stack=selected_stack,
            reject_invalid=True,
        )
    except InvalidProjectStackSelection as exc:
        raise InvalidProjectReadinessSelection from exc
    if requirement.requires_stack:
        if (
            selected_stack is None
            or result.selected_stack is None
            or result.selected_stack.id != selected_stack.id
        ):
            raise InvalidProjectReadinessSelection
    elif selected_stack is not None or result.selected_stack is not None:
        raise InvalidProjectReadinessSelection
    return role, result.selected_stack


@transaction.atomic
def create_project_readiness(*, user: User, session) -> ProjectReadiness:
    """Persist one exact-version readiness from the Phase 1 confirmation."""

    if not user.is_authenticated:
        raise InvalidProjectReadinessSelection
    project_version_id, selected_stack_id = _confirmed_readiness_selection_ids(
        user=user,
        session=session,
    )
    # Match ProjectRun startup's ProjectVersion -> user lock order.
    try:
        project_version = (
            ProjectVersion.objects.select_for_update(of=("self",)).get(
                id=project_version_id,
                published_at__isnull=False,
            )
        )
    except ProjectVersion.DoesNotExist as exc:
        raise InvalidProjectReadinessSelection from exc

    locked_user = User.objects.select_for_update().get(id=user.id)
    if not locked_user.is_active:
        raise InvalidProjectReadinessSelection

    if active_project_readinesses().filter(
        user=locked_user,
    ).exists():
        raise ActiveProjectReadinessExists

    if current_unresolved_ready_checks().filter(
        user=locked_user,
    ).exists():
        raise MemberHasUnresolvedFormation

    if active_project_run_memberships().filter(
        user=locked_user,
    ).exists():
        raise MemberHasActiveProjectRun

    profile = _locked_readiness_profile(user=locked_user)
    role, selected_stack = _validated_readiness_snapshot(
        profile=profile,
        project_version=project_version,
        selected_stack_id=selected_stack_id,
    )

    try:
        with transaction.atomic():
            return ProjectReadiness.objects.create(
                user=locked_user,
                role=role,
                project_version=project_version,
                technology_stack=selected_stack,
            )
    except IntegrityError as exc:
        if active_project_readinesses().filter(
            user=locked_user,
        ).exists():
            raise ActiveProjectReadinessExists from exc
        raise


def validate_member_roles(*, role_codes) -> None:
    codes = tuple(role_codes)
    if len(codes) != 3 or len(set(codes)) != 3 or set(codes) != EXPECTED_ROLE_CODES:
        raise InvalidFormationMembers


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


def _formation_readiness_uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidFormationReadiness from exc


def _normalized_formation_readiness_ids(*, readiness_ids, expected_count: int):
    ids = tuple(_formation_readiness_uuid(value) for value in readiness_ids)
    if len(ids) != expected_count or len(set(ids)) != expected_count:
        raise InvalidFormationReadiness
    return tuple(sorted(ids, key=str))


def _locked_formation_profiles(*, user_ids) -> dict:
    profiles = list(
        UserProfile.objects.select_for_update(of=("self",))
        .select_related("selected_role")
        .prefetch_related(
            Prefetch(
                "skills",
                queryset=UserSkill.objects.select_for_update(of=("self",))
                .select_related("technology_stack")
                .order_by("profile_id", "technology_stack__name", "id"),
            )
        )
        .filter(user_id__in=user_ids)
        .order_by("user_id")
    )
    if len(profiles) != len(user_ids):
        raise InvalidFormationMembers
    return {profile.user_id: profile for profile in profiles}


def _validated_stack_for_readiness(
    *,
    project_version: ProjectVersion,
    readiness: ProjectReadiness,
    profile: UserProfile,
):
    requirement = _requirement_for_member(
        project_version=project_version,
        role=readiness.role,
    )
    try:
        result = resolve_project_stack_selection(
            requirement=requirement,
            profile=profile,
            requested_stack=readiness.technology_stack,
            reject_invalid=True,
        )
    except InvalidProjectStackSelection as exc:
        raise InvalidFormationStack from exc
    if requirement.requires_stack and (
        readiness.technology_stack is None
        or result.selected_stack is None
        or result.selected_stack.id != readiness.technology_stack_id
    ):
        raise InvalidFormationStack
    if not requirement.requires_stack and (
        readiness.technology_stack is not None or result.selected_stack is not None
    ):
        raise InvalidFormationStack
    return result.selected_stack


def _locked_valid_formation_readinesses(
    *,
    readiness_ids,
    expected_count: int,
    expected_project_version_id=None,
) -> tuple[ProjectVersion, list[ProjectReadiness]]:
    """Lock and revalidate authoritative readiness snapshots.

    Shared participation lock order is exact ProjectVersion(s), users in UUID
    order, profiles/skills in user order, then readiness rows in UUID order.
    Callers that already own a Formation lock take that parent lock first.
    """

    normalized_ids = _normalized_formation_readiness_ids(
        readiness_ids=readiness_ids,
        expected_count=expected_count,
    )
    references = list(
        ProjectReadiness.objects.filter(id__in=normalized_ids)
        .order_by("id")
        .values("id", "user_id", "project_version_id")
    )
    if len(references) != expected_count:
        raise InvalidFormationReadiness
    reference_user_ids = {item["id"]: item["user_id"] for item in references}

    project_version_ids = {item["project_version_id"] for item in references}
    if expected_project_version_id is not None:
        project_version_ids.add(expected_project_version_id)
    locked_versions = list(
        ProjectVersion.objects.select_for_update(of=("self",))
        .filter(id__in=project_version_ids)
        .prefetch_related(
            "role_requirements__allowed_stacks__technology_stack",
            "role_requirements__role__compatible_stack_links__technology_stack",
        )
        .order_by("id")
    )
    reference_version_ids = {item["project_version_id"] for item in references}
    if (
        len(locked_versions) != len(project_version_ids)
        or len(reference_version_ids) != 1
    ):
        raise InvalidFormationReadiness
    reference_version_id = next(iter(reference_version_ids))
    project_version = next(
        (
            version
            for version in locked_versions
            if version.id == reference_version_id
        ),
        None,
    )
    if (
        project_version is None
        or not project_version.is_published
        or (
            expected_project_version_id is not None
            and project_version.id != expected_project_version_id
        )
    ):
        raise InvalidFormationReadiness

    user_ids = {item["user_id"] for item in references}
    locked_users = list(
        User.objects.select_for_update(of=("self",))
        .filter(id__in=user_ids)
        .order_by("id")
    )
    if len(locked_users) != expected_count or any(
        not user.is_active for user in locked_users
    ):
        raise InvalidFormationMembers
    profiles = _locked_formation_profiles(user_ids=user_ids)

    readinesses = list(
        ProjectReadiness.objects.select_for_update(of=("self",))
        .select_related("role", "technology_stack")
        .filter(id__in=normalized_ids)
        .order_by("id")
    )
    if (
        len(readinesses) != expected_count
        or any(readiness.consumed_at is not None for readiness in readinesses)
        or len({readiness.user_id for readiness in readinesses}) != expected_count
        or any(
            readiness.user_id != reference_user_ids[readiness.id]
            for readiness in readinesses
        )
        or any(
            readiness.project_version_id != project_version.id
            for readiness in readinesses
        )
    ):
        raise InvalidFormationReadiness

    if current_unresolved_ready_checks().filter(
        user_id__in=user_ids,
    ).exists():
        raise MemberHasUnresolvedFormation
    if active_project_run_memberships().filter(
        user_id__in=user_ids,
    ).exists():
        raise MemberHasActiveProjectRun

    for readiness in readinesses:
        profile = profiles[readiness.user_id]
        if profile.selected_role_id != readiness.role_id:
            raise InvalidFormationMembers
        _validated_stack_for_readiness(
            project_version=project_version,
            readiness=readiness,
            profile=profile,
        )
    return project_version, readinesses


def _consume_locked_readinesses(*, readinesses) -> None:
    readiness_ids = [readiness.id for readiness in readinesses]
    updated = ProjectReadiness.objects.filter(
        id__in=readiness_ids,
        consumed_at__isnull=True,
    ).update(consumed_at=timezone.now())
    if updated != len(readiness_ids):
        raise InvalidFormationReadiness


@transaction.atomic
def create_team_formation(
    *,
    created_by: User,
    readiness_ids,
    now=None,
) -> TeamFormation:
    now = now or timezone.now()
    if not created_by.is_active or not created_by.is_staff:
        raise InvalidFormationMembers
    project_version, readinesses = _locked_valid_formation_readinesses(
        readiness_ids=readiness_ids,
        expected_count=3,
    )
    validate_member_roles(role_codes=(item.role.code for item in readinesses))
    formation = TeamFormation.objects.create(
        project_version=project_version,
        created_by=created_by,
        created_at=now,
    )
    ReadyCheck.objects.bulk_create(
        [
            ReadyCheck(
                formation=formation,
                user_id=readiness.user_id,
                role_id=readiness.role_id,
                technology_stack_id=readiness.technology_stack_id,
                proposed_by=created_by,
                started_at=now,
                expires_at=now + READY_CHECK_DURATION,
            )
            for readiness in readinesses
        ]
    )
    _consume_locked_readinesses(readinesses=readinesses)
    return formation


def validate_sprint_transition(*, current_state: str, target_state: str) -> None:
    if target_state not in ALLOWED_SPRINT_TRANSITIONS.get(current_state, frozenset()):
        raise SprintTransitionNotAllowed


def project_run_deadline(*, started_at, duration_weeks: int):
    if not duration_weeks or duration_weeks < 1:
        raise SprintRuntimeConfigurationError
    return started_at + timedelta(weeks=duration_weeks)


def submission_deadline_passed(*, now, deadline_at) -> bool:
    return now >= deadline_at


def sprint_next_action(
    *,
    state: str | None,
    has_sprints: bool = True,
) -> str:
    if state is None:
        return "SPRINTS_COMPLETED" if has_sprints else "NO_SPRINT_AVAILABLE"
    if state == SprintRunState.LOCKED:
        return "WAIT_FOR_FACILITATOR"
    if state == SprintRunState.ACTIVE:
        return "SUBMIT_SPRINT"
    if state in {SprintRunState.SUBMITTED, SprintRunState.UNDER_REVIEW}:
        return "WAIT_FOR_REVIEW"
    if state == SprintRunState.CHANGES_REQUESTED:
        return "RESUBMIT_SPRINT"
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


def _activate_initial_sprint_for_new_project_run(
    *,
    project_run: ProjectRun,
    sprint_runs: list[SprintRun],
) -> None:
    if not sprint_runs:
        return

    initial_sprint = sprint_runs[0]
    if (
        initial_sprint.state != SprintRunState.LOCKED
        or initial_sprint.opened_at is not None
    ):
        raise SprintRuntimeConfigurationError

    initial_sprint.state = SprintRunState.ACTIVE
    initial_sprint.opened_at = project_run.started_at
    initial_sprint.save(update_fields=["state", "opened_at", "updated_at"])


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

    project_version = ProjectVersion.objects.select_for_update(of=("self",)).get(
        id=formation.project_version_id
    )
    deadline_at = project_run_deadline(
        started_at=started_at,
        duration_weeks=project_version.duration_weeks,
    )

    team, _ = Team.objects.get_or_create(
        formation=formation,
        defaults={"created_at": started_at},
    )
    project_run, project_run_created = ProjectRun.objects.get_or_create(
        team=team,
        defaults={
            "project_version_id": formation.project_version_id,
            "state": ProjectRunState.ACTIVE,
            "started_at": started_at,
            "deadline_at": deadline_at,
        },
    )
    if (
        project_run.project_version_id != formation.project_version_id
        or project_run.state != ProjectRunState.ACTIVE
        or project_run.started_at != started_at
        or project_run.deadline_at != deadline_at
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
    sprint_runs = _ensure_sprint_runs_locked(project_run=project_run)
    if project_run_created:
        _activate_initial_sprint_for_new_project_run(
            project_run=project_run,
            sprint_runs=sprint_runs,
        )
    return team, project_run


def _github_username_for_confirmation(
    *, ready_check: ReadyCheck, user: User, supplied_username: str | None
) -> str | None:
    locked_user = User.objects.select_for_update(of=("self",)).get(id=user.id)
    if not locked_user.is_active:
        raise InvalidFormationMembers
    profile = UserProfile.objects.select_for_update(of=("self",)).get(
        user=locked_user
    )
    if supplied_username == "":
        raise InvalidGithubUsername
    candidate = (
        supplied_username
        if supplied_username is not None
        else profile.github_username
    )
    if candidate:
        try:
            validate_github_username(candidate)
        except DjangoValidationError as exc:
            raise InvalidGithubUsername from exc
    elif ready_check.role.code in GITHUB_REQUIRED_ROLE_CODES:
        raise GithubUsernameRequired

    if supplied_username is not None and supplied_username != profile.github_username:
        profile.github_username = supplied_username
        profile.save(update_fields=["github_username", "updated_at"])
    return candidate


def _respond_to_ready_check(
    *,
    ready_check_id,
    user: User,
    confirm: bool,
    github_username: str | None = None,
    now=None,
):
    if not user.is_active:
        raise InvalidFormationMembers
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
            .select_related("formation", "role")
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
            if confirm:
                _github_username_for_confirmation(
                    ready_check=ready_check,
                    user=user,
                    supplied_username=github_username,
                )
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


def confirm_ready_check(
    *, ready_check_id, user: User, github_username: str | None = None, now=None
) -> ReadyCheck:
    return _respond_to_ready_check(
        ready_check_id=ready_check_id,
        user=user,
        confirm=True,
        github_username=github_username,
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
    replacement_readiness_id,
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
    _, readinesses = _locked_valid_formation_readinesses(
        readiness_ids=(replacement_readiness_id,),
        expected_count=1,
        expected_project_version_id=formation.project_version_id,
    )
    readiness = readinesses[0]
    if readiness.user_id == current.user_id or readiness.role_id != current.role_id:
        raise InvalidFormationMembers
    current.is_current = False
    current.save(update_fields=["is_current"])
    replacement = ReadyCheck.objects.create(
        formation=formation,
        user_id=readiness.user_id,
        role_id=readiness.role_id,
        technology_stack_id=readiness.technology_stack_id,
        proposed_by=proposed_by,
        started_at=now,
        expires_at=now + READY_CHECK_DURATION,
    )
    _consume_locked_readinesses(readinesses=readinesses)
    return replacement


@transaction.atomic
def update_project_run_repository(
    *, project_run_id, actor: User, repository_url: str | None
) -> ProjectRun:
    _require_active_staff(actor=actor)
    if repository_url is None or not repository_url.strip():
        normalized_url = None
        repository_identity = None
    else:
        normalized_url, repository_identity = _repository_url_identity(repository_url)
    # This operational endpoint is infrequent. Locking existing ProjectRuns in a
    # stable order serializes competing assignments made through this service.
    project_runs = list(
        ProjectRun.objects.select_for_update(of=("self",))
        .only("id", "state", "ended_at", "repository_url")
        .order_by("id")
    )
    try:
        project_run = next(
            item
            for item in project_runs
            if (
                item.id == project_run_id
                and item.state == ProjectRunState.ACTIVE
                and item.ended_at is None
            )
        )
    except StopIteration as exc:
        raise ProjectRun.DoesNotExist from exc

    if repository_identity is not None:
        for existing_run in project_runs:
            if existing_run.id == project_run.id or not existing_run.repository_url:
                continue
            try:
                _, existing_identity = _repository_url_identity(
                    existing_run.repository_url
                )
            except InvalidRepositoryUrl:
                # Historical invalid values are outside this write contract; they must
                # not prevent Staff from correcting another ProjectRun.
                continue
            if existing_identity == repository_identity:
                raise RepositoryAlreadyAssigned

    project_run.repository_url = normalized_url
    try:
        project_run.save(update_fields=["repository_url"])
    except IntegrityError as exc:
        if normalized_url is not None and _is_repository_unique_conflict(exc):
            raise RepositoryAlreadyAssigned from exc
        raise
    return project_run


def _is_repository_unique_conflict(exc: IntegrityError) -> bool:
    constraint_name = "formations_run_repository_unique"
    cause = exc.__cause__
    diagnostic = getattr(cause, "diag", None)
    return (
        getattr(diagnostic, "constraint_name", None) == constraint_name
        or constraint_name in str(exc)
    )


def _repository_url_identity(
    repository_url: str,
) -> tuple[str, tuple[str, int | None, str]]:
    candidate = repository_url.strip()
    try:
        URLValidator(schemes=["http", "https"])(candidate)
        parsed = urlsplit(candidate)
        port = parsed.port
    except (DjangoValidationError, ValueError) as exc:
        raise InvalidRepositoryUrl from exc

    if (
        parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidRepositoryUrl

    hostname = parsed.hostname.casefold()
    if hostname == "www.github.com":
        hostname = "github.com"
    if hostname != "github.com" or port is not None:
        raise InvalidRepositoryUrl

    path = parsed.path[:-1] if parsed.path.endswith("/") else parsed.path
    if path.endswith("/"):
        raise InvalidRepositoryUrl
    if path.casefold().endswith(".git"):
        path = path[:-4]
    path_parts = path.split("/")
    if len(path_parts) != 3 or path_parts[0] or not all(path_parts[1:]):
        raise InvalidRepositoryUrl
    owner, repository = path_parts[1:]
    try:
        validate_github_username(owner)
    except DjangoValidationError as exc:
        raise InvalidRepositoryUrl from exc
    allowed_repository_characters = frozenset("-_.")
    if (
        repository in {".", ".."}
        or any(
            not character.isascii()
            or not (character.isalnum() or character in allowed_repository_characters)
            for character in repository
        )
    ):
        raise InvalidRepositoryUrl

    comparison_path = f"/{owner.casefold()}/{repository.casefold()}"
    normalized_url = urlunsplit(("https", hostname, comparison_path, "", ""))
    return normalized_url, (hostname, None, comparison_path)


def _validated_external_url(url: str, *, error_class):
    try:
        candidate = url.strip()
        if len(candidate) > 500:
            raise ValueError
        URLValidator(schemes=["http", "https"])(candidate)
        parsed = urlsplit(candidate)
        parsed.port
    except (AttributeError, DjangoValidationError, ValueError) as exc:
        raise error_class from exc
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise error_class
    return candidate


def _final_commit_url_for_repository(
    *, final_commit_url: str, repository_identity
) -> str:
    try:
        candidate = final_commit_url.strip()
        if len(candidate) > 500:
            raise ValueError
        URLValidator(schemes=["http", "https"])(candidate)
        parsed = urlsplit(candidate)
        port = parsed.port
    except (AttributeError, DjangoValidationError, ValueError) as exc:
        raise InvalidFinalCommitUrl from exc
    if (
        parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
        or port is not None
    ):
        raise InvalidFinalCommitUrl
    hostname = parsed.hostname.casefold()
    if hostname == "www.github.com":
        hostname = "github.com"
    path_parts = parsed.path.strip("/").split("/")
    if (
        hostname != "github.com"
        or len(path_parts) != 4
        or path_parts[2].casefold() != "commit"
    ):
        raise InvalidFinalCommitUrl
    owner, repository, _, revision = path_parts
    try:
        repository_root, commit_repository_identity = _repository_url_identity(
            f"https://github.com/{owner}/{repository}"
        )
    except InvalidRepositoryUrl as exc:
        raise InvalidFinalCommitUrl from exc
    if commit_repository_identity != repository_identity:
        raise InvalidFinalCommitUrl
    if len(revision) not in {40, 64} or any(
        character not in "0123456789abcdefABCDEF" for character in revision
    ):
        raise InvalidFinalCommitUrl
    return f"{repository_root}/commit/{revision.casefold()}"


@transaction.atomic
def update_project_run_design_workspace(
    *, project_run_id, actor: User, design_workspace_url: str
) -> ProjectRun:
    if not actor.is_active:
        raise DesignWorkspaceAccessDenied
    project_run = ProjectRun.objects.select_for_update(of=("self",)).get(
        id=project_run_id,
        state=ProjectRunState.ACTIVE,
        ended_at__isnull=True,
    )
    if not actor.is_staff:
        try:
            member = (
                TeamMember.objects.select_for_update(of=("self",))
                .select_related("role")
                .get(
                    project_run=project_run,
                    user=actor,
                    ended_at__isnull=True,
                )
            )
        except TeamMember.DoesNotExist as exc:
            raise ProjectRun.DoesNotExist from exc
        if member.role.code != RoleCode.PRODUCT_DESIGNER:
            raise DesignWorkspaceAccessDenied
    project_run.design_workspace_url = _validated_external_url(
        design_workspace_url,
        error_class=InvalidDesignWorkspaceUrl,
    )
    project_run.save(update_fields=["design_workspace_url"])
    return project_run


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
    if (
        project_run.state != ProjectRunState.ACTIVE
        or project_run.ended_at is not None
    ):
        raise SprintTransitionNotAllowed
    return project_run, sprint_run


def _require_active_staff(*, actor: User) -> None:
    if not actor.is_active or not actor.is_staff:
        raise SprintAccessDenied


@transaction.atomic
def open_sprint(
    *,
    sprint_run_id,
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
    sprint_run.state = SprintRunState.ACTIVE
    sprint_run.opened_at = now
    sprint_run.save(update_fields=["state", "opened_at", "updated_at"])
    return sprint_run


@transaction.atomic
def submit_sprint(
    *,
    sprint_run_id,
    user: User,
    evidence: str = "",
    final_commit_url: str | None = None,
    deployment_url: str | None = None,
    project_run_id=None,
    now=None,
) -> tuple[SprintRun, SprintSubmission]:
    if not user.is_active:
        raise SprintAccessDenied
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
    if submission_deadline_passed(now=now, deadline_at=project_run.deadline_at):
        raise SprintDeadlinePassed
    source_state = sprint_run.state
    if source_state not in SPRINT_SUBMISSION_SOURCE_STATES:
        raise SprintTransitionNotAllowed
    if source_state != SprintRunState.SUBMITTED:
        validate_sprint_transition(
            current_state=source_state,
            target_state=SprintRunState.SUBMITTED,
        )
    if not project_run.repository_url:
        raise ProjectRunRepositoryRequired
    try:
        _, repository_identity = _repository_url_identity(project_run.repository_url)
    except InvalidRepositoryUrl as exc:
        raise ProjectRunRepositoryRequired from exc
    if not project_run.design_workspace_url:
        raise DesignWorkspaceRequired
    final_commit_url = _final_commit_url_for_repository(
        final_commit_url=final_commit_url or "",
        repository_identity=repository_identity,
    )
    deployment_url = _validated_external_url(
        deployment_url or "",
        error_class=InvalidDeploymentUrl,
    )
    design_url_snapshot = _validated_external_url(
        project_run.design_workspace_url,
        error_class=DesignWorkspaceRequired,
    )
    submission = SprintSubmission.objects.create(
        sprint_run=sprint_run,
        submitted_by=member,
        evidence=evidence,
        final_commit_url=final_commit_url,
        deployment_url=deployment_url,
        design_url_snapshot=design_url_snapshot,
        submitted_at=now,
    )
    if source_state != SprintRunState.SUBMITTED:
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
    if target_state != SprintRunState.UNDER_REVIEW:
        raise SprintTransitionNotAllowed
    _, sprint_run = _locked_sprint_run(
        sprint_run_id=sprint_run_id,
        project_run_id=project_run_id,
    )
    validate_sprint_transition(
        current_state=sprint_run.state,
        target_state=target_state,
    )
    sprint_run.state = target_state
    sprint_run.save(update_fields=["state", "updated_at"])
    return sprint_run


def _normalized_review_feedback(*, feedback, required: bool) -> str:
    if feedback is None:
        normalized = ""
    elif isinstance(feedback, str):
        normalized = feedback.strip()
    else:
        raise InvalidReviewFeedback
    if required and not normalized:
        raise InvalidReviewFeedback
    return normalized


def _latest_submission_for_review(*, sprint_run: SprintRun) -> SprintSubmission:
    submission = (
        SprintSubmission.objects.select_for_update(of=("self",))
        .filter(sprint_run=sprint_run)
        .order_by("-submitted_at", "-id")
        .first()
    )
    if submission is None:
        raise SprintRuntimeConfigurationError
    return submission


@transaction.atomic
def _finalize_sprint_review(
    *,
    sprint_run_id,
    actor: User,
    decision: str,
    feedback=None,
    project_run_id=None,
    now=None,
) -> SprintRun:
    _require_active_staff(actor=actor)
    if decision not in ReviewDecisionType.values:
        raise SprintTransitionNotAllowed
    now = now or timezone.now()
    project_run, sprint_run = _locked_sprint_run(
        sprint_run_id=sprint_run_id,
        project_run_id=project_run_id,
    )
    validate_sprint_transition(
        current_state=sprint_run.state,
        target_state=decision,
    )
    submission = _latest_submission_for_review(sprint_run=sprint_run)
    if ReviewDecision.objects.filter(sprint_submission=submission).exists():
        raise SprintTransitionNotAllowed
    normalized_feedback = _normalized_review_feedback(
        feedback=feedback,
        required=decision == ReviewDecisionType.CHANGES_REQUESTED,
    )
    ReviewDecision.objects.create(
        sprint_submission=submission,
        reviewed_by=actor,
        decision=decision,
        feedback=normalized_feedback,
        reviewed_at=now,
    )
    sprint_run.state = decision
    update_fields = ["state", "updated_at"]
    if decision == ReviewDecisionType.COMPLETED:
        sprint_run.completed_at = now
        update_fields.append("completed_at")
    sprint_run.save(update_fields=update_fields)
    if (
        decision == ReviewDecisionType.COMPLETED
        and _is_final_sprint_run(
            project_run=project_run,
            sprint_run=sprint_run,
        )
    ):
        _terminalize_project_run_locked(
            project_run=project_run,
            target_state=ProjectRunState.COMPLETED,
            ended_at=now,
        )
    return sprint_run


def _is_final_sprint_run(*, project_run: ProjectRun, sprint_run: SprintRun) -> bool:
    final_template_id = (
        SprintTemplate.objects.filter(project_version_id=project_run.project_version_id)
        .order_by("-sequence", "-id")
        .values_list("id", flat=True)
        .first()
    )
    if final_template_id is None:
        raise SprintRuntimeConfigurationError
    return sprint_run.sprint_template_id == final_template_id


def _terminalize_project_run_locked(
    *,
    project_run: ProjectRun,
    target_state: str,
    ended_at,
) -> ProjectRun:
    if (
        target_state not in {ProjectRunState.COMPLETED, ProjectRunState.INCOMPLETE}
        or project_run.state != ProjectRunState.ACTIVE
        or project_run.ended_at is not None
    ):
        raise ProjectRunTransitionNotAllowed

    members = list(
        TeamMember.objects.select_for_update(of=("self",))
        .filter(project_run=project_run)
        .order_by("user_id", "id")
    )
    if len(members) != 3 or any(member.ended_at is not None for member in members):
        raise ProjectRunTransitionNotAllowed

    TeamMember.objects.filter(id__in=[member.id for member in members]).update(
        ended_at=ended_at
    )
    project_run.state = target_state
    project_run.ended_at = ended_at
    project_run.save(update_fields=["state", "ended_at"])
    return project_run


@transaction.atomic
def mark_project_run_incomplete(
    *,
    project_run_id,
    actor: User,
    now=None,
) -> ProjectRun:
    _require_active_staff(actor=actor)
    now = now or timezone.now()
    project_run = ProjectRun.objects.select_for_update(of=("self",)).get(
        id=project_run_id
    )
    if (
        project_run.state != ProjectRunState.ACTIVE
        or project_run.ended_at is not None
    ):
        raise ProjectRunTransitionNotAllowed
    if now < project_run.deadline_at:
        raise ProjectRunDeadlineNotReached
    return _terminalize_project_run_locked(
        project_run=project_run,
        target_state=ProjectRunState.INCOMPLETE,
        ended_at=now,
    )


@transaction.atomic
def mark_sprint_under_review(**kwargs) -> SprintRun:
    return _staff_transition_sprint(
        target_state=SprintRunState.UNDER_REVIEW,
        **kwargs,
    )


@transaction.atomic
def request_sprint_changes(*, feedback=None, **kwargs) -> SprintRun:
    return _finalize_sprint_review(
        decision=ReviewDecisionType.CHANGES_REQUESTED,
        feedback=feedback,
        **kwargs,
    )


@transaction.atomic
def complete_sprint(*, feedback="", **kwargs) -> SprintRun:
    return _finalize_sprint_review(
        decision=ReviewDecisionType.COMPLETED,
        feedback=feedback,
        **kwargs,
    )
