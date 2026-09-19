import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_ENVIRONMENT_VARIABLES = {
    "LOAD_LOCAL_ENV",
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_SECURE_COOKIES",
    "DJANGO_TRUST_X_FORWARDED_PROTO",
    "DJANGO_SECURE_SSL_REDIRECT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
}
PRODUCTION_ENVIRONMENT = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "phase-3-test-only-secret-key-not-used-outside-tests",
    "DJANGO_ALLOWED_HOSTS": "app.example.test",
    "POSTGRES_DB": "prolearn",
    "POSTGRES_USER": "prolearn_user",
    "POSTGRES_PASSWORD": "test-only-password",
    "POSTGRES_HOST": "db.example.test",
    "POSTGRES_PORT": "5432",
}
SETTINGS_PROBE = """
import json
import os
from config import settings

database = settings.DATABASES["default"]
print(json.dumps({
    "debug": settings.DEBUG,
    "secret_matches": settings.SECRET_KEY == os.getenv("DJANGO_SECRET_KEY"),
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "csrf_trusted_origins": settings.CSRF_TRUSTED_ORIGINS,
    "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
    "secure_proxy_ssl_header": getattr(settings, "SECURE_PROXY_SSL_HEADER", None),
    "secure_ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "use_x_forwarded_host": settings.USE_X_FORWARDED_HOST,
    "secure_hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "secure_hsts_include_subdomains": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "secure_hsts_preload": settings.SECURE_HSTS_PRELOAD,
    "database": {
        "name": database["NAME"],
        "user": database["USER"],
        "password_matches": database["PASSWORD"] == os.getenv("POSTGRES_PASSWORD", ""),
        "host": database["HOST"],
        "port": database["PORT"],
    },
}))
"""


def run_settings(overrides=None):
    environment = os.environ.copy()
    for name in SETTINGS_ENVIRONMENT_VARIABLES:
        environment.pop(name, None)
    environment["LOAD_LOCAL_ENV"] = "0"
    environment.update(overrides or {})
    return subprocess.run(
        [sys.executable, "-c", SETTINGS_PROBE],
        cwd=BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def settings_data(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def assert_configuration_error(result, message):
    assert result.returncode != 0
    assert message in result.stderr


def test_development_defaults_remain_usable_without_production_values():
    data = settings_data(run_settings())

    assert data["debug"] is True
    assert data["secret_matches"] is False
    assert data["allowed_hosts"] == ["localhost", "127.0.0.1", "testserver"]
    assert data["csrf_trusted_origins"] == []
    assert data["session_cookie_secure"] is False
    assert data["csrf_cookie_secure"] is False
    assert data["secure_proxy_ssl_header"] is None
    assert data["secure_ssl_redirect"] is False
    assert data["use_x_forwarded_host"] is False
    assert data["secure_hsts_seconds"] == 0
    assert data["secure_hsts_include_subdomains"] is False
    assert data["secure_hsts_preload"] is False
    assert data["database"] == {
        "name": "platform_db",
        "user": "platform_user",
        "password_matches": True,
        "host": "127.0.0.1",
        "port": "5432",
    }


def test_production_settings_are_parsed_and_security_defaults_are_enabled():
    environment = {
        **PRODUCTION_ENVIRONMENT,
        "DJANGO_ALLOWED_HOSTS": " app.example.test, admin.example.test ",
        "DJANGO_CSRF_TRUSTED_ORIGINS": (
            " https://app.example.test,https://admin.example.test "
        ),
        "DJANGO_TRUST_X_FORWARDED_PROTO": "true",
        "DJANGO_SECURE_SSL_REDIRECT": "true",
    }

    data = settings_data(run_settings(environment))

    assert data["debug"] is False
    assert data["secret_matches"] is True
    assert data["allowed_hosts"] == ["app.example.test", "admin.example.test"]
    assert data["csrf_trusted_origins"] == [
        "https://app.example.test",
        "https://admin.example.test",
    ]
    assert data["session_cookie_secure"] is True
    assert data["csrf_cookie_secure"] is True
    assert data["secure_proxy_ssl_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert data["secure_ssl_redirect"] is True
    assert data["use_x_forwarded_host"] is False
    assert data["secure_hsts_seconds"] == 0
    assert data["secure_hsts_include_subdomains"] is False
    assert data["secure_hsts_preload"] is False
    assert data["database"] == {
        "name": "prolearn",
        "user": "prolearn_user",
        "password_matches": True,
        "host": "db.example.test",
        "port": "5432",
    }


@pytest.mark.parametrize("secret_key", [None, "", "   "])
def test_production_requires_a_non_blank_secret_key(secret_key):
    environment = PRODUCTION_ENVIRONMENT.copy()
    if secret_key is None:
        environment.pop("DJANGO_SECRET_KEY")
    else:
        environment["DJANGO_SECRET_KEY"] = secret_key

    result = run_settings(environment)

    assert_configuration_error(
        result,
        "DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.",
    )


@pytest.mark.parametrize("allowed_hosts", [None, "", "   "])
def test_production_requires_explicit_allowed_hosts(allowed_hosts):
    environment = PRODUCTION_ENVIRONMENT.copy()
    if allowed_hosts is None:
        environment.pop("DJANGO_ALLOWED_HOSTS")
    else:
        environment["DJANGO_ALLOWED_HOSTS"] = allowed_hosts

    result = run_settings(environment)

    assert_configuration_error(
        result,
        "DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG is false.",
    )


def test_production_rejects_wildcard_allowed_hosts():
    result = run_settings({**PRODUCTION_ENVIRONMENT, "DJANGO_ALLOWED_HOSTS": "*"})

    assert_configuration_error(
        result,
        "DJANGO_ALLOWED_HOSTS must list explicit hosts in production",
    )


@pytest.mark.parametrize(
    "name",
    [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    ],
)
@pytest.mark.parametrize("value", [None, "   "])
def test_production_requires_each_postgresql_value(name, value):
    environment = PRODUCTION_ENVIRONMENT.copy()
    if value is None:
        environment.pop(name)
    else:
        environment[name] = value

    result = run_settings(environment)

    assert_configuration_error(
        result,
        f"{name} is required when DJANGO_DEBUG is false.",
    )


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_postgresql_port_must_be_valid(port):
    result = run_settings({**PRODUCTION_ENVIRONMENT, "POSTGRES_PORT": port})

    assert result.returncode != 0
    assert "POSTGRES_PORT must" in result.stderr


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DJANGO_DEBUG", "sometimes"),
        ("DJANGO_SECURE_COOKIES", "maybe"),
        ("DJANGO_TRUST_X_FORWARDED_PROTO", "enabled"),
        ("DJANGO_SECURE_SSL_REDIRECT", "disabled-ish"),
    ],
)
def test_boolean_environment_values_are_strict(name, value):
    environment = PRODUCTION_ENVIRONMENT.copy()
    environment[name] = value

    result = run_settings(environment)

    assert_configuration_error(result, f"{name} must be a boolean value")


def test_production_cannot_disable_secure_cookies():
    result = run_settings(
        {**PRODUCTION_ENVIRONMENT, "DJANGO_SECURE_COOKIES": "false"}
    )

    assert_configuration_error(
        result,
        "DJANGO_SECURE_COOKIES must be true when DJANGO_DEBUG is false.",
    )


def test_ssl_redirect_requires_confirmed_forwarded_proto_trust():
    result = run_settings(
        {**PRODUCTION_ENVIRONMENT, "DJANGO_SECURE_SSL_REDIRECT": "true"}
    )

    assert_configuration_error(
        result,
        "DJANGO_SECURE_SSL_REDIRECT requires "
        "DJANGO_TRUST_X_FORWARDED_PROTO=true",
    )


@pytest.mark.parametrize(
    "origin",
    [
        "app.example.test",
        "ftp://app.example.test",
        "https://user@app.example.test",
        "https://app.example.test/path",
    ],
)
def test_csrf_trusted_origins_require_complete_http_origins(origin):
    result = run_settings(
        {**PRODUCTION_ENVIRONMENT, "DJANGO_CSRF_TRUSTED_ORIGINS": origin}
    )

    assert_configuration_error(
        result,
        "DJANGO_CSRF_TRUSTED_ORIGINS entries must be valid HTTP(S) origins",
    )


def test_production_csrf_trusted_origins_must_use_https():
    result = run_settings(
        {
            **PRODUCTION_ENVIRONMENT,
            "DJANGO_CSRF_TRUSTED_ORIGINS": "http://app.example.test",
        }
    )

    assert_configuration_error(
        result,
        "DJANGO_CSRF_TRUSTED_ORIGINS entries must use https in production.",
    )
