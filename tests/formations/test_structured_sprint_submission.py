from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.formations.exceptions import (
    DesignWorkspaceRequired,
    InvalidDeploymentUrl,
    InvalidFinalCommitUrl,
    ProjectRunRepositoryRequired,
    SprintTransitionNotAllowed,
)
from apps.formations.models import SprintRunState, SprintSubmission
from apps.formations.services import (
    mark_sprint_under_review,
    submit_sprint,
    update_project_run_design_workspace,
)
from tests.formations.test_sprint_runtime_services import _create_other_project_run


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _first_sprint(project_run):
    return project_run.sprint_runs.order_by("sprint_template__sequence").first()


def _configure_project_run(project_run, *, design_url="https://design.example.com/a"):
    project_run.repository_url = "https://github.com/prolearn/structured-runtime"
    project_run.design_workspace_url = design_url
    project_run.save(update_fields=["repository_url", "design_workspace_url"])


def _submit(project_run, sprint_run, user, *, revision="a", **kwargs):
    return submit_sprint(
        sprint_run_id=sprint_run.id,
        project_run_id=project_run.id,
        user=user,
        final_commit_url=(
            "https://github.com/prolearn/structured-runtime/commit/"
            f"{revision * 40}"
        ),
        deployment_url=f"https://deploy.example.com/{revision}",
        **kwargs,
    )


def test_submission_requires_repository_design_commit_and_deployment(
    runtime_project_run,
    runtime_members,
):
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(ProjectRunRepositoryRequired):
        _submit(runtime_project_run, sprint_run, backend.user)

    runtime_project_run.repository_url = (
        "https://github.com/prolearn/structured-runtime"
    )
    runtime_project_run.save(update_fields=["repository_url"])
    with pytest.raises(DesignWorkspaceRequired):
        _submit(runtime_project_run, sprint_run, backend.user)

    runtime_project_run.design_workspace_url = "https://design.example.com/current"
    runtime_project_run.save(update_fields=["design_workspace_url"])
    with pytest.raises(InvalidFinalCommitUrl):
        submit_sprint(
            sprint_run_id=sprint_run.id,
            user=backend.user,
            final_commit_url=runtime_project_run.repository_url,
            deployment_url="https://deploy.example.com/current",
        )
    with pytest.raises(InvalidFinalCommitUrl):
        submit_sprint(
            sprint_run_id=sprint_run.id,
            user=backend.user,
            final_commit_url=(
                "https://github.com/prolearn/other/commit/"
                f"{'a' * 40}"
            ),
            deployment_url="https://deploy.example.com/current",
        )
    with pytest.raises(InvalidDeploymentUrl):
        submit_sprint(
            sprint_run_id=sprint_run.id,
            user=backend.user,
            final_commit_url=(
                f"{runtime_project_run.repository_url}/commit/{'a' * 40}"
            ),
            deployment_url="not-a-url",
        )


def test_structured_submission_is_server_attributed_and_snapshots_current_design(
    runtime_project_run,
    runtime_members,
):
    _configure_project_run(runtime_project_run)
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    submitted_at = timezone.now()

    submitted, submission = _submit(
        runtime_project_run,
        sprint_run,
        backend.user,
        evidence="Optional participant note",
        now=submitted_at,
    )

    assert submitted.state == SprintRunState.SUBMITTED
    assert submission.final_commit_url.endswith("/commit/" + "a" * 40)
    assert submission.deployment_url == "https://deploy.example.com/a"
    assert submission.design_url_snapshot == "https://design.example.com/a"
    assert submission.evidence == "Optional participant note"
    assert submission.submitted_by_id == backend.id
    assert submission.submitted_at == submitted_at


def test_design_workspace_permissions_and_cross_run_scope(
    runtime_project_run,
    runtime_members,
    facilitator,
    django_user_model,
):
    designer = runtime_members["PRODUCT_DESIGNER"]
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]

    updated = update_project_run_design_workspace(
        project_run_id=runtime_project_run.id,
        actor=designer.user,
        design_workspace_url="https://design.example.com/designer",
    )
    assert updated.design_workspace_url == "https://design.example.com/designer"

    for member in (backend, frontend):
        client = APIClient()
        client.force_login(member.user)
        response = client.patch(
            f"/api/v1/project-runs/{runtime_project_run.id}/design-workspace/",
            {"design_workspace_url": "https://design.example.com/forbidden"},
            format="json",
        )
        assert response.status_code == 403

    staff_client = APIClient()
    staff_client.force_login(facilitator)
    corrected = staff_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/design-workspace/",
        {"design_workspace_url": "https://design.example.com/staff"},
        format="json",
    )
    assert corrected.status_code == 200

    outsider = django_user_model.objects.create_user(email="design-outsider@example.com")
    outsider_client = APIClient()
    outsider_client.force_login(outsider)
    assert (
        outsider_client.patch(
            f"/api/v1/project-runs/{runtime_project_run.id}/design-workspace/",
            {"design_workspace_url": "https://design.example.com/cross-run"},
            format="json",
        ).status_code
        == 404
    )
    other_run = _create_other_project_run(
        django_user_model=django_user_model,
        project_run=runtime_project_run,
        runtime_members=runtime_members,
        facilitator=facilitator,
    )
    other_member = other_run.members.select_related("user").first()
    cross_run_client = APIClient()
    cross_run_client.force_login(other_member.user)
    assert (
        cross_run_client.patch(
            f"/api/v1/project-runs/{runtime_project_run.id}/design-workspace/",
            {"design_workspace_url": "https://design.example.com/other-run"},
            format="json",
        ).status_code
        == 404
    )
    anonymous_client = APIClient()
    assert (
        anonymous_client.patch(
            f"/api/v1/project-runs/{runtime_project_run.id}/design-workspace/",
            {"design_workspace_url": "https://design.example.com/anonymous"},
            format="json",
        ).status_code
        == 403
    )


def test_design_snapshots_are_append_only_across_workspace_changes(
    runtime_project_run,
    runtime_members,
):
    _configure_project_run(runtime_project_run)
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    frontend = runtime_members["FRONTEND_DEVELOPER"]
    designer = runtime_members["PRODUCT_DESIGNER"]

    _, first = _submit(runtime_project_run, sprint_run, backend.user, revision="a")
    update_project_run_design_workspace(
        project_run_id=runtime_project_run.id,
        actor=designer.user,
        design_workspace_url="https://design.example.com/b",
    )
    _, second = _submit(runtime_project_run, sprint_run, frontend.user, revision="b")

    first.refresh_from_db()
    assert first.design_url_snapshot == "https://design.example.com/a"
    assert second.design_url_snapshot == "https://design.example.com/b"
    assert list(sprint_run.submissions.all()) == [first, second]


def test_under_review_still_rejects_structured_submission(
    runtime_project_run,
    runtime_members,
    facilitator,
):
    _configure_project_run(runtime_project_run)
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    _submit(runtime_project_run, sprint_run, backend.user)
    mark_sprint_under_review(sprint_run_id=sprint_run.id, actor=facilitator)

    with pytest.raises(SprintTransitionNotAllowed):
        _submit(runtime_project_run, sprint_run, backend.user, revision="b")
    assert sprint_run.submissions.count() == 1


def test_submission_api_rejects_server_owned_fields_and_exposes_snapshots(
    api_client,
    runtime_project_run,
    runtime_members,
):
    _configure_project_run(runtime_project_run)
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]
    url = (
        f"/api/v1/project-runs/{runtime_project_run.id}/sprints/"
        f"{sprint_run.id}/submit/"
    )
    api_client.force_login(backend.user)
    base_payload = {
        "final_commit_url": (
            f"{runtime_project_run.repository_url}/commit/{'a' * 40}"
        ),
        "deployment_url": "https://deploy.example.com/a",
    }

    for field, value in (
        ("submitted_by", str(runtime_members["PRODUCT_DESIGNER"].id)),
        ("submitted_at", (timezone.now() - timedelta(days=1)).isoformat()),
        ("design_url_snapshot", "https://design.example.com/spoofed"),
        ("repository_url", "https://github.com/attacker/repository"),
        ("user_id", str(runtime_members["PRODUCT_DESIGNER"].user_id)),
    ):
        response = api_client.post(url, {**base_payload, field: value}, format="json")
        assert response.status_code == 400

    created = api_client.post(url, base_payload, format="json")
    assert created.status_code == 200
    detail = api_client.get(f"/api/v1/project-runs/me/sprints/{sprint_run.id}/")
    assert detail.status_code == 200
    submission = detail.data["latest_submission"]
    assert submission["final_commit_url"] == base_payload["final_commit_url"]
    assert submission["deployment_url"] == base_payload["deployment_url"]
    assert submission["design_url_snapshot"] == runtime_project_run.design_workspace_url
    assert submission["evidence"] == ""
    assert submission["submitted_by"]["id"] == str(backend.id)


def test_insert_trigger_requires_structured_fields_and_immutability_still_applies(
    runtime_project_run,
    runtime_members,
):
    _configure_project_run(runtime_project_run)
    sprint_run = _first_sprint(runtime_project_run)
    backend = runtime_members["BACKEND_DEVELOPER"]

    with pytest.raises(IntegrityError, match="Invalid Sprint submission"):
        with transaction.atomic():
            SprintSubmission.objects.create(
                sprint_run=sprint_run,
                submitted_by=backend,
            )

    with pytest.raises(IntegrityError, match="Invalid Sprint submission"):
        with transaction.atomic():
            SprintSubmission.objects.create(
                sprint_run=sprint_run,
                submitted_by=backend,
                final_commit_url=(
                    f"{runtime_project_run.repository_url}/commit/{'a' * 40}"
                ),
                deployment_url="https://deploy.example.com/a",
                design_url_snapshot="https://design.example.com/spoofed",
            )

    _, submission = _submit(runtime_project_run, sprint_run, backend.user)
    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.filter(id=submission.id).update(
            evidence="Mutated"
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        SprintSubmission.objects.filter(id=submission.id).delete()
