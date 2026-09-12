from unittest.mock import patch

import pytest

from apps.formations.exceptions import FormationCompletionConflict, ReadyCheckExpired
from apps.formations.models import ProjectReadiness, ProjectRun, ReadyCheckStatus
from apps.formations.services import confirm_ready_check, create_team_formation
from apps.profiles.models import RoleCode, UserProfile


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def _confirm_url(ready_check):
    return f"/api/v1/ready-checks/{ready_check.id}/confirm/"


def _create_other_project_run(
    *, django_user_model, project_run, runtime_members, facilitator
):
    readinesses = []
    for member in runtime_members.values():
        user = django_user_model.objects.create_user(
            email=f"repository-{member.role.code.lower()}@example.com"
        )
        UserProfile.objects.create(
            user=user,
            selected_role=member.role,
            github_username=(
                f"repository-{user.id.hex[:12]}"
                if member.role.code
                in {RoleCode.BACKEND_DEVELOPER, RoleCode.FRONTEND_DEVELOPER}
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
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    return ProjectRun.objects.get(team__formation=formation)


@pytest.mark.parametrize("role_code", ["BACKEND_DEVELOPER", "FRONTEND_DEVELOPER"])
def test_developer_ready_check_requires_github_username(
    api_client, formation, role_code
):
    ready_check = formation.ready_checks.select_related("user__profile", "role").get(
        role__code=role_code,
        is_current=True,
    )
    ready_check.user.profile.github_username = None
    ready_check.user.profile.save(update_fields=["github_username"])
    api_client.force_login(ready_check.user)

    response = api_client.post(_confirm_url(ready_check), {}, format="json")

    assert response.status_code == 400
    assert "github_username" in response.data
    ready_check.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.PENDING


def test_product_designer_may_confirm_without_github_username(
    api_client, formation, designer_user
):
    ready_check = formation.ready_checks.get(user=designer_user, is_current=True)
    assert designer_user.profile.github_username is None
    api_client.force_login(designer_user)

    response = api_client.post(_confirm_url(ready_check), {}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == ReadyCheckStatus.CONFIRMED
    assert response.data["github_username"] is None


def test_ready_check_confirmation_persists_valid_github_username_atomically(
    api_client, formation, backend_user
):
    profile = backend_user.profile
    profile.github_username = None
    profile.save(update_fields=["github_username"])
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(backend_user)

    response = api_client.post(
        _confirm_url(ready_check),
        {"github_username": "backend-contributor"},
        format="json",
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.github_username == "backend-contributor"
    assert response.data["github_username"] == "backend-contributor"


def test_existing_profile_github_username_is_reused_without_request_field(
    api_client, formation, frontend_user
):
    ready_check = formation.ready_checks.get(user=frontend_user, is_current=True)
    existing = frontend_user.profile.github_username
    api_client.force_login(frontend_user)

    response = api_client.post(_confirm_url(ready_check), {}, format="json")

    assert response.status_code == 200
    assert response.data["github_username"] == existing


def test_failed_final_confirmation_rolls_back_github_profile_update(
    formation, backend_user
):
    final_check = formation.ready_checks.get(user=backend_user, is_current=True)
    profile = backend_user.profile
    profile.github_username = None
    profile.save(update_fields=["github_username"])
    for ready_check in formation.ready_checks.exclude(id=final_check.id):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)

    with patch(
        "apps.formations.services._ensure_team_and_project_run_locked",
        side_effect=FormationCompletionConflict,
    ), pytest.raises(FormationCompletionConflict):
        confirm_ready_check(
            ready_check_id=final_check.id,
            user=backend_user,
            github_username="rollback-user",
        )

    profile.refresh_from_db()
    final_check.refresh_from_db()
    assert profile.github_username is None
    assert final_check.status == ReadyCheckStatus.PENDING


def test_ready_check_cannot_update_another_users_github_identity(
    api_client, formation, backend_user, frontend_user
):
    target = formation.ready_checks.get(user=frontend_user, is_current=True)
    original = frontend_user.profile.github_username
    api_client.force_login(backend_user)

    response = api_client.post(
        _confirm_url(target),
        {"github_username": "spoofed-account"},
        format="json",
    )

    assert response.status_code == 404
    frontend_user.profile.refresh_from_db()
    assert frontend_user.profile.github_username == original


def test_ready_check_confirmation_rejects_client_selected_user(
    api_client, formation, backend_user, frontend_user
):
    profile = backend_user.profile
    profile.github_username = None
    profile.save(update_fields=["github_username"])
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(backend_user)

    response = api_client.post(
        _confirm_url(ready_check),
        {
            "github_username": "backend-owner",
            "user_id": str(frontend_user.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["user_id"] == ["Unknown field."]
    profile.refresh_from_db()
    assert profile.github_username is None


def test_decline_does_not_require_github_username(api_client, formation, backend_user):
    profile = backend_user.profile
    profile.github_username = None
    profile.save(update_fields=["github_username"])
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(backend_user)

    response = api_client.post(
        f"/api/v1/ready-checks/{ready_check.id}/decline/", {}, format="json"
    )

    assert response.status_code == 200
    assert response.data["status"] == ReadyCheckStatus.DECLINED


def test_expiry_remains_authoritative_before_github_requirement(
    formation, backend_user
):
    profile = backend_user.profile
    profile.github_username = None
    profile.save(update_fields=["github_username"])
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)

    with pytest.raises(ReadyCheckExpired):
        confirm_ready_check(
            ready_check_id=ready_check.id,
            user=backend_user,
            github_username="valid-user",
            now=ready_check.expires_at,
        )

    ready_check.refresh_from_db()
    profile.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.EXPIRED
    assert profile.github_username is None


def test_replacement_developer_ready_check_uses_same_github_rule(
    api_client,
    formation,
    backend_user,
    replacement_backend_user,
    django_stack,
    facilitator,
):
    original = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(backend_user)
    api_client.post(
        f"/api/v1/ready-checks/{original.id}/decline/", {}, format="json"
    )
    replacement_backend_user.profile.github_username = None
    replacement_backend_user.profile.save(update_fields=["github_username"])
    readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=original.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )
    api_client.force_login(facilitator)
    replaced = api_client.post(
        (
            f"/api/v1/team-formations/{formation.id}/ready-checks/"
            f"{original.id}/replace/"
        ),
        {"readiness_id": str(readiness.id)},
        format="json",
    )
    assert replaced.status_code == 201

    api_client.force_login(replacement_backend_user)
    response = api_client.post(
        f"/api/v1/ready-checks/{replaced.data['id']}/confirm/", {}, format="json"
    )

    assert response.status_code == 400
    assert "github_username" in response.data


def test_project_run_repository_starts_empty(runtime_project_run):
    assert runtime_project_run.repository_url is None


def test_staff_lists_members_and_updates_project_run_repository(
    api_client, facilitator, runtime_project_run
):
    api_client.force_login(facilitator)

    listed = api_client.get("/api/v1/project-runs/")
    updated = api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "https://github.com/prolearn/helpdesk-run"},
        format="json",
    )

    assert listed.status_code == 200
    item = next(row for row in listed.data if row["id"] == str(runtime_project_run.id))
    assert len(item["members"]) == 3
    assert {member["role"]["code"] for member in item["members"]} == {
        "BACKEND_DEVELOPER",
        "FRONTEND_DEVELOPER",
        "PRODUCT_DESIGNER",
    }
    assert all("github_username" in member for member in item["members"])
    assert updated.status_code == 200
    assert updated.data["repository_url"] == "https://github.com/prolearn/helpdesk-run"
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.repository_url == "https://github.com/prolearn/helpdesk-run"


def test_staff_repository_assignment_rejects_normalized_duplicate_on_another_run(
    api_client,
    django_user_model,
    facilitator,
    runtime_project_run,
    runtime_members,
):
    other_run = _create_other_project_run(
        django_user_model=django_user_model,
        project_run=runtime_project_run,
        runtime_members=runtime_members,
        facilitator=facilitator,
    )
    api_client.force_login(facilitator)

    first = api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "https://www.github.com/ProLearn/Shared-Repo.git/"},
        format="json",
    )
    same_run = api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "https://github.com/prolearn/shared-repo"},
        format="json",
    )
    duplicate = api_client.patch(
        f"/api/v1/project-runs/{other_run.id}/repository/",
        {"repository_url": "http://github.com/prolearn/shared-repo/?source=staff"},
        format="json",
    )

    assert first.status_code == 200
    assert same_run.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.data == {
        "repository_url": [
            "This repository is already assigned to another ProjectRun."
        ]
    }
    other_run.refresh_from_db()
    assert other_run.repository_url is None


def test_participant_and_anonymous_cannot_manage_project_run_repository(
    api_client, backend_user, runtime_project_run
):
    url = f"/api/v1/project-runs/{runtime_project_run.id}/repository/"
    payload = {"repository_url": "https://github.com/prolearn/forbidden"}

    assert api_client.patch(url, payload, format="json").status_code == 403
    api_client.force_login(backend_user)
    assert api_client.get("/api/v1/project-runs/").status_code == 403
    assert api_client.patch(url, payload, format="json").status_code == 403
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.repository_url is None


def test_invalid_project_run_repository_url_is_rejected(
    api_client, facilitator, runtime_project_run
):
    api_client.force_login(facilitator)
    response = api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "not-a-url"},
        format="json",
    )

    assert response.status_code == 400
    runtime_project_run.refresh_from_db()
    assert runtime_project_run.repository_url is None


def test_workspace_exposes_repository_url_and_allows_missing_value(
    api_client, backend_user, facilitator, runtime_project_run
):
    api_client.force_login(backend_user)
    missing = api_client.get("/api/v1/project-runs/me/workspace/")
    assert missing.status_code == 200
    assert missing.data["repository_url"] is None

    api_client.force_login(facilitator)
    api_client.patch(
        f"/api/v1/project-runs/{runtime_project_run.id}/repository/",
        {"repository_url": "https://github.com/prolearn/runtime"},
        format="json",
    )
    api_client.force_login(backend_user)
    configured = api_client.get("/api/v1/project-runs/me/workspace/")
    assert configured.status_code == 200
    assert configured.data["repository_url"] == "https://github.com/prolearn/runtime"
