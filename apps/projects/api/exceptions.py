from rest_framework.exceptions import APIException


class ProjectConfigurationUnavailable(APIException):
    status_code = 503
    default_detail = "Project configuration is temporarily unavailable."
    default_code = "project_configuration_unavailable"

