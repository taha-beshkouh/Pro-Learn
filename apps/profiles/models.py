import uuid

from django.conf import settings
from django.db import models

from apps.profiles.validators import validate_interests, validate_timezone_name


class RoleCode(models.TextChoices):
    BACKEND_DEVELOPER = "BACKEND_DEVELOPER", "Backend Developer"
    FRONTEND_DEVELOPER = "FRONTEND_DEVELOPER", "Frontend Developer"
    PRODUCT_DESIGNER = "PRODUCT_DESIGNER", "Product Designer"


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, choices=RoleCode.choices, unique=True)
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__in=RoleCode.values),
                name="profiles_role_known_code",
            )
        ]

    def __str__(self) -> str:
        return self.name


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=100, blank=True)
    selected_role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="profiles",
        null=True,
        blank=True,
    )
    timezone = models.CharField(
        max_length=64,
        blank=True,
        validators=[validate_timezone_name],
    )
    language = models.CharField(max_length=35, blank=True)
    interests = models.JSONField(default=list, blank=True, validators=[validate_interests])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self) -> str:
        return self.display_name or self.user.email


class ProfileLink(models.Model):
    class LinkType(models.TextChoices):
        PROFILE = "PROFILE", "Profile"
        PROJECT = "PROJECT", "Project"
        PORTFOLIO = "PORTFOLIO", "Portfolio"
        CASE_STUDY = "CASE_STUDY", "Case study"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="links",
    )
    link_type = models.CharField(max_length=16, choices=LinkType.choices)
    url = models.URLField(max_length=500)
    label = models.CharField(max_length=100, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "url"],
                name="profiles_link_profile_url_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["profile", "link_type", "position"],
                name="profiles_link_lookup_idx",
            )
        ]


class TechnologyStack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="user_skills",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["technology_stack__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "technology_stack"],
                name="profiles_skill_profile_stack_unique",
            )
        ]

