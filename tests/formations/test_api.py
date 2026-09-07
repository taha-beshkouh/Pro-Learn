import pytest

from apps.formations.models import ProjectReadiness, ReadyCheckStatus
from apps.formations.services import confirm_ready_check


pytestmark = pytest.mark.django_db


def formation_payload(helpdesk_version, proposed_members):
    return {
        "readiness_ids": [str(readiness.id) for readiness in proposed_members],
    }


def test_only_staff_can_create_or_list_formations(
    api_client,
    backend_user,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    payload = formation_payload(helpdesk_version, proposed_members)
    assert api_client.post(
        "/api/v1/team-formations/", payload, format="json"
    ).status_code == 403
    api_client.force_login(backend_user)
    assert api_client.post("/api/v1/team-formations/", payload, format="json").status_code == 403
    assert api_client.get("/api/v1/team-formations/").status_code == 403

    api_client.force_login(facilitator)
    created = api_client.post("/api/v1/team-formations/", payload, format="json")

    assert created.status_code == 201
    assert len([item for item in created.data["ready_checks"] if item["is_current"]]) == 3
    assert api_client.get("/api/v1/team-formations/").status_code == 200


def test_normal_member_cannot_view_formation_detail(
    api_client, formation, backend_user
):
    api_client.force_login(backend_user)

    response = api_client.get(f"/api/v1/team-formations/{formation.id}/")

    assert response.status_code == 403


def test_member_sees_only_own_current_ready_checks(
    api_client, formation, backend_user, frontend_user
):
    api_client.force_login(backend_user)
    response = api_client.get("/api/v1/ready-checks/me/")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["user"]["id"] == str(backend_user.id)
    assert response.data[0]["user"]["id"] != str(frontend_user.id)


def test_member_can_confirm_only_own_ready_check(
    api_client, formation, backend_user, frontend_user
):
    backend = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(frontend_user)
    hidden = api_client.post(f"/api/v1/ready-checks/{backend.id}/confirm/")
    assert hidden.status_code == 404

    api_client.force_login(backend_user)
    confirmed = api_client.post(f"/api/v1/ready-checks/{backend.id}/confirm/")
    assert confirmed.status_code == 200
    assert confirmed.data["status"] == ReadyCheckStatus.CONFIRMED


def test_member_can_decline_own_ready_check(api_client, formation, designer_user):
    ready_check = formation.ready_checks.get(user=designer_user, is_current=True)
    api_client.force_login(designer_user)

    response = api_client.post(f"/api/v1/ready-checks/{ready_check.id}/decline/")

    assert response.status_code == 200
    assert response.data["status"] == ReadyCheckStatus.DECLINED


def test_third_confirmation_exposes_created_team_and_project_run_to_staff(
    api_client,
    formation,
    facilitator,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        api_client.force_login(ready_check.user)
        response = api_client.post(
            f"/api/v1/ready-checks/{ready_check.id}/confirm/"
        )
        assert response.status_code == 200

    api_client.force_login(facilitator)
    response = api_client.get(f"/api/v1/team-formations/{formation.id}/")

    assert response.status_code == 200
    assert response.data["team_id"] is not None
    assert response.data["project_run_id"] is not None


def test_active_project_run_conflict_returns_safe_response(
    api_client,
    formation,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    for ready_check in formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    second_readinesses = [
        ProjectReadiness.objects.create(
            user=readiness.user,
            role=readiness.role,
            project_version=readiness.project_version,
            technology_stack=readiness.technology_stack,
        )
        for readiness in proposed_members
    ]

    api_client.force_login(facilitator)
    response = api_client.post(
        "/api/v1/team-formations/",
        {
            "readiness_ids": [
                str(readiness.id) for readiness in second_readinesses
            ]
        },
        format="json",
    )

    assert response.status_code == 409
    assert str(response.data["detail"]) == (
        "A selected user already has an active ProjectRun."
    )
    assert "constraint" not in str(response.data).lower()


def test_only_staff_can_replace_and_replacement_keeps_role(
    api_client,
    formation,
    backend_user,
    replacement_backend_user,
    django_stack,
    facilitator,
):
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    api_client.force_login(backend_user)
    api_client.post(f"/api/v1/ready-checks/{ready_check.id}/decline/")
    url = (
        f"/api/v1/team-formations/{formation.id}/ready-checks/"
        f"{ready_check.id}/replace/"
    )
    readiness = ProjectReadiness.objects.create(
        user=replacement_backend_user,
        role=ready_check.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )
    payload = {"readiness_id": str(readiness.id)}
    assert api_client.post(url, payload, format="json").status_code == 403

    api_client.force_login(facilitator)
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    assert response.data["role"]["code"] == "BACKEND_DEVELOPER"
    assert response.data["user"]["id"] == str(replacement_backend_user.id)


def test_invalid_stack_is_rejected_without_internal_details(
    api_client,
    facilitator,
    helpdesk_version,
    proposed_members,
    react_stack,
):
    payload = formation_payload(helpdesk_version, proposed_members)
    proposed_members[0].technology_stack = react_stack
    proposed_members[0].save(update_fields=["technology_stack"])
    api_client.force_login(facilitator)

    response = api_client.post("/api/v1/team-formations/", payload, format="json")

    assert response.status_code == 400
    assert response.data == {
        "readiness_ids": [
            "A readiness stack is not valid for its exact project role."
        ]
    }
    assert "constraint" not in str(response.data).lower()


def test_ready_check_response_requires_csrf(csrf_client, formation, backend_user):
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)
    csrf_client.force_login(backend_user)

    response = csrf_client.post(f"/api/v1/ready-checks/{ready_check.id}/confirm/")

    assert response.status_code == 403
    ready_check.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.PENDING
