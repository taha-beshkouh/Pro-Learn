import pytest

from apps.formations.api.serializers import SprintSubmissionInputSerializer
from apps.formations.exceptions import InvalidDeploymentUrl, InvalidFinalCommitUrl
from apps.formations.models import ProjectRun, SprintSubmission
from apps.formations.services import (
    _final_commit_url_for_repository,
    _repository_url_identity,
    _validated_external_url,
)


def test_exact_commit_url_is_normalized_against_canonical_repository():
    _, repository_identity = _repository_url_identity(
        "https://github.com/ProLearn/Runtime.git"
    )

    result = _final_commit_url_for_repository(
        final_commit_url=(
            "HTTP://WWW.GITHUB.COM/prolearn/runtime/commit/"
            + "A" * 40
        ),
        repository_identity=repository_identity,
    )

    assert result == (
        "https://github.com/prolearn/runtime/commit/" + "a" * 40
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/prolearn/runtime",
        "https://github.com/prolearn/runtime/tree/main",
        "https://github.com/prolearn/runtime/pull/1",
        "https://github.com/prolearn/other/commit/" + "a" * 40,
        "https://github.com/prolearn/runtime/commit/not-a-sha",
        "https://github.com/prolearn/runtime/commit/" + "a" * 40 + "?diff=1",
    ],
)
def test_non_commit_or_wrong_repository_urls_are_rejected(url):
    _, repository_identity = _repository_url_identity(
        "https://github.com/prolearn/runtime"
    )

    with pytest.raises(InvalidFinalCommitUrl):
        _final_commit_url_for_repository(
            final_commit_url=url,
            repository_identity=repository_identity,
        )


def test_deployment_validation_is_local_and_rejects_credentials():
    assert (
        _validated_external_url(
            "https://deploy.example.com/release/1",
            error_class=InvalidDeploymentUrl,
        )
        == "https://deploy.example.com/release/1"
    )

    with pytest.raises(InvalidDeploymentUrl):
        _validated_external_url(
            "https://token@deploy.example.com/release/1",
            error_class=InvalidDeploymentUrl,
        )


def test_structured_submission_input_requires_only_participant_owned_fields():
    missing = SprintSubmissionInputSerializer(data={})
    assert not missing.is_valid()
    assert set(missing.errors) == {"final_commit_url", "deployment_url"}

    spoofed = SprintSubmissionInputSerializer(
        data={
            "final_commit_url": (
                "https://github.com/prolearn/runtime/commit/" + "a" * 40
            ),
            "deployment_url": "https://deploy.example.com/release/1",
            "design_url_snapshot": "https://design.example.com/spoofed",
        }
    )
    assert not spoofed.is_valid()
    assert set(spoofed.errors) == {"design_url_snapshot"}


def test_new_storage_is_nullable_only_for_historical_compatibility():
    assert ProjectRun._meta.get_field("design_workspace_url").null is True
    for field_name in (
        "final_commit_url",
        "deployment_url",
        "design_url_snapshot",
    ):
        field = SprintSubmission._meta.get_field(field_name)
        assert field.null is True
        assert field.blank is True
