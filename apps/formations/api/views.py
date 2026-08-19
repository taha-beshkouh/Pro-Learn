from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.formations.api.exceptions import FormationCannotStart
from apps.formations.api.serializers import (
    MyReadyCheckSerializer,
    ReadyCheckSerializer,
    ReplacementInputSerializer,
    TeamFormationInputSerializer,
    TeamFormationSerializer,
)
from apps.formations.exceptions import (
    FormationAlreadyReady,
    FormationCompletionConflict,
    InvalidFormationMembers,
    InvalidFormationStack,
    MemberHasActiveProjectRun,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
)
from apps.formations.models import ReadyCheck, TeamFormation
from apps.formations.selectors import (
    current_ready_checks_for_user,
    formation_detail,
    formation_list,
    ready_check_detail,
)
from apps.formations.services import (
    ProposedMember,
    confirm_ready_check,
    create_team_formation,
    decline_ready_check,
    replace_ready_check_member,
)
from apps.projects.exceptions import ProjectConfigurationError
from apps.projects.api.exceptions import ProjectConfigurationUnavailable


def _formation_error(exc):
    if isinstance(exc, InvalidFormationMembers):
        return ValidationError(
            {"members": ["Members must be three unique active users with the required roles."]}
        )
    if isinstance(exc, InvalidFormationStack):
        return ValidationError(
            {"technology_stack_id": ["The selected stack is not valid for this project role."]}
        )
    if isinstance(exc, ProjectConfigurationError):
        return ProjectConfigurationUnavailable()
    return None


class TeamFormationListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(TeamFormationSerializer(formation_list(), many=True).data)

    def post(self, request):
        serializer = TeamFormationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        members = [ProposedMember(**member) for member in serializer.validated_data["members"]]
        try:
            formation = create_team_formation(
                project_version=serializer.validated_data["project_version"],
                created_by=request.user,
                members=members,
            )
        except (InvalidFormationMembers, InvalidFormationStack, ProjectConfigurationError) as exc:
            raise _formation_error(exc) from exc
        return Response(
            TeamFormationSerializer(formation_detail(formation_id=formation.id)).data,
            status=status.HTTP_201_CREATED,
        )


class TeamFormationDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, formation_id):
        try:
            formation = formation_detail(formation_id=formation_id)
        except ObjectDoesNotExist as exc:
            raise NotFound("Team formation not found.") from exc
        return Response(TeamFormationSerializer(formation).data)


class ReplaceReadyCheckView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, formation_id, ready_check_id):
        serializer = ReplacementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            replacement = replace_ready_check_member(
                formation_id=formation_id,
                ready_check_id=ready_check_id,
                replacement_user=serializer.validated_data["user"],
                technology_stack=serializer.validated_data.get("technology_stack"),
                proposed_by=request.user,
            )
        except (ReadyCheck.DoesNotExist, TeamFormation.DoesNotExist) as exc:
            raise NotFound("Ready check not found.") from exc
        except (InvalidFormationMembers, InvalidFormationStack, ProjectConfigurationError) as exc:
            raise _formation_error(exc) from exc
        except ReadyCheckNotReplaceable as exc:
            raise ValidationError(
                {"ready_check": ["Only a declined or expired slot can be replaced."]}
            ) from exc
        except FormationAlreadyReady as exc:
            raise ValidationError(
                {"formation": ["A fully confirmed formation cannot be replaced."]}
            ) from exc
        return Response(
            ReadyCheckSerializer(ready_check_detail(ready_check_id=replacement.id)).data,
            status=status.HTTP_201_CREATED,
        )


class MyReadyCheckListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            MyReadyCheckSerializer(
                current_ready_checks_for_user(user=request.user), many=True
            ).data
        )


class ReadyCheckResponseView(APIView):
    permission_classes = [IsAuthenticated]
    action = None

    def post(self, request, ready_check_id):
        service = confirm_ready_check if self.action == "confirm" else decline_ready_check
        try:
            ready_check = service(ready_check_id=ready_check_id, user=request.user)
        except ReadyCheck.DoesNotExist as exc:
            raise NotFound("Ready check not found.") from exc
        except ReadyCheckExpired as exc:
            raise ValidationError(
                {"ready_check": ["This Ready Check has expired."]}
            ) from exc
        except ReadyCheckNotPending as exc:
            raise ValidationError(
                {"ready_check": ["This Ready Check is no longer pending."]}
            ) from exc
        except MemberHasActiveProjectRun as exc:
            raise ValidationError(
                {
                    "ready_check": [
                        "A proposed member already has an active project run."
                    ]
                }
            ) from exc
        except (FormationCompletionConflict, InvalidFormationMembers) as exc:
            raise FormationCannotStart() from exc
        return Response(
            MyReadyCheckSerializer(
                ready_check_detail(ready_check_id=ready_check.id)
            ).data
        )


class ConfirmReadyCheckView(ReadyCheckResponseView):
    action = "confirm"


class DeclineReadyCheckView(ReadyCheckResponseView):
    action = "decline"
