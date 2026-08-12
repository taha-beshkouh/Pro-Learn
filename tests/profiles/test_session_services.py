import uuid
from types import SimpleNamespace

from apps.profiles.services import (
    GUEST_CONTEXT_SESSION_KEY,
    clear_guest_context,
    guest_context_from_session,
    update_guest_context,
)


class FakeSession(dict):
    modified = False


def test_guest_context_is_serialized_without_database_objects():
    role_id = uuid.uuid4()
    stack_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session = FakeSession()

    result = update_guest_context(
        session=session,
        changes={
            "selected_role": SimpleNamespace(pk=role_id),
            "selected_stack": SimpleNamespace(pk=stack_id),
            "selected_project_id": project_id,
            "intended_action": "join_project",
            "return_path": "/projects",
        },
    )

    assert result == {
        "selected_role_id": str(role_id),
        "selected_stack_id": str(stack_id),
        "selected_project_id": str(project_id),
        "intended_action": "join_project",
        "return_path": "/projects",
    }
    assert session[GUEST_CONTEXT_SESSION_KEY] == result
    assert session.modified is True


def test_guest_context_removes_null_values_and_filters_unknown_keys():
    session = FakeSession(
        {
            GUEST_CONTEXT_SESSION_KEY: {
                "return_path": "/projects",
                "unexpected": "must-not-be-reflected",
            }
        }
    )

    result = update_guest_context(
        session=session,
        changes={"return_path": None},
    )

    assert result == {}
    assert session[GUEST_CONTEXT_SESSION_KEY] == {}


def test_malformed_guest_context_is_ignored_and_clear_preserves_other_session_data():
    session = FakeSession(
        {
            GUEST_CONTEXT_SESSION_KEY: "malformed",
            "unrelated": "preserved",
        }
    )

    assert guest_context_from_session(session=session) == {}
    clear_guest_context(session=session)

    assert session == {"unrelated": "preserved"}
    assert session.modified is True

