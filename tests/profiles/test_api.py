import uuid

import pytest

from apps.profiles.models import ProfileLink, UserProfile, UserSkill
from apps.projects.models import ProjectTemplate, ProjectVersion
from tests.profiles.conftest import fetch_csrf_token


pytestmark = pytest.mark.django_db


PROFILE_URL = "/api/v1/profile/"
SELECT_ROLE_URL = "/api/v1/profile/select-role/"
LINKS_URL = "/api/v1/profile/links/"
SKILLS_URL = "/api/v1/profile/skills/"
GUEST_CONTEXT_URL = "/api/v1/guest-context/"


def test_roles_and_stacks_are_public_and_seeded(api_client, django_user_model):
    roles = api_client.get("/api/v1/roles/")
    stacks = api_client.get("/api/v1/technology-stacks/")

    assert roles.status_code == 200
    assert {item["code"] for item in roles.data} == {
        "BACKEND_DEVELOPER",
        "FRONTEND_DEVELOPER",
        "PRODUCT_DESIGNER",
    }
    assert stacks.status_code == 200
    assert {item["code"] for item in stacks.data} == {
        "django-drf",
        "aspnet-core-ef-core",
        "react-typescript-vite",
    }
    assert django_user_model.objects.count() == 0


def test_profile_requires_authentication(api_client):
    assert api_client.get(PROFILE_URL).status_code == 403


def test_role_mutation_requires_authentication(api_client, backend_role):
    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(backend_role.id)},
        format="json",
    )

    assert response.status_code == 403


def test_authenticated_role_mutation_requires_csrf(
    csrf_client,
    user,
    profile,
    backend_role,
):
    csrf_client.force_login(user)

    response = csrf_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(backend_role.id)},
        format="json",
    )

    assert response.status_code == 403
    profile.refresh_from_db()
    assert profile.selected_role is None


def test_profile_read_and_update_are_current_user_only(
    api_client, user, profile, backend_role
):
    api_client.force_login(user)

    response = api_client.patch(
        PROFILE_URL,
        {
            "display_name": "Backend Learner",
            "timezone": "Asia/Tehran",
            "language": "fa-IR",
            "interests": ["Django", "PostgreSQL"],
        },
        format="json",
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.display_name == "Backend Learner"
    assert profile.timezone == "Asia/Tehran"
    assert profile.selected_role is None


def test_profile_rejects_role_mass_assignment(api_client, user, profile, backend_role):
    api_client.force_login(user)

    response = api_client.patch(
        PROFILE_URL,
        {"selected_role": str(backend_role.id)},
        format="json",
    )

    assert response.status_code == 400
    profile.refresh_from_db()
    assert profile.selected_role is None


def test_role_selection_supports_initial_idempotent_and_eligible_change(
    api_client, user, profile, backend_role, frontend_role
):
    api_client.force_login(user)

    first = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(backend_role.id)},
        format="json",
    )
    second = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(backend_role.id)},
        format="json",
    )
    changed = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(frontend_role.id)},
        format="json",
    )

    assert first.status_code == 200
    assert first.data["selected_role"]["code"] == "BACKEND_DEVELOPER"
    assert second.status_code == 200
    assert changed.status_code == 200
    assert changed.data["selected_role"]["code"] == "FRONTEND_DEVELOPER"
    profile.refresh_from_db()
    assert profile.selected_role == frontend_role


def test_role_selection_rejects_an_unknown_role(api_client, user, profile):
    api_client.force_login(user)

    response = api_client.post(
        SELECT_ROLE_URL,
        {"role_id": str(uuid.uuid4())},
        format="json",
    )

    assert response.status_code == 400
    assert "role_id" in response.data
    profile.refresh_from_db()
    assert profile.selected_role is None


def test_profile_update_cannot_bypass_ready_check_github_flow(
    api_client, user, profile
):
    api_client.force_login(user)

    response = api_client.patch(
        PROFILE_URL,
        {"github_username": "bypass-ready-check"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["github_username"] == ["Unknown field."]
    profile.refresh_from_db()
    assert profile.github_username is None


def test_role_selection_cannot_target_another_user(
    api_client,
    user,
    profile,
    other_user,
    other_profile,
    backend_role,
):
    api_client.force_login(user)

    response = api_client.post(
        SELECT_ROLE_URL,
        {
            "role_id": str(backend_role.id),
            "user_id": str(other_user.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["user_id"] == ["Unknown field."]
    profile.refresh_from_db()
    other_profile.refresh_from_db()
    assert profile.selected_role is None
    assert other_profile.selected_role is None


def test_profile_link_crud_and_idor_protection(
    api_client, user, profile, other_profile
):
    api_client.force_login(user)
    created = api_client.post(
        LINKS_URL,
        {
            "link_type": "PORTFOLIO",
            "url": "https://example.com/portfolio",
            "label": "Portfolio",
        },
        format="json",
    )
    assert created.status_code == 201

    link_id = created.data["id"]
    updated = api_client.patch(
        f"{LINKS_URL}{link_id}/",
        {"label": "Updated portfolio"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["label"] == "Updated portfolio"

    foreign_link = ProfileLink.objects.create(
        profile=other_profile,
        link_type=ProfileLink.LinkType.PROJECT,
        url="https://example.com/foreign-project",
    )
    assert api_client.delete(f"{LINKS_URL}{foreign_link.id}/").status_code == 404
    assert ProfileLink.objects.filter(id=foreign_link.id).exists()

    assert api_client.delete(f"{LINKS_URL}{link_id}/").status_code == 204
    assert not ProfileLink.objects.filter(id=link_id).exists()


def test_profile_link_rejects_profile_mass_assignment(
    api_client, user, profile, other_profile
):
    api_client.force_login(user)

    response = api_client.post(
        LINKS_URL,
        {
            "profile": str(other_profile.id),
            "link_type": "PORTFOLIO",
            "url": "https://example.com/portfolio",
        },
        format="json",
    )

    assert response.status_code == 400
    assert not ProfileLink.objects.filter(url="https://example.com/portfolio").exists()


def test_user_skill_create_duplicate_and_idor_protection(
    api_client, user, profile, other_profile, django_stack
):
    api_client.force_login(user)
    payload = {"technology_stack_id": str(django_stack.id)}

    created = api_client.post(SKILLS_URL, payload, format="json")
    duplicate = api_client.post(SKILLS_URL, payload, format="json")

    assert created.status_code == 201
    assert duplicate.status_code == 400

    foreign_skill = UserSkill.objects.create(
        profile=other_profile,
        technology_stack=django_stack,
    )
    assert api_client.delete(f"{SKILLS_URL}{foreign_skill.id}/").status_code == 404
    assert UserSkill.objects.filter(id=foreign_skill.id).exists()


def test_session_authenticated_writes_require_csrf(csrf_client, user, profile):
    csrf_client.force_login(user)

    response = csrf_client.patch(
        PROFILE_URL,
        {"display_name": "No CSRF"},
        format="json",
    )

    assert response.status_code == 403
    profile.refresh_from_db()
    assert profile.display_name == ""


def test_guest_context_requires_csrf_for_writes(csrf_client):
    response = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"return_path": "/projects"},
        format="json",
    )

    assert response.status_code == 403


def test_guest_context_round_trip_does_not_create_user(
    csrf_client, django_user_model, backend_role
):
    project_version = ProjectVersion.objects.get(
        project_template__slug="helpdesk-lite",
        version_number=1,
    )
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {
            "selected_role_id": str(backend_role.id),
            "project_version_id": str(project_version.id),
            "intended_action": "join_project",
            "return_path": f"/projects/{project_version.id}/stack-selection",
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200
    assert response.data == {
        "selected_role_id": str(backend_role.id),
        "project_version_id": str(project_version.id),
        "intended_action": "join_project",
        "return_path": f"/projects/{project_version.id}/stack-selection",
    }
    assert csrf_client.get(GUEST_CONTEXT_URL).data == response.data
    assert django_user_model.objects.count() == 0


def test_guest_may_change_temporary_role_without_mutating_a_profile(
    csrf_client,
    django_user_model,
    backend_role,
    frontend_role,
):
    csrf_token = fetch_csrf_token(csrf_client)

    first = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"selected_role_id": str(backend_role.id)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    changed = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"selected_role_id": str(frontend_role.id)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
    )

    assert first.status_code == 200
    assert changed.status_code == 200
    assert changed.data["selected_role_id"] == str(frontend_role.id)
    assert django_user_model.objects.count() == 0


def test_guest_context_cannot_persist_a_final_stack(
    csrf_client, backend_role, django_stack
):
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {
            "selected_role_id": str(backend_role.id),
            "selected_stack_id": str(django_stack.id),
            "selected_project_id": str(uuid.uuid4()),
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert response.data == {
        "selected_project_id": ["Unknown field."],
        "selected_stack_id": ["Unknown field."],
    }
    assert csrf_client.get(GUEST_CONTEXT_URL).data == {}


def test_guest_context_rejects_an_unpublished_project_version(csrf_client):
    project_template = ProjectTemplate.objects.get(slug="helpdesk-lite")
    draft = ProjectVersion.objects.create(
        project_template=project_template,
        version_number=2,
    )
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"project_version_id": str(draft.id)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400
    assert response.data == {
        "project_version_id": ["Published project version not found."]
    }
    assert csrf_client.get(GUEST_CONTEXT_URL).data == {}


@pytest.mark.parametrize("return_path", ["https://evil.example", "//evil.example"])
def test_guest_context_rejects_unsafe_return_paths(csrf_client, return_path):
    csrf_token = fetch_csrf_token(csrf_client)

    response = csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"return_path": return_path},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400


def test_guest_context_delete_only_clears_participation_context(csrf_client):
    session = csrf_client.session
    session["unrelated"] = "preserved"
    session.save()
    csrf_token = fetch_csrf_token(csrf_client)
    csrf_client.patch(
        GUEST_CONTEXT_URL,
        {"return_path": "/projects"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    response = csrf_client.delete(
        GUEST_CONTEXT_URL,
        HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
    )

    assert response.status_code == 204
    assert csrf_client.session["unrelated"] == "preserved"
    assert csrf_client.get(GUEST_CONTEXT_URL).data == {}
