import re

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client


@pytest.fixture
def production_frontend(tmp_path, settings):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><head>'
        '<link rel="stylesheet" href="/assets/main-abc123.css">'
        '<script type="module" src="/assets/main-abc123.js"></script>'
        '</head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (assets / "main-abc123.css").write_text("body { color: black; }", encoding="utf-8")
    (assets / "main-abc123.js").write_text("console.log('built');", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (dist / "icons.svg").write_text("<svg></svg>", encoding="utf-8")
    static_root = tmp_path / "staticfiles"
    static_root.mkdir()

    settings.DEBUG = False
    settings.FRONTEND_DIST_DIR = dist
    settings.WHITENOISE_ROOT = dist
    settings.STATIC_ROOT = static_root
    return dist


@pytest.mark.parametrize(
    "route",
    ["/", "/dashboard", "/workspace", "/workspace/sprints/abc123", "/ready-check", "/staff/formations"],
)
def test_frontend_routes_serve_generated_index(production_frontend, route):
    response = Client().get(route)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    assert response["Cache-Control"] == "no-cache"
    assert b'<div id="root"></div>' in response.content


@pytest.mark.parametrize(
    "route",
    [
        "/api/v1/nonexistent/",
        "/static/nonexistent.css",
        "/assets/nonexistent.js",
    ],
)
def test_backend_and_asset_paths_never_fall_back_to_spa(production_frontend, route):
    response = Client().get(route)

    assert response.status_code == 404
    assert b'<div id="root"></div>' not in response.content


def test_api_and_admin_keep_their_own_routes(production_frontend):
    client = Client()

    csrf_response = client.get("/api/v1/auth/csrf/")
    admin_response = client.get("/admin/login/")
    missing_admin_response = client.get("/admin/nonexistent/")

    assert csrf_response.status_code == 200
    assert csrf_response["Content-Type"].startswith("application/json")
    assert admin_response.status_code == 200
    assert b'<div id="root"></div>' not in admin_response.content
    assert missing_admin_response.status_code == 302
    assert missing_admin_response["Location"].startswith("/admin/login/")


def test_unsafe_auth_request_still_requires_csrf(production_frontend):
    response = Client(enforce_csrf_checks=True).post(
        "/api/v1/auth/login/",
        {"email": "person@example.com", "password": "not-a-real-password"},
    )

    assert response.status_code == 403
    assert b'<div id="root"></div>' not in response.content


def test_vite_asset_references_and_public_files_are_served(production_frontend):
    client = Client()
    index = client.get("/").content.decode("utf-8")
    referenced_assets = re.findall(r'["\'](/assets/[^"\']+)["\']', index)

    assert len(referenced_assets) == 2
    for asset_url in referenced_assets:
        response = client.get(asset_url)
        assert response.status_code == 200
        assert response["Content-Type"] != "text/html; charset=utf-8"

    for public_url in ("/favicon.svg", "/icons.svg"):
        response = client.get(public_url)
        assert response.status_code == 200
        assert b"<svg" in b"".join(response.streaming_content)


def test_missing_root_public_file_does_not_fall_back_to_spa(production_frontend):
    (production_frontend / "favicon.svg").unlink()

    response = Client().get("/favicon.svg")

    assert response.status_code == 404
    assert b'<div id="root"></div>' not in response.content


def test_spa_entry_is_safe_method_only(production_frontend):
    response = Client().post("/dashboard", {})

    assert response.status_code == 405


def test_missing_frontend_build_is_a_configuration_error(tmp_path, settings):
    static_root = tmp_path / "staticfiles"
    static_root.mkdir()
    settings.STATIC_ROOT = static_root
    settings.FRONTEND_DIST_DIR = tmp_path / "missing-dist"

    with pytest.raises(ImproperlyConfigured, match="Frontend production build is missing"):
        Client().get("/")


def test_collectstatic_collects_django_admin_assets(tmp_path, settings):
    settings.STATIC_ROOT = tmp_path / "staticfiles"

    call_command("collectstatic", interactive=False, verbosity=0)

    assert (settings.STATIC_ROOT / "admin" / "css" / "base.css").is_file()
    assert Client().get("/static/admin/css/base.css").status_code == 200


def test_default_static_root_is_configured_for_collection():
    from django.conf import settings

    assert settings.STATIC_URL == "/static/"
    assert settings.STATIC_ROOT == settings.BASE_DIR / "staticfiles"


def test_current_vite_build_asset_references_resolve_when_built(tmp_path, settings):
    dist = settings.FRONTEND_DIST_DIR
    if not (dist / "index.html").is_file():
        pytest.skip("Build the frontend before validating its generated asset references.")

    static_root = tmp_path / "staticfiles"
    static_root.mkdir()
    settings.DEBUG = False
    settings.STATIC_ROOT = static_root
    client = Client()
    index = client.get("/").content.decode("utf-8")
    referenced_assets = re.findall(r'["\'](/assets/[^"\']+)["\']', index)

    assert referenced_assets
    for asset_url in referenced_assets:
        assert (dist / asset_url.lstrip("/")).is_file()
        assert client.get(asset_url).status_code == 200
