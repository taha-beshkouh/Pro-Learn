from rest_framework.permissions import BasePermission


class IsActiveAdminUser(BasePermission):
    """Require an authenticated, active Staff/Admin account."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
        )
