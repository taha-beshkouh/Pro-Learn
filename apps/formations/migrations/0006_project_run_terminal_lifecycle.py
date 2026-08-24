import datetime

from django.db import migrations, models
from django.db.models import F, Q


FORWARD_SQL = r"""
CREATE FUNCTION formations_project_run_lifecycle_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_duration_weeks smallint;
    v_final_sprint_state varchar(20);
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT duration_weeks
          INTO v_duration_weeks
          FROM projects_projectversion
         WHERE id = NEW.project_version_id;

        IF v_duration_weeks IS NULL
           OR v_duration_weeks < 1
           OR NEW.deadline_at IS DISTINCT FROM (
               NEW.started_at + v_duration_weeks * INTERVAL '7 days'
           )
        THEN
            RAISE EXCEPTION 'ProjectRun deadline must match its fixed ProjectVersion duration.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.state <> 'ACTIVE' OR NEW.ended_at IS NOT NULL THEN
            RAISE EXCEPTION 'A new ProjectRun must be active.'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.team_id IS DISTINCT FROM OLD.team_id
           OR NEW.project_version_id IS DISTINCT FROM OLD.project_version_id
           OR NEW.started_at IS DISTINCT FROM OLD.started_at
           OR NEW.deadline_at IS DISTINCT FROM OLD.deadline_at
        THEN
            RAISE EXCEPTION 'ProjectRun identity and deadline are immutable.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.state IS DISTINCT FROM OLD.state
           AND NOT (
               OLD.state = 'ACTIVE'
               AND NEW.state IN ('COMPLETED', 'INCOMPLETE')
           )
        THEN
            RAISE EXCEPTION 'Invalid ProjectRun state transition.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.state IS NOT DISTINCT FROM OLD.state
           AND NEW.ended_at IS DISTINCT FROM OLD.ended_at
        THEN
            RAISE EXCEPTION 'ProjectRun end time changes only with a terminal transition.'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF (NEW.state = 'ACTIVE' AND NEW.ended_at IS NOT NULL)
       OR (NEW.state IN ('COMPLETED', 'INCOMPLETE') AND NEW.ended_at IS NULL)
    THEN
        RAISE EXCEPTION 'ProjectRun state and end time are incompatible.'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.state = 'INCOMPLETE'
       AND (
           NEW.ended_at < NEW.deadline_at
           OR clock_timestamp() < NEW.deadline_at
       )
    THEN
        RAISE EXCEPTION 'ProjectRun cannot be incomplete before its deadline.'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.state IN ('COMPLETED', 'INCOMPLETE') THEN
        SELECT sprint.state
          INTO v_final_sprint_state
          FROM formations_sprintrun AS sprint
          JOIN projects_sprinttemplate AS template
            ON template.id = sprint.sprint_template_id
         WHERE sprint.project_run_id = NEW.id
         ORDER BY template.sequence DESC, template.id DESC
         LIMIT 1;

        IF NEW.state = 'COMPLETED'
           AND v_final_sprint_state IS DISTINCT FROM 'COMPLETED'
        THEN
            RAISE EXCEPTION 'Completed ProjectRun requires its final Sprint to be completed.'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.state = 'INCOMPLETE' AND v_final_sprint_state = 'COMPLETED' THEN
            RAISE EXCEPTION 'A ProjectRun with a completed final Sprint cannot be incomplete.'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_project_run_lifecycle_constraint
BEFORE INSERT OR UPDATE ON formations_projectrun
FOR EACH ROW
EXECUTE FUNCTION formations_project_run_lifecycle_trigger();

CREATE FUNCTION formations_active_run_sprint_transition_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_state varchar(10);
BEGIN
    SELECT state
      INTO v_run_state
      FROM formations_projectrun
     WHERE id = OLD.project_run_id;

    IF v_run_state IS DISTINCT FROM 'ACTIVE'
       AND (TG_OP = 'DELETE' OR NEW.state IS DISTINCT FROM OLD.state)
    THEN
        RAISE EXCEPTION 'A terminal ProjectRun cannot change Sprint history.'
            USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_active_run_sprint_transition_constraint
BEFORE UPDATE OR DELETE ON formations_sprintrun
FOR EACH ROW
EXECUTE FUNCTION formations_active_run_sprint_transition_trigger();

CREATE FUNCTION formations_submission_deadline_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_state varchar(10);
    v_deadline_at timestamptz;
BEGIN
    SELECT run.state, run.deadline_at
      INTO v_run_state, v_deadline_at
      FROM formations_sprintrun AS sprint
      JOIN formations_projectrun AS run ON run.id = sprint.project_run_id
     WHERE sprint.id = NEW.sprint_run_id;

    IF v_run_state IS DISTINCT FROM 'ACTIVE'
       OR clock_timestamp() >= v_deadline_at
       OR NEW.submitted_at >= v_deadline_at
    THEN
        RAISE EXCEPTION 'Sprint submissions are closed for this ProjectRun.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_submission_deadline_constraint
BEFORE INSERT ON formations_sprintsubmission
FOR EACH ROW
EXECUTE FUNCTION formations_submission_deadline_trigger();

CREATE FUNCTION formations_final_sprint_completion_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_project_run_id uuid;
    v_run_state varchar(10);
    v_final_sprint_state varchar(20);
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_project_run_id := OLD.project_run_id;
    ELSE
        v_project_run_id := NEW.project_run_id;
    END IF;

    SELECT state
      INTO v_run_state
      FROM formations_projectrun
     WHERE id = v_project_run_id;

    SELECT sprint.state
      INTO v_final_sprint_state
      FROM formations_sprintrun AS sprint
      JOIN projects_sprinttemplate AS template
        ON template.id = sprint.sprint_template_id
     WHERE sprint.project_run_id = v_project_run_id
     ORDER BY template.sequence DESC, template.id DESC
     LIMIT 1;

    IF (v_final_sprint_state = 'COMPLETED' AND v_run_state <> 'COMPLETED')
       OR (v_run_state = 'COMPLETED' AND v_final_sprint_state IS DISTINCT FROM 'COMPLETED')
    THEN
        RAISE EXCEPTION 'Final Sprint and ProjectRun completion must be atomic.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_final_sprint_completion_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_sprintrun
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_final_sprint_completion_trigger();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_final_sprint_completion_constraint
    ON formations_sprintrun;
DROP TRIGGER IF EXISTS formations_submission_deadline_constraint
    ON formations_sprintsubmission;
DROP TRIGGER IF EXISTS formations_active_run_sprint_transition_constraint
    ON formations_sprintrun;
DROP TRIGGER IF EXISTS formations_project_run_lifecycle_constraint
    ON formations_projectrun;

DROP FUNCTION IF EXISTS formations_final_sprint_completion_trigger();
DROP FUNCTION IF EXISTS formations_submission_deadline_trigger();
DROP FUNCTION IF EXISTS formations_active_run_sprint_transition_trigger();
DROP FUNCTION IF EXISTS formations_project_run_lifecycle_trigger();
"""


def backfill_project_run_lifecycle(apps, schema_editor):
    ProjectRun = apps.get_model("formations", "ProjectRun")
    SprintRun = apps.get_model("formations", "SprintRun")
    SprintTemplate = apps.get_model("projects", "SprintTemplate")
    database_alias = schema_editor.connection.alias

    for project_run in (
        ProjectRun.objects.using(database_alias)
        .select_related("project_version")
        .order_by("id")
        .iterator()
    ):
        duration_weeks = project_run.project_version.duration_weeks
        if not duration_weeks:
            raise RuntimeError(
                "Cannot backfill a ProjectRun whose ProjectVersion has no duration."
            )
        deadline_at = project_run.started_at + datetime.timedelta(
            weeks=duration_weeks
        )
        state = "ACTIVE"
        if project_run.ended_at is not None:
            final_template = (
                SprintTemplate.objects.using(database_alias)
                .filter(project_version_id=project_run.project_version_id)
                .order_by("-sequence", "-id")
                .first()
            )
            final_completed = bool(
                final_template
                and SprintRun.objects.using(database_alias).filter(
                    project_run_id=project_run.id,
                    sprint_template_id=final_template.id,
                    state="COMPLETED",
                ).exists()
            )
            if final_completed:
                state = "COMPLETED"
            elif project_run.ended_at >= deadline_at:
                state = "INCOMPLETE"
            else:
                raise RuntimeError(
                    "Cannot infer a valid terminal state for an ended ProjectRun."
                )
        ProjectRun.objects.using(database_alias).filter(id=project_run.id).update(
            state=state,
            deadline_at=deadline_at,
        )


class Migration(migrations.Migration):
    dependencies = [("formations", "0005_sprint_runtime")]

    operations = [
        migrations.AddField(
            model_name="projectrun",
            name="state",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Active"),
                    ("COMPLETED", "Completed"),
                    ("INCOMPLETE", "Incomplete"),
                ],
                default="ACTIVE",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="projectrun",
            name="deadline_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.RunPython(
            backfill_project_run_lifecycle,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="projectrun",
            name="deadline_at",
            field=models.DateTimeField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="projectrun",
            constraint=models.CheckConstraint(
                condition=Q(state__in=["ACTIVE", "COMPLETED", "INCOMPLETE"]),
                name="formations_run_state_known",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectrun",
            constraint=models.CheckConstraint(
                condition=(
                    Q(state="ACTIVE", ended_at__isnull=True)
                    | Q(
                        state__in=("COMPLETED", "INCOMPLETE"),
                        ended_at__isnull=False,
                    )
                ),
                name="formations_run_state_end_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectrun",
            constraint=models.CheckConstraint(
                condition=Q(deadline_at__gt=F("started_at")),
                name="formations_run_deadline_after_start",
            ),
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
