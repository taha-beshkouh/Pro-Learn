import uuid

import pytest
from django.db import IntegrityError, transaction


pytestmark = pytest.mark.django_db


def test_create_user_normalizes_email_and_hashes_password(django_user_model, password):
    user = django_user_model.objects.create_user(
        email="  Member@Example.COM  ",
        password=password,
    )

    assert isinstance(user.id, uuid.UUID)
    assert user.email == "member@example.com"
    assert user.check_password(password)
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_email_is_case_insensitively_unique_at_database_level(
    django_user_model, password
):
    django_user_model.objects.create_user("member@example.com", password)

    with pytest.raises(IntegrityError), transaction.atomic():
        django_user_model.objects.create_user("MEMBER@EXAMPLE.COM", password)


def test_get_by_natural_key_is_case_insensitive(django_user_model, password):
    expected = django_user_model.objects.create_user("member@example.com", password)

    assert django_user_model.objects.get_by_natural_key("MEMBER@EXAMPLE.COM") == expected


def test_create_user_requires_email(django_user_model, password):
    with pytest.raises(ValueError, match="email address is required"):
        django_user_model.objects.create_user("", password)


def test_create_superuser_sets_required_flags(django_user_model, password):
    user = django_user_model.objects.create_superuser("admin@example.com", password)

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True


@pytest.mark.parametrize("field", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_disabled_required_flag(
    django_user_model, password, field
):
    with pytest.raises(ValueError, match=f"{field}=True"):
        django_user_model.objects.create_superuser(
            "admin@example.com",
            password,
            **{field: False},
        )

