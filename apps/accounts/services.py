import re
from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest

from apps.accounts.models import User
from apps.profiles.models import Role, UserProfile
from apps.profiles.services import (
    create_profile_for_user,
    guest_context_from_session,
    update_guest_context,
)
from apps.profiles.validators import validate_internal_return_path
from apps.projects.models import ProjectVersion


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class RegistrationData:
    email: str
    password: str


@dataclass(frozen=True)
class LoginRoleConflict:
    guest_role: Role
    persisted_role: Role


def _uuid_or_none(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _validated_guest_continuation(
    *, request: HttpRequest
) -> tuple[Role | None, dict]:
    context = guest_context_from_session(session=request.session)

    role_id = _uuid_or_none(context.get("selected_role_id"))
    selected_role = Role.objects.filter(id=role_id).first() if role_id else None

    project_version_id = _uuid_or_none(context.get("project_version_id"))
    project_version = (
        ProjectVersion.objects.filter(
            id=project_version_id,
            published_at__isnull=False,
        ).first()
        if project_version_id
        else None
    )

    intended_action = context.get("intended_action")
    if not isinstance(intended_action, str) or not re.fullmatch(
        r"[a-z][a-z0-9_.:-]{0,63}", intended_action
    ):
        intended_action = None

    return_path = context.get("return_path")
    try:
        return_path = (
            validate_internal_return_path(return_path)
            if isinstance(return_path, str)
            else None
        )
    except DjangoValidationError:
        return_path = None

    return selected_role, {
        "selected_role": selected_role,
        "project_version_id": project_version.id if project_version else None,
        "intended_action": intended_action,
        "return_path": return_path,
    }


def _start_session_with_continuation(
    *, request: HttpRequest, user: User, continuation: dict
) -> None:
    from apps.projects.services import clear_authenticated_stack_selection

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    clear_authenticated_stack_selection(session=request.session)
    update_guest_context(session=request.session, changes=continuation)
    request.session.save()


def register_and_start_session(*, request: HttpRequest, data: RegistrationData) -> User:
    selected_role, continuation = _validated_guest_continuation(request=request)
    try:
        with transaction.atomic():
            user = User.objects.create_user(email=data.email, password=data.password)
            create_profile_for_user(user=user, selected_role=selected_role)
            _start_session_with_continuation(
                request=request,
                user=user,
                continuation=continuation,
            )
            return user
    except IntegrityError as exc:
        if User.objects.filter(email__iexact=data.email).exists():
            raise EmailAlreadyRegistered from exc
        raise


def authenticate_user(*, request: HttpRequest, email: str, password: str) -> User:
    user = authenticate(
        request=request,
        email=User.objects.normalize_email(email),
        password=password,
    )
    if user is None:
        raise InvalidCredentials
    return user


def start_authenticated_session(
    *, request: HttpRequest, user: User
) -> LoginRoleConflict | None:
    guest_role, continuation = _validated_guest_continuation(request=request)
    profile = (
        UserProfile.objects.select_related("selected_role")
        .filter(user=user)
        .first()
    )
    persisted_role = profile.selected_role if profile is not None else None
    role_conflict = (
        LoginRoleConflict(
            guest_role=guest_role,
            persisted_role=persisted_role,
        )
        if guest_role is not None
        and persisted_role is not None
        and guest_role.id != persisted_role.id
        else None
    )
    _start_session_with_continuation(
        request=request,
        user=user,
        continuation=continuation,
    )
    return role_conflict
