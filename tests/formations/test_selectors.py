import pytest

from apps.formations.api.serializers import (
    MyReadyCheckSerializer,
    ProjectRunDashboardSerializer,
    ProjectRunWorkspaceSerializer,
    TeamFormationSerializer,
)
from apps.formations.selectors import (
    active_project_run_for_user,
    current_ready_checks_for_user,
    formation_detail,
)
from apps.formations.services import confirm_ready_check


pytestmark = pytest.mark.django_db


def test_formation_detail_serialization_uses_two_queries(
    django_assert_num_queries, formation
):
    with django_assert_num_queries(2):
        selected = formation_detail(formation_id=formation.id)
        data = TeamFormationSerializer(selected).data

    assert len(data["ready_checks"]) == 3


def test_member_ready_check_serialization_uses_one_query(
    django_assert_num_queries, formation, backend_user
):
    with django_assert_num_queries(1):
        data = MyReadyCheckSerializer(
            current_ready_checks_for_user(user=backend_user),
            many=True,
        ).data

    assert len(data) == 1


def test_completed_formation_serialization_stays_at_two_queries(
    django_assert_num_queries,
    formation,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)

    with django_assert_num_queries(2):
        selected = formation_detail(formation_id=formation.id)
        data = TeamFormationSerializer(selected).data

    assert data["team_id"] is not None
    assert data["project_run_id"] is not None


def test_dashboard_and_workspace_serialization_use_bounded_prefetches(
    django_assert_num_queries,
    runtime_project_run,
    runtime_members,
):
    backend = runtime_members["BACKEND_DEVELOPER"]

    with django_assert_num_queries(5):
        project_run = active_project_run_for_user(user=backend.user)
        dashboard = ProjectRunDashboardSerializer(project_run).data
        workspace = ProjectRunWorkspaceSerializer(project_run).data

    assert dashboard["id"] == str(runtime_project_run.id)
    assert len(workspace["team"]) == 3
    assert len(workspace["sprints"]) == 3
