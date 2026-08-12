import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from apps.accounts.services import RegistrationData, register_and_start_session
from apps.profiles.models import UserProfile


pytestmark = pytest.mark.django_db


def test_registration_rolls_back_user_when_session_creation_fails(
    django_user_model, monkeypatch, password
):
    request = RequestFactory().post("/api/v1/auth/register/")
    SessionMiddleware(lambda incoming_request: None).process_request(request)

    monkeypatch.setattr("apps.accounts.services.login", lambda *args, **kwargs: None)

    def fail_to_save_session(*args, **kwargs):
        raise RuntimeError("session storage unavailable")

    monkeypatch.setattr(request.session, "save", fail_to_save_session)

    with pytest.raises(RuntimeError, match="session storage unavailable"):
        register_and_start_session(
            request=request,
            data=RegistrationData(
                email="rollback@example.com",
                password=password,
            ),
        )

    assert not django_user_model.objects.filter(email="rollback@example.com").exists()
    assert not UserProfile.objects.filter(user__email="rollback@example.com").exists()
