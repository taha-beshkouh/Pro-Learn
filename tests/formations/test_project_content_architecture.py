import pytest

from apps.formations.api.serializers import SprintRunDetailSerializer
from apps.formations.selectors import active_sprint_run_for_user


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


@pytest.mark.parametrize(
    ("role_code", "expected_titles", "expected_positions", "expected_stack_code"),
    [
        (
            "BACKEND_DEVELOPER",
            ["Shared Sprint work", "Django backend work"],
            [100, 101],
            "django-drf",
        ),
        (
            "FRONTEND_DEVELOPER",
            ["Shared Sprint work", "Frontend work"],
            [100, 103],
            "react-typescript-vite",
        ),
        (
            "PRODUCT_DESIGNER",
            ["Shared Sprint work", "Designer work"],
            [100, 104],
            None,
        ),
    ],
)
def test_sprint_content_is_ordered_shared_and_member_scoped_for_every_role(
    api_client,
    runtime_project_run,
    runtime_members,
    runtime_work_items,
    role_code,
    expected_titles,
    expected_positions,
    expected_stack_code,
):
    member = runtime_members[role_code]
    first_sprint = runtime_project_run.sprint_runs.order_by(
        "sprint_template__sequence"
    ).first()
    fixture_ids = {str(item.id) for item in runtime_work_items}
    api_client.force_login(member.user)

    response = api_client.get(f"/api/v1/project-runs/me/sprints/{first_sprint.id}/")

    assert response.status_code == 200
    assert response.data["sequence"] == 1
    assert response.data["title"] == "Sprint 1"
    assert response.data["brief"] == "Brief 1"
    visible_items = [
        item for item in response.data["work_items"] if item["id"] in fixture_ids
    ]
    assert [item["title"] for item in visible_items] == expected_titles
    assert [item["position"] for item in visible_items] == expected_positions

    shared_item, role_item = visible_items
    assert shared_item["role"] is None
    assert shared_item["technology_stack"] is None
    assert role_item["role"]["code"] == role_code
    if expected_stack_code is None:
        assert role_item["technology_stack"] is None
    else:
        assert role_item["technology_stack"]["code"] == expected_stack_code


def test_sprint_detail_selection_and_serialization_stay_at_five_queries(
    django_assert_num_queries,
    runtime_project_run,
    runtime_members,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first_sprint_id = runtime_project_run.sprint_runs.order_by(
        "sprint_template__sequence"
    ).values_list("id", flat=True).first()

    with django_assert_num_queries(5):
        sprint_run = active_sprint_run_for_user(
            user=backend.user,
            sprint_run_id=first_sprint_id,
        )
        data = SprintRunDetailSerializer(sprint_run).data

    assert data["sequence"] == 1
    assert [item["title"] for item in data["work_items"]] == [
        "Shared Sprint work",
        "Django backend work",
    ]
