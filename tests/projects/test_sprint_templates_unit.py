import uuid

import pytest
from django.core.exceptions import ValidationError

from apps.projects.models import ProjectTaskTemplate, ProjectVersion, SprintTemplate
from apps.projects.services import validate_sprint_template, validate_work_item_sprint


def test_sprint_planned_end_offset_is_derived_without_calendar_assumptions():
    sprint = SprintTemplate(
        planned_start_offset_days=10,
        planned_duration_days=5,
    )

    assert sprint.planned_end_offset_days == 15


def test_sprint_sequence_cannot_exceed_declared_version_count():
    version = ProjectVersion(id=uuid.uuid4(), sprint_count=6)
    sprint = SprintTemplate(project_version=version, sequence=7)

    with pytest.raises(ValidationError):
        validate_sprint_template(sprint_template=sprint)


def test_sprint_sequence_is_unbounded_when_version_count_is_unresolved():
    version = ProjectVersion(id=uuid.uuid4(), sprint_count=None)
    sprint = SprintTemplate(project_version=version, sequence=7)

    validate_sprint_template(sprint_template=sprint)


def test_work_item_and_sprint_must_use_the_same_project_version():
    work_version_id = uuid.uuid4()
    sprint_version_id = uuid.uuid4()
    sprint = SprintTemplate(
        id=uuid.uuid4(),
        project_version=ProjectVersion(id=sprint_version_id),
    )
    work_item = ProjectTaskTemplate(
        project_version=ProjectVersion(id=work_version_id),
        sprint_template=sprint,
    )

    with pytest.raises(ValidationError):
        validate_work_item_sprint(work_item=work_item)


def test_unscheduled_work_item_is_valid():
    work_item = ProjectTaskTemplate(
        project_version=ProjectVersion(id=uuid.uuid4()),
        sprint_template=None,
    )

    validate_work_item_sprint(work_item=work_item)

