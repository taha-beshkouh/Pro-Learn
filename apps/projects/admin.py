from django.contrib import admin

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


class ReadOnlyAdmin(admin.ModelAdmin):
    """Versioned project definitions are never edited through Django admin."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Level)
class LevelAdmin(ReadOnlyAdmin):
    list_display = ("number", "name", "id")
    search_fields = ("name",)
    ordering = ("number",)


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(ReadOnlyAdmin):
    list_display = ("name", "slug", "level", "id")
    list_filter = ("level",)
    search_fields = ("name", "slug")
    list_select_related = ("level",)
    ordering = ("level__number", "name")


@admin.register(ProjectVersion)
class ProjectVersionAdmin(ReadOnlyAdmin):
    list_display = (
        "project_template",
        "version_number",
        "published",
        "duration_weeks",
        "sprint_count",
        "created_at",
        "id",
    )
    list_filter = ("project_template__level", "project_template", "published_at")
    search_fields = ("project_template__name", "project_template__slug", "=id")
    list_select_related = ("project_template", "project_template__level")
    ordering = ("project_template__name", "-version_number")
    date_hierarchy = "created_at"

    @admin.display(boolean=True, ordering="published_at", description="Published")
    def published(self, obj):
        return obj.is_published


@admin.register(ProjectRoleRequirement)
class ProjectRoleRequirementAdmin(ReadOnlyAdmin):
    list_display = (
        "project_name",
        "version_number",
        "role",
        "requires_stack",
        "stack_policy",
        "id",
    )
    list_filter = (
        "project_version__project_template",
        "role",
        "requires_stack",
        "stack_policy",
    )
    search_fields = (
        "project_version__project_template__name",
        "project_version__project_template__slug",
        "role__name",
        "role__code",
    )
    list_select_related = (
        "project_version",
        "project_version__project_template",
        "role",
    )
    ordering = (
        "project_version__project_template__name",
        "project_version__version_number",
        "role__name",
    )

    @admin.display(ordering="project_version__project_template__name")
    def project_name(self, obj):
        return obj.project_version.project_template.name

    @admin.display(ordering="project_version__version_number")
    def version_number(self, obj):
        return obj.project_version.version_number


@admin.register(ProjectRoleAllowedStack)
class ProjectRoleAllowedStackAdmin(ReadOnlyAdmin):
    list_display = (
        "project_name",
        "version_number",
        "role",
        "technology_stack",
        "id",
    )
    list_filter = ("role_requirement__role", "technology_stack")
    search_fields = (
        "role_requirement__project_version__project_template__name",
        "role_requirement__role__name",
        "technology_stack__name",
    )
    list_select_related = (
        "role_requirement",
        "role_requirement__project_version",
        "role_requirement__project_version__project_template",
        "role_requirement__role",
        "technology_stack",
    )
    ordering = (
        "role_requirement__project_version__project_template__name",
        "role_requirement__project_version__version_number",
        "role_requirement__role__name",
        "technology_stack__name",
    )

    @admin.display(
        ordering="role_requirement__project_version__project_template__name"
    )
    def project_name(self, obj):
        return obj.role_requirement.project_version.project_template.name

    @admin.display(ordering="role_requirement__project_version__version_number")
    def version_number(self, obj):
        return obj.role_requirement.project_version.version_number

    @admin.display(ordering="role_requirement__role__name")
    def role(self, obj):
        return obj.role_requirement.role


@admin.register(RolePrerequisite)
class RolePrerequisiteAdmin(ReadOnlyAdmin):
    list_display = (
        "project_name",
        "version_number",
        "role",
        "position",
        "title",
        "id",
    )
    list_filter = ("role_requirement__project_version__project_template", "role_requirement__role")
    search_fields = (
        "title",
        "description",
        "role_requirement__project_version__project_template__name",
        "role_requirement__role__name",
    )
    list_select_related = (
        "role_requirement",
        "role_requirement__project_version",
        "role_requirement__project_version__project_template",
        "role_requirement__role",
    )
    ordering = (
        "role_requirement__project_version__project_template__name",
        "role_requirement__project_version__version_number",
        "role_requirement__role__name",
        "position",
        "id",
    )

    @admin.display(
        ordering="role_requirement__project_version__project_template__name"
    )
    def project_name(self, obj):
        return obj.role_requirement.project_version.project_template.name

    @admin.display(ordering="role_requirement__project_version__version_number")
    def version_number(self, obj):
        return obj.role_requirement.project_version.version_number

    @admin.display(ordering="role_requirement__role__name")
    def role(self, obj):
        return obj.role_requirement.role


@admin.register(SprintTemplate)
class SprintTemplateAdmin(ReadOnlyAdmin):
    list_display = (
        "project_name",
        "version_number",
        "sequence",
        "title",
        "planned_start_offset_days",
        "planned_duration_days",
        "id",
    )
    list_filter = (
        "project_version__project_template",
        "project_version__version_number",
        "sequence",
    )
    search_fields = (
        "title",
        "brief",
        "project_version__project_template__name",
        "project_version__project_template__slug",
    )
    list_select_related = ("project_version", "project_version__project_template")
    ordering = (
        "project_version__project_template__name",
        "project_version__version_number",
        "sequence",
        "id",
    )

    @admin.display(ordering="project_version__project_template__name")
    def project_name(self, obj):
        return obj.project_version.project_template.name

    @admin.display(ordering="project_version__version_number")
    def version_number(self, obj):
        return obj.project_version.version_number


@admin.register(ProjectTaskTemplate)
class ProjectTaskTemplateAdmin(ReadOnlyAdmin):
    list_display = (
        "project_name",
        "version_number",
        "sprint_sequence",
        "role",
        "technology_stack",
        "position",
        "title",
        "id",
    )
    list_filter = (
        "project_version__project_template",
        "project_version__version_number",
        "sprint_template__sequence",
        "role",
        "technology_stack",
    )
    search_fields = (
        "title",
        "description",
        "project_version__project_template__name",
        "project_version__project_template__slug",
    )
    list_select_related = (
        "project_version",
        "project_version__project_template",
        "sprint_template",
        "role",
        "technology_stack",
    )
    ordering = (
        "project_version__project_template__name",
        "project_version__version_number",
        "sprint_template__sequence",
        "role__name",
        "technology_stack__name",
        "position",
        "id",
    )

    @admin.display(ordering="project_version__project_template__name")
    def project_name(self, obj):
        return obj.project_version.project_template.name

    @admin.display(ordering="project_version__version_number")
    def version_number(self, obj):
        return obj.project_version.version_number

    @admin.display(ordering="sprint_template__sequence", empty_value="Unscheduled")
    def sprint_sequence(self, obj):
        return obj.sprint_template.sequence if obj.sprint_template else None
