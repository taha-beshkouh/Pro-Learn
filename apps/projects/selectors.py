from uuid import UUID

from django.db.models import OuterRef, Prefetch, QuerySet, Subquery

from apps.profiles.models import (
    Role,
    RoleTechnologyStack,
    TechnologyStack,
    UserProfile,
    UserSkill,
)
from apps.profiles.services import guest_context_from_session
from apps.projects.models import (
    Level,
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTaskTemplate,
    ProjectTemplate,
    ProjectVersion,
    RolePrerequisite,
    SprintTemplate,
)
from apps.projects.services import authenticated_stack_selection_from_session


def level_list() -> QuerySet[Level]:
    return Level.objects.order_by("number")


def project_template_list(*, level_number: int | None = None) -> QuerySet[ProjectTemplate]:
    latest_version = (
        ProjectVersion.objects.filter(
            project_template=OuterRef("pk"),
            published_at__isnull=False,
        )
        .order_by("-version_number")
        .values("id")[:1]
    )
    queryset = ProjectTemplate.objects.select_related("level").annotate(
        published_version_id=Subquery(latest_version)
    )
    if level_number is not None:
        queryset = queryset.filter(level__number=level_number)
    return queryset.order_by("level__number", "name")


def project_template_detail(*, project_id: UUID) -> ProjectTemplate:
    return project_template_list().get(id=project_id)


def published_project_version(*, version_id: UUID) -> ProjectVersion:
    allowed_stacks = ProjectRoleAllowedStack.objects.select_related(
        "technology_stack"
    ).order_by("technology_stack__name", "id")
    prerequisites = RolePrerequisite.objects.order_by("position", "id")
    role_stack_links = RoleTechnologyStack.objects.select_related(
        "technology_stack"
    ).order_by("technology_stack__name", "id")
    role_requirements = (
        ProjectRoleRequirement.objects.select_related("role")
        .prefetch_related(
            Prefetch("allowed_stacks", queryset=allowed_stacks),
            Prefetch("prerequisites", queryset=prerequisites),
            Prefetch("role__compatible_stack_links", queryset=role_stack_links),
        )
        .order_by("role__name", "id")
    )
    work_items = ProjectTaskTemplate.objects.select_related(
        "role", "technology_stack", "sprint_template"
    ).order_by("position", "id")
    sprint_templates = SprintTemplate.objects.order_by("sequence", "id")
    return (
        ProjectVersion.objects.select_related("project_template", "project_template__level")
        .prefetch_related(
            Prefetch("role_requirements", queryset=role_requirements),
            Prefetch("work_items", queryset=work_items),
            Prefetch("sprint_templates", queryset=sprint_templates),
        )
        .get(id=version_id, published_at__isnull=False)
    )


def selected_role_for_request(*, request) -> Role | None:
    if request.user.is_authenticated:
        try:
            return request.user.profile.selected_role
        except UserProfile.DoesNotExist:
            return None
    role_id = guest_context_from_session(session=request.session).get("selected_role_id")
    if not role_id:
        return None
    return Role.objects.filter(id=role_id).first()


def profile_with_skills_for_request(*, request) -> UserProfile | None:
    if not request.user.is_authenticated:
        return None
    return (
        UserProfile.objects.select_related("selected_role").filter(user=request.user)
        .prefetch_related(
            Prefetch(
                "skills",
                queryset=UserSkill.objects.select_related("technology_stack").order_by(
                    "technology_stack__name"
                ),
            )
        )
        .first()
    )


def selected_stack_for_request(
    *, request, project_version_id: UUID
) -> TechnologyStack | None:
    if not request.user.is_authenticated:
        return None
    selection = authenticated_stack_selection_from_session(session=request.session)
    if selection.get("user_id") != str(request.user.id):
        return None
    if selection.get("project_version_id") != str(project_version_id):
        return None
    stack_id = selection.get("selected_stack_id")
    if not stack_id:
        return None
    return TechnologyStack.objects.filter(id=stack_id).first()
