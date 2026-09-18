from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist

from apps.formations.exceptions import FormationDomainError
from apps.formations.models import (
    ProjectRun,
    ReadyCheck,
    SprintRun,
    SprintSubmission,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.formations.services import (
    complete_sprint,
    mark_project_run_incomplete,
    mark_sprint_under_review,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Historical and operational records are inspected, never form-edited."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ActionOnlyAdmin(ReadOnlyAdmin):
    """Allow service-backed changelist actions but no object form mutation."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return admin.ModelAdmin.has_change_permission(self, request, obj)


def _run_service_action(
    *,
    model_admin,
    request,
    queryset,
    service,
    identifier_keyword,
    object_label,
    success_message,
):
    if (
        not request.user.is_active
        or not request.user.is_staff
        or not model_admin.has_change_permission(request)
    ):
        model_admin.message_user(
            request,
            "An active staff account with change permission is required.",
            level=messages.ERROR,
        )
        return

    successful = 0
    object_ids = list(queryset.order_by("pk").values_list("pk", flat=True))
    for object_id in object_ids:
        try:
            service(
                **{
                    identifier_keyword: object_id,
                    "actor": request.user,
                }
            )
        except (FormationDomainError, ObjectDoesNotExist) as exc:
            reason = str(exc) or type(exc).__name__
            model_admin.message_user(
                request,
                f"{object_label} {object_id} was not changed: {reason}.",
                level=messages.ERROR,
            )
        else:
            successful += 1

    if successful:
        model_admin.message_user(
            request,
            f"{successful} {success_message}",
            level=messages.SUCCESS,
        )


@admin.register(TeamFormation)
class TeamFormationAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "project_name",
        "version_number",
        "created_by",
        "created_at",
        "ready_confirmed_at",
    )
    list_filter = (
        "project_version__project_template",
        ("ready_confirmed_at", admin.EmptyFieldListFilter),
        "created_at",
    )
    search_fields = (
        "=id",
        "created_by__email",
        "project_version__project_template__name",
    )
    list_select_related = (
        "project_version",
        "project_version__project_template",
        "created_by",
    )
    ordering = ("-created_at", "id")
    date_hierarchy = "created_at"

    @admin.display(ordering="project_version__project_template__name")
    def project_name(self, obj):
        return obj.project_version.project_template.name

    @admin.display(ordering="project_version__version_number")
    def version_number(self, obj):
        return obj.project_version.version_number


@admin.register(ReadyCheck)
class ReadyCheckAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "formation",
        "user",
        "role",
        "technology_stack",
        "status",
        "effective_status",
        "is_current",
        "expires_at",
        "responded_at",
    )
    list_filter = (
        "status",
        "is_current",
        "role",
        "technology_stack",
        "expires_at",
    )
    search_fields = ("=id", "=formation__id", "user__email", "proposed_by__email")
    list_select_related = (
        "formation",
        "user",
        "role",
        "technology_stack",
        "proposed_by",
    )
    ordering = ("-started_at", "formation_id", "role__name", "id")
    date_hierarchy = "started_at"

    @admin.display(description="Effective status")
    def effective_status(self, obj):
        return obj.effective_status()


@admin.register(Team)
class TeamAdmin(ReadOnlyAdmin):
    list_display = ("id", "formation", "project_name", "created_at")
    list_filter = ("formation__project_version__project_template", "created_at")
    search_fields = ("=id", "=formation__id")
    list_select_related = (
        "formation",
        "formation__project_version",
        "formation__project_version__project_template",
    )
    ordering = ("-created_at", "id")
    date_hierarchy = "created_at"

    @admin.display(
        ordering="formation__project_version__project_template__name"
    )
    def project_name(self, obj):
        return obj.formation.project_version.project_template.name


@admin.register(TeamMember)
class TeamMemberAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "project_run",
        "user",
        "role",
        "technology_stack",
        "ended_at",
    )
    list_filter = (
        "role",
        "technology_stack",
        ("ended_at", admin.EmptyFieldListFilter),
    )
    search_fields = ("=id", "=project_run__id", "user__email")
    list_select_related = (
        "project_run",
        "user",
        "role",
        "technology_stack",
    )
    ordering = ("-project_run__started_at", "role__name", "id")


@admin.register(ProjectRun)
class ProjectRunAdmin(ActionOnlyAdmin):
    list_display = (
        "id",
        "project_name",
        "version_number",
        "team",
        "state",
        "repository_url",
        "started_at",
        "deadline_at",
        "ended_at",
    )
    list_filter = (
        "state",
        "project_version__project_template",
        "project_version__version_number",
        ("ended_at", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "=id",
        "=team__id",
        "project_version__project_template__name",
        "repository_url",
    )
    list_select_related = (
        "team",
        "project_version",
        "project_version__project_template",
    )
    ordering = ("-started_at", "id")
    date_hierarchy = "started_at"
    actions = ("mark_selected_incomplete",)

    @admin.display(ordering="project_version__project_template__name")
    def project_name(self, obj):
        return obj.project_version.project_template.name

    @admin.display(ordering="project_version__version_number")
    def version_number(self, obj):
        return obj.project_version.version_number

    @admin.action(
        permissions=("change",),
        description="Mark selected overdue ProjectRuns incomplete",
    )
    def mark_selected_incomplete(self, request, queryset):
        _run_service_action(
            model_admin=self,
            request=request,
            queryset=queryset,
            service=mark_project_run_incomplete,
            identifier_keyword="project_run_id",
            object_label="ProjectRun",
            success_message="ProjectRun(s) marked incomplete.",
        )


@admin.register(SprintRun)
class SprintRunAdmin(ActionOnlyAdmin):
    list_display = (
        "id",
        "project_run",
        "sprint_sequence",
        "sprint_title",
        "state",
        "designated_submitter",
        "planned_start_at",
        "planned_end_at",
        "completed_at",
    )
    list_filter = (
        "state",
        "project_run__project_version__project_template",
        "sprint_template__sequence",
        ("completed_at", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "=id",
        "=project_run__id",
        "sprint_template__title",
        "designated_submitter__user__email",
    )
    list_select_related = (
        "project_run",
        "project_run__project_version",
        "project_run__project_version__project_template",
        "sprint_template",
        "designated_submitter",
        "designated_submitter__user",
    )
    ordering = (
        "-project_run__started_at",
        "sprint_template__sequence",
        "id",
    )
    actions = (
        "mark_selected_under_review",
        "complete_selected_sprints",
    )
    # Requesting changes requires per-Sprint feedback and is not a safe bulk action.

    @admin.display(ordering="sprint_template__sequence", description="Sprint")
    def sprint_sequence(self, obj):
        return obj.sprint_template.sequence

    @admin.display(ordering="sprint_template__title", description="Title")
    def sprint_title(self, obj):
        return obj.sprint_template.title

    @admin.action(
        permissions=("change",),
        description="Mark selected submitted Sprints under review",
    )
    def mark_selected_under_review(self, request, queryset):
        _run_service_action(
            model_admin=self,
            request=request,
            queryset=queryset,
            service=mark_sprint_under_review,
            identifier_keyword="sprint_run_id",
            object_label="SprintRun",
            success_message="SprintRun(s) marked under review.",
        )

    @admin.action(
        permissions=("change",),
        description="Complete selected Sprints under review",
    )
    def complete_selected_sprints(self, request, queryset):
        _run_service_action(
            model_admin=self,
            request=request,
            queryset=queryset,
            service=complete_sprint,
            identifier_keyword="sprint_run_id",
            object_label="SprintRun",
            success_message="SprintRun(s) completed.",
        )


@admin.register(SprintSubmission)
class SprintSubmissionAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "sprint_run",
        "sprint_sequence",
        "submitted_by",
        "submitted_at",
    )
    list_filter = (
        "sprint_run__project_run__project_version__project_template",
        "sprint_run__sprint_template__sequence",
        "submitted_at",
    )
    search_fields = (
        "=id",
        "=sprint_run__id",
        "submitted_by__user__email",
        "evidence",
    )
    list_select_related = (
        "sprint_run",
        "sprint_run__project_run",
        "sprint_run__sprint_template",
        "submitted_by",
        "submitted_by__user",
    )
    ordering = ("-submitted_at", "id")
    date_hierarchy = "submitted_at"

    @admin.display(
        ordering="sprint_run__sprint_template__sequence",
        description="Sprint",
    )
    def sprint_sequence(self, obj):
        return obj.sprint_run.sprint_template.sequence
