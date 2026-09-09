from unittest.mock import patch

import pytest
from django.contrib import admin, messages
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.formations.models import (
    ProjectRun,
    ProjectRunState,
    ReadyCheck,
    SprintRun,
    SprintRunState,
    SprintSubmission,
    Team,
    TeamFormation,
    TeamMember,
)
from apps.formations.services import open_sprint, submit_sprint
from apps.profiles.models import (
    ProfileLink,
    Role,
    RoleTechnologyStack,
    TechnologyStack,
    UserProfile,
    UserSkill,
)
from apps.projects.models import (
    Level,
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTaskTemplate,
    ProjectTemplate,
    ProjectVersion,
    RolePrerequisite,
    SprintTemplate,
)


REGISTERED_MODELS = {
    User,
    Role,
    UserProfile,
    ProfileLink,
    TechnologyStack,
    RoleTechnologyStack,
    UserSkill,
    Level,
    ProjectTemplate,
    ProjectVersion,
    ProjectRoleRequirement,
    ProjectRoleAllowedStack,
    RolePrerequisite,
    SprintTemplate,
    ProjectTaskTemplate,
    TeamFormation,
    ReadyCheck,
    Team,
    TeamMember,
    ProjectRun,
    SprintRun,
    SprintSubmission,
}

VERSIONED_DEFINITION_MODELS = (
    ProjectVersion,
    ProjectRoleRequirement,
    ProjectRoleAllowedStack,
    RolePrerequisite,
    SprintTemplate,
    ProjectTaskTemplate,
)

HISTORICAL_READ_ONLY_MODELS = (
    User,
    UserProfile,
    TeamFormation,
    ReadyCheck,
    Team,
    TeamMember,
    SprintSubmission,
)

OPERATIONAL_CHANGELISTS = (
    "admin:accounts_user_changelist",
    "admin:profiles_userprofile_changelist",
    "admin:profiles_role_changelist",
    "admin:profiles_technologystack_changelist",
    "admin:profiles_userskill_changelist",
    "admin:projects_projectversion_changelist",
    "admin:projects_sprinttemplate_changelist",
    "admin:projects_projecttasktemplate_changelist",
    "admin:formations_teamformation_changelist",
    "admin:formations_readycheck_changelist",
    "admin:formations_team_changelist",
    "admin:formations_teammember_changelist",
    "admin:formations_projectrun_changelist",
    "admin:formations_sprintrun_changelist",
    "admin:formations_sprintsubmission_changelist",
)


def action_request(user):
    request = RequestFactory().post("/admin/")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def message_levels(request):
    return [message.level for message in get_messages(request)]


def first_sprint_run(project_run):
    return (
        project_run.sprint_runs.select_related("sprint_template")
        .order_by("sprint_template__sequence", "id")
        .first()
    )


def test_all_mvp_operational_models_are_registered():
    assert REGISTERED_MODELS <= set(admin.site._registry)


@pytest.mark.django_db
@pytest.mark.postgresql
def test_nonstaff_user_cannot_access_admin(client, outside_user):
    client.force_login(outside_user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


@pytest.mark.django_db
@pytest.mark.postgresql
def test_staff_with_standard_view_permission_can_access_admin_model(
    client,
    django_user_model,
    password,
):
    staff_user = django_user_model.objects.create_user(
        email="admin-viewer@example.com",
        password=password,
        is_staff=True,
    )
    staff_user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="projects",
            codename="view_projectversion",
        )
    )
    client.force_login(staff_user)

    response = client.get(reverse("admin:projects_projectversion_changelist"))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.postgresql
def test_admin_user_can_access_operational_changelists(admin_client):
    for url_name in OPERATIONAL_CHANGELISTS:
        response = admin_client.get(reverse(url_name))
        assert response.status_code == 200, url_name


@pytest.mark.django_db
@pytest.mark.postgresql
def test_versioned_project_definitions_are_read_only_in_admin(admin_user):
    request = action_request(admin_user)

    for model in VERSIONED_DEFINITION_MODELS:
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_delete_permission(request) is False
        assert set(model_admin.get_readonly_fields(request)) == {
            field.name for field in model._meta.fields
        }


@pytest.mark.django_db
@pytest.mark.postgresql
def test_account_profile_and_historical_records_are_read_only_in_admin(admin_user):
    request = action_request(admin_user)

    for model in HISTORICAL_READ_ONLY_MODELS:
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_delete_permission(request) is False


@pytest.mark.django_db
@pytest.mark.postgresql
def test_referenced_project_version_cannot_be_changed_through_admin(
    admin_client,
    runtime_project_run,
):
    project_version = runtime_project_run.project_version
    original_sprint_count = project_version.sprint_count
    url = reverse(
        "admin:projects_projectversion_change",
        args=(project_version.id,),
    )

    response = admin_client.post(
        url,
        {
            "sprint_count": 99,
            "_save": "Save",
        },
    )

    assert response.status_code == 403
    project_version.refresh_from_db()
    assert project_version.sprint_count == original_sprint_count


@pytest.mark.django_db
@pytest.mark.postgresql
def test_static_work_content_cannot_be_changed_through_admin(
    admin_client,
    runtime_work_items,
):
    work_item = runtime_work_items[0]
    original_title = work_item.title
    url = reverse(
        "admin:projects_projecttasktemplate_change",
        args=(work_item.id,),
    )

    response = admin_client.post(
        url,
        {
            "title": "Unsafe admin rewrite",
            "_save": "Save",
        },
    )

    assert response.status_code == 403
    work_item.refresh_from_db()
    assert work_item.title == original_title


@pytest.mark.django_db
@pytest.mark.postgresql
def test_runtime_forms_are_read_only_but_changelist_actions_require_change_permission(
    admin_user,
    runtime_project_run,
):
    request = action_request(admin_user)
    sprint_run = first_sprint_run(runtime_project_run)

    for model, instance in (
        (ProjectRun, runtime_project_run),
        (SprintRun, sprint_run),
    ):
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is True
        assert model_admin.has_change_permission(request, instance) is False
        assert model_admin.has_delete_permission(request, instance) is False


@pytest.mark.django_db
@pytest.mark.postgresql
def test_nonstaff_cannot_invoke_state_changing_admin_actions(
    outside_user,
    runtime_project_run,
):
    request = action_request(outside_user)
    sprint_admin = admin.site._registry[SprintRun]
    project_admin = admin.site._registry[ProjectRun]
    sprint_queryset = SprintRun.objects.filter(project_run=runtime_project_run)
    project_queryset = ProjectRun.objects.filter(id=runtime_project_run.id)

    with patch("apps.formations.admin.mark_sprint_under_review") as service:
        sprint_admin.mark_selected_under_review(request, sprint_queryset)
        service.assert_not_called()

    with patch("apps.formations.admin.mark_project_run_incomplete") as service:
        project_admin.mark_selected_incomplete(request, project_queryset)
        service.assert_not_called()

    assert message_levels(request) == [messages.ERROR, messages.ERROR]


@pytest.mark.django_db
@pytest.mark.postgresql
def test_sprint_admin_actions_use_the_validated_service_flow(
    admin_user,
    runtime_project_run,
    runtime_members,
):
    sprint_run = first_sprint_run(runtime_project_run)
    submitter = runtime_members["BACKEND_DEVELOPER"]
    sprint_admin = admin.site._registry[SprintRun]
    queryset = SprintRun.objects.filter(id=sprint_run.id)

    open_sprint(
        sprint_run_id=sprint_run.id,
        actor=admin_user,
    )
    submit_sprint(
        sprint_run_id=sprint_run.id,
        user=submitter.user,
        evidence="First review candidate",
    )
    sprint_admin.mark_selected_under_review(action_request(admin_user), queryset)
    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.UNDER_REVIEW

    sprint_admin.request_changes_for_selected(action_request(admin_user), queryset)
    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.CHANGES_REQUESTED

    submit_sprint(
        sprint_run_id=sprint_run.id,
        user=submitter.user,
        evidence="Corrected review candidate",
    )
    sprint_admin.mark_selected_under_review(action_request(admin_user), queryset)
    sprint_admin.complete_selected_sprints(action_request(admin_user), queryset)

    sprint_run.refresh_from_db()
    runtime_project_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.COMPLETED
    assert runtime_project_run.state == ProjectRunState.ACTIVE


@pytest.mark.django_db
@pytest.mark.postgresql
def test_forbidden_sprint_transition_remains_forbidden_through_admin(
    admin_user,
    runtime_project_run,
):
    sprint_run = first_sprint_run(runtime_project_run)
    request = action_request(admin_user)
    sprint_admin = admin.site._registry[SprintRun]

    sprint_admin.mark_selected_under_review(
        request,
        SprintRun.objects.filter(id=sprint_run.id),
    )

    sprint_run.refresh_from_db()
    assert sprint_run.state == SprintRunState.LOCKED
    assert messages.ERROR in message_levels(request)


@pytest.mark.django_db
@pytest.mark.postgresql
def test_early_project_run_cannot_be_marked_incomplete_through_admin(
    admin_user,
    runtime_project_run,
):
    request = action_request(admin_user)
    project_admin = admin.site._registry[ProjectRun]

    project_admin.mark_selected_incomplete(
        request,
        ProjectRun.objects.filter(id=runtime_project_run.id),
    )

    runtime_project_run.refresh_from_db()
    assert runtime_project_run.state == ProjectRunState.ACTIVE
    assert runtime_project_run.ended_at is None
    assert runtime_project_run.members.filter(ended_at__isnull=True).count() == 3
    assert messages.ERROR in message_levels(request)


@pytest.mark.django_db
@pytest.mark.postgresql
def test_overdue_project_run_admin_action_uses_terminal_service_guards(
    admin_user,
    overdue_runtime_project_run,
):
    project_admin = admin.site._registry[ProjectRun]
    queryset = ProjectRun.objects.filter(id=overdue_runtime_project_run.id)

    project_admin.mark_selected_incomplete(action_request(admin_user), queryset)

    overdue_runtime_project_run.refresh_from_db()
    first_ended_at = overdue_runtime_project_run.ended_at
    assert overdue_runtime_project_run.state == ProjectRunState.INCOMPLETE
    assert first_ended_at is not None
    assert overdue_runtime_project_run.members.filter(
        ended_at=first_ended_at
    ).count() == 3

    terminal_request = action_request(admin_user)
    project_admin.mark_selected_incomplete(terminal_request, queryset)

    overdue_runtime_project_run.refresh_from_db()
    assert overdue_runtime_project_run.state == ProjectRunState.INCOMPLETE
    assert overdue_runtime_project_run.ended_at == first_ended_at
    assert messages.ERROR in message_levels(terminal_request)


def test_unsafe_input_dependent_operations_are_not_bulk_admin_actions():
    formation_actions = admin.site._registry[TeamFormation].actions
    ready_check_actions = admin.site._registry[ReadyCheck].actions
    sprint_actions = admin.site._registry[SprintRun].actions

    assert not formation_actions
    assert not ready_check_actions
    assert set(sprint_actions) == {
        "mark_selected_under_review",
        "request_changes_for_selected",
        "complete_selected_sprints",
    }
