from rest_framework import serializers

from apps.common.serializers import StrictFieldsSerializer
from apps.profiles.api.serializers import RoleSerializer, TechnologyStackSerializer
from apps.profiles.models import TechnologyStack
from apps.projects.models import (
    Level,
    ProjectRoleRequirement,
    ProjectTaskTemplate,
    ProjectTemplate,
    ProjectVersion,
    RolePrerequisite,
    SprintTemplate,
)
from apps.projects.services import resolve_project_stack_selection


class ProjectStackSelectionInputSerializer(StrictFieldsSerializer):
    technology_stack_id = serializers.PrimaryKeyRelatedField(
        source="technology_stack",
        queryset=TechnologyStack.objects.all(),
    )


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ("id", "number", "name")
        read_only_fields = fields


class ProjectListSerializer(serializers.ModelSerializer):
    level = LevelSerializer(read_only=True)
    published_version_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = ProjectTemplate
        fields = ("id", "slug", "name", "level", "published_version_id")
        read_only_fields = fields


class ProjectTemplateIdentitySerializer(serializers.ModelSerializer):
    level = LevelSerializer(read_only=True)

    class Meta:
        model = ProjectTemplate
        fields = ("id", "slug", "name", "level")
        read_only_fields = fields


class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePrerequisite
        fields = ("id", "title", "description", "position")
        read_only_fields = fields


class SprintTemplateSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SprintTemplate
        fields = ("id", "sequence", "title")
        read_only_fields = fields


class SprintTemplateSerializer(serializers.ModelSerializer):
    planned_end_offset_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = SprintTemplate
        fields = (
            "id",
            "sequence",
            "title",
            "brief",
            "planned_start_offset_days",
            "planned_duration_days",
            "planned_end_offset_days",
        )
        read_only_fields = fields


class WorkItemSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    technology_stack = TechnologyStackSerializer(read_only=True)
    sprint_template = SprintTemplateSummarySerializer(read_only=True)

    class Meta:
        model = ProjectTaskTemplate
        fields = (
            "id",
            "title",
            "description",
            "position",
            "role",
            "technology_stack",
            "sprint_template",
        )
        read_only_fields = fields


class RoleContextSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    compatible_stacks = serializers.SerializerMethodField()
    auto_selected_stack = serializers.SerializerMethodField()
    selected_stack = serializers.SerializerMethodField()
    prerequisites = PrerequisiteSerializer(many=True, read_only=True)
    work_items = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRoleRequirement
        fields = (
            "id",
            "role",
            "requires_stack",
            "stack_policy",
            "context",
            "compatible_stacks",
            "auto_selected_stack",
            "selected_stack",
            "prerequisites",
            "work_items",
        )
        read_only_fields = fields

    def _selection_result(self, obj):
        cache = self.context.setdefault("stack_selection_results", {})
        if obj.id not in cache:
            cache[obj.id] = resolve_project_stack_selection(
                requirement=obj,
                profile=self.context.get("profile"),
                requested_stack=self.context.get("selected_stack"),
                reject_invalid=False,
            )
        return cache[obj.id]

    def get_compatible_stacks(self, obj):
        return TechnologyStackSerializer(
            self._selection_result(obj).compatible_stacks,
            many=True,
        ).data

    def get_auto_selected_stack(self, obj):
        stack = self._selection_result(obj).auto_selected_stack
        return TechnologyStackSerializer(stack).data if stack else None

    def _selected_stack(self, obj):
        return self._selection_result(obj).selected_stack

    def get_selected_stack(self, obj):
        stack = self._selected_stack(obj)
        return TechnologyStackSerializer(stack).data if stack else None

    def get_work_items(self, obj):
        selected_stack = self._selected_stack(obj)
        items = [
            item
            for item in self.context["project_version"].work_items.all()
            if item.role_id == obj.role_id
            and (
                item.technology_stack_id is None
                or (
                    selected_stack is not None
                    and item.technology_stack_id == selected_stack.id
                )
            )
        ]
        return WorkItemSerializer(items, many=True).data


class ProjectRoleRequirementDefinitionSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    configured_stacks = serializers.SerializerMethodField()
    prerequisites = PrerequisiteSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectRoleRequirement
        fields = (
            "id",
            "role",
            "requires_stack",
            "stack_policy",
            "context",
            "configured_stacks",
            "prerequisites",
        )
        read_only_fields = fields

    def get_configured_stacks(self, obj):
        stacks = [allowance.technology_stack for allowance in obj.allowed_stacks.all()]
        return TechnologyStackSerializer(stacks, many=True).data


class ProjectVersionSerializer(serializers.ModelSerializer):
    role_context = serializers.SerializerMethodField()
    shared_work_items = serializers.SerializerMethodField()
    sprint_templates = SprintTemplateSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectVersion
        fields = (
            "id",
            "version_number",
            "summary",
            "duration_weeks",
            "sprint_count",
            "weekly_effort_hours_min",
            "weekly_effort_hours_max",
            "participant_database",
            "sprint_templates",
            "role_context",
            "shared_work_items",
        )
        read_only_fields = fields

    def get_role_context(self, obj):
        selected_role = self.context.get("selected_role")
        if selected_role is None:
            return None
        requirement = next(
            (item for item in obj.role_requirements.all() if item.role_id == selected_role.id),
            None,
        )
        if requirement is None:
            return None
        context = {**self.context, "project_version": obj}
        return RoleContextSerializer(requirement, context=context).data

    def get_shared_work_items(self, obj):
        items = [
            item
            for item in obj.work_items.all()
            if item.role_id is None and item.technology_stack_id is None
        ]
        return WorkItemSerializer(items, many=True).data


class ProjectDetailSerializer(ProjectListSerializer):
    published_version = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = (*ProjectListSerializer.Meta.fields, "published_version")

    def get_published_version(self, obj):
        version = self.context.get("published_version")
        if version is None:
            return None
        return ProjectVersionSerializer(version, context=self.context).data


class ProjectVersionDetailSerializer(ProjectVersionSerializer):
    project_template = ProjectTemplateIdentitySerializer(read_only=True)
    role_requirements = ProjectRoleRequirementDefinitionSerializer(
        many=True,
        read_only=True,
    )
    work_items = WorkItemSerializer(many=True, read_only=True)

    class Meta(ProjectVersionSerializer.Meta):
        fields = (
            "project_template",
            "id",
            "version_number",
            "summary",
            "full_description",
            "duration_weeks",
            "sprint_count",
            "weekly_effort_hours_min",
            "weekly_effort_hours_max",
            "participant_database",
            "published_at",
            "sprint_templates",
            "role_requirements",
            "work_items",
            "role_context",
            "shared_work_items",
        )
        read_only_fields = fields
