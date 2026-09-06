import pytest
from django.conf import settings

from apps.profiles.models import Role, RoleCode, UserProfile
from apps.projects.models import ProjectVersion
from tests.accounts.conftest import fetch_csrf_token


pytestmark = pytest.mark.django_db


REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"


def test_csrf_endpoint_sets_cookie_and_returns_token(csrf_client):
    response = csrf_client.get("/api/v1/auth/csrf/")

    assert response.status_code == 200
    assert response.data["csrfToken"]
    assert csrf_client.cookies["csrftoken"].value


def test_register_creates_user_and_authenticated_session(
    csrf_client, django_user_model, password
):
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        REGISTER_URL,
        {"email": "New.Member@Example.COM", "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 201
    assert set(response.data) == {"id", "email"}
    assert response.data["email"] == "new.member@example.com"
    assert "password" not in response.data
    user = django_user_model.objects.get(email="new.member@example.com")
    assert csrf_client.session["_auth_user_id"] == str(user.pk)
    assert UserProfile.objects.filter(user=user).exists()


def test_registration_reconciles_role_and_preserves_exact_version_continuation(
    csrf_client, django_user_model, password
):
    role = Role.objects.get(code=RoleCode.BACKEND_DEVELOPER)
    project_version = ProjectVersion.objects.get(
        project_template__slug="helpdesk-lite",
        version_number=1,
    )
    return_path = f"/projects/{project_version.id}/stack-selection"
    session = csrf_client.session
    session["participation_context"] = {
        "selected_role_id": str(role.id),
        "project_version_id": str(project_version.id),
        "intended_action": "join_project",
        "return_path": return_path,
    }
    session["project_stack_selection"] = {
        "user_id": "pre-authenticated-session-data-must-not-survive"
    }
    session.save()
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        REGISTER_URL,
        {"email": "continuing@example.com", "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 201
    user = django_user_model.objects.get(email="continuing@example.com")
    assert user.profile.selected_role_id == role.id
    assert csrf_client.session["participation_context"] == {
        "selected_role_id": str(role.id),
        "project_version_id": str(project_version.id),
        "intended_action": "join_project",
        "return_path": return_path,
    }
    assert "project_stack_selection" not in csrf_client.session


def test_register_requires_csrf_token(csrf_client, django_user_model, password):
    response = csrf_client.post(
        REGISTER_URL,
        {"email": "new@example.com", "password": password},
        format="json",
    )

    assert response.status_code == 403
    assert not django_user_model.objects.filter(email="new@example.com").exists()


def test_register_rejects_duplicate_email_case_insensitively(
    csrf_client, django_user_model, password
):
    django_user_model.objects.create_user("member@example.com", password)
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        REGISTER_URL,
        {"email": "MEMBER@EXAMPLE.COM", "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert "email" in response.data
    assert django_user_model.objects.count() == 1


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "not-an-email", "password": "A-Strong-Password-739!"}, "email"),
        ({"email": "new@example.com", "password": "password"}, "password"),
    ],
)
def test_register_validates_input(csrf_client, django_user_model, payload, field):
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        REGISTER_URL,
        payload,
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert field in response.data
    assert django_user_model.objects.count() == 0


def test_register_rejects_mass_assignment_fields(
    csrf_client, django_user_model, password
):
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        REGISTER_URL,
        {
            "email": "new@example.com",
            "password": password,
            "is_staff": True,
            "is_superuser": True,
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert response.data["is_staff"] == ["Unknown field."]
    assert response.data["is_superuser"] == ["Unknown field."]
    assert django_user_model.objects.count() == 0


def test_login_is_case_insensitive_and_rotates_session(
    csrf_client, user, password
):
    session = csrf_client.session
    session["anonymous_context"] = "preserved"
    session.save()
    previous_session_key = session.session_key
    csrf_token = fetch_csrf_token(csrf_client)
    previous_csrf_cookie = csrf_client.cookies["csrftoken"].value

    response = csrf_client.post(
        LOGIN_URL,
        {"email": "MEMBER@EXAMPLE.COM", "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200
    assert response.data == {"id": str(user.pk), "email": user.email}
    assert csrf_client.session.session_key != previous_session_key
    assert csrf_client.cookies["csrftoken"].value != previous_csrf_cookie
    assert csrf_client.session["anonymous_context"] == "preserved"


def test_login_preserves_exact_version_without_overwriting_existing_profile_role(
    csrf_client, user, password
):
    profile_role = Role.objects.get(code=RoleCode.BACKEND_DEVELOPER)
    guest_role = Role.objects.get(code=RoleCode.FRONTEND_DEVELOPER)
    UserProfile.objects.create(user=user, selected_role=profile_role)
    project_version = ProjectVersion.objects.get(
        project_template__slug="helpdesk-lite",
        version_number=1,
    )
    return_path = f"/projects/{project_version.id}/stack-selection"
    session = csrf_client.session
    session["participation_context"] = {
        "selected_role_id": str(guest_role.id),
        "project_version_id": str(project_version.id),
        "intended_action": "join_project",
        "return_path": return_path,
    }
    session.save()
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        LOGIN_URL,
        {"email": user.email, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200
    profile = UserProfile.objects.get(user=user)
    assert profile.selected_role_id == profile_role.id
    assert csrf_client.session["participation_context"] == {
        "selected_role_id": str(guest_role.id),
        "project_version_id": str(project_version.id),
        "intended_action": "join_project",
        "return_path": return_path,
    }


def test_login_requires_csrf_token(csrf_client, user, password):
    response = csrf_client.post(
        LOGIN_URL,
        {"email": user.email, "password": password},
        format="json",
    )

    assert response.status_code == 403
    assert "_auth_user_id" not in csrf_client.session


@pytest.mark.parametrize("account_state", ["missing", "wrong_password", "inactive"])
def test_login_returns_same_safe_error_for_invalid_credentials(
    csrf_client, django_user_model, password, account_state
):
    email = "member@example.com"
    submitted_password = password
    if account_state != "missing":
        user = django_user_model.objects.create_user(email, password)
        if account_state == "inactive":
            user.is_active = False
            user.save(update_fields=["is_active"])
        else:
            submitted_password = "Incorrect-Password-482!"
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        LOGIN_URL,
        {"email": email, "password": submitted_password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert response.data == {
        "detail": "Unable to log in with the provided credentials."
    }


def test_current_user_returns_authenticated_user(api_client, user):
    api_client.force_login(user)

    response = api_client.get(ME_URL)

    assert response.status_code == 200
    assert response.data == {"id": str(user.pk), "email": user.email}


def test_current_user_rejects_anonymous_client(api_client):
    response = api_client.get(ME_URL)

    assert response.status_code == 403


def test_logout_requires_csrf_token(csrf_client, user):
    csrf_client.force_login(user)

    response = csrf_client.post(LOGOUT_URL, format="json")

    assert response.status_code == 403
    assert csrf_client.session["_auth_user_id"] == str(user.pk)


def test_logout_invalidates_session(csrf_client, user):
    csrf_client.force_login(user)
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.post(
        LOGOUT_URL,
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 204
    assert "_auth_user_id" not in csrf_client.session
    assert csrf_client.get(ME_URL).status_code == 403


def test_auth_throttle_defaults_are_configured():
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {
        "login": "10/min",
        "registration": "5/hour",
    }
