from django.db import migrations, models
from django.db.models import F


SPRINT_RUN_FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION formations_sprint_run_validity_trigger()
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
    v_legacy_submitter_project_run_id uuid;
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
        SELECT project_run_id
          INTO v_legacy_submitter_project_run_id
          FROM formations_teammember
         WHERE id = NEW.designated_submitter_id;
        IF v_legacy_submitter_project_run_id IS DISTINCT FROM NEW.project_run_id THEN
            RAISE EXCEPTION 'Legacy Sprint designation must belong to its ProjectRun.'
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
"""


SPRINT_RUN_REVERSE_SQL = r"""
CREATE OR REPLACE FUNCTION formations_sprint_run_validity_trigger()
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
"""


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION formations_sprint_submission_insert_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_state varchar(20);
    v_opened_at timestamptz;
    v_project_run_id uuid;
    v_run_ended_at timestamptz;
    v_submitter_project_run_id uuid;
    v_submitter_ended_at timestamptz;
BEGIN
    SELECT sprint.state,
           sprint.opened_at,
           sprint.project_run_id,
           run.ended_at
      INTO v_state,
           v_opened_at,
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
"""


REVERSE_SQL = r"""
CREATE OR REPLACE FUNCTION formations_sprint_submission_insert_trigger()
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
"""


class Migration(migrations.Migration):
    dependencies = [("formations", "0008_projectreadiness")]

    operations = [
        migrations.RemoveConstraint(
            model_name="sprintrun",
            name="formations_sprint_state_timestamps_valid",
        ),
        migrations.AddConstraint(
            model_name="sprintrun",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        state="LOCKED",
                        opened_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        state__in=(
                            "ACTIVE",
                            "SUBMITTED",
                            "UNDER_REVIEW",
                            "CHANGES_REQUESTED",
                        ),
                        opened_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        state="COMPLETED",
                        opened_at__isnull=False,
                        completed_at__isnull=False,
                        completed_at__gte=F("opened_at"),
                    )
                ),
                name="formations_sprint_state_timestamps_valid",
            ),
        ),
        migrations.RunSQL(
            sql=SPRINT_RUN_FORWARD_SQL,
            reverse_sql=SPRINT_RUN_REVERSE_SQL,
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
