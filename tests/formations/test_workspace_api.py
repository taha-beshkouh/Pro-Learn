import pytest

from apps.formations.models import ReviewDecision, ReviewDecisionType, SprintRunState
from apps.formations.services import (
    confirm_ready_check,
    mark_sprint_under_review,
    request_sprint_changes,
    submit_sprint,
)
from tests.formations.structured_submission import (
    configure_submission_runtime,
    structured_submission_kwargs,
)
from tests.formations.test_sprint_runtime_services import _create_other_project_run


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
    assert response.data["next_action"] == "SUBMIT_SPRINT"
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

    backend_work = next(
        item for item in runtime_work_items if item.title == "Django backend work"
    )
    assert backend_work.project_version_id == runtime_project_run.project_version_id
    assert workspace.status_code == 200
    assert len(workspace.data["sprints"]) == 3
    assert sprint_list.status_code == 200
    assert [item["sequence"] for item in sprint_list.data] == [1, 2, 3]
    assert {item["title"] for item in workspace.data["resources"]} == {
        "Shared Sprint work",
        "Django backend work",
        "Shared project resource",
    }
    assert detail.status_code == 200
    assert {item["title"] for item in detail.data["work_items"]} == {
        "Shared Sprint work",
        "Django backend work",
    }
    assert detail.data["submissions"] == []
    assert detail.data["latest_submission"] is None


def test_non_member_cannot_read_or_submit_another_project_run(
    api_client,
    runtime_project_run,
    outside_user,
):
    first = _ordered_sprints(runtime_project_run)[0]
    configure_submission_runtime(runtime_project_run)
    payload = {
        **structured_submission_kwargs(
            project_run=runtime_project_run,
            sprint_run_id=first.id,
        ),
        "evidence": "Not mine",
    }
    api_client.force_login(outside_user)

    assert api_client.get("/api/v1/project-runs/me/dashboard/").status_code == 404
    assert (
        api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/").status_code
        == 404
    )
    assert (
        api_client.post(
            _action_url(runtime_project_run, first, "submit"),
            payload,
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


def test_current_member_submits_auto_active_first_sprint_without_designation(
    api_client,
    runtime_project_run,
    runtime_members,
):
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    configure_submission_runtime(runtime_project_run)
    payload = {
        **structured_submission_kwargs(
            project_run=runtime_project_run,
            sprint_run_id=first.id,
        ),
        "evidence": "Current member evidence",
    }
    assert first.state == SprintRunState.ACTIVE
    assert first.designated_submitter_id is None

    api_client.force_login(frontend.user)
    submitted = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        payload,
        format="json",
    )

    assert submitted.status_code == 200
    assert submitted.data["state"] == SprintRunState.SUBMITTED
    initial_detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")
    assert initial_detail.status_code == 200
    assert initial_detail.data["submissions"][0]["review_decision"] is None
    assert initial_detail.data["latest_submission"]["review_decision"] is None
    first.refresh_from_db()
    assert first.completed_at is None
    assert first.submissions.count() == 1
    assert first.submissions.get().submitted_by_id == frontend.id


def test_review_changes_resubmission_and_completion_use_same_sprint(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    backend = runtime_members["BACKEND_DEVELOPER"]
    first = _ordered_sprints(runtime_project_run)[0]
    configure_submission_runtime(runtime_project_run)
    first_submission = {
        **structured_submission_kwargs(
            project_run=runtime_project_run,
            sprint_run_id=first.id,
            revision_character="1",
        ),
        "evidence": "Version one",
    }
    second_submission = {
        **structured_submission_kwargs(
            project_run=runtime_project_run,
            sprint_run_id=first.id,
            revision_character="2",
        ),
        "evidence": "Version two",
    }
    design_url = runtime_project_run.design_workspace_url
    first.refresh_from_db()
    assert first.state == SprintRunState.ACTIVE

    api_client.force_login(backend.user)

    submitted = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        first_submission,
        format="json",
    )
    assert submitted.status_code == 200, submitted.data

    api_client.force_login(facilitator)
    under_review = api_client.post(
        _action_url(runtime_project_run, first, "under-review"), {}, format="json"
    )
    changes = api_client.post(
        _action_url(runtime_project_run, first, "request-changes"),
        {"feedback": "Correct the reviewed submission."},
        format="json",
    )
    assert under_review.status_code == 200
    assert changes.status_code == 200
    assert under_review.data["state"] == SprintRunState.UNDER_REVIEW
    assert changes.data["state"] == SprintRunState.CHANGES_REQUESTED

    api_client.force_login(backend.user)
    changes_detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")
    assert changes_detail.status_code == 200
    first_review = changes_detail.data["latest_submission"]["review_decision"]
    assert first_review["decision"] == ReviewDecisionType.CHANGES_REQUESTED
    assert first_review["feedback"] == "Correct the reviewed submission."
    assert first_review["reviewed_at"] is not None
    assert set(first_review) == {"decision", "feedback", "reviewed_at"}
    assert "reviewed_by" not in first_review
    assert "id" not in first_review

    resubmitted = api_client.post(
        _action_url(runtime_project_run, first, "submit"),
        second_submission,
        format="json",
    )
    assert resubmitted.status_code == 200
    assert resubmitted.data["id"] == str(first.id)
    resubmitted_detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")
    assert resubmitted_detail.status_code == 200
    assert resubmitted_detail.data["submissions"][0]["review_decision"] == first_review
    assert resubmitted_detail.data["submissions"][1]["review_decision"] is None
    assert resubmitted_detail.data["latest_submission"]["review_decision"] is None
    api_client.force_login(facilitator)
    api_client.post(
        _action_url(runtime_project_run, first, "under-review"), {}, format="json"
    )
    completed = api_client.post(
        _action_url(runtime_project_run, first, "complete"),
        {"feedback": "Accepted revision two."},
        format="json",
    )
    assert completed.status_code == 200
    assert completed.data["state"] == SprintRunState.COMPLETED

    api_client.force_login(backend.user)
    first.refresh_from_db()
    state_before_get = first.state
    history_before_get = list(
        first.submissions.order_by("submitted_at", "id").values_list("id", flat=True)
    )
    decisions_before_get = list(
        ReviewDecision.objects.order_by("id").values_list(
            "id", "sprint_submission_id", "decision", "feedback", "reviewed_at"
        )
    )
    detail = api_client.get(f"/api/v1/project-runs/me/sprints/{first.id}/")
    assert detail.status_code == 200
    assert [item["evidence"] for item in detail.data["submissions"]] == [
        "Version one",
        "Version two",
    ]
    assert [
        item["final_commit_url"] for item in detail.data["submissions"]
    ] == [
        first_submission["final_commit_url"],
        second_submission["final_commit_url"],
    ]
    assert [
        item["deployment_url"] for item in detail.data["submissions"]
    ] == [
        first_submission["deployment_url"],
        second_submission["deployment_url"],
    ]
    assert [
        item["design_url_snapshot"] for item in detail.data["submissions"]
    ] == [design_url, design_url]
    first_result, second_result = detail.data["submissions"]
    assert first_result["review_decision"] == first_review
    assert second_result["review_decision"]["decision"] == ReviewDecisionType.COMPLETED
    assert second_result["review_decision"]["feedback"] == "Accepted revision two."
    assert second_result["review_decision"]["reviewed_at"] is not None
    assert set(second_result["review_decision"]) == {
        "decision", "feedback", "reviewed_at"
    }
    assert detail.data["latest_submission"]["id"] == second_result["id"]
    assert detail.data["latest_submission"]["review_decision"] == second_result["review_decision"]
    first.refresh_from_db()
    assert first.state == state_before_get
    assert list(
        first.submissions.order_by("submitted_at", "id").values_list("id", flat=True)
    ) == history_before_get
    assert list(
        ReviewDecision.objects.order_by("id").values_list(
            "id", "sprint_submission_id", "decision", "feedback", "reviewed_at"
        )
    ) == decisions_before_get
    assert list(
        first.submissions.order_by("submitted_at", "id").values_list(
            "review_decision__decision",
            "review_decision__feedback",
        )
    ) == [
        (
            ReviewDecisionType.CHANGES_REQUESTED,
            "Correct the reviewed submission.",
        ),
        (ReviewDecisionType.COMPLETED, "Accepted revision two."),
    ]


def test_participant_review_feedback_stays_scoped_to_exact_project_run(
    api_client,
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
    outside_user,
):
    other_run = _create_other_project_run(
        django_user_model=django_user_model,
        project_run=runtime_project_run,
        runtime_members=runtime_members,
        facilitator=facilitator,
    )
    other_sprint = _ordered_sprints(other_run)[0]
    other_member = other_run.members.select_related("user").first()
    configure_submission_runtime(other_run)
    submit_sprint(
        project_run_id=other_run.id,
        sprint_run_id=other_sprint.id,
        user=other_member.user,
        evidence="Other team's evidence",
        **structured_submission_kwargs(
            project_run=other_run,
            sprint_run_id=other_sprint.id,
        ),
    )
    mark_sprint_under_review(sprint_run_id=other_sprint.id, actor=facilitator)
    request_sprint_changes(
        sprint_run_id=other_sprint.id,
        actor=facilitator,
        feedback="Private feedback for the other team.",
    )
    url = f"/api/v1/project-runs/me/sprints/{other_sprint.id}/"
    decisions_before_get = ReviewDecision.objects.count()

    api_client.force_login(runtime_members["BACKEND_DEVELOPER"].user)
    cross_run = api_client.get(url)
    assert cross_run.status_code == 404
    assert "Private feedback for the other team." not in str(cross_run.data)

    api_client.force_login(outside_user)
    non_member = api_client.get(url)
    assert non_member.status_code == 404
    assert "Private feedback for the other team." not in str(non_member.data)

    api_client.logout()
    assert api_client.get(url).status_code in (401, 403)

    api_client.force_login(other_member.user)
    permitted = api_client.get(url)
    assert permitted.status_code == 200
    assert permitted.data["latest_submission"]["review_decision"]["feedback"] == (
        "Private feedback for the other team."
    )
    assert ReviewDecision.objects.count() == decisions_before_get


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
