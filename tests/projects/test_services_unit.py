import uuid
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from apps.projects.models import StackPolicy
from apps.projects.services import (
    AUTHENTICATED_STACK_SELECTION_SESSION_KEY,
    authenticated_stack_selection_from_session,
    store_authenticated_stack_selection,
    validate_stack_policy_shape,
)


class FakeSession(dict):
    modified = False


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


def test_authenticated_stack_selection_is_scoped_to_user_and_exact_version():
    user_id = uuid.uuid4()
    project_version_id = uuid.uuid4()
    stack_id = uuid.uuid4()
    session = FakeSession()

    result = store_authenticated_stack_selection(
        session=session,
        profile=SimpleNamespace(user_id=user_id),
        project_version=SimpleNamespace(id=project_version_id),
        selected_stack=SimpleNamespace(id=stack_id),
    )

    assert result == {
        "user_id": str(user_id),
        "project_version_id": str(project_version_id),
        "selected_stack_id": str(stack_id),
    }
    assert session[AUTHENTICATED_STACK_SELECTION_SESSION_KEY] == result
    assert session.modified is True


def test_authenticated_stack_selection_supports_stackless_confirmation():
    session = FakeSession()

    result = store_authenticated_stack_selection(
        session=session,
        profile=SimpleNamespace(user_id=uuid.uuid4()),
        project_version=SimpleNamespace(id=uuid.uuid4()),
        selected_stack=None,
    )

    assert result["selected_stack_id"] is None


def test_malformed_authenticated_stack_selection_is_ignored():
    session = FakeSession({AUTHENTICATED_STACK_SELECTION_SESSION_KEY: "malformed"})

    assert authenticated_stack_selection_from_session(session=session) == {}
