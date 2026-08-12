import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


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
        email="member@example.com",
        password=password,
    )


def fetch_csrf_token(client: APIClient) -> str:
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return client.cookies["csrftoken"].value

