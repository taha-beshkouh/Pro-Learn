from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.formations.exceptions import (
    ActiveProjectReadinessExists,
    InvalidFormationMembers,
    InvalidFormationReadiness,
    InvalidFormationStack,
    MemberHasActiveProjectRun,
    MemberHasUnresolvedFormation,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ReadyCheck,
    ReadyCheckStatus,
    TeamFormation,
)
from apps.formations.services import (
    confirm_ready_check,
    create_project_readiness,
    create_team_formation,
    decline_ready_check,
    replace_ready_check_member,
)
from apps.profiles.models import RoleCode, UserProfile, UserSkill
from apps.projects.models import (
    ProjectRoleAllowedStack,
    ProjectRoleRequirement,
    ProjectTemplate,
    ProjectVersion,
    StackPolicy,
)


pytestmark = [pytest.mark.django_db, pytest.mark.postgresql]


def readiness_ids(readinesses):
    return [readiness.id for readiness in readinesses]


def create_member(django_user_model, password, *, role, label):
    user = django_user_model.objects.create_user(
        email=f"phase3-{label}@example.com",
        password=password,
    )
    github_username = (
        f"phase3-{user.id.hex[:12]}"
        if role.code in {
            RoleCode.BACKEND_DEVELOPER,
            RoleCode.FRONTEND_DEVELOPER,
        }
        else None
    )
    UserProfile.objects.create(
        user=user,
        selected_role=role,
        github_username=github_username,
    )
    return user


def create_readiness(*, user, role, project_version, technology_stack=None):
    return ProjectReadiness.objects.create(
        user=user,
        role=role,
        project_version=project_version,
        technology_stack=technology_stack,
    )


def create_alternate_members(
    django_user_model,
    password,
    formation_catalog,
    helpdesk_version,
    *,
    label,
):
    specs = (
        (
            RoleCode.BACKEND_DEVELOPER,
            formation_catalog["stacks"]["django-drf"],
        ),
        (
            RoleCode.FRONTEND_DEVELOPER,
            formation_catalog["stacks"]["react-typescript-vite"],
        ),
        (RoleCode.PRODUCT_DESIGNER, None),
    )
    readinesses = []
    for index, (role_code, stack) in enumerate(specs):
        role = formation_catalog["roles"][role_code]
        user = create_member(
            django_user_model,
            password,
            role=role,
            label=f"{label}-{index}",
        )
        readinesses.append(
            create_readiness(
                user=user,
                role=role,
                project_version=helpdesk_version,
                technology_stack=stack,
            )
        )
    return readinesses


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


def test_successful_formation_uses_and_consumes_exact_readiness_snapshots(
    facilitator,
    helpdesk_version,
    proposed_members,
):
    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(proposed_members),
    )

    assert formation.project_version_id == helpdesk_version.id
    checks = list(formation.ready_checks.filter(is_current=True).order_by("role__code"))
    assert len(checks) == 3
    assert {
        (check.user_id, check.role_id, check.technology_stack_id)
        for check in checks
    } == {
        (item.user_id, item.role_id, item.technology_stack_id)
        for item in proposed_members
    }
    for readiness in proposed_members:
        readiness.refresh_from_db()
        assert readiness.consumed_at is not None
        assert readiness.consumed_at >= readiness.created_at


def test_old_arbitrary_member_payload_cannot_bypass_readiness(
    api_client,
    facilitator,
    helpdesk_version,
    proposed_members,
):
    api_client.force_login(facilitator)
    response = api_client.post(
        "/api/v1/team-formations/",
        {
            "project_version_id": str(helpdesk_version.id),
            "members": [
                {
                    "user_id": str(item.user_id),
                    "role_id": str(item.role_id),
                    "technology_stack_id": (
                        str(item.technology_stack_id)
                        if item.technology_stack_id is not None
                        else None
                    ),
                }
                for item in proposed_members
            ],
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["members"] == ["Unknown field."]
    assert response.data["project_version_id"] == ["Unknown field."]
    assert not TeamFormation.objects.exists()
    assert ProjectReadiness.objects.filter(consumed_at__isnull=True).count() == 3


@pytest.mark.parametrize("selected_count", [0, 1, 2, 4])
def test_formation_requires_exactly_three_readiness_ids(
    facilitator,
    proposed_members,
    selected_count,
):
    selected = readiness_ids(proposed_members[:selected_count])
    if selected_count == 4:
        selected.append(uuid4())

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=selected,
        )

    assert not TeamFormation.objects.exists()


def test_formation_requires_exactly_one_of_each_mvp_role(
    django_user_model,
    password,
    facilitator,
    backend_role,
    django_stack,
    helpdesk_version,
    proposed_members,
):
    second_backend = create_member(
        django_user_model,
        password,
        role=backend_role,
        label="duplicate-backend-role",
    )
    duplicate_role_readiness = create_readiness(
        user=second_backend,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )

    with pytest.raises(InvalidFormationMembers):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=[
                proposed_members[0].id,
                proposed_members[1].id,
                duplicate_role_readiness.id,
            ],
        )


def test_formation_rejects_mixed_exact_project_versions(
    facilitator,
    formation_catalog,
    proposed_members,
):
    newer = ProjectVersion.objects.create(
        project_template=formation_catalog["project_template"],
        version_number=3,
        duration_weeks=6,
        sprint_count=6,
        published_at=timezone.now(),
    )
    proposed_members[-1].project_version = newer
    proposed_members[-1].save(update_fields=["project_version"])

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_formation_rejects_consumed_readiness(
    facilitator,
    proposed_members,
):
    proposed_members[0].consumed_at = timezone.now()
    proposed_members[0].save(update_fields=["consumed_at"])

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_formation_rejects_invalid_stack_snapshot(
    facilitator,
    proposed_members,
    react_stack,
):
    proposed_members[0].technology_stack = react_stack
    proposed_members[0].save(update_fields=["technology_stack"])

    with pytest.raises(InvalidFormationStack):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_formation_revalidates_open_stack_against_current_user_skills(
    facilitator,
    backend_user,
    frontend_user,
    designer_user,
    backend_role,
    frontend_role,
    designer_role,
    django_stack,
    react_stack,
    formation_catalog,
):
    project_version = ProjectVersion.objects.create(
        project_template=formation_catalog["project_template"],
        version_number=3,
        duration_weeks=6,
        sprint_count=6,
        published_at=timezone.now(),
    )
    backend_requirement = ProjectRoleRequirement.objects.create(
        project_version=project_version,
        role=backend_role,
        requires_stack=True,
        stack_policy=StackPolicy.OPEN,
    )
    frontend_requirement = ProjectRoleRequirement.objects.create(
        project_version=project_version,
        role=frontend_role,
        requires_stack=True,
        stack_policy=StackPolicy.FIXED,
    )
    ProjectRoleRequirement.objects.create(
        project_version=project_version,
        role=designer_role,
        requires_stack=False,
        stack_policy=None,
    )
    ProjectRoleAllowedStack.objects.create(
        role_requirement=frontend_requirement,
        technology_stack=react_stack,
    )
    skill = UserSkill.objects.create(
        profile=backend_user.profile,
        technology_stack=django_stack,
    )
    readinesses = [
        create_readiness(
            user=backend_user,
            role=backend_role,
            project_version=project_version,
            technology_stack=django_stack,
        ),
        create_readiness(
            user=frontend_user,
            role=frontend_role,
            project_version=project_version,
            technology_stack=react_stack,
        ),
        create_readiness(
            user=designer_user,
            role=designer_role,
            project_version=project_version,
            technology_stack=None,
        ),
    ]
    assert backend_requirement.stack_policy == StackPolicy.OPEN
    skill.delete()

    with pytest.raises(InvalidFormationStack):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(readinesses),
        )


def test_formation_rejects_fake_stack_for_stackless_role(
    facilitator,
    proposed_members,
    django_stack,
):
    proposed_members[-1].technology_stack = django_stack
    proposed_members[-1].save(update_fields=["technology_stack"])

    with pytest.raises(InvalidFormationStack):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_formation_revalidates_active_user_and_authoritative_profile_role(
    facilitator,
    backend_user,
    frontend_role,
    proposed_members,
):
    UserProfile.objects.filter(user=backend_user).update(selected_role=frontend_role)

    with pytest.raises(InvalidFormationMembers):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_formation_rejects_inactive_readiness_user(
    facilitator,
    backend_user,
    proposed_members,
):
    backend_user.is_active = False
    backend_user.save(update_fields=["is_active"])

    with pytest.raises(InvalidFormationMembers):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )


def test_current_proposed_formation_user_cannot_be_selected_again(
    formation,
    facilitator,
    proposed_members,
):
    second_readinesses = [
        create_readiness(
            user=item.user,
            role=item.role,
            project_version=item.project_version,
            technology_stack=item.technology_stack,
        )
        for item in proposed_members
    ]

    with pytest.raises(MemberHasUnresolvedFormation):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(second_readinesses),
        )

    assert TeamFormation.objects.count() == 1


def test_current_formation_exclusion_is_user_level_across_project_templates(
    formation,
    facilitator,
    formation_catalog,
    proposed_members,
):
    other_template = ProjectTemplate.objects.create(
        level=formation_catalog["level"],
        slug="phase3-other-template",
        name="Phase 3 Other Template",
    )
    other_version = ProjectVersion.objects.create(
        project_template=other_template,
        version_number=1,
        duration_weeks=6,
        sprint_count=6,
        published_at=timezone.now(),
    )
    second_readinesses = [
        create_readiness(
            user=item.user,
            role=item.role,
            project_version=other_version,
            technology_stack=item.technology_stack,
        )
        for item in proposed_members
    ]

    with pytest.raises(MemberHasUnresolvedFormation):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(second_readinesses),
        )


def test_newer_publication_does_not_replace_readiness_exact_version(
    facilitator,
    helpdesk_version,
    formation_catalog,
    proposed_members,
):
    newer = ProjectVersion.objects.create(
        project_template=formation_catalog["project_template"],
        version_number=3,
        duration_weeks=6,
        sprint_count=6,
        published_at=timezone.now(),
    )

    formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(proposed_members),
    )

    assert formation.project_version_id == helpdesk_version.id
    assert formation.project_version_id != newer.id


def test_formation_failure_rolls_back_formation_ready_checks_and_consumption(
    facilitator,
    proposed_members,
):
    with patch(
        "apps.formations.services._consume_locked_readinesses",
        side_effect=RuntimeError("forced failure after ReadyCheck creation"),
    ), pytest.raises(RuntimeError):
        create_team_formation(
            created_by=facilitator,
            readiness_ids=readiness_ids(proposed_members),
        )

    assert not TeamFormation.objects.exists()
    assert not ReadyCheck.objects.exists()
    assert ProjectReadiness.objects.filter(consumed_at__isnull=True).count() == 3


def test_sequential_reuse_of_consumed_readiness_is_rejected(
    facilitator,
    proposed_members,
):
    selected = readiness_ids(proposed_members)
    create_team_formation(created_by=facilitator, readiness_ids=selected)

    with pytest.raises(InvalidFormationReadiness):
        create_team_formation(created_by=facilitator, readiness_ids=selected)

    assert TeamFormation.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_formations_sharing_one_user_cannot_both_succeed(
    django_user_model,
    password,
    facilitator,
    formation_catalog,
    helpdesk_version,
    proposed_members,
):
    alternatives = create_alternate_members(
        django_user_model,
        password,
        formation_catalog,
        helpdesk_version,
        label="concurrent-alternative",
    )
    selections = (
        readiness_ids(proposed_members),
        [proposed_members[0].id, alternatives[1].id, alternatives[2].id],
    )
    barrier = Barrier(2)

    def create_once(selected):
        close_old_connections()
        try:
            actor = type(facilitator).objects.get(id=facilitator.id)
            barrier.wait(timeout=5)
            try:
                create_team_formation(
                    created_by=actor,
                    readiness_ids=selected,
                )
            except (InvalidFormationReadiness, MemberHasUnresolvedFormation):
                return "rejected"
            return "created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_once, selections))

    assert sorted(results) == ["created", "rejected"]
    assert TeamFormation.objects.count() == 1
    assert ReadyCheck.objects.filter(
        user_id=proposed_members[0].user_id,
        is_current=True,
        formation__ready_confirmed_at__isnull=True,
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_formation_and_concurrent_readiness_creation_preserve_one_flow(
    facilitator,
    backend_user,
    helpdesk_version,
    django_stack,
    proposed_members,
):
    barrier = Barrier(2)

    def form_team():
        close_old_connections()
        try:
            actor = type(facilitator).objects.get(id=facilitator.id)
            barrier.wait(timeout=5)
            create_team_formation(
                created_by=actor,
                readiness_ids=readiness_ids(proposed_members),
            )
            return "formed"
        finally:
            close_old_connections()

    def create_again():
        close_old_connections()
        try:
            user = type(backend_user).objects.get(id=backend_user.id)
            barrier.wait(timeout=5)
            try:
                create_project_readiness(
                    user=user,
                    session=confirmed_selection(
                        user=user,
                        project_version=helpdesk_version,
                        technology_stack=django_stack,
                    ),
                )
            except (ActiveProjectReadinessExists, MemberHasUnresolvedFormation):
                return "rejected"
            return "unexpected-readiness"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        formation_result = executor.submit(form_team)
        readiness_result = executor.submit(create_again)
        results = [formation_result.result(), readiness_result.result()]

    assert sorted(results) == ["formed", "rejected"]
    assert TeamFormation.objects.count() == 1
    assert ReadyCheck.objects.filter(is_current=True).count() == 3
    assert not ProjectReadiness.objects.filter(
        user=backend_user,
        consumed_at__isnull=True,
    ).exists()


def test_staff_can_list_only_active_readiness_for_one_exact_version(
    api_client,
    facilitator,
    password,
    backend_user,
    backend_role,
    django_stack,
    helpdesk_version,
    proposed_members,
):
    historical = create_readiness(
        user=create_member(
            type(backend_user),
            password,
            role=backend_role,
            label="historical-listing",
        ),
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    historical.consumed_at = timezone.now()
    historical.save(update_fields=["consumed_at"])
    url = f"/api/v1/project-readiness/?project_version_id={helpdesk_version.id}"

    assert api_client.get(url).status_code == 403
    api_client.force_login(facilitator)
    response = api_client.get(url)

    assert response.status_code == 200
    assert {item["id"] for item in response.data} == {
        str(item.id) for item in proposed_members
    }
    assert all(item["project_version_id"] == str(helpdesk_version.id) for item in response.data)


def test_replacement_requires_active_readiness(
    formation,
    facilitator,
    backend_user,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)

    with pytest.raises(InvalidFormationReadiness):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=uuid4(),
            proposed_by=facilitator,
        )


def test_old_replacement_user_and_stack_payload_cannot_bypass_readiness(
    api_client,
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    django_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    api_client.force_login(facilitator)
    response = api_client.post(
        (
            f"/api/v1/team-formations/{formation.id}/ready-checks/"
            f"{target.id}/replace/"
        ),
        {
            "user_id": str(replacement_backend_user.id),
            "technology_stack_id": str(django_stack.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["user_id"] == ["Unknown field."]
    assert response.data["technology_stack_id"] == ["Unknown field."]
    assert formation.ready_checks.filter(is_current=True).count() == 3


def test_replacement_readiness_must_use_formation_exact_version(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    django_stack,
    formation_catalog,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    newer = ProjectVersion.objects.create(
        project_template=formation_catalog["project_template"],
        version_number=3,
        duration_weeks=6,
        sprint_count=6,
        published_at=timezone.now(),
    )
    readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=newer,
        technology_stack=django_stack,
    )

    with pytest.raises(InvalidFormationReadiness):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
        )


def test_consumed_replacement_readiness_is_rejected(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    django_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )
    readiness.consumed_at = timezone.now()
    readiness.save(update_fields=["consumed_at"])

    with pytest.raises(InvalidFormationReadiness):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
        )


def test_replacement_readiness_must_match_slot_role(
    django_user_model,
    password,
    formation,
    facilitator,
    backend_user,
    frontend_role,
    react_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    replacement_user = create_member(
        django_user_model,
        password,
        role=frontend_role,
        label="wrong-replacement-role",
    )
    readiness = create_readiness(
        user=replacement_user,
        role=frontend_role,
        project_version=formation.project_version,
        technology_stack=react_stack,
    )

    with pytest.raises(InvalidFormationMembers):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
        )


def test_replacement_revalidates_stack_snapshot(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    react_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=formation.project_version,
        technology_stack=react_stack,
    )

    with pytest.raises(InvalidFormationStack):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
        )


def test_successful_replacement_consumes_readiness_and_allows_replaced_user_reentry(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    django_stack,
    proposed_members,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    other_current_ids = set(
        formation.ready_checks.filter(is_current=True)
        .exclude(id=target.id)
        .values_list("id", flat=True)
    )
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    replacement_readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    replacement = replace_ready_check_member(
        formation_id=formation.id,
        ready_check_id=target.id,
        replacement_readiness_id=replacement_readiness.id,
        proposed_by=facilitator,
    )

    replacement_readiness.refresh_from_db()
    target.refresh_from_db()
    original_readiness = next(
        item for item in proposed_members if item.user_id == backend_user.id
    )
    original_readiness.refresh_from_db()
    assert replacement_readiness.consumed_at is not None
    assert original_readiness.consumed_at is not None
    assert target.is_current is False
    assert replacement.user_id == replacement_backend_user.id
    assert set(
        formation.ready_checks.filter(is_current=True).values_list("id", flat=True)
    ) == other_current_ids | {replacement.id}

    new_readiness = create_project_readiness(
        user=backend_user,
        session=confirmed_selection(
            user=backend_user,
            project_version=formation.project_version,
            technology_stack=django_stack,
        ),
    )
    assert new_readiness.user_id == backend_user.id
    assert new_readiness.consumed_at is None


def test_replacement_failure_rolls_back_slot_and_readiness_consumption(
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    django_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    with patch(
        "apps.formations.services._consume_locked_readinesses",
        side_effect=RuntimeError("forced replacement failure"),
    ), pytest.raises(RuntimeError):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=readiness.id,
            proposed_by=facilitator,
        )

    target.refresh_from_db()
    readiness.refresh_from_db()
    assert target.is_current is True
    assert target.status == ReadyCheckStatus.DECLINED
    assert readiness.consumed_at is None
    assert formation.ready_checks.count() == 3


def test_replacement_user_with_active_project_run_is_rejected(
    django_user_model,
    password,
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    formation_catalog,
    helpdesk_version,
    django_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    active_run_readinesses = create_alternate_members(
        django_user_model,
        password,
        formation_catalog,
        helpdesk_version,
        label="active-run-replacement",
    )
    active_run_readinesses[0] = create_readiness(
        user=replacement_backend_user,
        role=formation_catalog["roles"][RoleCode.BACKEND_DEVELOPER],
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    active_formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(active_run_readinesses),
    )
    for ready_check in active_formation.ready_checks.order_by("role__code"):
        confirm_ready_check(ready_check_id=ready_check.id, user=ready_check.user)
    assert ProjectRun.objects.filter(
        members__user=replacement_backend_user,
        state="ACTIVE",
    ).exists()
    replacement_readiness = create_readiness(
        user=replacement_backend_user,
        role=target.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    with pytest.raises(MemberHasActiveProjectRun):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=replacement_readiness.id,
            proposed_by=facilitator,
        )


def test_replacement_user_in_another_current_formation_is_rejected(
    django_user_model,
    password,
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    formation_catalog,
    helpdesk_version,
    django_stack,
):
    target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=target.id, user=backend_user)
    other_readinesses = create_alternate_members(
        django_user_model,
        password,
        formation_catalog,
        helpdesk_version,
        label="current-formation-replacement",
    )
    other_readinesses[0] = create_readiness(
        user=replacement_backend_user,
        role=formation_catalog["roles"][RoleCode.BACKEND_DEVELOPER],
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    other_formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(other_readinesses),
    )
    assert other_formation.ready_confirmed_at is None
    replacement_readiness = create_readiness(
        user=replacement_backend_user,
        role=target.role,
        project_version=formation.project_version,
        technology_stack=django_stack,
    )

    with pytest.raises(MemberHasUnresolvedFormation):
        replace_ready_check_member(
            formation_id=formation.id,
            ready_check_id=target.id,
            replacement_readiness_id=replacement_readiness.id,
            proposed_by=facilitator,
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_replacements_cannot_consume_same_readiness_twice(
    django_user_model,
    password,
    formation,
    facilitator,
    backend_user,
    replacement_backend_user,
    backend_role,
    django_stack,
    formation_catalog,
    helpdesk_version,
):
    first_target = formation.ready_checks.get(user=backend_user, is_current=True)
    decline_ready_check(ready_check_id=first_target.id, user=backend_user)
    second_members = create_alternate_members(
        django_user_model,
        password,
        formation_catalog,
        helpdesk_version,
        label="concurrent-replacement-target",
    )
    second_formation = create_team_formation(
        created_by=facilitator,
        readiness_ids=readiness_ids(second_members),
    )
    second_target = second_formation.ready_checks.get(
        role__code=RoleCode.BACKEND_DEVELOPER,
        is_current=True,
    )
    decline_ready_check(
        ready_check_id=second_target.id,
        user=second_target.user,
    )
    replacement_readiness = create_readiness(
        user=replacement_backend_user,
        role=backend_role,
        project_version=helpdesk_version,
        technology_stack=django_stack,
    )
    barrier = Barrier(2)

    def replace_once(target):
        close_old_connections()
        try:
            actor = type(facilitator).objects.get(id=facilitator.id)
            barrier.wait(timeout=5)
            try:
                replace_ready_check_member(
                    formation_id=target.formation_id,
                    ready_check_id=target.id,
                    replacement_readiness_id=replacement_readiness.id,
                    proposed_by=actor,
                )
            except (InvalidFormationReadiness, MemberHasUnresolvedFormation):
                return "rejected"
            return "replaced"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(replace_once, (first_target, second_target)))

    assert sorted(results) == ["rejected", "replaced"]
    replacement_readiness.refresh_from_db()
    assert replacement_readiness.consumed_at is not None
    assert ReadyCheck.objects.filter(
        user=replacement_backend_user,
        is_current=True,
        formation__ready_confirmed_at__isnull=True,
    ).count() == 1


def test_anonymous_ready_check_action_remains_rejected(
    api_client,
    formation,
    backend_user,
):
    ready_check = formation.ready_checks.get(user=backend_user, is_current=True)

    response = api_client.post(f"/api/v1/ready-checks/{ready_check.id}/confirm/")

    assert response.status_code == 403
    ready_check.refresh_from_db()
    assert ready_check.status == ReadyCheckStatus.PENDING
