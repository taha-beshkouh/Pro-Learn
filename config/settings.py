import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{name} must be a boolean value: 1/0, true/false, yes/no, or on/off."
    )


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_origins(name: str, *, https_only: bool = False) -> list[str]:
    origins = env_list(name)
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            parsed.port
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"{name} entries must be valid HTTP(S) origins including a scheme."
            ) from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ImproperlyConfigured(
                f"{name} entries must be valid HTTP(S) origins including a scheme."
            )
        if https_only and parsed.scheme != "https":
            raise ImproperlyConfigured(
                f"{name} entries must use https in production."
            )
    return origins


def required_env(name: str, *, strip: bool = True) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ImproperlyConfigured(
            f"{name} is required when DJANGO_DEBUG is false."
        )
    return value.strip() if strip else value


LOAD_LOCAL_ENV = env_bool("LOAD_LOCAL_ENV", False)

if LOAD_LOCAL_ENV:
    load_dotenv(BASE_DIR / ".env")


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if SECRET_KEY is None or not SECRET_KEY.strip():
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.")
    SECRET_KEY = "development-only-insecure-secret-key"

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,testserver" if DEBUG else "",
)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG is false."
    )
if not DEBUG and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list explicit hosts in production; '*' is not allowed."
    )

CSRF_TRUSTED_ORIGINS = env_origins(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    https_only=not DEBUG,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts.apps.AccountsConfig",
    "apps.profiles.apps.ProfilesConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.formations.apps.FormationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if DEBUG:
    database_name = os.getenv("POSTGRES_DB", "platform_db").strip()
    database_user = os.getenv("POSTGRES_USER", "platform_user").strip()
    database_password = os.getenv("POSTGRES_PASSWORD", "")
    database_host = os.getenv("POSTGRES_HOST", "127.0.0.1").strip()
    database_port_value = os.getenv("POSTGRES_PORT", "5432").strip()
else:
    database_name = required_env("POSTGRES_DB")
    database_user = required_env("POSTGRES_USER")
    database_password = required_env("POSTGRES_PASSWORD", strip=False)
    database_host = required_env("POSTGRES_HOST")
    database_port_value = required_env("POSTGRES_PORT")

try:
    database_port = int(database_port_value)
except ValueError as exc:
    raise ImproperlyConfigured("POSTGRES_PORT must be an integer.") from exc
if not 1 <= database_port <= 65535:
    raise ImproperlyConfigured("POSTGRES_PORT must be between 1 and 65535.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": database_user,
        "PASSWORD": database_password,
        "HOST": database_host,
        "PORT": str(database_port),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
WHITENOISE_ROOT = FRONTEND_DIST_DIR
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
secure_cookies = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
if not DEBUG and not secure_cookies:
    raise ImproperlyConfigured(
        "DJANGO_SECURE_COOKIES must be true when DJANGO_DEBUG is false."
    )
SESSION_COOKIE_SECURE = secure_cookies
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = secure_cookies
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Enable these only after confirming that the deployment proxy overwrites the
# forwarded-proto header and terminates HTTPS for the application.
trust_x_forwarded_proto = env_bool("DJANGO_TRUST_X_FORWARDED_PROTO", False)
if trust_x_forwarded_proto:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
if SECURE_SSL_REDIRECT and not trust_x_forwarded_proto:
    raise ImproperlyConfigured(
        "DJANGO_SECURE_SSL_REDIRECT requires DJANGO_TRUST_X_FORWARDED_PROTO=true "
        "for the supported reverse-proxy deployment."
    )
USE_X_FORWARDED_HOST = False

# HSTS stays disabled until the real HTTPS host and proxy behavior have been
# validated. Preload and subdomain coverage must not be enabled prematurely.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("LOGIN_THROTTLE_RATE", "10/min"),
        "registration": os.getenv("REGISTRATION_THROTTLE_RATE", "5/hour"),
    },
}
