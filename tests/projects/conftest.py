import pytest
from rest_framework.test import APIClient

from apps.profiles.models import Role, RoleCode, TechnologyStack, UserProfile
from apps.projects.models import ProjectTemplate, ProjectVersion


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def csrf_client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def password():
    return "A-Strong-Password-739!"


@pytest.fixture
def user(django_user_model, password):
    return django_user_model.objects.create_user(
        email="catalog-user@example.com",
        password=password,
    )


@pytest.fixture
def profile(user):
    return UserProfile.objects.create(user=user)


@pytest.fixture
def backend_role():
    return Role.objects.get(code=RoleCode.BACKEND_DEVELOPER)


@pytest.fixture
def frontend_role():
    return Role.objects.get(code=RoleCode.FRONTEND_DEVELOPER)


@pytest.fixture
def designer_role():
    return Role.objects.get(code=RoleCode.PRODUCT_DESIGNER)


@pytest.fixture
def django_stack():
    return TechnologyStack.objects.get(code="django-drf")


@pytest.fixture
def react_stack():
    return TechnologyStack.objects.get(code="react-typescript-vite")


@pytest.fixture
def helpdesk_template():
    return ProjectTemplate.objects.get(slug="helpdesk-lite")


@pytest.fixture
def helpdesk_version(helpdesk_template):
    return ProjectVersion.objects.get(
        project_template=helpdesk_template,
        version_number=1,
    )
