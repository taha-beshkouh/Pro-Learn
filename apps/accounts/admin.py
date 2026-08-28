from django.contrib import admin

from apps.accounts.models import User


class ReadOnlyAdmin(admin.ModelAdmin):
    """Inspection-only admin surface for operational account data."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(ReadOnlyAdmin):
    list_display = (
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
        "last_login",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("email",)
    ordering = ("email",)
    date_hierarchy = "date_joined"
    fields = (
        "id",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
        "last_login",
    )
