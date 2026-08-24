from rest_framework.exceptions import APIException


class FormationCannotStart(APIException):
    status_code = 409
    default_detail = "The team cannot be started from this formation."
    default_code = "formation_cannot_start"


class SprintConflict(APIException):
    status_code = 409
    default_detail = "The Sprint cannot perform that transition."
    default_code = "sprint_transition_conflict"


class ProjectRunConflict(APIException):
    status_code = 409
    default_detail = "The ProjectRun cannot perform that transition."
    default_code = "project_run_transition_conflict"
