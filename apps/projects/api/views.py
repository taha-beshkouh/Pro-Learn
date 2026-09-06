from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.services import guest_context_from_session
from apps.projects.api.exceptions import ProjectConfigurationUnavailable
from apps.projects.api.serializers import (
    LevelSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectStackSelectionInputSerializer,
    ProjectVersionDetailSerializer,
)
from apps.projects.models import ProjectTemplate, ProjectVersion
from apps.projects.exceptions import (
    InvalidProjectStackSelection,
    ProjectConfigurationError,
)
from apps.projects.selectors import (
    level_list,
    profile_with_skills_for_request,
    project_template_detail,
    project_template_list,
    published_project_version,
    selected_role_for_request,
    selected_stack_for_request,
)
from apps.projects.services import confirm_project_version_stack


class LevelListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(LevelSerializer(level_list(), many=True).data)


class ProjectListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raw_level = request.query_params.get("level")
        level_number = None
        if raw_level is not None:
            try:
                level_number = int(raw_level)
            except ValueError as exc:
                raise ValidationError({"level": ["Enter a valid level number."]}) from exc
            if level_number not in {1, 2, 3}:
                raise ValidationError({"level": ["Enter a level from 1 to 3."]})
        return Response(
            ProjectListSerializer(
                project_template_list(level_number=level_number), many=True
            ).data
        )


class ProjectDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, project_id):
        try:
            project = project_template_detail(project_id=project_id)
        except ProjectTemplate.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc

        version = None
        if project.published_version_id:
            try:
                version = published_project_version(
                    version_id=project.published_version_id
                )
            except ProjectVersion.DoesNotExist as exc:
                raise NotFound("Published project version not found.") from exc

        profile = profile_with_skills_for_request(request=request)
        if request.user.is_authenticated:
            selected_role = profile.selected_role if profile is not None else None
        else:
            selected_role = selected_role_for_request(request=request)
        selected_stack = (
            selected_stack_for_request(
                request=request,
                project_version_id=version.id,
            )
            if version is not None
            else None
        )
        try:
            data = ProjectDetailSerializer(
                project,
                context={
                    "published_version": version,
                    "selected_role": selected_role,
                    "selected_stack": selected_stack,
                    "profile": profile,
                },
            ).data
        except ProjectConfigurationError as exc:
            raise ProjectConfigurationUnavailable from exc
        return Response(data)


class ProjectVersionDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, project_version_id):
        try:
            version = published_project_version(version_id=project_version_id)
        except ProjectVersion.DoesNotExist as exc:
            raise NotFound("Published project version not found.") from exc

        profile = profile_with_skills_for_request(request=request)
        if request.user.is_authenticated:
            selected_role = profile.selected_role if profile is not None else None
        else:
            selected_role = selected_role_for_request(request=request)
        selected_stack = selected_stack_for_request(
            request=request,
            project_version_id=version.id,
        )
        try:
            data = ProjectVersionDetailSerializer(
                version,
                context={
                    "selected_role": selected_role,
                    "selected_stack": selected_stack,
                    "profile": profile,
                },
            ).data
        except ProjectConfigurationError as exc:
            raise ProjectConfigurationUnavailable from exc
        return Response(data)


@method_decorator(csrf_protect, name="dispatch")
class ProjectVersionStackSelectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_version_id):
        serializer = ProjectStackSelectionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = published_project_version(version_id=project_version_id)
        except ProjectVersion.DoesNotExist as exc:
            raise NotFound("Published project version not found.") from exc

        profile = profile_with_skills_for_request(request=request)
        if profile is None:
            raise NotFound("Profile not found.")
        role = profile.selected_role
        if role is None:
            raise ValidationError(
                {"role": ["Select a platform role before selecting a stack."]}
            )

        continuation = guest_context_from_session(session=request.session)
        guest_role_id = continuation.get("selected_role_id")
        if guest_role_id and guest_role_id != str(role.id):
            raise ValidationError(
                {
                    "role": [
                        "The continuation role does not match the authenticated profile role."
                    ]
                },
                code="role_conflict",
            )
        continued_version_id = continuation.get("project_version_id")
        if continued_version_id and continued_version_id != str(version.id):
            raise ValidationError(
                {
                    "project_version_id": [
                        "The requested version does not match the continued project version."
                    ]
                },
                code="project_version_conflict",
            )

        try:
            selected_stack = confirm_project_version_stack(
                project_version=version,
                profile=profile,
                technology_stack=serializer.validated_data.get("technology_stack"),
                session=request.session,
            )
        except InvalidProjectStackSelection as exc:
            raise ValidationError(
                {
                    "technology_stack_id": [
                        "This stack is not available for the selected project role."
                    ]
                }
            ) from exc
        except ProjectConfigurationError as exc:
            raise ProjectConfigurationUnavailable from exc

        return Response(
            {
                "project_version_id": str(version.id),
                "selected_role_id": str(role.id),
                "selected_stack_id": (
                    str(selected_stack.id) if selected_stack is not None else None
                ),
            }
        )
