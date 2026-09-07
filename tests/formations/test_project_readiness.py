from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from apps.formations.exceptions import (
    ActiveProjectReadinessExists,
    InvalidProjectReadinessSelection,
    MemberHasActiveProjectRun,
    MemberHasUnresolvedFormation,
)
from apps.formations.models import ProjectReadiness, ProjectRunState
from apps.formations.selectors import active_project_readiness_for_user
from apps.formations.services import (
    create_project_readiness,
    mark_project_run_incomplete,
)
from apps.profiles.models import UserProfile, UserSkill
from apps.projects.models import (
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTemplate,
    ProjectVersion,
    StackPolicy,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]

READINESS_URL = "/api/v1/project-readiness/me/"


def confirmed_selection(*, user, project_version, technology_stack):
    return {
        "project_stack_selection": {
            "user_id": str(user.id),
            "project_version_id": str(project_version.id),
            "selected_stack_id": (
                str(technology_stack.id) if technology_stack is not None else None
            ),
        }
    }


def install_confirmed_selection(
    client,
    *,
    user,
    project_version,
    technology_stack,
):
    session = client.session
    session.update(
        confirmed_selection(
            user=user,
            project_version=project_version,
            technology_stack=technology_stack,
        )
    )
    session.save()


def confirm_stack(client, *, user, project_version, technology_stack=None):
    client.force_login(user)
    payload = (
        {"technology_stack_id": str(technology_stack.id)}
        if technology_stack is not None
        else {}
    )
    response = client.post(
        f"/api/v1/project-versions/{project_version.id}/stack-selection/",
        payload,
        format="json",
    )
    assert response.status_code == 200
    return response


def create_version(
    *,
    project_template,
    version_number,
    role,
    stack_policy,
    allowed_stacks=(),
    requires_stack=True,
):
    with transaction.atomic():
        project_version = ProjectVersion.objects.create(
            project_template=project_template,
            version_number=version_number,
            duration_weeks=6,
            sprint_count=6,
            published_at=timezone.now(),
        )
        requirement = ProjectRoleRequirement.objects.create(
            project_version=project_version,
            role=role,
            requires_stack=requires_stack,
            stack_policy=stack_policy,
        )
        ProjectRoleAllowedStack.objects.bulk_create(
            [
                ProjectRoleAllowedStack(
                    role_requirement=requirement,
                    technology_stack=stack,
                )
                for stack in allowed_stacks
            ]
        )
    return project_version


def create_other_template(formation_catalog, *, slug):
    return ProjectTemplate.objects.create(
        level=formation_catalog["level"],
        slug=slug,
        name=slug.replace("-", " ").title(),
    )


def test_readiness_model_stores_required_historical_snapshot(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    readiness = ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    assert readiness.user_id == backend_user.id
    assert readiness.role_id == backend_role.id
    assert readiness.project_version_id == helpdesk_version.id
    assert readiness.technology_stack_id == django_stack.id
    assert readiness.created_at is not None
    assert readiness.consumed_at is None


def test_readiness_model_allows_null_stack_for_stackless_role(
    designer_user,
    designer_role,
    helpdesk_version,
):
    readiness = ProjectReadiness.objects.create(
        user=designer_user,
        role=designer_role,
        project_version=helpdesk_version,
        technology_stack=None,
    )

    assert readiness.technology_stack_id is None


def test_database_rejects_two_active_readiness_rows_for_one_user(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectReadiness.objects.create(
            user=backend_user,
            role=backend_role,
            project_version=helpdesk_version,
            technology_stack=django_stack,
        )

    assert ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).count() == 1


def test_historical_rows_are_retained_and_allow_one_new_active_readiness(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    now = timezone.now()
    for age in (timedelta(days=2), timedelta(days=1)):
        created_at = now - age
        ProjectReadiness.objects.create(
            user=backend_user,
            role=backend_role,
            project_version=helpdesk_version,
            technology_stack=django_stack,
            created_at=created_at,
            consumed_at=created_at + timedelta(hours=1),
        )

    active = create_project_readiness(
        user=backend_user,
        session=confirmed_selection(
            user=backend_user,
            project_version=helpdesk_version,
            technology_stack=django_stack,
        ),
    )

    assert active.consumed_at is None
    assert ProjectReadiness.objects.filter(user=backend_user).count() == 3
    assert ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).count() == 1


def test_database_rejects_consumption_before_readiness_creation(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    created_at = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectReadiness.objects.create(
            user=backend_user,
            role=backend_role,
            project_version=helpdesk_version,
            technology_stack=django_stack,
            created_at=created_at,
            consumed_at=created_at - timedelta(microseconds=1),
        )


def test_anonymous_user_cannot_create_or_read_readiness(api_client):
    assert api_client.post(READINESS_URL, {}, format="json").status_code == 403
    assert api_client.get(READINESS_URL).status_code == 403
    assert not ProjectReadiness.objects.exists()


def test_readiness_api_does_not_expose_update_or_delete_actions(
    api_client,
    backend_user,
):
    api_client.force_login(backend_user)

    assert api_client.patch(READINESS_URL, {}, format="json").status_code == 405
    assert api_client.delete(READINESS_URL).status_code == 405


def test_guest_can_still_view_public_exact_version_information(
    api_client,
    helpdesk_version,
):
    response = api_client.get(
        f"/api/v1/project-versions/{helpdesk_version.id}/"
    )

    assert response.status_code == 200
    assert response.data["id"] == str(helpdesk_version.id)
    assert not ProjectReadiness.objects.exists()


def test_readiness_creation_requires_phase_one_confirmation(
    api_client,
    backend_user,
):
    api_client.force_login(backend_user)

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 400
    assert "readiness" in response.data
    assert not ProjectReadiness.objects.exists()


def test_guest_continuation_context_cannot_manufacture_readiness(
    api_client,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    api_client.force_login(backend_user)
    session = api_client.session
    session["participation_context"] = {
        "selected_role_id": str(backend_role.id),
        "project_version_id": str(helpdesk_version.id),
        "selected_stack_id": str(django_stack.id),
        "intended_action": "join_project",
    }
    session.save()

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 400
    assert not ProjectReadiness.objects.exists()


def test_authenticated_user_without_selected_role_cannot_create_readiness(
    outside_user,
    helpdesk_version,
    django_stack,
):
    UserProfile.objects.create(user=outside_user)

    with pytest.raises(InvalidProjectReadinessSelection):
        create_project_readiness(
            user=outside_user,
            session=confirmed_selection(
                user=outside_user,
                project_version=helpdesk_version,
                technology_stack=django_stack,
            ),
        )

    assert not ProjectReadiness.objects.exists()


def test_readiness_creation_rejects_all_spoofable_domain_fields(
    api_client,
    backend_user,
    frontend_user,
    frontend_role,
    helpdesk_version,
    django_stack,
    react_stack,
):
    api_client.force_login(backend_user)
    install_confirmed_selection(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    response = api_client.post(
        READINESS_URL,
        {
            "user_id": str(frontend_user.id),
            "role_id": str(frontend_role.id),
            "project_version_id": str(helpdesk_version.id),
            "technology_stack_id": str(react_stack.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data == {
        "project_version_id": ["Unknown field."],
        "role_id": ["Unknown field."],
        "technology_stack_id": ["Unknown field."],
        "user_id": ["Unknown field."],
    }
    assert not ProjectReadiness.objects.exists()


def test_authenticated_allowlist_confirmation_creates_exact_readiness(
    api_client,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    confirm_stack(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 201
    assert response.data["user"]["id"] == str(backend_user.id)
    assert response.data["role"]["id"] == str(backend_role.id)
    assert response.data["project_version_id"] == str(helpdesk_version.id)
    assert response.data["technology_stack"]["id"] == str(django_stack.id)
    readiness = ProjectReadiness.objects.get()
    assert readiness.user_id == backend_user.id
    assert readiness.role_id == backend_role.id
    assert readiness.project_version_id == helpdesk_version.id
    assert readiness.technology_stack_id == django_stack.id


def test_fixed_confirmation_creates_readiness_with_configured_stack(
    api_client,
    frontend_user,
    frontend_role,
    helpdesk_version,
    react_stack,
):
    confirmation = confirm_stack(
        api_client,
        user=frontend_user,
        project_version=helpdesk_version,
    )
    assert confirmation.data["selected_stack_id"] == str(react_stack.id)

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 201
    readiness = ProjectReadiness.objects.get(user=frontend_user)
    assert readiness.role_id == frontend_role.id
    assert readiness.technology_stack_id == react_stack.id


def test_open_confirmation_uses_authenticated_user_skill_for_readiness(
    api_client,
    backend_user,
    backend_role,
    django_stack,
    formation_catalog,
):
    profile = backend_user.profile
    UserSkill.objects.create(profile=profile, technology_stack=django_stack)
    project_version = create_version(
        project_template=formation_catalog["project_template"],
        version_number=3,
        role=backend_role,
        stack_policy=StackPolicy.OPEN,
    )
    confirm_stack(
        api_client,
        user=backend_user,
        project_version=project_version,
        technology_stack=django_stack,
    )

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 201
    readiness = ProjectReadiness.objects.get(user=backend_user)
    assert readiness.project_version_id == project_version.id
    assert readiness.technology_stack_id == django_stack.id


def test_stackless_confirmation_creates_readiness_with_null_stack(
    api_client,
    designer_user,
    designer_role,
    helpdesk_version,
):
    confirmation = confirm_stack(
        api_client,
        user=designer_user,
        project_version=helpdesk_version,
    )
    assert confirmation.data["selected_stack_id"] is None

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 201
    readiness = ProjectReadiness.objects.get(user=designer_user)
    assert readiness.role_id == designer_role.id
    assert readiness.technology_stack_id is None
    assert response.data["technology_stack"] is None


def test_tampered_or_mismatched_stack_confirmation_is_rejected(
    api_client,
    backend_user,
    helpdesk_version,
    react_stack,
):
    api_client.force_login(backend_user)
    install_confirmed_selection(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=react_stack,
    )

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 400
    assert not ProjectReadiness.objects.exists()


def test_readiness_does_not_auto_confirm_a_missing_required_session_stack(
    frontend_user,
    helpdesk_version,
):
    with pytest.raises(InvalidProjectReadinessSelection):
        create_project_readiness(
            user=frontend_user,
            session=confirmed_selection(
                user=frontend_user,
                project_version=helpdesk_version,
                technology_stack=None,
            ),
        )

    assert not ProjectReadiness.objects.exists()


def test_version_must_still_be_published_when_readiness_is_created(
    api_client,
    backend_user,
    helpdesk_version,
    django_stack,
):
    api_client.force_login(backend_user)
    install_confirmed_selection(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    ProjectVersion.objects.filter(id=helpdesk_version.id).update(
        published_at=None
    )

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 400
    assert not ProjectReadiness.objects.exists()


def test_confirmation_for_another_user_is_rejected(
    backend_user,
    frontend_user,
    helpdesk_version,
    django_stack,
):
    with pytest.raises(InvalidProjectReadinessSelection):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=frontend_user,
                project_version=helpdesk_version,
                technology_stack=django_stack,
            ),
        )

    assert not ProjectReadiness.objects.exists()


def test_newer_publication_never_replaces_confirmed_exact_version(
    api_client,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
    formation_catalog,
):
    newer_version = create_version(
        project_template=formation_catalog["project_template"],
        version_number=3,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )
    confirm_stack(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    response = api_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 201
    assert response.data["project_version_id"] == str(helpdesk_version.id)
    assert response.data["project_version_id"] != str(newer_version.id)
    assert ProjectReadiness.objects.get().project_version_id == helpdesk_version.id


def test_active_readiness_cannot_be_replaced_by_another_version(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
    formation_catalog,
):
    original = create_project_readiness(
        user=backend_user,
        session=confirmed_selection(
            user=backend_user,
            project_version=helpdesk_version,
            technology_stack=django_stack,
        ),
    )
    newer_version = create_version(
        project_template=formation_catalog["project_template"],
        version_number=3,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )

    with pytest.raises(ActiveProjectReadinessExists):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=backend_user,
                project_version=newer_version,
                technology_stack=django_stack,
            ),
        )

    original.refresh_from_db()
    assert original.consumed_at is None
    assert original.project_version_id == helpdesk_version.id
    assert ProjectReadiness.objects.filter(user=backend_user).count() == 1


def test_same_active_readiness_repeat_returns_explicit_conflict(
    api_client,
    backend_user,
    helpdesk_version,
    django_stack,
):
    confirm_stack(
        api_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    assert api_client.post(READINESS_URL, {}, format="json").status_code == 201

    repeated = api_client.post(READINESS_URL, {}, format="json")

    assert repeated.status_code == 409
    assert ProjectReadiness.objects.filter(user=backend_user).count() == 1


def test_active_readiness_retrieval_is_user_scoped_and_excludes_history(
    api_client,
    backend_user,
    frontend_user,
    backend_role,
    frontend_role,
    helpdesk_version,
    django_stack,
    react_stack,
):
    own = ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    ProjectReadiness.objects.create(
        user=frontend_user,
        role=frontend_role,
        project_version=helpdesk_version,
        technology_stack=react_stack,
    )
    api_client.force_login(backend_user)

    response = api_client.get(READINESS_URL)

    assert response.status_code == 200
    assert response.data["id"] == str(own.id)
    assert response.data["user"]["id"] == str(backend_user.id)

    own.consumed_at = timezone.now()
    own.save(update_fields=["consumed_at"])
    missing = api_client.get(READINESS_URL)
    assert missing.status_code == 404


def test_current_proposed_formation_blocks_readiness_creation(
    formation,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
    formation_catalog,
):
    assert formation.ready_confirmed_at is None
    created_at = timezone.now() - timedelta(hours=2)
    ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
        created_at=created_at,
        consumed_at=created_at + timedelta(hours=1),
    )
    other_template = create_other_template(
        formation_catalog,
        slug="formation-conflict-project",
    )
    other_version = create_version(
        project_template=other_template,
        version_number=1,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )

    with pytest.raises(MemberHasUnresolvedFormation):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=backend_user,
                project_version=other_version,
                technology_stack=django_stack,
            ),
        )

    assert not ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).exists()


def test_active_project_run_blocks_readiness_for_another_template(
    runtime_project_run,
    backend_user,
    backend_role,
    django_stack,
    formation_catalog,
):
    other_template = create_other_template(
        formation_catalog,
        slug="another-project",
    )
    other_version = create_version(
        project_template=other_template,
        version_number=1,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )
    assert runtime_project_run.state == ProjectRunState.ACTIVE

    with pytest.raises(MemberHasActiveProjectRun):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=backend_user,
                project_version=other_version,
                technology_stack=django_stack,
            ),
        )


def test_active_project_run_blocks_readiness_for_another_version_same_template(
    runtime_project_run,
    backend_user,
    backend_role,
    django_stack,
    formation_catalog,
):
    newer_version = create_version(
        project_template=formation_catalog["project_template"],
        version_number=3,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )
    assert runtime_project_run.project_version_id != newer_version.id

    with pytest.raises(MemberHasActiveProjectRun):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=backend_user,
                project_version=newer_version,
                technology_stack=django_stack,
            ),
        )


def test_consumed_history_does_not_bypass_active_project_run_guard(
    runtime_project_run,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
    formation_catalog,
):
    created_at = timezone.now() - timedelta(days=1)
    ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
        created_at=created_at,
        consumed_at=created_at + timedelta(hours=1),
    )
    other_template = create_other_template(
        formation_catalog,
        slug="post-consumption-project",
    )
    other_version = create_version(
        project_template=other_template,
        version_number=1,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )

    with pytest.raises(MemberHasActiveProjectRun):
        create_project_readiness(
            user=backend_user,
            session=confirmed_selection(
                user=backend_user,
                project_version=other_version,
                technology_stack=django_stack,
            ),
        )

    assert ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).count() == 0


def test_terminal_project_run_no_longer_blocks_future_readiness(
    overdue_runtime_project_run,
    facilitator,
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    ended = mark_project_run_incomplete(
        project_run_id=overdue_runtime_project_run.id,
        actor=facilitator,
    )
    assert ended.state == ProjectRunState.INCOMPLETE
    assert ended.ended_at is not None

    readiness = create_project_readiness(
        user=backend_user,
        session=confirmed_selection(
            user=backend_user,
            project_version=helpdesk_version,
            technology_stack=django_stack,
        ),
    )

    assert readiness.user_id == backend_user.id
    assert readiness.role_id == backend_role.id
    assert readiness.project_version_id == helpdesk_version.id


def test_readiness_creation_requires_csrf(
    csrf_client,
    backend_user,
    helpdesk_version,
    django_stack,
):
    csrf_client.force_login(backend_user)
    install_confirmed_selection(
        csrf_client,
        user=backend_user,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    response = csrf_client.post(READINESS_URL, {}, format="json")

    assert response.status_code == 403
    assert not ProjectReadiness.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_readiness_creation_never_creates_two_active_rows(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
    formation_catalog,
):
    barrier = Barrier(2)
    newer_version = create_version(
        project_template=formation_catalog["project_template"],
        version_number=3,
        role=backend_role,
        stack_policy=StackPolicy.ALLOWLIST,
        allowed_stacks=(django_stack,),
    )
    selections = [
        confirmed_selection(
            user=backend_user,
            project_version=project_version,
            technology_stack=django_stack,
        )
        for project_version in (helpdesk_version, newer_version)
    ]

    def create_once(selection):
        close_old_connections()
        try:
            thread_user = type(backend_user).objects.get(id=backend_user.id)
            barrier.wait(timeout=5)
            try:
                create_project_readiness(
                    user=thread_user,
                    session=selection.copy(),
                )
            except ActiveProjectReadinessExists:
                return "rejected"
            return "created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_once, selections))

    assert sorted(results) == ["created", "rejected"]
    active = ProjectReadiness.objects.get(
        user=backend_user,
        consumed_at__isnull=True,
    )
    assert active.project_version_id in {helpdesk_version.id, newer_version.id}


def test_active_readiness_selector_returns_only_the_active_row(
    backend_user,
    backend_role,
    helpdesk_version,
    django_stack,
):
    created_at = timezone.now() - timedelta(days=1)
    ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
        created_at=created_at,
        consumed_at=created_at + timedelta(hours=1),
    )
    active = ProjectReadiness.objects.create(
        user=backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    selected = active_project_readiness_for_user(user=backend_user)

    assert selected.id == active.id
