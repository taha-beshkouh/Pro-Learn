from django.contrib import admin

from apps.profiles.models import (
    ProfileLink,
    Role,
    RoleTechnologyStack,
    TechnologyStack,
    UserProfile,
    UserSkill,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Profiles are inspected here; participant services remain the write path."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(ReadOnlyAdmin):
    list_display = ("name", "code", "id")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(TechnologyStack)
class TechnologyStackAdmin(ReadOnlyAdmin):
    list_display = ("name", "code", "id")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(UserProfile)
class UserProfileAdmin(ReadOnlyAdmin):
    list_display = (
        "user",
        "display_name",
        "github_username",
        "selected_role",
        "timezone",
        "language",
        "updated_at",
    )
    list_filter = ("selected_role", "language", "created_at")
    search_fields = ("user__email", "display_name", "github_username")
    list_select_related = ("user", "selected_role")
    ordering = ("user__email",)
    date_hierarchy = "created_at"


@admin.register(ProfileLink)
class ProfileLinkAdmin(ReadOnlyAdmin):
    list_display = ("profile", "link_type", "label", "url", "position")
    list_filter = ("link_type", "created_at")
    search_fields = ("profile__user__email", "label", "url")
    list_select_related = ("profile", "profile__user")
    ordering = ("profile__user__email", "position", "id")


@admin.register(RoleTechnologyStack)
class RoleTechnologyStackAdmin(ReadOnlyAdmin):
    list_display = ("role", "technology_stack", "id")
    list_filter = ("role", "technology_stack")
    search_fields = ("role__name", "role__code", "technology_stack__name")
    list_select_related = ("role", "technology_stack")
    ordering = ("role__name", "technology_stack__name")


@admin.register(UserSkill)
class UserSkillAdmin(ReadOnlyAdmin):
    list_display = ("profile", "technology_stack", "created_at", "id")
    list_filter = ("technology_stack", "created_at")
    search_fields = ("profile__user__email", "technology_stack__name")
    list_select_related = ("profile", "profile__user", "technology_stack")
    ordering = ("profile__user__email", "technology_stack__name")
    date_hierarchy = "created_at"
