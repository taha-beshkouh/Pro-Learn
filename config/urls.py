from django.contrib import admin
from django.urls import include, path, re_path

from config.spa import spa_index


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.api.urls")),
    path("api/v1/", include("apps.profiles.api.urls")),
    path("api/v1/", include("apps.projects.api.urls")),
    path("api/v1/", include("apps.formations.api.urls")),
    path("", spa_index, name="spa-index"),
    re_path(
        r"^(?!(?:api|admin|static|assets)(?:/|$)|(?:favicon\.svg|icons\.svg)(?:/|$)).+",
        spa_index,
        name="spa-fallback",
    ),
]
