import pytest

from apps.formations.exceptions import SprintTransitionNotAllowed
from apps.formations.models import SprintRun, SprintRunState, SprintSubmission
from apps.formations.services import sprint_next_action, validate_sprint_transition


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (SprintRunState.LOCKED, SprintRunState.ACTIVE),
        (SprintRunState.ACTIVE, SprintRunState.SUBMITTED),
        (SprintRunState.SUBMITTED, SprintRunState.UNDER_REVIEW),
        (SprintRunState.UNDER_REVIEW, SprintRunState.CHANGES_REQUESTED),
        (SprintRunState.UNDER_REVIEW, SprintRunState.COMPLETED),
        (SprintRunState.CHANGES_REQUESTED, SprintRunState.SUBMITTED),
    ],
)
def test_accepted_sprint_transitions(current_state, target_state):
    validate_sprint_transition(
        current_state=current_state,
        target_state=target_state,
    )


@pytest.mark.parametrize(
    ("current_state", "target_state"),
    [
        (SprintRunState.LOCKED, SprintRunState.SUBMITTED),
        (SprintRunState.ACTIVE, SprintRunState.COMPLETED),
        (SprintRunState.SUBMITTED, SprintRunState.COMPLETED),
        (SprintRunState.CHANGES_REQUESTED, SprintRunState.COMPLETED),
        (SprintRunState.COMPLETED, SprintRunState.ACTIVE),
    ],
)
def test_unaccepted_sprint_transitions_are_rejected(current_state, target_state):
    with pytest.raises(SprintTransitionNotAllowed):
        validate_sprint_transition(
            current_state=current_state,
            target_state=target_state,
        )


def test_next_action_is_sprint_state_aware():
    assert sprint_next_action(state=SprintRunState.ACTIVE) == "SUBMIT_SPRINT"
    assert (
        sprint_next_action(state=SprintRunState.CHANGES_REQUESTED)
        == "RESUBMIT_SPRINT"
    )
    assert (
        sprint_next_action(state=SprintRunState.UNDER_REVIEW) == "WAIT_FOR_REVIEW"
    )
    assert sprint_next_action(state=None) == "SPRINTS_COMPLETED"
    assert sprint_next_action(
        state=None,
        has_sprints=False,
    ) == "NO_SPRINT_AVAILABLE"


def test_runtime_models_contain_no_task_lifecycle_fields():
    sprint_fields = {field.name for field in SprintRun._meta.fields}
    submission_fields = {field.name for field in SprintSubmission._meta.fields}

    forbidden = {
        "task",
        "assignee",
        "task_status",
        "task_deadline",
        "completion_percentage",
        "kanban_column",
        "todo_state",
    }
    assert sprint_fields.isdisjoint(forbidden)
    assert submission_fields.isdisjoint(forbidden)
