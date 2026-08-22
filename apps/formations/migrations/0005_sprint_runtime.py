import datetime
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


FORWARD_SQL = r"""
CREATE FUNCTION formations_sprint_run_validity_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_project_version_id uuid;
    v_run_started_at timestamptz;
    v_run_ended_at timestamptz;
    v_template_project_version_id uuid;
    v_template_sequence smallint;
    v_start_offset integer;
    v_duration integer;
    v_submitter_project_run_id uuid;
    v_submitter_ended_at timestamptz;
BEGIN
    SELECT project_version_id, started_at, ended_at
      INTO v_run_project_version_id, v_run_started_at, v_run_ended_at
      FROM formations_projectrun
     WHERE id = NEW.project_run_id;

    SELECT project_version_id,
           sequence,
           planned_start_offset_days,
           planned_duration_days
      INTO v_template_project_version_id,
           v_template_sequence,
           v_start_offset,
           v_duration
      FROM projects_sprinttemplate
     WHERE id = NEW.sprint_template_id;

    IF v_run_project_version_id IS DISTINCT FROM v_template_project_version_id
       OR NEW.planned_start_at IS DISTINCT FROM (
           v_run_started_at + v_start_offset * INTERVAL '1 day'
       )
       OR NEW.planned_end_at IS DISTINCT FROM (
           v_run_started_at + (v_start_offset + v_duration) * INTERVAL '1 day'
       )
    THEN
        RAISE EXCEPTION 'Sprint runtime must match its ProjectRun schedule.'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.designated_submitter_id IS NOT NULL THEN
        SELECT project_run_id, ended_at
          INTO v_submitter_project_run_id, v_submitter_ended_at
          FROM formations_teammember
         WHERE id = NEW.designated_submitter_id;
        IF v_submitter_project_run_id IS DISTINCT FROM NEW.project_run_id
           OR v_submitter_ended_at IS NOT NULL
        THEN
            RAISE EXCEPTION 'Sprint submitter must be a current member of its ProjectRun.'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'LOCKED'
           OR NEW.designated_submitter_id IS NOT NULL
           OR NEW.opened_at IS NOT NULL
           OR NEW.completed_at IS NOT NULL
        THEN
            RAISE EXCEPTION 'A new Sprint runtime must be locked.'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.project_run_id IS DISTINCT FROM OLD.project_run_id
           OR NEW.sprint_template_id IS DISTINCT FROM OLD.sprint_template_id
           OR NEW.planned_start_at IS DISTINCT FROM OLD.planned_start_at
           OR NEW.planned_end_at IS DISTINCT FROM OLD.planned_end_at
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
        THEN
            RAISE EXCEPTION 'Sprint runtime identity and schedule are immutable.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.state IS DISTINCT FROM OLD.state
           AND NOT (
               (OLD.state = 'LOCKED' AND NEW.state = 'ACTIVE')
               OR (OLD.state = 'ACTIVE' AND NEW.state = 'SUBMITTED')
               OR (OLD.state = 'SUBMITTED' AND NEW.state = 'UNDER_REVIEW')
               OR (
                   OLD.state = 'UNDER_REVIEW'
                   AND NEW.state IN ('CHANGES_REQUESTED', 'COMPLETED')
               )
               OR (OLD.state = 'CHANGES_REQUESTED' AND NEW.state = 'SUBMITTED')
           )
        THEN
            RAISE EXCEPTION 'Invalid Sprint runtime state transition.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.designated_submitter_id IS DISTINCT FROM OLD.designated_submitter_id
           AND NOT (OLD.state = 'LOCKED' AND NEW.state = 'ACTIVE')
        THEN
            RAISE EXCEPTION 'Sprint submitter designation is immutable after opening.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.opened_at IS DISTINCT FROM OLD.opened_at
           AND NOT (OLD.state = 'LOCKED' AND NEW.state = 'ACTIVE')
        THEN
            RAISE EXCEPTION 'Sprint opening timestamp is immutable.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.completed_at IS DISTINCT FROM OLD.completed_at
           AND NOT (OLD.state = 'UNDER_REVIEW' AND NEW.state = 'COMPLETED')
        THEN
            RAISE EXCEPTION 'Sprint completion timestamp is immutable.'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF NEW.state <> 'LOCKED' AND EXISTS (
        SELECT 1
          FROM formations_sprintrun AS prior
          JOIN projects_sprinttemplate AS prior_template
            ON prior_template.id = prior.sprint_template_id
         WHERE prior.project_run_id = NEW.project_run_id
           AND prior_template.sequence < v_template_sequence
           AND prior.state <> 'COMPLETED'
    ) THEN
        RAISE EXCEPTION 'Earlier Sprints must be completed first.'
            USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'UPDATE'
       AND v_run_ended_at IS NOT NULL
       AND NEW.state IS DISTINCT FROM OLD.state THEN
        RAISE EXCEPTION 'An ended ProjectRun cannot transition Sprints.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_sprint_run_validity_constraint
BEFORE INSERT OR UPDATE ON formations_sprintrun
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_run_validity_trigger();

CREATE FUNCTION formations_sprint_submission_insert_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_state varchar(20);
    v_opened_at timestamptz;
    v_designated_submitter_id uuid;
    v_project_run_id uuid;
    v_run_ended_at timestamptz;
    v_submitter_project_run_id uuid;
    v_submitter_ended_at timestamptz;
BEGIN
    SELECT sprint.state,
           sprint.opened_at,
           sprint.designated_submitter_id,
           sprint.project_run_id,
           run.ended_at
      INTO v_state,
           v_opened_at,
           v_designated_submitter_id,
           v_project_run_id,
           v_run_ended_at
      FROM formations_sprintrun AS sprint
      JOIN formations_projectrun AS run ON run.id = sprint.project_run_id
     WHERE sprint.id = NEW.sprint_run_id;

    SELECT project_run_id, ended_at
      INTO v_submitter_project_run_id, v_submitter_ended_at
      FROM formations_teammember
     WHERE id = NEW.submitted_by_id;

    IF v_state NOT IN ('ACTIVE', 'CHANGES_REQUESTED')
       OR v_run_ended_at IS NOT NULL
       OR NEW.submitted_by_id IS DISTINCT FROM v_designated_submitter_id
       OR v_submitter_project_run_id IS DISTINCT FROM v_project_run_id
       OR v_submitter_ended_at IS NOT NULL
       OR NEW.submitted_at < v_opened_at
    THEN
        RAISE EXCEPTION 'Invalid Sprint submission.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_sprint_submission_insert_constraint
BEFORE INSERT ON formations_sprintsubmission
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_submission_insert_trigger();

CREATE FUNCTION formations_sprint_submission_immutable_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Sprint submission history is append-only.'
        USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER formations_sprint_submission_immutable_constraint
BEFORE UPDATE OR DELETE ON formations_sprintsubmission
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_submission_immutable_trigger();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_sprint_submission_immutable_constraint
    ON formations_sprintsubmission;
DROP TRIGGER IF EXISTS formations_sprint_submission_insert_constraint
    ON formations_sprintsubmission;
DROP TRIGGER IF EXISTS formations_sprint_run_validity_constraint
    ON formations_sprintrun;

DROP FUNCTION IF EXISTS formations_sprint_submission_immutable_trigger();
DROP FUNCTION IF EXISTS formations_sprint_submission_insert_trigger();
DROP FUNCTION IF EXISTS formations_sprint_run_validity_trigger();
"""


def backfill_sprint_runs(apps, schema_editor):
    ProjectRun = apps.get_model("formations", "ProjectRun")
    SprintRun = apps.get_model("formations", "SprintRun")
    SprintTemplate = apps.get_model("projects", "SprintTemplate")
    database_alias = schema_editor.connection.alias

    for project_run in ProjectRun.objects.using(database_alias).order_by("id").iterator():
        sprint_templates = SprintTemplate.objects.using(database_alias).filter(
            project_version_id=project_run.project_version_id
        ).order_by("sequence", "id")
        SprintRun.objects.using(database_alias).bulk_create(
            [
                SprintRun(
                    project_run_id=project_run.id,
                    sprint_template_id=sprint_template.id,
                    state="LOCKED",
                    planned_start_at=(
                        project_run.started_at
                        + datetime.timedelta(
                            days=sprint_template.planned_start_offset_days
                        )
                    ),
                    planned_end_at=(
                        project_run.started_at
                        + datetime.timedelta(
                            days=(
                                sprint_template.planned_start_offset_days
                                + sprint_template.planned_duration_days
                            )
                        )
                    ),
                )
                for sprint_template in sprint_templates
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0004_preserve_ready_check_history"),
        ("projects", "0004_project_definition_integrity_triggers"),
    ]

    operations = [
        migrations.CreateModel(
            name="SprintRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("LOCKED", "Locked"),
                            ("ACTIVE", "Active"),
                            ("SUBMITTED", "Submitted"),
                            ("UNDER_REVIEW", "Under review"),
                            ("CHANGES_REQUESTED", "Changes requested"),
                            ("COMPLETED", "Completed"),
                        ],
                        default="LOCKED",
                        max_length=20,
                    ),
                ),
                ("planned_start_at", models.DateTimeField(editable=False)),
                ("planned_end_at", models.DateTimeField(editable=False)),
                (
                    "opened_at",
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "designated_submitter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="designated_sprint_runs",
                        to="formations.teammember",
                    ),
                ),
                (
                    "project_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sprint_runs",
                        to="formations.projectrun",
                    ),
                ),
                (
                    "sprint_template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sprint_runs",
                        to="projects.sprinttemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["sprint_template__sequence", "id"],
                "indexes": [
                    models.Index(
                        fields=["project_run", "state", "planned_start_at"],
                        name="formations_sprint_state_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("project_run", "sprint_template"),
                        name="formations_run_sprint_template_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "state__in",
                                [
                                    "LOCKED",
                                    "ACTIVE",
                                    "SUBMITTED",
                                    "UNDER_REVIEW",
                                    "CHANGES_REQUESTED",
                                    "COMPLETED",
                                ],
                            )
                        ),
                        name="formations_sprint_state_known",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("planned_end_at__gt", models.F("planned_start_at"))
                        ),
                        name="formations_sprint_schedule_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("completed_at__isnull", True),
                                ("designated_submitter__isnull", True),
                                ("opened_at__isnull", True),
                                ("state", "LOCKED"),
                            ),
                            models.Q(
                                ("completed_at__isnull", True),
                                ("designated_submitter__isnull", False),
                                ("opened_at__isnull", False),
                                (
                                    "state__in",
                                    (
                                        "ACTIVE",
                                        "SUBMITTED",
                                        "UNDER_REVIEW",
                                        "CHANGES_REQUESTED",
                                    ),
                                ),
                            ),
                            models.Q(
                                ("completed_at__gte", models.F("opened_at")),
                                ("completed_at__isnull", False),
                                ("designated_submitter__isnull", False),
                                ("opened_at__isnull", False),
                                ("state", "COMPLETED"),
                            ),
                            _connector="OR",
                        ),
                        name="formations_sprint_state_timestamps_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SprintSubmission",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("evidence", models.TextField(blank=True)),
                (
                    "submitted_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                    ),
                ),
                (
                    "sprint_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="submissions",
                        to="formations.sprintrun",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sprint_submissions",
                        to="formations.teammember",
                    ),
                ),
            ],
            options={
                "ordering": ["submitted_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["sprint_run", "submitted_at"],
                        name="formations_submission_time_idx",
                    )
                ],
            },
        ),
        migrations.RunPython(
            backfill_sprint_runs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
