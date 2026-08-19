import pytest

from apps.formations.api.serializers import (
    MyReadyCheckSerializer,
    TeamFormationSerializer,
)
from apps.formations.selectors import (
    current_ready_checks_for_user,
    formation_detail,
)


pytestmark = pytest.mark.django_db


def test_formation_detail_serialization_uses_two_queries(
    django_assert_num_queries, formation
):
    with django_assert_num_queries(2):
        selected = formation_detail(formation_id=formation.id)
        data = TeamFormationSerializer(selected).data

    assert len(data["ready_checks"]) == 3


def test_member_ready_check_serialization_uses_one_query(
    django_assert_num_queries, formation, backend_user
):
    with django_assert_num_queries(1):
        data = MyReadyCheckSerializer(
            current_ready_checks_for_user(user=backend_user),
            many=True,
        ).data

    assert len(data) == 1
