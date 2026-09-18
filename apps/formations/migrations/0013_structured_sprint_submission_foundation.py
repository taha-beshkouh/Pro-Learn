from django.db import migrations, models


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
    v_repository_url varchar(500);
    v_design_workspace_url varchar(500);
    v_submitter_project_run_id uuid;
    v_submitter_ended_at timestamptz;
BEGIN
    SELECT sprint.state,
           sprint.opened_at,
           sprint.project_run_id,
           run.ended_at,
           run.repository_url,
           run.design_workspace_url
      INTO v_state,
           v_opened_at,
           v_project_run_id,
           v_run_ended_at,
           v_repository_url,
           v_design_workspace_url
      FROM formations_sprintrun AS sprint
      JOIN formations_projectrun AS run ON run.id = sprint.project_run_id
     WHERE sprint.id = NEW.sprint_run_id;

    SELECT project_run_id, ended_at
      INTO v_submitter_project_run_id, v_submitter_ended_at
      FROM formations_teammember
     WHERE id = NEW.submitted_by_id;

    IF v_state NOT IN ('ACTIVE', 'SUBMITTED', 'CHANGES_REQUESTED')
       OR v_run_ended_at IS NOT NULL
       OR v_submitter_project_run_id IS DISTINCT FROM v_project_run_id
       OR v_submitter_ended_at IS NOT NULL
       OR NEW.submitted_at < v_opened_at
       OR NULLIF(BTRIM(v_repository_url), '') IS NULL
       OR NULLIF(BTRIM(v_design_workspace_url), '') IS NULL
       OR NULLIF(BTRIM(NEW.final_commit_url), '') IS NULL
       OR NULLIF(BTRIM(NEW.deployment_url), '') IS NULL
       OR NULLIF(BTRIM(NEW.design_url_snapshot), '') IS NULL
       OR NEW.design_url_snapshot IS DISTINCT FROM v_design_workspace_url
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

    IF v_state NOT IN ('ACTIVE', 'SUBMITTED', 'CHANGES_REQUESTED')
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


class Migration(migrations.Migration):
    dependencies = [("formations", "0012_projectrun_repository_unique")]

    operations = [
        migrations.AddField(
            model_name="projectrun",
            name="design_workspace_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="sprintsubmission",
            name="final_commit_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="sprintsubmission",
            name="deployment_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="sprintsubmission",
            name="design_url_snapshot",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
