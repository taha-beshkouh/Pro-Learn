from django.contrib.sessions.backends.base import SessionBase
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.profiles.models import ProfileLink, Role, UserProfile, UserSkill


GUEST_CONTEXT_SESSION_KEY = "participation_context"


class RoleAlreadySelected(Exception):
    pass


class SkillAlreadyRegistered(Exception):
    pass


class ProfileLinkAlreadyRegistered(Exception):
    pass


def create_profile_for_user(
    *, user: User, selected_role: Role | None = None
) -> UserProfile:
    return UserProfile.objects.create(user=user, selected_role=selected_role)


def update_profile(*, profile: UserProfile, changes: dict) -> UserProfile:
    allowed_fields = {"display_name", "timezone", "language", "interests"}
    update_fields: list[str] = []
    for field, value in changes.items():
        if field not in allowed_fields:
            continue
        setattr(profile, field, value)
        update_fields.append(field)
    if update_fields:
        update_fields.append("updated_at")
        profile.save(update_fields=update_fields)
    return profile


@transaction.atomic
def select_profile_role(*, user: User, role: Role) -> UserProfile:
    profile = UserProfile.objects.select_for_update().get(user=user)
    if profile.selected_role_id is not None:
        if profile.selected_role_id == role.id:
            return profile
        raise RoleAlreadySelected
    profile.selected_role = role
    profile.save(update_fields=["selected_role", "updated_at"])
    return profile


def create_profile_link(*, profile: UserProfile, data: dict) -> ProfileLink:
    try:
        with transaction.atomic():
            return ProfileLink.objects.create(profile=profile, **data)
    except IntegrityError as exc:
        if ProfileLink.objects.filter(profile=profile, url=data["url"]).exists():
            raise ProfileLinkAlreadyRegistered from exc
        raise


def update_profile_link(*, link: ProfileLink, changes: dict) -> ProfileLink:
    allowed_fields = {"link_type", "url", "label", "position"}
    update_fields: list[str] = []
    for field, value in changes.items():
        if field not in allowed_fields:
            continue
        setattr(link, field, value)
        update_fields.append(field)
    if update_fields:
        update_fields.append("updated_at")
        try:
            with transaction.atomic():
                link.save(update_fields=update_fields)
        except IntegrityError as exc:
            if ProfileLink.objects.filter(
                profile=link.profile,
                url=link.url,
            ).exclude(id=link.id).exists():
                raise ProfileLinkAlreadyRegistered from exc
            raise
    return link


def delete_profile_link(*, link: ProfileLink) -> None:
    link.delete()


def add_user_skill(*, profile: UserProfile, technology_stack) -> UserSkill:
    try:
        with transaction.atomic():
            return UserSkill.objects.create(
                profile=profile,
                technology_stack=technology_stack,
            )
    except IntegrityError as exc:
        if UserSkill.objects.filter(
            profile=profile,
            technology_stack=technology_stack,
        ).exists():
            raise SkillAlreadyRegistered from exc
        raise


def remove_user_skill(*, skill: UserSkill) -> None:
    skill.delete()


def guest_context_from_session(*, session: SessionBase) -> dict:
    context = session.get(GUEST_CONTEXT_SESSION_KEY, {})
    if not isinstance(context, dict):
        return {}
    allowed_keys = {
        "selected_role_id",
        "project_version_id",
        "intended_action",
        "return_path",
    }
    return {key: value for key, value in context.items() if key in allowed_keys}


def update_guest_context(*, session: SessionBase, changes: dict) -> dict:
    context = guest_context_from_session(session=session).copy()
    key_map = {
        "selected_role": "selected_role_id",
        "project_version_id": "project_version_id",
        "intended_action": "intended_action",
        "return_path": "return_path",
    }
    for key, value in changes.items():
        session_key = key_map[key]
        if value is None or value == "":
            context.pop(session_key, None)
        elif key == "selected_role":
            context[session_key] = str(value.pk)
        else:
            context[session_key] = str(value)
    session[GUEST_CONTEXT_SESSION_KEY] = context
    session.modified = True
    return context


def clear_guest_context(*, session: SessionBase) -> None:
    session.pop(GUEST_CONTEXT_SESSION_KEY, None)
    session.modified = True
