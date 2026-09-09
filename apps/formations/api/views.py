from django.core.exceptions import ObjectDoesNotExist
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.formations.api.exceptions import (
    FormationCannotStart,
    ProjectReadinessConflict,
    ProjectRunConflict,
    SprintConflict,
)
from apps.formations.api.serializers import (
    EmptyActionInputSerializer,
    MyReadyCheckSerializer,
    OpenSprintInputSerializer,
    ProjectReadinessCandidateQuerySerializer,
    ProjectReadinessSerializer,
    ProjectRunDashboardSerializer,
    ProjectRunLifecycleSerializer,
    ProjectRunWorkspaceSerializer,
    ReadyCheckSerializer,
    ReplacementInputSerializer,
    SprintRunDetailSerializer,
    SprintRunSerializer,
    SprintSubmissionInputSerializer,
    TeamFormationInputSerializer,
    TeamFormationSerializer,
)
from apps.formations.exceptions import (
    ActiveProjectReadinessExists,
    FormationAlreadyReady,
    FormationCompletionConflict,
    InvalidFormationMembers,
    InvalidFormationReadiness,
    InvalidFormationStack,
    InvalidProjectReadinessSelection,
    MemberHasActiveProjectRun,
    MemberHasUnresolvedFormation,
    ProjectRunDeadlineNotReached,
    ProjectRunTransitionNotAllowed,
    ReadyCheckExpired,
    ReadyCheckNotPending,
    ReadyCheckNotReplaceable,
    SprintAccessDenied,
    SprintDeadlinePassed,
    SprintRuntimeConfigurationError,
    SprintTransitionNotAllowed,
)
from apps.formations.models import (
    ProjectReadiness,
    ProjectRun,
    ReadyCheck,
    SprintRun,
    TeamFormation,
)
from apps.formations.selectors import (
    active_project_readiness_candidates,
    active_project_readiness_for_user,
    active_project_run_for_user,
    active_sprint_run_for_user,
    current_ready_checks_for_user,
    formation_detail,
    formation_list,
    ready_check_detail,
)
from apps.formations.services import (
    confirm_ready_check,
    complete_sprint,
    create_project_readiness,
    create_team_formation,
    decline_ready_check,
    mark_project_run_incomplete,
    mark_sprint_under_review,
    open_sprint,
    replace_ready_check_member,
    request_sprint_changes,
    submit_sprint,
)
from apps.projects.api.exceptions import ProjectConfigurationUnavailable
from apps.projects.exceptions import ProjectConfigurationError
from apps.projects.models import ProjectVersion


@method_decorator(csrf_protect, name="dispatch")
class MyProjectReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            readiness = active_project_readiness_for_user(user=request.user)
        except ProjectReadiness.DoesNotExist as exc:
            raise NotFound("Active project readiness not found.") from exc
        return Response(ProjectReadinessSerializer(readiness).data)

    def post(self, request):
        serializer = EmptyActionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            readiness = create_project_readiness(
                user=request.user,
                session=request.session,
            )
        except InvalidProjectReadinessSelection as exc:
            raise ValidationError(
                {
                    "readiness": [
                        "A valid exact-version stack confirmation is required."
                    ]
                }
            ) from exc
        except ActiveProjectReadinessExists as exc:
            raise ProjectReadinessConflict(
                "The user already has an active project readiness."
            ) from exc
        except MemberHasUnresolvedFormation as exc:
            raise ProjectReadinessConflict(
                "The user is already in a current proposed formation."
            ) from exc
        except MemberHasActiveProjectRun as exc:
            raise ProjectReadinessConflict(
                "The user already has an active ProjectRun."
            ) from exc
        except ProjectConfigurationError as exc:
            raise ProjectConfigurationUnavailable from exc
        return Response(
            ProjectReadinessSerializer(
                active_project_readiness_for_user(user=readiness.user)
            ).data,
            status=status.HTTP_201_CREATED,
        )


def _formation_error(exc, *, readiness_field="readiness_ids"):
    if isinstance(exc, InvalidFormationReadiness):
        return ValidationError(
            {
                readiness_field: [
                    "Active readiness for the required exact ProjectVersion is required."
                ]
            }
        )
    if isinstance(exc, InvalidFormationMembers):
        return ValidationError(
            {
                readiness_field: [
                    "Readinesses must represent unique active users with the required roles."
                ]
            }
        )
    if isinstance(exc, InvalidFormationStack):
        return ValidationError(
            {
                readiness_field: [
                    "A readiness stack is not valid for its exact project role."
                ]
            }
        )
    if isinstance(exc, MemberHasUnresolvedFormation):
        return FormationCannotStart(
            "A selected user is already in a current proposed formation."
        )
    if isinstance(exc, MemberHasActiveProjectRun):
        return FormationCannotStart(
            "A selected user already has an active ProjectRun."
        )
    if isinstance(exc, ProjectConfigurationError):
        return ProjectConfigurationUnavailable()
    return None


class ProjectReadinessCandidateListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        serializer = ProjectReadinessCandidateQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        project_version_id = serializer.validated_data["project_version_id"]
        if not ProjectVersion.objects.filter(
            id=project_version_id,
            published_at__isnull=False,
        ).exists():
            raise NotFound("Published project version not found.")
        return Response(
            ProjectReadinessSerializer(
                active_project_readiness_candidates(
                    project_version_id=project_version_id
                ),
                many=True,
            ).data
        )


class TeamFormationListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(TeamFormationSerializer(formation_list(), many=True).data)

    def post(self, request):
        serializer = TeamFormationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            formation = create_team_formation(
                created_by=request.user,
                readiness_ids=serializer.validated_data["readiness_ids"],
            )
        except (
            InvalidFormationMembers,
            InvalidFormationReadiness,
            InvalidFormationStack,
            MemberHasActiveProjectRun,
            MemberHasUnresolvedFormation,
            ProjectConfigurationError,
        ) as exc:
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
                replacement_readiness_id=serializer.validated_data["readiness_id"],
                proposed_by=request.user,
            )
        except (ReadyCheck.DoesNotExist, TeamFormation.DoesNotExist) as exc:
            raise NotFound("Ready check not found.") from exc
        except (
            InvalidFormationMembers,
            InvalidFormationReadiness,
            InvalidFormationStack,
            MemberHasActiveProjectRun,
            MemberHasUnresolvedFormation,
            ProjectConfigurationError,
        ) as exc:
            raise _formation_error(exc, readiness_field="readiness_id") from exc
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
        except (
            FormationCompletionConflict,
            InvalidFormationMembers,
            SprintRuntimeConfigurationError,
        ) as exc:
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


class CurrentProjectRunMixin:
    def get_project_run(self, request):
        try:
            return active_project_run_for_user(user=request.user)
        except ProjectRun.DoesNotExist as exc:
            raise NotFound("Active project run not found.") from exc


class CurrentProjectRunDashboardView(CurrentProjectRunMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProjectRunDashboardSerializer(self.get_project_run(request)).data)


class CurrentProjectRunWorkspaceView(CurrentProjectRunMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProjectRunWorkspaceSerializer(self.get_project_run(request)).data)


class CurrentProjectRunSprintListView(CurrentProjectRunMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_run = self.get_project_run(request)
        return Response(SprintRunSerializer(project_run.sprint_runs.all(), many=True).data)


class CurrentProjectRunSprintDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, sprint_run_id):
        try:
            sprint_run = active_sprint_run_for_user(
                user=request.user,
                sprint_run_id=sprint_run_id,
            )
        except (ProjectRun.DoesNotExist, SprintRun.DoesNotExist) as exc:
            raise NotFound("Sprint not found.") from exc
        return Response(SprintRunDetailSerializer(sprint_run).data)


def _empty_action_data(request):
    serializer = EmptyActionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)


def _sprint_transition_error(exc):
    if isinstance(
        exc,
        (
            ProjectRunTransitionNotAllowed,
            SprintTransitionNotAllowed,
            SprintRuntimeConfigurationError,
        ),
    ):
        return SprintConflict()
    if isinstance(exc, SprintDeadlinePassed):
        return SprintConflict("The ProjectRun deadline has passed.")
    if isinstance(exc, SprintAccessDenied):
        return NotFound("Sprint not found.")
    return None


class OpenSprintView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, project_run_id, sprint_run_id):
        serializer = OpenSprintInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sprint_run = open_sprint(
                project_run_id=project_run_id,
                sprint_run_id=sprint_run_id,
                actor=request.user,
            )
        except (ProjectRun.DoesNotExist, SprintRun.DoesNotExist) as exc:
            raise NotFound("Sprint not found.") from exc
        except (
            SprintAccessDenied,
            SprintTransitionNotAllowed,
            SprintRuntimeConfigurationError,
        ) as exc:
            raise _sprint_transition_error(exc) from exc
        return Response(SprintRunSerializer(sprint_run).data)


class SubmitSprintView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_run_id, sprint_run_id):
        serializer = SprintSubmissionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sprint_run, _ = submit_sprint(
                project_run_id=project_run_id,
                sprint_run_id=sprint_run_id,
                user=request.user,
                evidence=serializer.validated_data["evidence"],
            )
        except (ProjectRun.DoesNotExist, SprintRun.DoesNotExist) as exc:
            raise NotFound("Sprint not found.") from exc
        except (
            SprintAccessDenied,
            SprintDeadlinePassed,
            SprintTransitionNotAllowed,
        ) as exc:
            raise _sprint_transition_error(exc) from exc
        return Response(SprintRunSerializer(sprint_run).data)


class StaffSprintTransitionView(APIView):
    permission_classes = [IsAdminUser]
    service = None

    def post(self, request, project_run_id, sprint_run_id):
        _empty_action_data(request)
        try:
            sprint_run = self.service(
                project_run_id=project_run_id,
                sprint_run_id=sprint_run_id,
                actor=request.user,
            )
        except (ProjectRun.DoesNotExist, SprintRun.DoesNotExist) as exc:
            raise NotFound("Sprint not found.") from exc
        except (
            ProjectRunTransitionNotAllowed,
            SprintAccessDenied,
            SprintRuntimeConfigurationError,
            SprintTransitionNotAllowed,
        ) as exc:
            raise _sprint_transition_error(exc) from exc
        return Response(SprintRunSerializer(sprint_run).data)


class MarkProjectRunIncompleteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, project_run_id):
        _empty_action_data(request)
        try:
            project_run = mark_project_run_incomplete(
                project_run_id=project_run_id,
                actor=request.user,
            )
        except ProjectRun.DoesNotExist as exc:
            raise NotFound("Project run not found.") from exc
        except ProjectRunDeadlineNotReached as exc:
            raise ProjectRunConflict(
                "An active ProjectRun can be marked incomplete only at or after its deadline."
            ) from exc
        except ProjectRunTransitionNotAllowed as exc:
            raise ProjectRunConflict() from exc
        return Response(ProjectRunLifecycleSerializer(project_run).data)


class MarkSprintUnderReviewView(StaffSprintTransitionView):
    service = staticmethod(mark_sprint_under_review)


class RequestSprintChangesView(StaffSprintTransitionView):
    service = staticmethod(request_sprint_changes)


class CompleteSprintView(StaffSprintTransitionView):
    service = staticmethod(complete_sprint)
