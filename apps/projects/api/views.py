from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.api.exceptions import ProjectConfigurationUnavailable
from apps.projects.api.serializers import (
    LevelSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectStackSelectionInputSerializer,
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
from apps.projects.services import select_project_stack


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
        selected_stack = selected_stack_for_request(
            request=request,
            project_id=project.id,
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


@method_decorator(csrf_protect, name="dispatch")
class ProjectStackSelectionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, project_id):
        serializer = ProjectStackSelectionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            project = project_template_detail(project_id=project_id)
        except ProjectTemplate.DoesNotExist as exc:
            raise NotFound("Project not found.") from exc
        if project.published_version_id is None:
            raise ValidationError(
                {"project_id": ["This project is not available for stack selection."]}
            )
        try:
            version = published_project_version(
                version_id=project.published_version_id
            )
        except ProjectVersion.DoesNotExist as exc:
            raise NotFound("Published project version not found.") from exc

        profile = profile_with_skills_for_request(request=request)
        if request.user.is_authenticated:
            role = profile.selected_role if profile is not None else None
        else:
            role = selected_role_for_request(request=request)
        if role is None:
            raise ValidationError(
                {"role": ["Select a platform role before selecting a stack."]}
            )

        try:
            selected_stack = select_project_stack(
                project_version=version,
                role=role,
                profile=profile,
                technology_stack=serializer.validated_data["technology_stack"],
                project_id=project.id,
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
                "selected_project_id": str(project.id),
                "selected_role_id": str(role.id),
                "selected_stack_id": str(selected_stack.id),
            }
        )
