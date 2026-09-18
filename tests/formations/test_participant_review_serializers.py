from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from apps.formations.api.serializers import SprintSubmissionSerializer
from apps.formations.models import ReviewDecisionType


def _submission(review_decision):
    member = SimpleNamespace(
        id=uuid4(),
        user=SimpleNamespace(id=uuid4(), email="member@example.test"),
        role=SimpleNamespace(id=uuid4(), code="BACKEND_DEVELOPER", name="Backend"),
        technology_stack=None,
        ended_at=None,
    )
    return SimpleNamespace(
        id=uuid4(),
        submitted_by=member,
        final_commit_url="https://github.com/prolearn/example/commit/" + "a" * 40,
        deployment_url="https://deploy.example.test",
        design_url_snapshot="https://design.example.test",
        evidence="Submission note",
        submitted_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
        review_decision=review_decision,
    )


def test_participant_submission_serializes_only_safe_review_fields():
    decision = SimpleNamespace(
        id=uuid4(),
        decision=ReviewDecisionType.CHANGES_REQUESTED,
        feedback="Correct the integration.",
        reviewed_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
        reviewed_by=SimpleNamespace(id=uuid4(), email="private-staff@example.test"),
    )

    data = SprintSubmissionSerializer(_submission(decision)).data

    assert data["review_decision"]["decision"] == ReviewDecisionType.CHANGES_REQUESTED
    assert data["review_decision"]["feedback"] == "Correct the integration."
    assert data["review_decision"]["reviewed_at"] is not None
    assert set(data["review_decision"]) == {"decision", "feedback", "reviewed_at"}
    assert "private-staff@example.test" not in str(data)


def test_participant_submission_serializes_absent_review_as_null():
    data = SprintSubmissionSerializer(_submission(None)).data

    assert data["review_decision"] is None
