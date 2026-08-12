from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections

from apps.profiles.models import UserProfile
from apps.profiles.services import (
    RoleAlreadySelected,
    SkillAlreadyRegistered,
    add_user_skill,
    select_profile_role,
)


pytestmark = pytest.mark.django_db


def test_select_role_is_idempotent_for_the_same_role(user, profile, backend_role):
    select_profile_role(user=user, role=backend_role)
    select_profile_role(user=user, role=backend_role)

    profile.refresh_from_db()
    assert profile.selected_role == backend_role


def test_selected_role_cannot_be_changed(
    user, profile, backend_role, frontend_role
):
    select_profile_role(user=user, role=backend_role)

    with pytest.raises(RoleAlreadySelected):
        select_profile_role(user=user, role=frontend_role)

    profile.refresh_from_db()
    assert profile.selected_role == backend_role


def test_duplicate_skill_is_reported(profile, django_stack):
    add_user_skill(profile=profile, technology_stack=django_stack)

    with pytest.raises(SkillAlreadyRegistered):
        add_user_skill(profile=profile, technology_stack=django_stack)


@pytest.mark.django_db(transaction=True)
@pytest.mark.postgresql
def test_concurrent_role_selection_allows_exactly_one_role(
    user, profile, backend_role, frontend_role
):
    barrier = Barrier(2)

    def choose(role_id):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            thread_user = type(user).objects.get(id=user.id)
            role = type(backend_role).objects.get(id=role_id)
            try:
                select_profile_role(user=thread_user, role=role)
            except RoleAlreadySelected:
                return "rejected"
            return "selected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(choose, [backend_role.id, frontend_role.id])
        )

    assert sorted(results) == ["rejected", "selected"]
    selected_role_id = UserProfile.objects.get(id=profile.id).selected_role_id
    assert selected_role_id in {backend_role.id, frontend_role.id}

