from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.formations.exceptions import (
    FormationAlreadyReady,
    InvalidFormationMembers,
    InvalidFormationStack,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
)
from apps.formations.models import (
    READY_CHECK_DURATION,
    ReadyCheck,
    ReadyCheckStatus,
    TeamFormation,
)
from apps.profiles.models import Role, RoleCode, TechnologyStack, UserProfile
from apps.projects.exceptions import (
    InvalidProjectStackSelection,
    ProjectConfigurationError,
)
from apps.projects.models import ProjectRoleRequirement, ProjectVersion
from apps.projects.services import resolve_project_stack_selection


EXPECTED_ROLE_CODES = frozenset(RoleCode.values)


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
    if not created_by.is_active or not created_by.is_staff or not project_version.is_published:
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
                confirmed_count = ReadyCheck.objects.filter(
                    formation=formation,
                    is_current=True,
                    status=ReadyCheckStatus.CONFIRMED,
                ).count()
                if confirmed_count == 3 and formation.ready_confirmed_at is None:
                    formation.ready_confirmed_at = now
                    formation.save(update_fields=["ready_confirmed_at", "updated_at"])
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
