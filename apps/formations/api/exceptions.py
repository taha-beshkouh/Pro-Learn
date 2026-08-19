from rest_framework.exceptions import APIException


class FormationCannotStart(APIException):
    status_code = 409
    default_detail = "The team cannot be started from this formation."
    default_code = "formation_cannot_start"
