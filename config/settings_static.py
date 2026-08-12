"""Settings for static Django checks that must never access a database."""

from config.settings import *  # noqa: F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.dummy",
    }
}

