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
def mvp_roles():
    role_definitions = (
        (RoleCode.BACKEND_DEVELOPER, "Backend Developer"),
        (RoleCode.FRONTEND_DEVELOPER, "Frontend Developer"),
        (RoleCode.PRODUCT_DESIGNER, "Product Designer"),
    )
    return {
        code: Role.objects.get_or_create(code=code, defaults={"name": name})[0]
        for code, name in role_definitions
    }


@pytest.fixture
def backend_role(mvp_roles):
    return mvp_roles[RoleCode.BACKEND_DEVELOPER]


@pytest.fixture
def frontend_role(mvp_roles):
    return mvp_roles[RoleCode.FRONTEND_DEVELOPER]


@pytest.fixture
def product_designer_role(mvp_roles):
    return mvp_roles[RoleCode.PRODUCT_DESIGNER]


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
