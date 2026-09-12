from django.core.validators import URLValidator
from rest_framework import serializers

from apps.accounts.api.serializers import UserOutputSerializer
from apps.common.serializers import StrictFieldsSerializer
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ReadyCheck,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    TeamFormation,
    TeamMember,
)
from apps.formations.services import sprint_next_action
from apps.profiles.api.serializers import RoleSerializer, TechnologyStackSerializer
from apps.profiles.validators import (
    GITHUB_USERNAME_MAX_LENGTH,
    validate_github_username,
)
from apps.projects.api.serializers import WorkItemSerializer


class ProjectReadinessSerializer(serializers.ModelSerializer):
    user = UserOutputSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    project_version_id = serializers.UUIDField(read_only=True)
    project_name = serializers.CharField(
        source="project_version.project_template.name",
        read_only=True,
    )
    version_number = serializers.IntegerField(
        source="project_version.version_number",
        read_only=True,
    )
    technology_stack = TechnologyStackSerializer(read_only=True)

    class Meta:
        model = ProjectReadiness
        fields = (
            "id",
            "user",
            "role",
            "project_version_id",
            "project_name",
            "version_number",
            "technology_stack",
            "created_at",
            "consumed_at",
        )
        read_only_fields = fields


class TeamFormationInputSerializer(StrictFieldsSerializer):
    readiness_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=3,
        max_length=3,
    )

    def validate_readiness_ids(self, value):
        if len(set(value)) != 3:
            raise serializers.ValidationError(
                "Exactly three distinct readiness IDs are required."
            )
        return value


class ReplacementInputSerializer(StrictFieldsSerializer):
    readiness_id = serializers.UUIDField()


class ProjectReadinessCandidateQuerySerializer(StrictFieldsSerializer):
    project_version_id = serializers.UUIDField()


class ReadyCheckSerializer(serializers.ModelSerializer):
    user = UserOutputSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    technology_stack = TechnologyStackSerializer(read_only=True)
    effective_status = serializers.SerializerMethodField()
    github_username = serializers.CharField(
        source="user.profile.github_username",
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = ReadyCheck
        fields = (
            "id",
            "user",
            "role",
            "technology_stack",
            "github_username",
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


class ReadyCheckConfirmInputSerializer(StrictFieldsSerializer):
    github_username = serializers.CharField(
        max_length=GITHUB_USERNAME_MAX_LENGTH,
        allow_blank=False,
        required=False,
        validators=[validate_github_username],
    )


class OpenSprintInputSerializer(StrictFieldsSerializer):
    pass


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


class StaffRepositoryTeamMemberSerializer(TeamMemberSnapshotSerializer):
    github_username = serializers.CharField(
        source="user.profile.github_username",
        allow_null=True,
        read_only=True,
    )

    class Meta(TeamMemberSnapshotSerializer.Meta):
        fields = (*TeamMemberSnapshotSerializer.Meta.fields, "github_username")


class StaffProjectRunRepositorySerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    team_id = serializers.UUIDField(read_only=True)
    members = StaffRepositoryTeamMemberSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectRun
        fields = (
            "id",
            "project",
            "team_id",
            "state",
            "started_at",
            "repository_url",
            "members",
        )
        read_only_fields = fields

    def get_project(self, obj):
        return {
            "id": str(obj.project_version.project_template_id),
            "name": obj.project_version.project_template.name,
            "version_id": str(obj.project_version_id),
            "version_number": obj.project_version.version_number,
        }


class ProjectRunRepositoryInputSerializer(StrictFieldsSerializer):
    repository_url = serializers.URLField(
        max_length=500,
        allow_blank=False,
        validators=[URLValidator(schemes=["http", "https"])],
    )


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
            has_sprints=bool(obj.sprint_runs.all()),
        )


class ProjectRunWorkspaceSerializer(ProjectRunDashboardSerializer):
    sprints = SprintRunSerializer(source="sprint_runs", many=True, read_only=True)
    resources = serializers.SerializerMethodField()

    class Meta(ProjectRunDashboardSerializer.Meta):
        fields = (
            *ProjectRunDashboardSerializer.Meta.fields,
            "repository_url",
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
    repository_url = serializers.URLField(
        source="workspace_project_run.repository_url",
        allow_null=True,
        read_only=True,
    )
    latest_submission = serializers.SerializerMethodField()
    submissions = SprintSubmissionSerializer(many=True, read_only=True)
    work_items = serializers.SerializerMethodField()

    class Meta(SprintRunSerializer.Meta):
        fields = (
            *SprintRunSerializer.Meta.fields,
            "repository_url",
            "work_items",
            "latest_submission",
            "submissions",
        )

    def get_latest_submission(self, obj):
        submissions = list(obj.submissions.all())
        if not submissions:
            return None
        return SprintSubmissionSerializer(submissions[-1]).data

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
