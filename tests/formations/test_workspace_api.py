import pytest

from apps.formations.models import ProjectRunState, SprintRunState
from apps.formations.services import confirm_ready_check
from apps.projects.models import ProjectVersion


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
    assert response.data["current_sprint"]["state"] == SprintRunState.ACTIVE
    assert response.data["current_sprint"]["opened_at"] == (
        runtime_project_run.started_at.isoformat().replace("+00:00", "Z")
    )
    assert response.data["next_action"] == "SUBMIT_SPRINT"
    assert response.data["state"] == ProjectRunState.ACTIVE
    assert response.data["deadline"] == response.data["deadline_at"]


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
    canonical_version = ProjectVersion.objects.get(
        project_template__slug="helpdesk-lite",
        version_number=1,
    )
    canonical_work_item_ids = {
        str(item_id)
        for item_id in canonical_version.work_items.values_list("id", flat=True)
    }
    assert {
        item["id"] for item in workspace.data["resources"]
    }.isdisjoint(canonical_work_item_ids)
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
    assert {
        item["id"] for item in detail.data["work_items"]
    }.isdisjoint(canonical_work_item_ids)
    assert detail.data["repository_url"] is None
    assert detail.data["latest_submission"] is None
    assert detail.data["submissions"] == []


def test_locked_sprint_detail_is_visible_but_not_submittable(
    api_client,
    runtime_project_run,
    runtime_members,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    second = _ordered_sprints(runtime_project_run)[1]
    api_client.force_login(backend.user)

    detail = api_client.get(f"/api/v1/project-runs/me/sprints/{second.id}/")
    submission = api_client.post(
        _action_url(runtime_project_run, second, "submit"),
        {"evidence": "A locked Sprint cannot be submitted."},
        format="json",
    )

    assert detail.status_code == 200
    assert detail.data["state"] == SprintRunState.LOCKED
    assert submission.status_code == 409
    second.refresh_from_db()
    assert second.state == SprintRunState.LOCKED
    assert second.submissions.count() == 0


def test_anonymous_and_invalid_sprint_detail_requests_are_safe(
    api_client,
    runtime_project_run,
    runtime_members,
):
    first = _ordered_sprints(runtime_project_run)[0]

    anonymous = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")

    api_client.force_login(runtime_members["BACKEND_DEVELOPER"].user)
    invalid = api_client.get("/api/v1/project-runs/me/sprints/not-a-uuid/")

    assert anonymous.status_code == 403
    assert invalid.status_code == 404


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


@pytest.mark.parametrize(
    ("action", "payload"),
    [
        ("open", None),
        ("under-review", {}),
        ("request-changes", {}),
        ("complete", {}),
    ],
)
def test_normal_member_cannot_perform_management_transition(
    api_client,
    runtime_project_run,
    runtime_members,
    action,
    payload,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(backend.user)
    if payload is None:
        payload = {}

    response = api_client.post(
        _action_url(runtime_project_run, first, action),
        payload,
        format="json",
    )

    assert response.status_code == 403


def test_first_sprint_starts_without_designation_and_current_member_submits(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    assert first.state == SprintRunState.ACTIVE
    assert first.opened_at == runtime_project_run.started_at
    assert first.designated_submitter_id is None

    api_client.force_login(frontend.user)
    dashboard = api_client.get("/api/v1/project-runs/me/dashboard/")
    assert dashboard.status_code == 200
    assert dashboard.data["next_action"] == "SUBMIT_SPRINT"

    spoofed = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        {
            "evidence": "Spoofed actor",
            "submitted_by": str(backend.id),
        },
        format="json",
    )
    assert spoofed.status_code == 400

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
    assert first.submissions.get().submitted_by_id == frontend.id

    submitted_dashboard = api_client.get("/api/v1/project-runs/me/dashboard/")
    assert submitted_dashboard.status_code == 200
    assert submitted_dashboard.data["next_action"] == "WAIT_FOR_REVIEW"


def test_staff_open_rejects_legacy_designation_input_and_anonymous_access(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    second = _ordered_sprints(runtime_project_run)[1]
    backend = runtime_members["BACKEND_DEVELOPER"]
    url = _action_url(runtime_project_run, second, "open")

    api_client.force_login(facilitator)
    legacy = api_client.post(
        url,
        {"designated_submitter_id": str(backend.id)},
        format="json",
    )
    assert legacy.status_code == 400

    api_client.logout()
    anonymous = api_client.post(url, {}, format="json")
    assert anonymous.status_code == 403

    second.refresh_from_db()
    assert second.state == SprintRunState.LOCKED
    assert second.designated_submitter_id is None


def test_review_changes_resubmission_and_completion_use_same_sprint(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    api_client.force_login(facilitator)
    repository = api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "https://github.com/prolearn/review-history"},
        format="json",
    )
    assert repository.status_code == 200
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

    api_client.force_login(frontend.user)
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
    assert detail.data["repository_url"] == (
        "https://github.com/prolearn/review-history"
    )
    assert [item["evidence"] for item in detail.data["submissions"]] == [
        "Version one",
        "Version two",
    ]
    assert detail.data["latest_submission"]["id"] == detail.data["submissions"][-1][
        "id"
    ]
    assert detail.data["latest_submission"]["evidence"] == "Version two"
    assert [
        item["submitted_by"]["id"] for item in detail.data["submissions"]
    ] == [str(backend.id), str(frontend.id)]


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


def test_overdue_submission_is_conflict_and_client_time_cannot_bypass_cutoff(
    api_client,
    overdue_runtime_project_run,
    overdue_runtime_members,
    facilitator,
):
    backend = overdue_runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(overdue_runtime_project_run)[0]
    api_client.force_login(backend.user)
    rejected = api_client.post(
        _action_url(overdue_runtime_project_run, first, "submit"),
        {"evidence": "Late evidence"},
        format="json",
    )
    spoofed = api_client.post(
        _action_url(overdue_runtime_project_run, first, "submit"),
        {
            "evidence": "Backdated evidence",
            "submitted_at": overdue_runtime_project_run.started_at.isoformat(),
        },
        format="json",
    )

    assert rejected.status_code == 409
    assert spoofed.status_code == 400
    assert first.submissions.count() == 0


def test_manual_incomplete_api_is_staff_only_and_deadline_gated(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    url = f"/api/v1/project-runs/{runtime_project_run.id}/incomplete/"
    api_client.force_login(backend.user)
    assert api_client.post(url, {}, format="json").status_code == 403

    api_client.force_login(facilitator)
    response = api_client.post(url, {}, format="json")

    assert response.status_code == 409
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.ACTIVE


def test_staff_marks_overdue_project_run_incomplete(
    api_client,
    overdue_runtime_project_run,
    facilitator,
):
    api_client.force_login(facilitator)
    response = api_client.post(
        f"/api/v1/project-runs/{overdue_runtime_project_run.id}/incomplete/",
        {},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["state"] == ProjectRunState.INCOMPLETE
    assert response.data["ended_at"] is not None
