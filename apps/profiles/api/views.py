from django.core.exceptions import ObjectDoesNotExist
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.formations.eligibility import ParticipationBlocker
from apps.profiles.api.serializers import (
    GuestContextUpdateSerializer,
    ProfileLinkInputSerializer,
    ProfileLinkSerializer,
    ProfileUpdateSerializer,
    RoleSelectionSerializer,
    RoleSerializer,
    TechnologyStackSerializer,
    UserProfileSerializer,
    UserSkillInputSerializer,
    UserSkillSerializer,
)
from apps.profiles.models import UserProfile
from apps.profiles.selectors import (
    link_for_user,
    profile_for_user,
    role_list,
    skill_for_user,
    technology_stack_list,
)
from apps.profiles.services import (
    ProfileLinkAlreadyRegistered,
    RoleChangeBlocked,
    SkillAlreadyRegistered,
    add_user_skill,
    clear_guest_context,
    create_profile_link,
    delete_profile_link,
    guest_context_from_session,
    remove_user_skill,
    select_profile_role,
    update_guest_context,
    update_profile,
    update_profile_link,
)
from apps.projects.services import clear_authenticated_stack_selection


ROLE_CHANGE_BLOCKER_MESSAGES = {
    ParticipationBlocker.ACTIVE_READINESS: (
        "An active project readiness prevents changing the role."
    ),
    ParticipationBlocker.CURRENT_FORMATION_OR_READY_CHECK: (
        "A current Formation or Ready Check prevents changing the role."
    ),
    ParticipationBlocker.ACTIVE_PROJECT_RUN: (
        "An active ProjectRun prevents changing the role."
    ),
}


def current_profile_or_404(user):
    try:
        return profile_for_user(user=user)
    except UserProfile.DoesNotExist as exc:
        raise NotFound("Profile not found.") from exc


class RoleListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(RoleSerializer(role_list(), many=True).data)


class TechnologyStackListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            TechnologyStackSerializer(technology_stack_list(), many=True).data
        )


class CurrentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(current_profile_or_404(request.user)).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = current_profile_or_404(request.user)
        update_profile(profile=profile, changes=serializer.validated_data)
        return Response(UserProfileSerializer(profile_for_user(user=request.user)).data)


class SelectRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoleSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = current_profile_or_404(request.user)
        previous_role_id = profile.selected_role_id
        try:
            selected_profile = select_profile_role(
                user=request.user,
                role=serializer.validated_data["role"],
            )
        except UserProfile.DoesNotExist as exc:
            raise NotFound("Profile not found.") from exc
        except RoleChangeBlocked as exc:
            return Response(
                {
                    "detail": ROLE_CHANGE_BLOCKER_MESSAGES[exc.reason],
                    "code": "role_change_blocked",
                    "reason": exc.reason.value,
                },
                status=status.HTTP_409_CONFLICT,
            )
        if previous_role_id != selected_profile.selected_role_id:
            clear_authenticated_stack_selection(session=request.session)
        return Response(UserProfileSerializer(profile_for_user(user=request.user)).data)


class ProfileLinkListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = current_profile_or_404(request.user)
        return Response(ProfileLinkSerializer(profile.links.all(), many=True).data)

    def post(self, request):
        serializer = ProfileLinkInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = current_profile_or_404(request.user)
        try:
            link = create_profile_link(profile=profile, data=serializer.validated_data)
        except ProfileLinkAlreadyRegistered as exc:
            raise ValidationError(
                {"url": ["This URL is already registered for the profile."]},
                code="unique",
            ) from exc
        return Response(ProfileLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class ProfileLinkDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, link_id):
        try:
            return link_for_user(user=request.user, link_id=link_id)
        except ObjectDoesNotExist as exc:
            raise NotFound("Profile link not found.") from exc

    def patch(self, request, link_id):
        serializer = ProfileLinkInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        link = self.get_object(request, link_id)
        try:
            update_profile_link(link=link, changes=serializer.validated_data)
        except ProfileLinkAlreadyRegistered as exc:
            raise ValidationError(
                {"url": ["This URL is already registered for the profile."]},
                code="unique",
            ) from exc
        return Response(ProfileLinkSerializer(link).data)

    def delete(self, request, link_id):
        delete_profile_link(link=self.get_object(request, link_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserSkillListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = current_profile_or_404(request.user)
        return Response(UserSkillSerializer(profile.skills.all(), many=True).data)

    def post(self, request):
        serializer = UserSkillInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = current_profile_or_404(request.user)
        try:
            skill = add_user_skill(
                profile=profile,
                technology_stack=serializer.validated_data["technology_stack"],
            )
        except SkillAlreadyRegistered as exc:
            raise ValidationError(
                {"technology_stack_id": ["This skill is already registered."]},
                code="unique",
            ) from exc
        return Response(UserSkillSerializer(skill).data, status=status.HTTP_201_CREATED)


class UserSkillDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, skill_id):
        try:
            skill = skill_for_user(user=request.user, skill_id=skill_id)
        except ObjectDoesNotExist as exc:
            raise NotFound("User skill not found.") from exc
        remove_user_skill(skill=skill)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class GuestContextView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(guest_context_from_session(session=request.session))

    def patch(self, request):
        serializer = GuestContextUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            update_guest_context(
                session=request.session,
                changes=serializer.validated_data,
            )
        )

    def delete(self, request):
        clear_guest_context(session=request.session)
        return Response(status=status.HTTP_204_NO_CONTENT)
