from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.formations.exceptions import SprintRuntimeConfigurationError
from apps.formations.api.serializers import StaffProjectRunRepositorySerializer
from apps.formations.models import ProjectRun, ProjectRunState
from apps.formations.services import (
    project_run_deadline,
    submission_deadline_passed,
)


def test_project_run_states_are_exactly_the_accepted_terminal_lifecycle():
    assert set(ProjectRunState.values) == {"ACTIVE", "COMPLETED", "INCOMPLETE"}


def test_project_run_deadline_uses_fixed_version_duration():
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert project_run_deadline(started_at=started_at, duration_weeks=6) == (
        started_at + timedelta(weeks=6)
    )


@pytest.mark.parametrize("duration_weeks", [None, 0])
def test_project_run_deadline_rejects_missing_duration(duration_weeks):
    with pytest.raises(SprintRuntimeConfigurationError):
        project_run_deadline(
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            duration_weeks=duration_weeks,
        )


def test_submission_cutoff_is_inclusive_at_deadline():
    deadline_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

    assert submission_deadline_passed(
        now=deadline_at - timedelta(microseconds=1),
        deadline_at=deadline_at,
    ) is False
    assert submission_deadline_passed(
        now=deadline_at,
        deadline_at=deadline_at,
    ) is True


def test_staff_incomplete_read_flag_uses_server_time_and_terminal_state():
    deadline = datetime(2026, 2, 1, tzinfo=timezone.utc)
    run = SimpleNamespace(
        state=ProjectRunState.ACTIVE,
        ended_at=None,
        deadline_at=deadline,
    )
    serializer = StaffProjectRunRepositorySerializer()

    with patch(
        "apps.formations.api.serializers.timezone.now",
        return_value=deadline - timedelta(microseconds=1),
    ):
        assert serializer.get_can_mark_incomplete(run) is False
    with patch(
        "apps.formations.api.serializers.timezone.now",
        return_value=deadline,
    ):
        assert serializer.get_can_mark_incomplete(run) is True
        run.state = ProjectRunState.COMPLETED
        assert serializer.get_can_mark_incomplete(run) is False
        run.state = ProjectRunState.INCOMPLETE
        assert serializer.get_can_mark_incomplete(run) is False


def test_project_run_has_no_extension_or_runtime_task_lifecycle_fields():
    fields = {field.name for field in ProjectRun._meta.fields}

    assert fields.isdisjoint(
        {
            "extended_deadline_at",
            "extension_status",
            "completion_percentage",
            "task_status",
        }
    )
