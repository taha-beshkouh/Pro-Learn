import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.profiles.models import (
    ProfileLink,
    Role,
    RoleCode,
    RoleTechnologyStack,
    TechnologyStack,
    UserProfile,
    UserSkill,
)


pytestmark = pytest.mark.django_db


def test_known_roles_and_stacks_are_seeded():
    assert set(Role.objects.values_list("code", flat=True)) == set(RoleCode.values)
    assert set(TechnologyStack.objects.values_list("code", flat=True)) == {
        "django-drf",
        "aspnet-core-ef-core",
        "react-typescript-vite",
    }
    assert set(
        RoleTechnologyStack.objects.values_list("role__code", "technology_stack__code")
    ) == {
        ("BACKEND_DEVELOPER", "django-drf"),
        ("BACKEND_DEVELOPER", "aspnet-core-ef-core"),
        ("FRONTEND_DEVELOPER", "react-typescript-vite"),
    }


def test_profile_uses_external_uuid_and_is_unique_per_user(user, profile):
    assert isinstance(profile.id, uuid.UUID)

    with pytest.raises(IntegrityError), transaction.atomic():
        UserProfile.objects.create(user=user)


@pytest.mark.postgresql
def test_role_code_database_constraint_rejects_unknown_code():
    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(code="UNKNOWN_ROLE", name="Unknown role")


def test_profile_role_is_protected(profile, backend_role):
    profile.selected_role = backend_role
    profile.save(update_fields=["selected_role"])

    with pytest.raises(ProtectedError):
        backend_role.delete()


def test_profile_is_deleted_with_user(user, profile):
    profile_id = profile.id

    user.delete()

    assert not UserProfile.objects.filter(id=profile_id).exists()


def test_profile_link_is_unique_per_profile_and_url(profile):
    data = {
        "profile": profile,
        "link_type": ProfileLink.LinkType.PORTFOLIO,
        "url": "https://example.com/portfolio",
    }
    ProfileLink.objects.create(**data)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProfileLink.objects.create(**data)


def test_user_skill_is_unique_and_stack_is_protected(profile, django_stack):
    UserSkill.objects.create(profile=profile, technology_stack=django_stack)

    with pytest.raises(IntegrityError), transaction.atomic():
        UserSkill.objects.create(profile=profile, technology_stack=django_stack)

    with pytest.raises(ProtectedError):
        django_stack.delete()


def test_role_technology_stack_mapping_is_unique(backend_role, django_stack):
    assert RoleTechnologyStack.objects.filter(
        role=backend_role,
        technology_stack=django_stack,
    ).exists()

    with pytest.raises(IntegrityError), transaction.atomic():
        RoleTechnologyStack.objects.create(
            role=backend_role,
            technology_stack=django_stack,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("timezone", "Unknown/Timezone"), ("interests", ["backend", "BACKEND"])],
)
def test_profile_model_validation(profile, field, value):
    setattr(profile, field, value)

    with pytest.raises(ValidationError) as exc_info:
        profile.full_clean()

    assert field in exc_info.value.message_dict
