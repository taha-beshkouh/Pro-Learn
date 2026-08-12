import pytest
from django.core.exceptions import ValidationError

from apps.profiles.api.serializers import ProfileUpdateSerializer
from apps.profiles.validators import (
    validate_interests,
    validate_internal_return_path,
    validate_timezone_name,
)


@pytest.mark.parametrize("timezone", ["UTC", "Asia/Tehran", "Europe/London"])
def test_valid_timezone_names(timezone):
    validate_timezone_name(timezone)


def test_invalid_timezone_name():
    with pytest.raises(ValidationError):
        validate_timezone_name("Not/A-Timezone")


@pytest.mark.parametrize(
    "path",
    ["/", "/projects", "/projects?level=1", "/profile#skills"],
)
def test_safe_internal_return_paths(path):
    assert validate_internal_return_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "https://example.com/projects",
        "//example.com/projects",
        "projects",
        "/\\example.com/projects",
    ],
)
def test_unsafe_return_paths_are_rejected(path):
    with pytest.raises(ValidationError):
        validate_internal_return_path(path)


@pytest.mark.parametrize(
    "interests",
    ["backend", ["backend", "BACKEND"], [""], [" not-trimmed"]],
)
def test_invalid_interest_collections(interests):
    with pytest.raises(ValidationError):
        validate_interests(interests)


def test_profile_update_rejects_unknown_fields():
    serializer = ProfileUpdateSerializer(data={"selected_role": "not-allowed"})

    assert serializer.is_valid() is False
    assert serializer.errors == {"selected_role": ["Unknown field."]}


def test_profile_update_normalizes_interest_whitespace():
    serializer = ProfileUpdateSerializer(data={"interests": ["  Backend  "]})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["interests"] == ["Backend"]

