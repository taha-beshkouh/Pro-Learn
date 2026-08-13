import uuid

from django.db import models
from django.db.models import Q

from apps.profiles.models import Role, TechnologyStack


class Level(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(number__in=(1, 2, 3)),
                name="projects_level_known_number",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ProjectTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.ForeignKey(
        Level,
        on_delete=models.PROTECT,
        related_name="project_templates",
    )
    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["level__number", "name"]

    def __str__(self) -> str:
        return self.name


class ProjectVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    summary = models.TextField(blank=True)
    duration_weeks = models.PositiveSmallIntegerField(null=True, blank=True)
    sprint_count = models.PositiveSmallIntegerField(null=True, blank=True)
    weekly_effort_hours_min = models.PositiveSmallIntegerField(null=True, blank=True)
    weekly_effort_hours_max = models.PositiveSmallIntegerField(null=True, blank=True)
    participant_database = models.CharField(max_length=120, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["project_template_id", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_template", "version_number"],
                name="projects_version_template_number_unique",
            ),
            models.CheckConstraint(
                condition=Q(version_number__gte=1),
                name="projects_version_number_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(weekly_effort_hours_min__isnull=True)
                    | Q(weekly_effort_hours_max__isnull=True)
                    | Q(weekly_effort_hours_min__lte=models.F("weekly_effort_hours_max"))
                ),
                name="projects_version_effort_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["project_template", "published_at", "-version_number"],
                name="projects_version_public_idx",
            )
        ]

    @property
    def is_published(self) -> bool:
        return self.published_at is not None


class StackPolicy(models.TextChoices):
    FIXED = "FIXED", "Fixed"
    ALLOWLIST = "ALLOWLIST", "Allowlist"
    OPEN = "OPEN", "Open"


class ProjectRoleRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.CASCADE,
        related_name="role_requirements",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="project_requirements",
    )
    requires_stack = models.BooleanField(default=True)
    stack_policy = models.CharField(
        max_length=16,
        choices=StackPolicy.choices,
        null=True,
        blank=True,
    )
    context = models.TextField(blank=True)

    class Meta:
        ordering = ["role__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_version", "role"],
                name="projects_requirement_version_role_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(requires_stack=True, stack_policy__in=StackPolicy.values)
                    | Q(requires_stack=False, stack_policy__isnull=True)
                ),
                name="projects_requirement_stack_policy_valid",
            ),
        ]


class ProjectRoleAllowedStack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_requirement = models.ForeignKey(
        ProjectRoleRequirement,
        on_delete=models.CASCADE,
        related_name="allowed_stacks",
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="project_role_allowances",
    )

    class Meta:
        ordering = ["technology_stack__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["role_requirement", "technology_stack"],
                name="projects_allowed_stack_unique",
            )
        ]


class RolePrerequisite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_requirement = models.ForeignKey(
        ProjectRoleRequirement,
        on_delete=models.CASCADE,
        related_name="prerequisites",
    )
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["role_requirement", "position"],
                name="projects_prerequisite_position_unique",
            )
        ]


class SprintTemplate(models.Model):
    """Versioned sprint definition and relative project-run schedule data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.CASCADE,
        related_name="sprint_templates",
    )
    sequence = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=160)
    brief = models.TextField(blank=True)
    planned_start_offset_days = models.PositiveIntegerField()
    planned_duration_days = models.PositiveIntegerField()

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_version", "sequence"],
                name="projects_sprint_version_sequence_unique",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="projects_sprint_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(planned_duration_days__gte=1),
                name="projects_sprint_duration_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["project_version", "sequence"],
                name="projects_sprint_schedule_idx",
            )
        ]

    @property
    def planned_end_offset_days(self) -> int:
        return self.planned_start_offset_days + self.planned_duration_days

    def __str__(self) -> str:
        return f"{self.project_version_id}: {self.sequence} - {self.title}"

    def clean(self) -> None:
        super().clean()
        from apps.projects.services import validate_sprint_template

        validate_sprint_template(sprint_template=self)


class ProjectTaskTemplate(models.Model):
    """Static informational work content; it has no runtime lifecycle."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey(
        ProjectVersion,
        on_delete=models.CASCADE,
        related_name="work_items",
    )
    sprint_template = models.ForeignKey(
        SprintTemplate,
        on_delete=models.PROTECT,
        related_name="work_items",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="project_work_items",
        null=True,
        blank=True,
    )
    technology_stack = models.ForeignKey(
        TechnologyStack,
        on_delete=models.PROTECT,
        related_name="project_work_items",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project_version", "role", "technology_stack", "position"],
                nulls_distinct=False,
                name="projects_work_item_scope_position_unique",
            ),
            models.CheckConstraint(
                condition=Q(technology_stack__isnull=True) | Q(role__isnull=False),
                name="projects_work_item_stack_requires_role",
            ),
        ]
        indexes = [
            models.Index(
                fields=["project_version", "role", "technology_stack", "position"],
                name="projects_work_item_context_idx",
            ),
            models.Index(
                fields=["sprint_template", "position"],
                name="projects_work_item_sprint_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        from apps.projects.services import validate_work_item_sprint

        validate_work_item_sprint(work_item=self)
