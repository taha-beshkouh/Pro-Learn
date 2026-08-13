import pytest

from apps.profiles.models import RoleCode
from apps.projects.exceptions import ProjectConfigurationError
from apps.projects.models import ProjectTaskTemplate, SprintTemplate


pytestmark = pytest.mark.django_db


def test_levels_and_projects_are_public(api_client):
    levels = api_client.get("/api/v1/levels/")
    projects = api_client.get("/api/v1/projects/")

    assert levels.status_code == 200
    assert [item["number"] for item in levels.data] == [1, 2, 3]
    assert projects.status_code == 200
    assert [item["slug"] for item in projects.data] == [
        "helpdesk-lite",
        "healthchecks-lite",
        "event-ticketing-lite",
    ]


def test_project_list_filters_by_level_and_validates_input(api_client):
    response = api_client.get("/api/v1/projects/?level=2")
    invalid = api_client.get("/api/v1/projects/?level=4")

    assert response.status_code == 200
    assert [item["slug"] for item in response.data] == ["healthchecks-lite"]
    assert invalid.status_code == 400
    assert "level" in invalid.data


def test_helpdesk_detail_without_role_has_only_general_content(
    api_client, helpdesk_template
):
    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    assert response.status_code == 200
    version = response.data["published_version"]
    assert version["duration_weeks"] == 6
    assert version["sprint_count"] == 6
    assert version["role_context"] is None
    assert len(version["shared_work_items"]) == 16
    assert version["sprint_templates"] == []


def test_project_detail_exposes_relative_sprint_schedule_and_work_relation(
    api_client, helpdesk_template, helpdesk_version
):
    second = SprintTemplate.objects.create(
        project_version=helpdesk_version,
        sequence=2,
        title="Second sprint",
        brief="Second brief",
        planned_start_offset_days=9,
        planned_duration_days=4,
    )
    first = SprintTemplate.objects.create(
        project_version=helpdesk_version,
        sequence=1,
        title="First sprint",
        brief="First brief",
        planned_start_offset_days=0,
        planned_duration_days=5,
    )
    work_item = helpdesk_version.work_items.order_by("position").first()
    work_item.sprint_template = first
    work_item.save(update_fields=["sprint_template"])

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    sprints = response.data["published_version"]["sprint_templates"]
    assert [item["sequence"] for item in sprints] == [1, 2]
    assert sprints[0]["planned_end_offset_days"] == 5
    assert sprints[1]["planned_end_offset_days"] == 13
    serialized_work = next(
        item
        for item in response.data["published_version"]["shared_work_items"]
        if item["id"] == str(work_item.id)
    )
    assert serialized_work["sprint_template"] == {
        "id": str(first.id),
        "sequence": 1,
        "title": "First sprint",
    }


def test_unfinalized_project_does_not_invent_a_version(api_client):
    projects = api_client.get("/api/v1/projects/").data
    healthchecks = next(item for item in projects if item["slug"] == "healthchecks-lite")

    response = api_client.get(f"/api/v1/projects/{healthchecks['id']}/")

    assert response.status_code == 200
    assert response.data["published_version_id"] is None
    assert response.data["published_version"] is None


def test_guest_role_context_uses_session_selection(
    api_client, helpdesk_template, backend_role
):
    session = api_client.session
    session["participation_context"] = {"selected_role_id": str(backend_role.id)}
    session.save()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    context = response.data["published_version"]["role_context"]
    assert context["role"]["code"] == RoleCode.BACKEND_DEVELOPER
    assert context["stack_policy"] == "ALLOWLIST"
    assert len(context["compatible_stacks"]) == 2
    assert context["auto_selected_stack"] is None
    assert context["selected_stack"] is None


def test_fixed_frontend_stack_is_auto_selected(
    api_client, helpdesk_template, frontend_role
):
    session = api_client.session
    session["participation_context"] = {"selected_role_id": str(frontend_role.id)}
    session.save()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    context = response.data["published_version"]["role_context"]
    assert context["stack_policy"] == "FIXED"
    assert context["auto_selected_stack"]["code"] == "react-typescript-vite"
    assert context["selected_stack"]["code"] == "react-typescript-vite"


def test_authenticated_profile_role_overrides_guest_session(
    api_client, user, profile, helpdesk_template, backend_role, frontend_role
):
    profile.selected_role = backend_role
    profile.save(update_fields=["selected_role"])
    api_client.force_login(user)
    session = api_client.session
    session["participation_context"] = {"selected_role_id": str(frontend_role.id)}
    session.save()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    assert response.data["published_version"]["role_context"]["role"]["code"] == (
        RoleCode.BACKEND_DEVELOPER
    )


def test_role_and_stack_specific_work_content_is_filtered(
    api_client,
    helpdesk_template,
    helpdesk_version,
    backend_role,
    django_stack,
):
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        role=backend_role,
        position=100,
        title="Backend shared-stack work",
    )
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        role=backend_role,
        technology_stack=django_stack,
        position=101,
        title="Django-specific work",
    )
    session = api_client.session
    session["participation_context"] = {
        "selected_project_id": str(helpdesk_template.id),
        "selected_role_id": str(backend_role.id),
        "selected_stack_id": str(django_stack.id),
    }
    session.save()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    role_items = response.data["published_version"]["role_context"]["work_items"]
    titles = {
        item["title"]
        for item in role_items
    }
    assert "Backend shared-stack work" in titles
    assert "Django-specific work" in titles
    shared_items = response.data["published_version"]["shared_work_items"]
    assert len(shared_items) == 16
    assert {item["id"] for item in role_items}.isdisjoint(
        {item["id"] for item in shared_items}
    )
    assert response.data["published_version"]["role_context"]["selected_stack"][
        "code"
    ] == "django-drf"


def test_invalid_stack_configuration_returns_safe_api_error(
    api_client, helpdesk_template, backend_role, monkeypatch
):
    session = api_client.session
    session["participation_context"] = {"selected_role_id": str(backend_role.id)}
    session.save()

    def fail_resolution(**kwargs):
        raise ProjectConfigurationError("internal stack-policy diagnostics")

    monkeypatch.setattr(
        "apps.projects.api.serializers.resolve_project_stack_selection",
        fail_resolution,
    )

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    assert response.status_code == 503
    assert response.data == {
        "detail": "Project configuration is temporarily unavailable."
    }
    assert "stack-policy" not in str(response.data)


@pytest.mark.parametrize("authenticated", [False, True])
def test_allowlist_stack_selection_is_consistent_for_anonymous_and_authenticated(
    api_client,
    authenticated,
    user,
    profile,
    helpdesk_template,
    backend_role,
    django_stack,
):
    if authenticated:
        profile.selected_role = backend_role
        profile.save(update_fields=["selected_role"])
        api_client.force_login(user)
    else:
        session = api_client.session
        session["participation_context"] = {
            "selected_role_id": str(backend_role.id)
        }
        session.save()

    response = api_client.post(
        f"/api/v1/projects/{helpdesk_template.id}/stack-selection/",
        {"technology_stack_id": str(django_stack.id)},
        format="json",
    )

    assert response.status_code == 200
    assert response.data == {
        "selected_project_id": str(helpdesk_template.id),
        "selected_role_id": str(backend_role.id),
        "selected_stack_id": str(django_stack.id),
    }
    context = api_client.session["participation_context"]
    assert context == {
        "selected_project_id": str(helpdesk_template.id),
        "selected_role_id": str(backend_role.id),
        "selected_stack_id": str(django_stack.id),
    }
    detail = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")
    assert detail.data["published_version"]["role_context"]["selected_stack"][
        "id"
    ] == str(django_stack.id)


@pytest.mark.parametrize("authenticated", [False, True])
def test_incompatible_stack_selection_is_rejected(
    api_client,
    authenticated,
    user,
    profile,
    helpdesk_template,
    backend_role,
    react_stack,
):
    if authenticated:
        profile.selected_role = backend_role
        profile.save(update_fields=["selected_role"])
        api_client.force_login(user)
    else:
        session = api_client.session
        session["participation_context"] = {
            "selected_role_id": str(backend_role.id)
        }
        session.save()

    response = api_client.post(
        f"/api/v1/projects/{helpdesk_template.id}/stack-selection/",
        {"technology_stack_id": str(react_stack.id)},
        format="json",
    )

    assert response.status_code == 400
    assert response.data == {
        "technology_stack_id": [
            "This stack is not available for the selected project role."
        ]
    }
    assert "selected_stack_id" not in api_client.session.get(
        "participation_context", {}
    )


def test_stackless_role_rejects_selection_and_has_no_fake_stack(
    api_client,
    user,
    profile,
    helpdesk_template,
    designer_role,
    react_stack,
):
    profile.selected_role = designer_role
    profile.save(update_fields=["selected_role"])
    api_client.force_login(user)

    selection = api_client.post(
        f"/api/v1/projects/{helpdesk_template.id}/stack-selection/",
        {"technology_stack_id": str(react_stack.id)},
        format="json",
    )
    detail = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    assert selection.status_code == 400
    role_context = detail.data["published_version"]["role_context"]
    assert role_context["requires_stack"] is False
    assert role_context["compatible_stacks"] == []
    assert role_context["auto_selected_stack"] is None
    assert role_context["selected_stack"] is None


def test_anonymous_stack_selection_requires_csrf(
    csrf_client,
    helpdesk_template,
    backend_role,
    django_stack,
):
    session = csrf_client.session
    session["participation_context"] = {
        "selected_role_id": str(backend_role.id)
    }
    session.save()

    response = csrf_client.post(
        f"/api/v1/projects/{helpdesk_template.id}/stack-selection/",
        {"technology_stack_id": str(django_stack.id)},
        format="json",
    )

    assert response.status_code == 403
    assert "selected_stack_id" not in csrf_client.session["participation_context"]


def test_unknown_project_returns_safe_404(api_client):
    response = api_client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/")

    assert response.status_code == 404
    assert response.data == {"detail": "Project not found."}
