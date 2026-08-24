from rest_framework import serializers

from apps.accounts.api.serializers import UserOutputSerializer
from apps.accounts.models import User
from apps.common.serializers import StrictFieldsSerializer
from apps.formations.models import (
    ProjectRun,
    ReadyCheck,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    TeamFormation,
    TeamMember,
)
from apps.profiles.api.serializers import RoleSerializer, TechnologyStackSerializer
from apps.profiles.models import Role, TechnologyStack
from apps.projects.api.serializers import WorkItemSerializer
from apps.projects.models import ProjectVersion
from apps.formations.services import sprint_next_action


class FormationMemberInputSerializer(StrictFieldsSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.filter(is_active=True),
    )
    role_id = serializers.PrimaryKeyRelatedField(
        source="role",
        queryset=Role.objects.all(),
    )
    technology_stack_id = serializers.PrimaryKeyRelatedField(
        source="technology_stack",
        queryset=TechnologyStack.objects.all(),
        allow_null=True,
        required=False,
    )


class TeamFormationInputSerializer(StrictFieldsSerializer):
    project_version_id = serializers.PrimaryKeyRelatedField(
        source="project_version",
        queryset=ProjectVersion.objects.filter(published_at__isnull=False),
    )
    members = FormationMemberInputSerializer(many=True)

    def validate_members(self, value):
        if len(value) != 3:
            raise serializers.ValidationError("Exactly three members are required.")
        return value


class ReplacementInputSerializer(StrictFieldsSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.filter(is_active=True),
    )
    technology_stack_id = serializers.PrimaryKeyRelatedField(
        source="technology_stack",
        queryset=TechnologyStack.objects.all(),
        allow_null=True,
        required=False,
    )


class ReadyCheckSerializer(serializers.ModelSerializer):
    user = UserOutputSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    technology_stack = TechnologyStackSerializer(read_only=True)
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = ReadyCheck
        fields = (
            "id",
            "user",
            "role",
            "technology_stack",
            "status",
            "effective_status",
            "is_current",
            "started_at",
            "expires_at",
            "responded_at",
        )
        read_only_fields = fields

    def get_effective_status(self, obj):
        return obj.effective_status()


class TeamFormationSerializer(serializers.ModelSerializer):
    project_version_id = serializers.UUIDField(read_only=True)
    project_name = serializers.CharField(
        source="project_version.project_template.name",
        read_only=True,
    )
    created_by = UserOutputSerializer(read_only=True)
    ready_checks = ReadyCheckSerializer(many=True, read_only=True)
    team_id = serializers.SerializerMethodField()
    project_run_id = serializers.SerializerMethodField()

    class Meta:
        model = TeamFormation
        fields = (
            "id",
            "project_version_id",
            "project_name",
            "created_by",
            "created_at",
            "ready_confirmed_at",
            "team_id",
            "project_run_id",
            "ready_checks",
        )
        read_only_fields = fields

    def get_team_id(self, obj):
        team = getattr(obj, "team", None)
        return str(team.id) if team is not None else None

    def get_project_run_id(self, obj):
        team = getattr(obj, "team", None)
        project_run = getattr(team, "project_run", None) if team is not None else None
        return str(project_run.id) if project_run is not None else None


class MyReadyCheckSerializer(ReadyCheckSerializer):
    formation_id = serializers.UUIDField(read_only=True)
    project_version_id = serializers.UUIDField(
        source="formation.project_version_id",
        read_only=True,
    )
    project_name = serializers.CharField(
        source="formation.project_version.project_template.name",
        read_only=True,
    )

    class Meta(ReadyCheckSerializer.Meta):
        fields = (
            "formation_id",
            "project_version_id",
            "project_name",
            *ReadyCheckSerializer.Meta.fields,
        )


class OpenSprintInputSerializer(StrictFieldsSerializer):
    designated_submitter_id = serializers.PrimaryKeyRelatedField(
        source="designated_submitter",
        queryset=TeamMember.objects.filter(ended_at__isnull=True),
    )


class SprintSubmissionInputSerializer(StrictFieldsSerializer):
    evidence = serializers.CharField(allow_blank=True, required=False, default="")


class EmptyActionInputSerializer(StrictFieldsSerializer):
    pass


class TeamMemberSnapshotSerializer(serializers.ModelSerializer):
    user = UserOutputSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    technology_stack = TechnologyStackSerializer(read_only=True)

    class Meta:
        model = TeamMember
        fields = ("id", "user", "role", "technology_stack", "ended_at")
        read_only_fields = fields


class SprintSubmissionSerializer(serializers.ModelSerializer):
    submitted_by = TeamMemberSnapshotSerializer(read_only=True)

    class Meta:
        model = SprintSubmission
        fields = ("id", "submitted_by", "evidence", "submitted_at")
        read_only_fields = fields


class SprintRunSerializer(serializers.ModelSerializer):
    sprint_template_id = serializers.UUIDField(read_only=True)
    sequence = serializers.IntegerField(
        source="sprint_template.sequence",
        read_only=True,
    )
    title = serializers.CharField(source="sprint_template.title", read_only=True)
    brief = serializers.CharField(source="sprint_template.brief", read_only=True)
    designated_submitter = TeamMemberSnapshotSerializer(read_only=True)

    class Meta:
        model = SprintRun
        fields = (
            "id",
            "sprint_template_id",
            "sequence",
            "title",
            "brief",
            "state",
            "planned_start_at",
            "planned_end_at",
            "opened_at",
            "completed_at",
            "designated_submitter",
        )
        read_only_fields = fields


def _visible_work_items(*, project_run: ProjectRun, member: TeamMember):
    return [
        item
        for item in project_run.project_version.work_items.all()
        if (
            item.role_id is None
            or (
                item.role_id == member.role_id
                and (
                    item.technology_stack_id is None
                    or item.technology_stack_id == member.technology_stack_id
                )
            )
        )
    ]


def _current_sprint(project_run: ProjectRun):
    return next(
        (
            sprint_run
            for sprint_run in project_run.sprint_runs.all()
            if sprint_run.state != SprintRunState.COMPLETED
        ),
        None,
    )


class ProjectRunDashboardSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    team = TeamMemberSnapshotSerializer(source="members", many=True, read_only=True)
    current_sprint = serializers.SerializerMethodField()
    deadline = serializers.DateTimeField(
    source="deadline_at",
    read_only=True,)
    next_action = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRun
        fields = (
            "id",
            "project",
            "state",
            "started_at",
            "deadline_at",
            "ended_at",
            "membership",
            "current_sprint",
            "deadline",
            "team",
            "next_action",
        )
        read_only_fields = fields

    def get_project(self, obj):
        template = obj.project_version.project_template
        return {
            "id": str(template.id),
            "name": template.name,
            "version_id": str(obj.project_version_id),
            "version_number": obj.project_version.version_number,
            "summary": obj.project_version.summary,
        }

    def get_membership(self, obj):
        return TeamMemberSnapshotSerializer(obj.requesting_member).data

    def get_current_sprint(self, obj):
        current = _current_sprint(obj)
        return SprintRunSerializer(current).data if current is not None else None

    
    def get_next_action(self, obj):
        current = _current_sprint(obj)
        return sprint_next_action(
            state=current.state if current is not None else None,
            is_designated_submitter=(
                current is not None
                and current.designated_submitter_id == obj.requesting_member.id
            ),
            has_sprints=bool(obj.sprint_runs.all()),
        )


class ProjectRunWorkspaceSerializer(ProjectRunDashboardSerializer):
    sprints = SprintRunSerializer(source="sprint_runs", many=True, read_only=True)
    resources = serializers.SerializerMethodField()

    class Meta(ProjectRunDashboardSerializer.Meta):
        fields = (
            *ProjectRunDashboardSerializer.Meta.fields,
            "sprints",
            "resources",
        )

    def get_resources(self, obj):
        return WorkItemSerializer(
            _visible_work_items(project_run=obj, member=obj.requesting_member),
            many=True,
        ).data


class ProjectRunLifecycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRun
        fields = ("id", "state", "started_at", "deadline_at", "ended_at")
        read_only_fields = fields


class SprintRunDetailSerializer(SprintRunSerializer):
    submissions = SprintSubmissionSerializer(many=True, read_only=True)
    work_items = serializers.SerializerMethodField()

    class Meta(SprintRunSerializer.Meta):
        fields = (*SprintRunSerializer.Meta.fields, "work_items", "submissions")

    def get_work_items(self, obj):
        project_run = obj.workspace_project_run
        items = [
            item
            for item in _visible_work_items(
                project_run=project_run,
                member=obj.requesting_member,
            )
            if item.sprint_template_id == obj.sprint_template_id
        ]
        return WorkItemSerializer(items, many=True).data
