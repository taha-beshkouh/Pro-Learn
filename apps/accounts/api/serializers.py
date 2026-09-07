from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User
from apps.common.serializers import StrictFieldsSerializer
from apps.profiles.api.serializers import RoleSerializer


class RegistrationInputSerializer(StrictFieldsSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        max_length=128,
    )

    def validate_email(self, value: str) -> str:
        return User.objects.normalize_email(value)

    def validate(self, attrs):
        candidate = User(email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs


class LoginInputSerializer(StrictFieldsSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        max_length=128,
    )

    def validate_email(self, value: str) -> str:
        return User.objects.normalize_email(value)


class UserOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email")
        read_only_fields = fields


class LoginRoleConflictSerializer(serializers.Serializer):
    guest_role = RoleSerializer(read_only=True)
    persisted_role = RoleSerializer(read_only=True)


class LoginResponseSerializer(UserOutputSerializer):
    role_conflict = serializers.SerializerMethodField()

    class Meta(UserOutputSerializer.Meta):
        fields = (*UserOutputSerializer.Meta.fields, "role_conflict")
        read_only_fields = fields

    def get_role_conflict(self, obj):
        conflict = self.context.get("role_conflict")
        if conflict is None:
            return None
        return LoginRoleConflictSerializer(conflict).data
