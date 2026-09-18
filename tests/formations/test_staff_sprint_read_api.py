import pytest
from django.utils import timezone

from apps.formations.api.serializers import (
    StaffSprintRunDetailSerializer,
    StaffSprintRunListSerializer,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ProjectRunState,
    ReviewDecisionType,
    SprintRunState,
)
from apps.formations.selectors import (
    project_run_sprints_for_staff,
    sprint_run_detail_for_staff,
)
from apps.formations.services import (
    complete_sprint,
    confirm_ready_check,
    create_team_formation,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
    submit_sprint,
)
from apps.profiles.models import RoleCode, UserProfile
from tests.formations.structured_submission import (
    configure_submission_runtime,
    structured_submission_kwargs,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence", "id"))


def _list_url(project_run):
    return f"/api/v1/project-runs/{project_run.id}/sprints/"


def _detail_url(project_run, sprint_run):
    return f"{_list_url(project_run)}{sprint_run.id}/"


def _submit(
    *,
    project_run,
    sprint_run,
    member,
    revision_character,
    evidence,
    now=None,
):
    configure_submission_runtime(project_run)
    return submit_sprint(
        project_run_id=project_run.id,
        sprint_run_id=sprint_run.id,
        user=member.user,
        evidence=evidence,
        now=now,
        **structured_submission_kwargs(
            project_run=project_run,
            sprint_run_id=sprint_run.id,
            revision_character=revision_character,
        ),
    )


def _create_other_project_run(
    *,
    django_user_model,
    project_run,
    runtime_members,
    facilitator,
):
    readinesses = []
    for member in runtime_members.values():
        user = django_user_model.objects.create_user(
            email=f"staff-read-{member.role.code.lower()}@example.com"
        )
        UserProfile.objects.create(
            user=user,
            selected_role=member.role,
            github_username=(
                f"staff-read-{user.id.hex[:12]}"
                if member.role.code
                in {
                    RoleCode.BACKEND_DEVELOPER,
                    RoleCode.FRONTEND_DEVELOPER,
                }
                else None
            ),
        )
        readinesses.append(
            ProjectReadiness.objects.create(
                user=user,
                role=member.role,
                project_version=project_run.project_version,
                technology_stack=member.technology_stack,
            )
        )

    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=[readiness.id for readiness in readinesses],
    )
    for ready_check in formation.ready_checks.select_related("user").order_by("id"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    return ProjectRun.objects.get(team__formation=formation)


def test_active_staff_and_admin_list_ordered_project_run_sprints(
    api_client,
    django_user_model,
    runtime_project_run,
    facilitator,
):
    admin = django_user_model.objects.create_superuser(
        email="staff-sprint-read-admin@example.com",
        password="Staff-Sprint-Read-739!",
    )

    for actor in (facilitator, admin):
        api_client.force_authenticate(user=actor)
        response = api_client.get(_list_url(runtime_project_run))

        assert response.status_code == 200
        assert [item["sequence"] for item in response.data] == [1, 2, 3]
        assert [item["state"] for item in response.data] == [
            SprintRunState.ACTIVE,
            SprintRunState.LOCKED,
            SprintRunState.LOCKED,
        ]
        assert response.data[0]["opened_at"] is not None
        assert response.data[1]["opened_at"] is None
        assert response.data[2]["opened_at"] is None
        assert all(item["latest_submission"] is None for item in response.data)


def test_staff_reads_exact_sprint_with_clean_empty_history_and_no_mutation(
    api_client,
    runtime_project_run,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    initial_state = first.state
    api_client.force_authenticate(user=facilitator)

    response = api_client.get(_detail_url(runtime_project_run, first))

    assert response.status_code == 200
    assert response.data["id"] == str(first.id)
    assert response.data["project_run_id"] == str(runtime_project_run.id)
    assert response.data["sequence"] == 1
    assert response.data["title"] == first.sprint_template.title
    assert response.data["state"] == SprintRunState.ACTIVE
    assert response.data["submissions"] == []
    assert response.data["latest_submission"] is None
    assert api_client.post(_detail_url(runtime_project_run, first), {}).status_code == 405
    assert api_client.post(_list_url(runtime_project_run), {}).status_code == 405
    first.refresh_from_db()
    assert first.state == initial_state
    assert first.submissions.count() == 0


def test_staff_detail_exposes_ordered_submission_and_review_history(
    api_client,
    django_assert_num_queries,
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first = _ordered_sprints(runtime_project_run)[0]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    final_reviewer = django_user_model.objects.create_user(
        email="staff-sprint-final-reviewer@example.com",
        password="Staff-Sprint-Review-739!",
        is_staff=True,
    )
    first_submission_time = timezone.now()
    _, first_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=first,
        member=backend,
        revision_character="1",
        evidence="First review candidate",
        now=first_submission_time,
    )
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    request_sprint_changes(
        sprint_run_id=first.id,
        actor=facilitator,
        feedback="Correct the integration contract.",
    )
    second_submission_time = timezone.now()
    _, second_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=first,
        member=frontend,
        revision_character="2",
        evidence="Corrected review candidate",
        now=second_submission_time,
    )
    mark_sprint_under_review(sprint_run_id=first.id, actor=facilitator)
    complete_sprint(
        sprint_run_id=first.id,
        actor=final_reviewer,
        feedback="Accepted.",
    )
    first_submission.refresh_from_db()
    second_submission.refresh_from_db()
    first_decision = first_submission.review_decision
    second_decision = second_submission.review_decision
    assert second_submission.submitted_at > first_submission.submitted_at
    history_ids_before = list(first.submissions.values_list("id", flat=True))
    decision_ids_before = [first_decision.id, second_decision.id]

    with django_assert_num_queries(3):
        list_data = StaffSprintRunListSerializer(
            project_run_sprints_for_staff(project_run_id=runtime_project_run.id),
            many=True,
        ).data
    with django_assert_num_queries(2):
        detail_data = StaffSprintRunDetailSerializer(
            sprint_run_detail_for_staff(
                project_run_id=runtime_project_run.id,
                sprint_run_id=first.id,
            )
        ).data
    assert list_data[0]["latest_submission"]["id"] == str(second_submission.id)
    assert detail_data["latest_submission"]["id"] == str(second_submission.id)

    api_client.force_authenticate(user=facilitator)
    response = api_client.get(_detail_url(runtime_project_run, first))

    assert response.status_code == 200
    assert response.data["state"] == SprintRunState.COMPLETED
    assert [item["id"] for item in response.data["submissions"]] == [
        str(first_submission.id),
        str(second_submission.id),
    ]
    first_data, second_data = response.data["submissions"]
    assert first_data["submitted_by"]["id"] == str(backend.id)
    assert first_data["submitted_at"] is not None
    assert first_data["final_commit_url"] == first_submission.final_commit_url
    assert first_data["deployment_url"] == first_submission.deployment_url
    assert first_data["design_url_snapshot"] == first_submission.design_url_snapshot
    assert first_data["evidence"] == "First review candidate"
    assert first_data["review_decision"] == {
        "id": str(first_decision.id),
        "decision": ReviewDecisionType.CHANGES_REQUESTED,
        "feedback": "Correct the integration contract.",
        "reviewed_by": {
            "id": str(facilitator.id),
            "email": facilitator.email,
        },
        "reviewed_at": first_data["review_decision"]["reviewed_at"],
    }
    assert first_data["review_decision"]["reviewed_at"] is not None
    assert second_data["submitted_by"]["id"] == str(frontend.id)
    assert second_data["review_decision"]["decision"] == ReviewDecisionType.COMPLETED
    assert second_data["review_decision"]["feedback"] == "Accepted."
    assert second_data["review_decision"]["reviewed_by"] == {
        "id": str(final_reviewer.id),
        "email": final_reviewer.email,
    }
    assert second_data["review_decision"]["reviewed_at"] is not None
    assert response.data["latest_submission"] == second_data

    first.refresh_from_db()
    assert first.state == SprintRunState.COMPLETED
    assert list(first.submissions.values_list("id", flat=True)) == history_ids_before
    assert [
        first.submissions.get(id=first_submission.id).review_decision.id,
        first.submissions.get(id=second_submission.id).review_decision.id,
    ] == decision_ids_before


def test_staff_sprint_reads_reject_participant_inactive_staff_and_anonymous(
    api_client,
    django_user_model,
    runtime_project_run,
    runtime_members,
):
    first = _ordered_sprints(runtime_project_run)[0]
    urls = (_list_url(runtime_project_run), _detail_url(runtime_project_run, first))
    inactive_staff = django_user_model.objects.create_user(
        email="inactive-staff-sprint-reader@example.com",
        password="Inactive-Staff-Reader-739!",
        is_staff=True,
        is_active=False,
    )

    for actor in (runtime_members["BACKEND_DEVELOPER"].user, inactive_staff):
        api_client.force_authenticate(user=actor)
        assert all(api_client.get(url).status_code == 403 for url in urls)

    api_client.force_authenticate(user=None)
    assert all(api_client.get(url).status_code in {401, 403} for url in urls)


def test_staff_sprint_detail_rejects_cross_project_run_mismatch(
    api_client,
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    other_run = _create_other_project_run(
        django_user_model=django_user_model,
        project_run=runtime_project_run,
        runtime_members=runtime_members,
        facilitator=facilitator,
    )
    other_sprint = _ordered_sprints(other_run)[0]
    api_client.force_authenticate(user=facilitator)

    mismatched = api_client.get(_detail_url(runtime_project_run, other_sprint))

    assert mismatched.status_code == 404
    assert mismatched.data == {"detail": "Sprint not found."}


def test_staff_can_read_preserved_history_after_project_run_terminalization(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprints = _ordered_sprints(runtime_project_run)
    submission_ids = []
    decision_ids = []
    for index, sprint in enumerate(sprints, start=1):
        if index > 1:
            open_sprint(
                project_run_id=runtime_project_run.id,
                sprint_run_id=sprint.id,
                actor=facilitator,
            )
        _, submission = _submit(
            project_run=runtime_project_run,
            sprint_run=sprint,
            member=runtime_members["BACKEND_DEVELOPER"],
            revision_character=str(index),
            evidence=f"Historical terminal-run evidence {index}",
        )
        mark_sprint_under_review(
            project_run_id=runtime_project_run.id,
            sprint_run_id=sprint.id,
            actor=facilitator,
        )
        complete_sprint(
            project_run_id=runtime_project_run.id,
            sprint_run_id=sprint.id,
            actor=facilitator,
        )
        submission.refresh_from_db()
        submission_ids.append(submission.id)
        decision_ids.append(submission.review_decision.id)

    runtime_project_run.refresh_from_db()
    terminal_sprints = _ordered_sprints(runtime_project_run)
    terminal_state_before = runtime_project_run.state
    terminal_ended_at_before = runtime_project_run.ended_at
    sprint_states_before = [
        (sprint.id, sprint.state, sprint.completed_at) for sprint in terminal_sprints
    ]
    assert runtime_project_run.state == ProjectRunState.COMPLETED
    assert all(
        sprint.state == SprintRunState.COMPLETED for sprint in terminal_sprints
    )

    api_client.force_authenticate(user=facilitator)
    sprint_list = api_client.get(_list_url(runtime_project_run))
    detail = api_client.get(_detail_url(runtime_project_run, sprints[0]))

    assert sprint_list.status_code == 200
    assert detail.status_code == 200
    assert detail.data["submissions"][0]["id"] == str(submission_ids[0])
    assert detail.data["submissions"][0]["review_decision"]["id"] == str(
        decision_ids[0]
    )
    assert detail.data["latest_submission"]["id"] == str(submission_ids[0])

    runtime_project_run.refresh_from_db()
    refreshed_sprints = _ordered_sprints(runtime_project_run)
    assert runtime_project_run.state == terminal_state_before
    assert runtime_project_run.ended_at == terminal_ended_at_before
    assert [
        (sprint.id, sprint.state, sprint.completed_at) for sprint in refreshed_sprints
    ] == sprint_states_before
    assert [
        submission_id
        for sprint in refreshed_sprints
        for submission_id in sprint.submissions.values_list("id", flat=True)
    ] == submission_ids
    assert [
        sprint.submissions.get().review_decision.id for sprint in refreshed_sprints
    ] == decision_ids
