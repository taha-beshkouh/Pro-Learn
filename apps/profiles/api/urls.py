from django.urls import path

from apps.profiles.api.views import (
    CurrentProfileView,
    GuestContextView,
    ProfileLinkDetailView,
    ProfileLinkListCreateView,
    RoleListView,
    SelectRoleView,
    TechnologyStackListView,
    UserSkillDetailView,
    UserSkillListCreateView,
)


app_name = "profiles"

urlpatterns = [
    path("roles/", RoleListView.as_view(), name="role-list"),
    path(
        "technology-stacks/",
        TechnologyStackListView.as_view(),
        name="technology-stack-list",
    ),
    path("profile/", CurrentProfileView.as_view(), name="current-profile"),
    path("profile/select-role/", SelectRoleView.as_view(), name="select-role"),
    path(
        "profile/links/",
        ProfileLinkListCreateView.as_view(),
        name="profile-link-list",
    ),
    path(
        "profile/links/<uuid:link_id>/",
        ProfileLinkDetailView.as_view(),
        name="profile-link-detail",
    ),
    path(
        "profile/skills/",
        UserSkillListCreateView.as_view(),
        name="user-skill-list",
    ),
    path(
        "profile/skills/<uuid:skill_id>/",
        UserSkillDetailView.as_view(),
        name="user-skill-detail",
    ),
    path("guest-context/", GuestContextView.as_view(), name="guest-context"),
]

