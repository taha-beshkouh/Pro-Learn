from datetime import timedelta
import pytest
from django.utils import timezone

from apps.formations.exceptions import InvalidFormationMembers
from apps.formations.models import ReadyCheck, ReadyCheckStatus
from apps.formations.services import validate_member_roles
from apps.profiles.models import RoleCode


def test_exact_mvp_role_set_is_valid():
    validate_member_roles(role_codes=RoleCode.values)


@pytest.mark.parametrize(
    "codes",
    [
        [],
        [RoleCode.BACKEND_DEVELOPER],
        [
            RoleCode.BACKEND_DEVELOPER,
            RoleCode.BACKEND_DEVELOPER,
            RoleCode.PRODUCT_DESIGNER,
        ],
        [
            RoleCode.BACKEND_DEVELOPER,
            RoleCode.FRONTEND_DEVELOPER,
            "UNKNOWN",
        ],
    ],
)
def test_incomplete_duplicate_or_unknown_role_sets_are_rejected(codes):
    with pytest.raises(InvalidFormationMembers):
        validate_member_roles(role_codes=codes)


def test_pending_ready_check_is_effectively_expired_at_deadline():
    deadline = timezone.now()
    ready_check = ReadyCheck(
        status=ReadyCheckStatus.PENDING,
        expires_at=deadline,
    )

    assert ready_check.effective_status(at=deadline - timedelta(microseconds=1)) == (
        ReadyCheckStatus.PENDING
    )
    assert ready_check.effective_status(at=deadline) == ReadyCheckStatus.EXPIRED
