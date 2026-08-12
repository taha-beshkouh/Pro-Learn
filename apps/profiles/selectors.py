from django.db.models import Prefetch, QuerySet

from apps.accounts.models import User
from apps.profiles.models import (
    ProfileLink,
    Role,
    TechnologyStack,
    UserProfile,
    UserSkill,
)


def role_list() -> QuerySet[Role]:
    return Role.objects.order_by("name")


def technology_stack_list() -> QuerySet[TechnologyStack]:
    return TechnologyStack.objects.order_by("name")


def profile_for_user(*, user: User) -> UserProfile:
    return (
        UserProfile.objects.select_related("user", "selected_role")
        .prefetch_related(
            Prefetch("links", queryset=ProfileLink.objects.order_by("position", "created_at")),
            Prefetch(
                "skills",
                queryset=UserSkill.objects.select_related("technology_stack").order_by(
                    "technology_stack__name"
                ),
            ),
        )
        .get(user=user)
    )


def link_for_user(*, user: User, link_id) -> ProfileLink:
    return ProfileLink.objects.select_related("profile").get(
        id=link_id,
        profile__user=user,
    )


def skill_for_user(*, user: User, skill_id) -> UserSkill:
    return UserSkill.objects.select_related("profile", "technology_stack").get(
        id=skill_id,
        profile__user=user,
    )

