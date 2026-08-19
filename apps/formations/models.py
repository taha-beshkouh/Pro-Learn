import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.profiles.models import Role, TechnologyStack
from apps.projects.models import ProjectVersion


READY_CHECK_DURATION = timedelta(hours=48)


class ReadyCheckStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"


class TeamFormation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.PROTECT,
        related_name="team_formations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_team_formations",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    ready_confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(
                fields=["project_version", "ready_confirmed_at"],
                name="formations_version_ready_idx",
            )
        ]


class Team(models.Model):
    """The durable team produced by one successfully confirmed formation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formation = models.OneToOneField(
        TeamFormation,
        on_delete=models.PROTECT,
        related_name="team",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at", "id"]


class ProjectRun(models.Model):
    """One team's execution of the exact ProjectVersion it confirmed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(
        Team,
        on_delete=models.PROTECT,
        related_name="project_run",
    )
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.PROTECT,
        related_name="project_runs",
    )
    started_at = models.DateTimeField(editable=False)
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-started_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="formations_run_end_after_start",
            )
        ]
        indexes = [
            models.Index(
                fields=["project_version", "ended_at", "started_at"],
                name="formations_run_ver_active_idx",
            )
        ]


class TeamMember(models.Model):
    """Immutable participation snapshots for a started ProjectRun."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_run = models.ForeignKey(
        ProjectRun,
        on_delete=models.PROTECT,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="team_memberships",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="historical_team_members",
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="historical_team_members",
        null=True,
        blank=True,
    )
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["role__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_run", "user"],
                name="formations_run_member_user_unique",
            ),
            models.UniqueConstraint(
                fields=["project_run", "role"],
                name="formations_run_member_role_unique",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(ended_at__isnull=True),
                name="formations_active_run_user_unique",
            ),
        ]


class ReadyCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formation = models.ForeignKey(
        TeamFormation,
        on_delete=models.CASCADE,
        related_name="ready_checks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ready_checks",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="ready_checks",
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="ready_checks",
        null=True,
        blank=True,
    )
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="proposed_ready_checks",
    )
    status = models.CharField(
        max_length=16,
        choices=ReadyCheckStatus.choices,
        default=ReadyCheckStatus.PENDING,
    )
    is_current = models.BooleanField(default=True)
    started_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField(editable=False)
    responded_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["formation_id", "role__name", "started_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["formation", "role"],
                condition=Q(is_current=True),
                name="formations_current_role_unique",
            ),
            models.UniqueConstraint(
                fields=["formation", "user"],
                condition=Q(is_current=True),
                name="formations_current_user_unique",
            ),
            models.CheckConstraint(
                condition=Q(status__in=ReadyCheckStatus.values),
                name="formations_ready_status_known",
            ),
            models.CheckConstraint(
                condition=Q(expires_at=F("started_at") + READY_CHECK_DURATION),
                name="formations_ready_expiry_48h",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=ReadyCheckStatus.PENDING, responded_at__isnull=True)
                    | Q(status=ReadyCheckStatus.EXPIRED, responded_at__isnull=True)
                    | Q(
                        status__in=(
                            ReadyCheckStatus.CONFIRMED,
                            ReadyCheckStatus.DECLINED,
                        ),
                        responded_at__isnull=False,
                    )
                ),
                name="formations_ready_response_coherent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_current", "status", "expires_at"],
                name="formations_user_ready_idx",
            )
        ]

    def effective_status(self, *, at=None) -> str:
        at = at or timezone.now()
        if self.status == ReadyCheckStatus.PENDING and at >= self.expires_at:
            return ReadyCheckStatus.EXPIRED
        return self.status
