import pytest
from django.core.exceptions import ValidationError

from apps.projects.models import StackPolicy
from apps.projects.services import validate_stack_policy_shape


@pytest.mark.parametrize(
    ("requires_stack", "policy", "allowed_count"),
    [
        (False, None, 0),
        (True, StackPolicy.FIXED, 1),
        (True, StackPolicy.ALLOWLIST, 1),
        (True, StackPolicy.ALLOWLIST, 3),
        (True, StackPolicy.OPEN, 0),
    ],
)
def test_valid_stack_policy_shapes(requires_stack, policy, allowed_count):
    validate_stack_policy_shape(
        requires_stack=requires_stack,
        stack_policy=policy,
        allowed_count=allowed_count,
    )


@pytest.mark.parametrize(
    ("requires_stack", "policy", "allowed_count"),
    [
        (False, StackPolicy.FIXED, 0),
        (False, None, 1),
        (True, None, 0),
        (True, StackPolicy.FIXED, 0),
        (True, StackPolicy.FIXED, 2),
        (True, StackPolicy.ALLOWLIST, 0),
        (True, StackPolicy.OPEN, 1),
    ],
)
def test_invalid_stack_policy_shapes(requires_stack, policy, allowed_count):
    with pytest.raises(ValidationError):
        validate_stack_policy_shape(
            requires_stack=requires_stack,
            stack_policy=policy,
            allowed_count=allowed_count,
        )

