from dataclasses import dataclass

from django.contrib.auth import authenticate, login
from django.db import IntegrityError, transaction
from django.http import HttpRequest

from apps.accounts.models import User


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class RegistrationData:
    email: str
    password: str


def register_and_start_session(*, request: HttpRequest, data: RegistrationData) -> User:
    from apps.profiles.services import create_profile_for_user

    try:
        with transaction.atomic():
            user = User.objects.create_user(email=data.email, password=data.password)
            create_profile_for_user(user=user)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.save()
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
