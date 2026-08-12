import pytest

from apps.profiles.api.serializers import UserProfileSerializer
from apps.profiles.models import ProfileLink, UserSkill
from apps.profiles.selectors import profile_for_user


pytestmark = pytest.mark.django_db


def test_profile_selector_prevents_nested_n_plus_one_queries(
    django_assert_num_queries, user, profile, django_stack
):
    for index in range(3):
        ProfileLink.objects.create(
            profile=profile,
            link_type=ProfileLink.LinkType.PROJECT,
            url=f"https://example.com/projects/{index}",
            position=index,
        )
    UserSkill.objects.create(profile=profile, technology_stack=django_stack)

    with django_assert_num_queries(3):
        selected = profile_for_user(user=user)
        data = UserProfileSerializer(selected).data

    assert len(data["links"]) == 3
    assert len(data["skills"]) == 1

