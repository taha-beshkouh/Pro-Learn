from types import SimpleNamespace

import pytest

from apps.formations.api.permissions import IsActiveAdminUser


@pytest.mark.parametrize(
    ("is_authenticated", "is_active", "is_staff", "expected"),
    [
        (True, True, True, True),
        (True, False, True, False),
        (True, True, False, False),
        (False, True, True, False),
    ],
)
def test_staff_sprint_read_permission_requires_active_authenticated_staff(
    is_authenticated,
    is_active,
    is_staff,
    expected,
):
    request = SimpleNamespace(
        user=SimpleNamespace(
            is_authenticated=is_authenticated,
            is_active=is_active,
            is_staff=is_staff,
        )
    )

    assert IsActiveAdminUser().has_permission(request, view=None) is expected
