from django.db import migrations


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


class Migration(migrations.Migration):
    dependencies = [("formations", "0010_projectrun_repository_url")]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
