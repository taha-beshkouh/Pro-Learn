import pytest

from apps.formations.models import SprintRunState
from apps.formations.services import confirm_ready_check


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence"))


def _action_url(project_run, sprint_run, action):
    return (
        f"/api/v1/project-runs/{project_run.id}/sprints/"
        f"{sprint_run.id}/{action}/"
    )


def test_dashboard_summarizes_members_active_run_and_next_action(
    api_client,
    runtime_project_run,
    runtime_members,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(backend.user)

    response = api_client.get("/api/v1/project-runs/me/dashboard/")

    assert response.status_code == 200
    assert response.data["id"] == str(runtime_project_run.id)
    assert response.data["project"]["version_id"] == str(
        runtime_project_run.project_version_id
    )
    assert response.data["membership"]["role"]["code"] == "BACKEND_DEVELOPER"
    assert response.data["membership"]["technology_stack"]["code"] == "django-drf"
    assert len(response.data["team"]) == 3
    assert response.data["current_sprint"]["id"] == str(first.id)
    assert response.data["current_sprint"]["state"] == SprintRunState.LOCKED
    assert response.data["next_action"] == "WAIT_FOR_FACILITATOR"
    assert response.data["deadline"] is not None


def test_dashboard_does_not_report_unconfigured_sprints_as_completed(
    api_client,
    formation,
    backend_user,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    api_client.force_login(backend_user)

    response = api_client.get("/api/v1/project-runs/me/dashboard/")

    assert response.status_code == 200
    assert response.data["current_sprint"] is None
    assert response.data["next_action"] == "NO_SPRINT_AVAILABLE"


def test_workspace_and_sprint_detail_show_only_member_relevant_static_content(
    api_client,
    runtime_project_run,
    runtime_members,
    runtime_work_items,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(backend.user)

    workspace = api_client.get("/api/v1/project-runs/me/workspace/")
    sprint_list = api_client.get("/api/v1/project-runs/me/sprints/")
    detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")

    assert workspace.status_code == 200
    assert len(workspace.data["sprints"]) == 3
    assert sprint_list.status_code == 200
    assert [item["sequence"] for item in sprint_list.data] == [1, 2, 3]
    fixture_ids = {str(item.id) for item in runtime_work_items}
    visible_resource_ids = {
        item["id"]
        for item in workspace.data["resources"]
        if item["id"] in fixture_ids
    }
    expected_resource_ids = {
        str(item.id)
        for item in runtime_work_items
        if item.title
        in {"Shared Sprint work", "Django backend work", "Shared project resource"}
    }
    assert visible_resource_ids == expected_resource_ids
    assert detail.status_code == 200
    visible_sprint_ids = {
        item["id"] for item in detail.data["work_items"] if item["id"] in fixture_ids
    }
    expected_sprint_ids = {
        str(item.id)
        for item in runtime_work_items
        if item.title in {"Shared Sprint work", "Django backend work"}
    }
    assert visible_sprint_ids == expected_sprint_ids
    assert detail.data["submissions"] == []


def test_non_member_cannot_read_or_submit_another_project_run(
    api_client,
    runtime_project_run,
    outside_user,
):
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(outside_user)

    assert api_client.get("/api/v1/project-runs/me/dashboard/").status_code == 404
    assert (
        api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/").status_code
        == 404
    )
    assert (
        api_client.post(
            _action_url(runtime_project_run, first, "submit"),
            {"evidence": "Not mine"},
            format="json",
        ).status_code
        == 404
    )


def test_normal_member_cannot_perform_management_transition(
    api_client,
    runtime_project_run,
    runtime_members,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(backend.user)

    response = api_client.post(
        _action_url(runtime_project_run, first, "open"),
        {"designated_submitter_id": str(backend.id)},
        format="json",
    )

    assert response.status_code == 403


def test_staff_opens_sprint_and_designated_member_submits_without_approval(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(facilitator)
    opened = api_client.post(
        _action_url(runtime_project_run, first, "open"),
        {"designated_submitter_id": str(backend.id)},
        format="json",
    )
    assert opened.status_code == 200
    assert opened.data["state"] == SprintRunState.ACTIVE

    api_client.force_login(frontend.user)
    rejected = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        {"evidence": "Wrong submitter"},
        format="json",
    )
    assert rejected.status_code == 403

    api_client.force_login(backend.user)
    submitted = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        {"evidence": "Manual evidence"},
        format="json",
    )

    assert submitted.status_code == 200
    assert submitted.data["state"] == SprintRunState.SUBMITTED
    first.refresh_from_db()
    assert first.completed_at is None
    assert first.submissions.count() == 1


def test_review_changes_resubmission_and_completion_use_same_sprint(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(facilitator)
    api_client.post(
        _action_url(runtime_project_run, first, "open"),
        {"designated_submitter_id": str(backend.id)},
        format="json",
    )
    api_client.force_login(backend.user)
    api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        {"evidence": "Version one"},
        format="json",
    )
    api_client.force_login(facilitator)
    under_review = api_client.post(
        _action_url(runtime_project_run, first, "under-review"), {}, format="json"
    )
    changes = api_client.post(
        _action_url(runtime_project_run, first, "request-changes"), {}, format="json"
    )
    assert under_review.status_code == 200
    assert changes.status_code == 200
    assert under_review.data["state"] == SprintRunState.UNDER_REVIEW
    assert changes.data["state"] == SprintRunState.CHANGES_REQUESTED

    api_client.force_login(backend.user)
    resubmitted = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        {"evidence": "Version two"},
        format="json",
    )
    assert resubmitted.status_code == 200
    assert resubmitted.data["id"] == str(first.id)
    api_client.force_login(facilitator)
    api_client.post(
        _action_url(runtime_project_run, first, "under-review"), {}, format="json"
    )
    completed = api_client.post(
        _action_url(runtime_project_run, first, "complete"), {}, format="json"
    )
    assert completed.status_code == 200
    assert completed.data["state"] == SprintRunState.COMPLETED

    api_client.force_login(backend.user)
    detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")
    assert detail.status_code == 200
    assert [item["evidence"] for item in detail.data["submissions"]] == [
        "Version one",
        "Version two",
    ]


def test_invalid_api_transition_returns_conflict(
    api_client,
    runtime_project_run,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(facilitator)

    response = api_client.post(
        _action_url(runtime_project_run, first, "complete"), {}, format="json"
    )

    assert response.status_code == 409
