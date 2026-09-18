import pytest

from apps.formations.api.serializers import (
    CompleteSprintInputSerializer,
    RequestSprintChangesInputSerializer,
)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"feedback": None},
        {"feedback": ""},
        {"feedback": "   "},
        {"feedback": "\t\n"},
    ],
)
def test_request_changes_input_requires_meaningful_feedback(payload):
    serializer = RequestSprintChangesInputSerializer(data=payload)

    assert not serializer.is_valid()
    assert set(serializer.errors) == {"feedback"}


def test_request_changes_input_trims_feedback():
    serializer = RequestSprintChangesInputSerializer(
        data={"feedback": "  Correct the deployment configuration.  "}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {
        "feedback": "Correct the deployment configuration."
    }


@pytest.mark.parametrize(
    ("payload", "expected_feedback"),
    [
        ({}, ""),
        ({"feedback": ""}, ""),
        ({"feedback": "  Accepted.  "}, "Accepted."),
    ],
)
def test_complete_input_accepts_optional_feedback(payload, expected_feedback):
    serializer = CompleteSprintInputSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"feedback": expected_feedback}


@pytest.mark.parametrize(
    "field",
    [
        "reviewed_by",
        "reviewed_at",
        "sprint_submission",
        "submission_id",
        "decision",
    ],
)
def test_review_inputs_reject_client_authority_fields(field):
    serializer = RequestSprintChangesInputSerializer(
        data={"feedback": "Valid feedback.", field: "spoofed"}
    )

    assert not serializer.is_valid()
    assert set(serializer.errors) == {field}
