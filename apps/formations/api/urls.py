from django.urls import path

from apps.formations.api.views import (
    ConfirmReadyCheckView,
    DeclineReadyCheckView,
    MyReadyCheckListView,
    ReplaceReadyCheckView,
    TeamFormationDetailView,
    TeamFormationListCreateView,
)


app_name = "formations"

urlpatterns = [
    path("team-formations/", TeamFormationListCreateView.as_view(), name="list-create"),
    path(
        "team-formations/<uuid:formation_id>/",
        TeamFormationDetailView.as_view(),
        name="detail",
    ),
    path(
        "team-formations/<uuid:formation_id>/ready-checks/<uuid:ready_check_id>/replace/",
        ReplaceReadyCheckView.as_view(),
        name="replace-ready-check",
    ),
    path("ready-checks/me/", MyReadyCheckListView.as_view(), name="my-ready-checks"),
    path(
        "ready-checks/<uuid:ready_check_id>/confirm/",
        ConfirmReadyCheckView.as_view(),
        name="confirm-ready-check",
    ),
    path(
        "ready-checks/<uuid:ready_check_id>/decline/",
        DeclineReadyCheckView.as_view(),
        name="decline-ready-check",
    ),
]

