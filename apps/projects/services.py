from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError
from django.contrib.sessions.backends.base import SessionBase

from apps.profiles.models import Role, TechnologyStack, UserProfile
from apps.profiles.services import update_guest_context
from apps.projects.exceptions import (
    InvalidProjectStackSelection,
    ProjectConfigurationError,
)
from apps.projects.models import (
    ProjectRoleRequirement,
    ProjectTaskTemplate,
    ProjectVersion,
    SprintTemplate,
    StackPolicy,
)


@dataclass(frozen=True)
class StackPolicyResult:
    compatible_stacks: tuple[TechnologyStack, ...]
    auto_selected_stack: TechnologyStack | None


@dataclass(frozen=True)
class StackSelectionResult:
    compatible_stacks: tuple[TechnologyStack, ...]
    auto_selected_stack: TechnologyStack | None
    selected_stack: TechnologyStack | None


def validate_sprint_template(*, sprint_template: SprintTemplate) -> None:
    sprint_count = sprint_template.project_version.sprint_count
    if sprint_count is not None and sprint_template.sequence > sprint_count:
        raise ValidationError(
            "Sprint sequence cannot exceed the ProjectVersion sprint count."
        )


def validate_work_item_sprint(*, work_item: ProjectTaskTemplate) -> None:
    if work_item.sprint_template_id is None:
        return
    if work_item.sprint_template.project_version_id != work_item.project_version_id:
        raise ValidationError(
            "Static work content and its SprintTemplate must belong to the same ProjectVersion."
        )


def validate_role_requirement_configuration(
    *, requirement: ProjectRoleRequirement
) -> None:
    allowed_count = requirement.allowed_stacks.count()
    validate_stack_policy_shape(
        requires_stack=requirement.requires_stack,
        stack_policy=requirement.stack_policy,
        allowed_count=allowed_count,
    )


def validate_stack_policy_shape(
    *, requires_stack: bool, stack_policy: str | None, allowed_count: int
) -> None:
    if not requires_stack:
        if stack_policy is not None or allowed_count:
            raise ValidationError("A stackless role cannot define a stack policy or stacks.")
        return
    if stack_policy not in StackPolicy.values:
        raise ValidationError("A stack-requiring role must define a valid stack policy.")
    if stack_policy == StackPolicy.FIXED and allowed_count != 1:
        raise ValidationError("FIXED requires exactly one allowed stack.")
    if stack_policy == StackPolicy.ALLOWLIST and allowed_count < 1:
        raise ValidationError("ALLOWLIST requires at least one allowed stack.")
    if stack_policy == StackPolicy.OPEN and allowed_count:
        raise ValidationError("OPEN cannot define configured allowed stacks.")


def resolve_compatible_stacks(
    *,
    requirement: ProjectRoleRequirement,
    profile: UserProfile | None = None,
) -> StackPolicyResult:
    try:
        validate_role_requirement_configuration(requirement=requirement)
    except ValidationError as exc:
        raise ProjectConfigurationError from exc
    if not requirement.requires_stack:
        compatible: tuple[TechnologyStack, ...] = ()
    elif requirement.stack_policy in {StackPolicy.FIXED, StackPolicy.ALLOWLIST}:
        compatible = tuple(
            allowance.technology_stack for allowance in requirement.allowed_stacks.all()
        )
    elif profile is None:
        compatible = ()
    else:
        compatible_stack_ids = {
            link.technology_stack_id
            for link in requirement.role.compatible_stack_links.all()
        }
        compatible = tuple(
            skill.technology_stack
            for skill in profile.skills.all()
            if skill.technology_stack_id in compatible_stack_ids
        )
    auto_selected = compatible[0] if len(compatible) == 1 else None
    return StackPolicyResult(compatible, auto_selected)


def resolve_project_stack_selection(
    *,
    requirement: ProjectRoleRequirement,
    profile: UserProfile | None,
    requested_stack: TechnologyStack | None,
    reject_invalid: bool,
) -> StackSelectionResult:
    policy_result = resolve_compatible_stacks(
        requirement=requirement,
        profile=profile,
    )
    compatible_by_id = {
        stack.id: stack for stack in policy_result.compatible_stacks
    }
    selected_stack = None
    if requested_stack is not None:
        selected_stack = compatible_by_id.get(requested_stack.id)
        if selected_stack is None and reject_invalid:
            raise InvalidProjectStackSelection
    if selected_stack is None:
        selected_stack = policy_result.auto_selected_stack
    return StackSelectionResult(
        compatible_stacks=policy_result.compatible_stacks,
        auto_selected_stack=policy_result.auto_selected_stack,
        selected_stack=selected_stack,
    )


def select_project_stack(
    *,
    project_version: ProjectVersion,
    role: Role,
    profile: UserProfile | None,
    technology_stack: TechnologyStack,
    project_id: UUID,
    session: SessionBase,
) -> TechnologyStack:
    requirement = next(
        (
            item
            for item in project_version.role_requirements.all()
            if item.role_id == role.id
        ),
        None,
    )
    if requirement is None:
        raise InvalidProjectStackSelection
    result = resolve_project_stack_selection(
        requirement=requirement,
        profile=profile,
        requested_stack=technology_stack,
        reject_invalid=True,
    )
    if result.selected_stack is None:
        raise InvalidProjectStackSelection
    update_guest_context(
        session=session,
        changes={
            "selected_project_id": project_id,
            "selected_role": role,
            "selected_stack": result.selected_stack,
        },
    )
    return result.selected_stack
