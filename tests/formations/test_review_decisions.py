from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from apps.formations.exceptions import (
    InvalidReviewFeedback,
    SprintAccessDenied,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    ProjectRunState,
    ReviewDecision,
    ReviewDecisionType,
    SprintRunState,
)
from apps.formations.services import (
    complete_sprint,
    mark_sprint_under_review,
    open_sprint,
    request_sprint_changes,
    submit_sprint,
)
from tests.formations.structured_submission import (
    configure_submission_runtime,
    structured_submission_kwargs,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _ordered_sprints(project_run):
    return list(project_run.sprint_runs.order_by("sprint_template__sequence", "id"))


def _action_url(project_run, sprint_run, action):
    return (
        f"/api/v1/project-runs/{project_run.id}/sprints/"
        f"{sprint_run.id}/{action}/"
    )


def _submit(
    *,
    project_run,
    sprint_run,
    member,
    evidence="Review candidate",
    revision_character="a",
    now=None,
):
    configure_submission_runtime(project_run)
    return submit_sprint(
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


def _submission_under_review(*, project_run, sprint_run, member, facilitator):
    _, submission = _submit(
        project_run=project_run,
        sprint_run=sprint_run,
        member=member,
    )
    mark_sprint_under_review(sprint_run_id=sprint_run.id, actor=facilitator)
    return submission


def test_start_review_does_not_create_review_decision(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.UNDER_REVIEW
    assert not ReviewDecision.objects.filter(
        sprint_submission=submission
    ).exists()


def test_request_changes_records_latest_submission_and_server_actor(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    first_submitted_at = sprint_run.opened_at
    latest_submitted_at = first_submitted_at + timedelta(microseconds=1)
    _, first_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        evidence="First candidate",
        revision_character="a",
        now=first_submitted_at,
    )
    _, latest_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["FRONTEND_DEVELOPER"],
        evidence="Latest candidate",
        revision_character="b",
        now=latest_submitted_at,
    )
    mark_sprint_under_review(sprint_run_id=sprint_run.id, actor=facilitator)
    before = timezone.now()

    result = request_sprint_changes(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        feedback="  Correct the authentication flow.  ",
    )

    after = timezone.now()
    decision = ReviewDecision.objects.get()
    assert result.state == SprintRunState.CHANGES_REQUESTED
    assert decision.sprint_submission_id == latest_submission.id
    assert decision.sprint_submission_id != first_submission.id
    assert decision.decision == ReviewDecisionType.CHANGES_REQUESTED
    assert decision.reviewed_by_id == facilitator.id
    assert before <= decision.reviewed_at <= after
    assert decision.feedback == "Correct the authentication flow."


@pytest.mark.parametrize("feedback", [None, "", "   ", "\t\n"])
def test_request_changes_requires_meaningful_feedback(
    runtime_project_run,
    runtime_members,
    facilitator,
    feedback,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    with pytest.raises(InvalidReviewFeedback):
        request_sprint_changes(
            sprint_run_id=sprint_run.id,
            actor=facilitator,
            feedback=feedback,
        )

    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.UNDER_REVIEW
    assert ReviewDecision.objects.count() == 0


def test_complete_records_one_decision_with_optional_feedback(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["PRODUCT_DESIGNER"],
        facilitator=facilitator,
    )

    completed = complete_sprint(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
    )

    decision = ReviewDecision.objects.get()
    assert completed.state == SprintRunState.COMPLETED
    assert decision.sprint_submission_id == submission.id
    assert decision.decision == ReviewDecisionType.COMPLETED
    assert decision.feedback == ""
    assert decision.reviewed_by_id == facilitator.id


def test_different_staff_member_may_finalize_review(
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    final_reviewer = django_user_model.objects.create_user(
        email="final-reviewer@example.com",
        password="Final-Reviewer-739!",
        is_staff=True,
    )

    request_sprint_changes(
        sprint_run_id=sprint_run.id,
        actor=final_reviewer,
        feedback="Update the final integration.",
    )

    assert submission.review_decision.reviewed_by_id == final_reviewer.id
    assert submission.review_decision.decision == ReviewDecisionType.CHANGES_REQUESTED


def test_resubmission_preserves_both_submissions_and_review_decisions(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _, first_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        evidence="Submission one",
        revision_character="1",
    )
    mark_sprint_under_review(sprint_run_id=sprint_run.id, actor=facilitator)
    request_sprint_changes(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        feedback="Fix the API integration.",
    )
    first_decision = first_submission.review_decision

    _, second_submission = _submit(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["FRONTEND_DEVELOPER"],
        evidence="Submission two",
        revision_character="2",
    )
    mark_sprint_under_review(sprint_run_id=sprint_run.id, actor=facilitator)
    complete_sprint(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        feedback="Accepted.",
    )
    second_decision = second_submission.review_decision

    assert list(sprint_run.submissions.all()) == [first_submission, second_submission]
    assert first_decision.decision == ReviewDecisionType.CHANGES_REQUESTED
    assert first_decision.feedback == "Fix the API integration."
    assert second_decision.decision == ReviewDecisionType.COMPLETED
    assert second_decision.feedback == "Accepted."
    assert ReviewDecision.objects.count() == 2


def test_review_decision_history_is_database_immutable(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    request_sprint_changes(
        sprint_run_id=sprint_run.id,
        actor=facilitator,
        feedback="Keep this immutable.",
    )
    decision = submission.review_decision

    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewDecision.objects.filter(id=decision.id).update(feedback="Changed")
    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewDecision.objects.filter(id=decision.id).delete()

    decision.refresh_from_db()
    assert decision.feedback == "Keep this immutable."


def test_database_allows_only_one_decision_per_submission(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewDecision.objects.create(
            sprint_submission=submission,
            reviewed_by=facilitator,
            decision=ReviewDecisionType.CHANGES_REQUESTED,
            feedback="First decision.",
        )
        ReviewDecision.objects.create(
            sprint_submission=submission,
            reviewed_by=facilitator,
            decision=ReviewDecisionType.COMPLETED,
            feedback="Second decision.",
        )

    assert ReviewDecision.objects.count() == 0
    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.UNDER_REVIEW


def test_database_rejects_blank_feedback_and_nonstaff_reviewer(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewDecision.objects.create(
            sprint_submission=submission,
            reviewed_by=facilitator,
            decision=ReviewDecisionType.CHANGES_REQUESTED,
            feedback="  \t\n",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewDecision.objects.create(
            sprint_submission=submission,
            reviewed_by=runtime_members["FRONTEND_DEVELOPER"].user,
            decision=ReviewDecisionType.COMPLETED,
            feedback="",
        )

    assert ReviewDecision.objects.count() == 0


@pytest.mark.parametrize(
    "payload",
    [{}, {"feedback": None}, {"feedback": ""}, {"feedback": "  \t"}],
)
def test_request_changes_api_rejects_missing_or_blank_feedback(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
    payload,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    api_client.force_login(facilitator)

    response = api_client.post(
        _action_url(runtime_project_run, sprint_run, "request-changes"),
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert set(response.data) == {"feedback"}
    assert ReviewDecision.objects.count() == 0


def test_review_api_does_not_accept_client_authority_fields(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    api_client.force_login(facilitator)
    client_time = timezone.now().isoformat()

    response = api_client.post(
        _action_url(runtime_project_run, sprint_run, "request-changes"),
        {
            "feedback": "Valid feedback.",
            "reviewed_by": str(runtime_members["BACKEND_DEVELOPER"].user_id),
            "reviewed_at": client_time,
            "sprint_submission": str(submission.id),
            "submission_id": str(submission.id),
            "decision": ReviewDecisionType.COMPLETED,
        },
        format="json",
    )

    assert response.status_code == 400
    assert set(response.data) == {
        "decision",
        "reviewed_at",
        "reviewed_by",
        "sprint_submission",
        "submission_id",
    }
    assert ReviewDecision.objects.count() == 0


def test_review_actions_require_staff_and_exact_project_run_scope(
    api_client,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    url = _action_url(runtime_project_run, sprint_run, "request-changes")

    api_client.force_login(runtime_members["FRONTEND_DEVELOPER"].user)
    assert (
        api_client.post(url, {"feedback": "Not authorized."}, format="json").status_code
        == 403
    )
    api_client.logout()
    assert (
        api_client.post(url, {"feedback": "Anonymous."}, format="json").status_code
        in {401, 403}
    )
    api_client.force_login(facilitator)
    mismatched_url = (
        f"/api/v1/project-runs/{uuid4()}/sprints/{sprint_run.id}/request-changes/"
    )
    assert (
        api_client.post(
            mismatched_url,
            {"feedback": "Wrong run."},
            format="json",
        ).status_code
        == 404
    )
    assert ReviewDecision.objects.count() == 0


def test_inactive_staff_cannot_finalize_review(
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    inactive_reviewer = django_user_model.objects.create_user(
        email="inactive-reviewer@example.com",
        password="Inactive-Reviewer-739!",
        is_staff=True,
        is_active=False,
    )

    with pytest.raises(SprintAccessDenied):
        complete_sprint(sprint_run_id=sprint_run.id, actor=inactive_reviewer)

    assert ReviewDecision.objects.count() == 0


def test_database_rejects_review_transition_without_matching_decision(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        type(sprint_run).objects.filter(id=sprint_run.id).update(
            state=SprintRunState.CHANGES_REQUESTED
        )

    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.UNDER_REVIEW
    assert ReviewDecision.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_staff_final_decisions_commit_exactly_one(
    django_user_model,
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprint_run = _ordered_sprints(runtime_project_run)[0]
    _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=sprint_run,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )
    other_staff = django_user_model.objects.create_user(
        email="second-reviewer@example.com",
        password="Second-Reviewer-739!",
        is_staff=True,
    )
    barrier = Barrier(2)

    def finalize(actor_id, decision):
        close_old_connections()
        try:
            actor = django_user_model.objects.get(id=actor_id)
            barrier.wait(timeout=5)
            try:
                if decision == ReviewDecisionType.CHANGES_REQUESTED:
                    request_sprint_changes(
                        sprint_run_id=sprint_run.id,
                        actor=actor,
                        feedback="Concurrent requested changes.",
                    )
                else:
                    complete_sprint(sprint_run_id=sprint_run.id, actor=actor)
            except SprintTransitionNotAllowed:
                return "rejected"
            return decision
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        changes_future = executor.submit(
            finalize,
            facilitator.id,
            ReviewDecisionType.CHANGES_REQUESTED,
        )
        complete_future = executor.submit(
            finalize,
            other_staff.id,
            ReviewDecisionType.COMPLETED,
        )
        results = [changes_future.result(), complete_future.result()]

    assert results.count("rejected") == 1
    decision = ReviewDecision.objects.get()
    assert decision.decision in results
    sprint_run.refresh_from_db()
    assert sprint_run.state == decision.decision


def test_nonfinal_completion_records_decision_without_opening_next_sprint(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    first, second, _ = _ordered_sprints(runtime_project_run)
    submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=first,
        member=runtime_members["BACKEND_DEVELOPER"],
        facilitator=facilitator,
    )

    complete_sprint(sprint_run_id=first.id, actor=facilitator)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.state == SprintRunState.COMPLETED
    assert submission.review_decision.decision == ReviewDecisionType.COMPLETED
    assert second.state == SprintRunState.LOCKED
    assert second.opened_at is None


def test_final_completion_keeps_decision_sprint_and_project_run_atomic(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    sprints = _ordered_sprints(runtime_project_run)
    member = runtime_members["BACKEND_DEVELOPER"]
    for sprint_run in sprints[:-1]:
        if sprint_run.state == SprintRunState.LOCKED:
            open_sprint(sprint_run_id=sprint_run.id, actor=facilitator)
        _submission_under_review(
            project_run=runtime_project_run,
            sprint_run=sprint_run,
            member=member,
            facilitator=facilitator,
        )
        complete_sprint(sprint_run_id=sprint_run.id, actor=facilitator)

    final_sprint = sprints[-1]
    open_sprint(sprint_run_id=final_sprint.id, actor=facilitator)
    final_submission = _submission_under_review(
        project_run=runtime_project_run,
        sprint_run=final_sprint,
        member=member,
        facilitator=facilitator,
    )

    with patch(
        "apps.formations.services._terminalize_project_run_locked",
        side_effect=RuntimeError("terminalization failed"),
    ), pytest.raises(RuntimeError):
        complete_sprint(sprint_run_id=final_sprint.id, actor=facilitator)

    final_sprint.refresh_from_db()
    runtime_project_run.refresh_from_db()
    assert final_sprint.state == SprintRunState.UNDER_REVIEW
    assert runtime_project_run.state == ProjectRunState.ACTIVE
    assert not ReviewDecision.objects.filter(
        sprint_submission=final_submission
    ).exists()

    completed = complete_sprint(sprint_run_id=final_sprint.id, actor=facilitator)

    runtime_project_run.refresh_from_db()
    assert completed.state == SprintRunState.COMPLETED
    assert final_submission.review_decision.decision == ReviewDecisionType.COMPLETED
    assert runtime_project_run.state == ProjectRunState.COMPLETED
    assert runtime_project_run.ended_at == completed.completed_at
