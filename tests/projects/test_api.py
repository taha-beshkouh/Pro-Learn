from collections import Counter

import pytest

from apps.profiles.models import Role, RoleCode, TechnologyStack
from apps.projects.exceptions import ProjectConfigurationError
from apps.projects.models import ProjectTaskTemplate


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
    assert len(version["shared_work_items"]) == 18
    assert [sprint["sequence"] for sprint in version["sprint_templates"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]


@pytest.mark.parametrize(
    ("role_code", "stack_code"),
    [
        (RoleCode.BACKEND_DEVELOPER, "django-drf"),
        (RoleCode.FRONTEND_DEVELOPER, "react-typescript-vite"),
        (RoleCode.PRODUCT_DESIGNER, None),
    ],
)
def test_helpdesk_detail_exposes_canonical_role_and_shared_content(
    api_client,
    helpdesk_template,
    role_code,
    stack_code,
):
    role = Role.objects.get(code=role_code)
    stack = (
        TechnologyStack.objects.get(code=stack_code)
        if stack_code is not None
        else None
    )
    session = api_client.session
    session["participation_context"] = {
        "selected_project_id": str(helpdesk_template.id),
        "selected_role_id": str(role.id),
        "selected_stack_id": str(stack.id) if stack is not None else None,
    }
    session.save()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    assert response.status_code == 200
    version = response.data["published_version"]
    role_items = version["role_context"]["work_items"]
    shared_items = version["shared_work_items"]
    assert len(role_items) == 36
    assert len(shared_items) == 18
    assert all(item["role"]["code"] == role_code for item in role_items)
    assert all(item["technology_stack"] is None for item in role_items)
    assert all(item["role"] is None for item in shared_items)
    assert all(item["technology_stack"] is None for item in shared_items)
    assert Counter(
        item["sprint_template"]["sequence"] for item in role_items
    ) == {sequence: 6 for sequence in range(1, 7)}
    assert Counter(
        item["sprint_template"]["sequence"] for item in shared_items
    ) == {sequence: 3 for sequence in range(1, 7)}
    assert [(item["position"], item["id"]) for item in role_items] == sorted(
        (item["position"], item["id"]) for item in role_items
    )
    assert [(item["position"], item["id"]) for item in shared_items] == sorted(
        (item["position"], item["id"]) for item in shared_items
    )


def test_project_detail_exposes_relative_sprint_schedule_and_work_relation(
    api_client, helpdesk_template, helpdesk_version
):
    first = helpdesk_version.sprint_templates.get(sequence=1)
    work_item = first.work_items.filter(
        role__isnull=True,
        technology_stack__isnull=True,
    ).order_by("position", "id").first()

    response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")

    sprints = response.data["published_version"]["sprint_templates"]
    assert [item["sequence"] for item in sprints] == [1, 2, 3, 4, 5, 6]
    assert [item["planned_end_offset_days"] for item in sprints] == [
        7,
        14,
        21,
        28,
        35,
        42,
    ]
    serialized_work = next(
        item
        for item in response.data["published_version"]["shared_work_items"]
        if item["id"] == str(work_item.id)
    )
    assert serialized_work["sprint_template"] == {
        "id": str(first.id),
        "sequence": 1,
        "title": "Product Foundation & Authentication",
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
    aspnet_stack = TechnologyStack.objects.get(code="aspnet-core-ef-core")
    ProjectTaskTemplate.objects.create(
        project_version=helpdesk_version,
        role=backend_role,
        technology_stack=aspnet_stack,
        position=102,
        title="ASP.NET-specific work",
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
    assert "ASP.NET-specific work" not in titles
    shared_items = response.data["published_version"]["shared_work_items"]
    assert len(shared_items) == 18
    assert {item["id"] for item in role_items}.isdisjoint(
        {item["id"] for item in shared_items}
    )
    assert response.data["published_version"]["role_context"]["selected_stack"][
        "code"
    ] == "django-drf"

    session = api_client.session
    participation_context = session["participation_context"]
    participation_context["selected_stack_id"] = str(aspnet_stack.id)
    session["participation_context"] = participation_context
    session.save()
    aspnet_response = api_client.get(f"/api/v1/projects/{helpdesk_template.id}/")
    aspnet_titles = {
        item["title"]
        for item in aspnet_response.data["published_version"]["role_context"][
            "work_items"
        ]
    }
    assert "Backend shared-stack work" in aspnet_titles
    assert "ASP.NET-specific work" in aspnet_titles
    assert "Django-specific work" not in aspnet_titles


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
