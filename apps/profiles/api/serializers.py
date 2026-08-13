from rest_framework import serializers

from apps.common.serializers import StrictFieldsSerializer
from apps.profiles.models import (
    ProfileLink,
    Role,
    TechnologyStack,
    UserProfile,
    UserSkill,
)
from apps.profiles.validators import validate_internal_return_path


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "code", "name")
        read_only_fields = fields


class TechnologyStackSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnologyStack
        fields = ("id", "code", "name")
        read_only_fields = fields


class ProfileLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileLink
        fields = ("id", "link_type", "url", "label", "position")
        read_only_fields = fields


class UserSkillSerializer(serializers.ModelSerializer):
    technology_stack = TechnologyStackSerializer(read_only=True)

    class Meta:
        model = UserSkill
        fields = ("id", "technology_stack")
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    selected_role = RoleSerializer(read_only=True)
    links = ProfileLinkSerializer(many=True, read_only=True)
    skills = UserSkillSerializer(many=True, read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "email",
            "display_name",
            "selected_role",
            "timezone",
            "language",
            "interests",
            "links",
            "skills",
        )
        read_only_fields = fields


class ProfileUpdateSerializer(StrictFieldsSerializer):
    display_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    timezone = serializers.CharField(max_length=64, allow_blank=True, required=False)
    language = serializers.CharField(max_length=35, allow_blank=True, required=False)
    interests = serializers.ListField(
        child=serializers.CharField(max_length=100, trim_whitespace=True),
        max_length=50,
        required=False,
    )

    def validate_timezone(self, value: str) -> str:
        from apps.profiles.validators import validate_timezone_name

        validate_timezone_name(value)
        return value

    def validate_interests(self, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for interest in value:
            if not interest:
                raise serializers.ValidationError("Interests must not be empty.")
            key = interest.casefold()
            if key in seen:
                raise serializers.ValidationError("Interests must be unique.")
            seen.add(key)
            normalized.append(interest)
        return normalized


class RoleSelectionSerializer(StrictFieldsSerializer):
    role_id = serializers.PrimaryKeyRelatedField(
        source="role",
        queryset=Role.objects.all(),
    )


class ProfileLinkInputSerializer(StrictFieldsSerializer):
    link_type = serializers.ChoiceField(choices=ProfileLink.LinkType.choices)
    url = serializers.URLField(max_length=500)
    label = serializers.CharField(max_length=100, allow_blank=True, required=False)
    position = serializers.IntegerField(min_value=0, max_value=32767, required=False)


class UserSkillInputSerializer(StrictFieldsSerializer):
    technology_stack_id = serializers.PrimaryKeyRelatedField(
        source="technology_stack",
        queryset=TechnologyStack.objects.all(),
    )


class GuestContextUpdateSerializer(StrictFieldsSerializer):
    selected_role_id = serializers.PrimaryKeyRelatedField(
        source="selected_role",
        queryset=Role.objects.all(),
        allow_null=True,
        required=False,
    )
    intended_action = serializers.RegexField(
        regex=r"^[a-z][a-z0-9_.:-]*$",
        max_length=64,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    return_path = serializers.CharField(
        max_length=500,
        allow_blank=True,
        allow_null=True,
        required=False,
    )

    def validate_return_path(self, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_internal_return_path(value)

