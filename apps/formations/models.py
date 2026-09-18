import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.profiles.models import Role, TechnologyStack
from apps.projects.models import ProjectVersion, SprintTemplate


READY_CHECK_DURATION = timedelta(hours=48)


class ReadyCheckStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"


class SprintRunState(models.TextChoices):
    LOCKED = "LOCKED", "Locked"
    ACTIVE = "ACTIVE", "Active"
    SUBMITTED = "SUBMITTED", "Submitted"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
    COMPLETED = "COMPLETED", "Completed"


class ProjectRunState(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    INCOMPLETE = "INCOMPLETE", "Incomplete"


class ReviewDecisionType(models.TextChoices):
    CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
    COMPLETED = "COMPLETED", "Completed"


class ProjectReadiness(models.Model):
    """An authenticated user's active or historical pre-formation readiness."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_readinesses",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="project_readinesses",
    )
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.PROTECT,
        related_name="project_readinesses",
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="project_readinesses",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    consumed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(consumed_at__isnull=True),
                name="formations_active_readiness_user_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(consumed_at__isnull=True)
                    | Q(consumed_at__gte=F("created_at"))
                ),
                name="formations_readiness_consumed_after_created",
            ),
        ]


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
    state = models.CharField(
        max_length=10,
        choices=ProjectRunState.choices,
        default=ProjectRunState.ACTIVE,
    )
    started_at = models.DateTimeField(editable=False)
    deadline_at = models.DateTimeField(editable=False)
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)
    repository_url = models.URLField(max_length=500, null=True, blank=True)
    design_workspace_url = models.URLField(max_length=500, null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(state__in=ProjectRunState.values),
                name="formations_run_state_known",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state=ProjectRunState.ACTIVE, ended_at__isnull=True)
                    | Q(
                        state__in=(
                            ProjectRunState.COMPLETED,
                            ProjectRunState.INCOMPLETE,
                        ),
                        ended_at__isnull=False,
                    )
                ),
                name="formations_run_state_end_coherent",
            ),
            models.CheckConstraint(
                condition=Q(deadline_at__gt=F("started_at")),
                name="formations_run_deadline_after_start",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="formations_run_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["repository_url"],
                condition=Q(repository_url__isnull=False),
                name="formations_run_repository_unique",
            ),
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


class SprintRun(models.Model):
    """Runtime state and schedule snapshot for one project Sprint."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_run = models.ForeignKey(
        ProjectRun,
        on_delete=models.PROTECT,
        related_name="sprint_runs",
    )
    sprint_template = models.ForeignKey(
        SprintTemplate,
        on_delete=models.PROTECT,
        related_name="sprint_runs",
    )
    designated_submitter = models.ForeignKey(
        TeamMember,
        on_delete=models.PROTECT,
        related_name="designated_sprint_runs",
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=20,
        choices=SprintRunState.choices,
        default=SprintRunState.LOCKED,
    )
    planned_start_at = models.DateTimeField(editable=False)
    planned_end_at = models.DateTimeField(editable=False)
    opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sprint_template__sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_run", "sprint_template"],
                name="formations_run_sprint_template_unique",
            ),
            models.CheckConstraint(
                condition=Q(state__in=SprintRunState.values),
                name="formations_sprint_state_known",
            ),
            models.CheckConstraint(
                condition=Q(planned_end_at__gt=F("planned_start_at")),
                name="formations_sprint_schedule_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state=SprintRunState.LOCKED,
                        opened_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        state__in=(
                            SprintRunState.ACTIVE,
                            SprintRunState.SUBMITTED,
                            SprintRunState.UNDER_REVIEW,
                            SprintRunState.CHANGES_REQUESTED,
                        ),
                        opened_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        state=SprintRunState.COMPLETED,
                        opened_at__isnull=False,
                        completed_at__isnull=False,
                        completed_at__gte=F("opened_at"),
                    )
                ),
                name="formations_sprint_state_timestamps_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["project_run", "state", "planned_start_at"],
                name="formations_sprint_state_idx",
            )
        ]


class SprintSubmission(models.Model):
    """Append-only evidence history for Sprint submissions and resubmissions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sprint_run = models.ForeignKey(
        SprintRun,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    submitted_by = models.ForeignKey(
        TeamMember,
        on_delete=models.PROTECT,
        related_name="sprint_submissions",
    )
    final_commit_url = models.URLField(max_length=500, null=True, blank=True)
    deployment_url = models.URLField(max_length=500, null=True, blank=True)
    design_url_snapshot = models.URLField(max_length=500, null=True, blank=True)
    evidence = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["submitted_at", "id"]
        indexes = [
            models.Index(
                fields=["sprint_run", "submitted_at"],
                name="formations_submission_time_idx",
            )
        ]


class ReviewDecision(models.Model):
    """Append-only final Staff decision for one exact Sprint submission."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sprint_submission = models.OneToOneField(
        SprintSubmission,
        on_delete=models.PROTECT,
        related_name="review_decision",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sprint_review_decisions",
    )
    decision = models.CharField(
        max_length=20,
        choices=ReviewDecisionType.choices,
    )
    feedback = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["reviewed_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(decision__in=ReviewDecisionType.values),
                name="formations_review_decision_known",
            )
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
