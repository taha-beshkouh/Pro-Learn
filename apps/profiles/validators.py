import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError


MAX_INTERESTS = 50
MAX_INTEREST_LENGTH = 100
GITHUB_USERNAME_MAX_LENGTH = 39
GITHUB_USERNAME_PATTERN = re.compile(
    rf"^(?=.{{1,{GITHUB_USERNAME_MAX_LENGTH}}}\Z)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$"
)


def validate_github_username(value: str) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, str) or not GITHUB_USERNAME_PATTERN.fullmatch(value):
        raise ValidationError(
            "Enter a valid GitHub username (letters, numbers, and single hyphens only).",
            code="invalid",
        )


def validate_timezone_name(value: str) -> None:
    if not value:
        return
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValidationError("Enter a valid IANA timezone name.", code="invalid") from exc


def validate_interests(value) -> None:
    if not isinstance(value, list):
        raise ValidationError("Interests must be a list.", code="invalid")
    if len(value) > MAX_INTERESTS:
        raise ValidationError(
            f"At most {MAX_INTERESTS} interests are allowed.",
            code="max_items",
        )

    seen: set[str] = set()
    for interest in value:
        if not isinstance(interest, str):
            raise ValidationError("Every interest must be text.", code="invalid")
        if not interest or interest != interest.strip():
            raise ValidationError(
                "Interests must be non-empty and trimmed.",
                code="invalid",
            )
        if len(interest) > MAX_INTEREST_LENGTH:
            raise ValidationError(
                f"Each interest must be at most {MAX_INTEREST_LENGTH} characters.",
                code="max_length",
            )
        normalized = interest.casefold()
        if normalized in seen:
            raise ValidationError("Interests must be unique.", code="unique")
        seen.add(normalized)


def validate_internal_return_path(value: str) -> str:
    if not value:
        return value
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or parsed.scheme
        or parsed.netloc
    ):
        raise ValidationError("Return path must be a safe internal path.", code="invalid")
    return value

