import pytest

from apps.projects.api.serializers import (
    ProjectDetailSerializer,
    ProjectVersionDetailSerializer,
)
from apps.projects.selectors import (
    project_template_detail,
    published_project_version,
)


pytestmark = pytest.mark.django_db


def test_detail_selector_and_serialization_have_bounded_queries(
    django_assert_num_queries, helpdesk_template, backend_role
):
    with django_assert_num_queries(8):
        project = project_template_detail(project_id=helpdesk_template.id)
        version = published_project_version(version_id=project.published_version_id)
        data = ProjectDetailSerializer(
            project,
            context={
                "published_version": version,
                "selected_role": backend_role,
                "profile": None,
            },
        ).data
        definition_data = ProjectVersionDetailSerializer(
            version,
            context={
                "selected_role": backend_role,
                "profile": None,
            },
        ).data

    assert data["published_version"]["role_context"]["role"]["code"] == (
        "BACKEND_DEVELOPER"
    )
    assert len(definition_data["role_requirements"]) == 3
    assert len(definition_data["work_items"]) == 126
