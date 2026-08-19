from rest_framework import serializers

from apps.accounts.api.serializers import UserOutputSerializer
from apps.accounts.models import User
from apps.common.serializers import StrictFieldsSerializer
from apps.formations.models import ReadyCheck, TeamFormation
from apps.profiles.api.serializers import RoleSerializer, TechnologyStackSerializer
from apps.profiles.models import Role, TechnologyStack
from apps.projects.models import ProjectVersion


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

    class Meta:
        model = TeamFormation
        fields = (
            "id",
            "project_version_id",
            "project_name",
            "created_by",
            "created_at",
            "ready_confirmed_at",
            "ready_checks",
        )
        read_only_fields = fields


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

