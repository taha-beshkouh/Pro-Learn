from django.urls import path

from apps.projects.api.views import (
    LevelListView,
    ProjectDetailView,
    ProjectListView,
    ProjectStackSelectionView,
)


app_name = "projects"

urlpatterns = [
    path("levels/", LevelListView.as_view(), name="level-list"),
    path("projects/", ProjectListView.as_view(), name="project-list"),
    path("projects/<uuid:project_id>/", ProjectDetailView.as_view(), name="project-detail"),
    path(
        "projects/<uuid:project_id>/stack-selection/",
        ProjectStackSelectionView.as_view(),
        name="project-stack-selection",
    ),
]
