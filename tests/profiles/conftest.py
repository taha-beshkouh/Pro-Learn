import pytest
from rest_framework.test import APIClient

from apps.profiles.models import Role, RoleCode, TechnologyStack, UserProfile


@pytest.fixture
def password():
    return "A-Strong-Password-739!"


@pytest.fixture
def user(django_user_model, password):
    return django_user_model.objects.create_user(
        email="profile-owner@example.com",
        password=password,
    )


@pytest.fixture
def other_user(django_user_model, password):
    return django_user_model.objects.create_user(
        email="other-user@example.com",
        password=password,
    )


@pytest.fixture
def profile(user):
    return UserProfile.objects.create(user=user)


@pytest.fixture
def other_profile(other_user):
    return UserProfile.objects.create(user=other_user)


@pytest.fixture
def backend_role():
    return Role.objects.get(code=RoleCode.BACKEND_DEVELOPER)


@pytest.fixture
def frontend_role():
    return Role.objects.get(code=RoleCode.FRONTEND_DEVELOPER)


@pytest.fixture
def django_stack():
    return TechnologyStack.objects.get(code="django-drf")


@pytest.fixture
def csrf_client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def api_client():
    return APIClient()


def fetch_csrf_token(client: APIClient) -> str:
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return client.cookies["csrftoken"].value
