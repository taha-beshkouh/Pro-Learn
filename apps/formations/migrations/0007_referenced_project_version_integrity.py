from django.db import migrations


FORWARD_SQL = r"""
CREATE FUNCTION projects_assert_version_unreferenced(p_project_version_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_project_version_id IS NULL THEN
        RETURN;
    END IF;

    PERFORM id
      FROM projects_projectversion
     WHERE id = p_project_version_id
     FOR UPDATE;

    IF EXISTS (
        SELECT 1
          FROM formations_teamformation
         WHERE project_version_id = p_project_version_id
    ) OR EXISTS (
        SELECT 1
          FROM formations_projectrun
         WHERE project_version_id = p_project_version_id
    ) THEN
        RAISE EXCEPTION 'A formation-referenced ProjectVersion definition is immutable.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION formations_lock_project_version_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM id
      FROM projects_projectversion
     WHERE id = NEW.project_version_id
     FOR UPDATE;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_00_lock_project_run_version_constraint
BEFORE INSERT ON formations_projectrun
FOR EACH ROW
EXECUTE FUNCTION formations_lock_project_version_trigger();

CREATE TRIGGER formations_00_lock_formation_version_constraint
BEFORE INSERT ON formations_teamformation
FOR EACH ROW
EXECUTE FUNCTION formations_lock_project_version_trigger();

CREATE FUNCTION projects_referenced_version_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM projects_assert_version_unreferenced(OLD.id);
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER projects_referenced_version_constraint
BEFORE UPDATE OR DELETE ON projects_projectversion
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_version_trigger();

CREATE FUNCTION projects_referenced_direct_definition_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM projects_assert_version_unreferenced(OLD.project_version_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM projects_assert_version_unreferenced(NEW.project_version_id);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER projects_referenced_sprint_template_constraint
BEFORE INSERT OR UPDATE OR DELETE ON projects_sprinttemplate
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_direct_definition_trigger();

CREATE TRIGGER projects_referenced_work_item_constraint
BEFORE INSERT OR UPDATE OR DELETE ON projects_projecttasktemplate
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_direct_definition_trigger();

CREATE TRIGGER projects_referenced_role_requirement_constraint
BEFORE INSERT OR UPDATE OR DELETE ON projects_projectrolerequirement
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_direct_definition_trigger();

CREATE FUNCTION projects_referenced_indirect_definition_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_project_version_id uuid;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT project_version_id
          INTO v_project_version_id
          FROM projects_projectrolerequirement
         WHERE id = OLD.role_requirement_id;
        PERFORM projects_assert_version_unreferenced(v_project_version_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT project_version_id
          INTO v_project_version_id
          FROM projects_projectrolerequirement
         WHERE id = NEW.role_requirement_id;
        PERFORM projects_assert_version_unreferenced(v_project_version_id);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER projects_referenced_allowed_stack_constraint
BEFORE INSERT OR UPDATE OR DELETE ON projects_projectroleallowedstack
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_indirect_definition_trigger();

CREATE TRIGGER projects_referenced_prerequisite_constraint
BEFORE INSERT OR UPDATE OR DELETE ON projects_roleprerequisite
FOR EACH ROW
EXECUTE FUNCTION projects_referenced_indirect_definition_trigger();

CREATE FUNCTION formations_validate_sprint_run_set(p_project_run_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_project_version_id uuid;
BEGIN
    SELECT project_version_id
      INTO v_project_version_id
      FROM formations_projectrun
     WHERE id = p_project_run_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM projects_sprinttemplate AS template
          LEFT JOIN formations_sprintrun AS sprint
            ON sprint.project_run_id = p_project_run_id
           AND sprint.sprint_template_id = template.id
         WHERE template.project_version_id = v_project_version_id
           AND sprint.id IS NULL
    ) OR EXISTS (
        SELECT 1
          FROM formations_sprintrun AS sprint
          JOIN projects_sprinttemplate AS template
            ON template.id = sprint.sprint_template_id
         WHERE sprint.project_run_id = p_project_run_id
           AND template.project_version_id IS DISTINCT FROM v_project_version_id
    ) THEN
        RAISE EXCEPTION 'ProjectRun Sprint runtimes must match its fixed ProjectVersion.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION formations_sprint_run_set_run_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM formations_validate_sprint_run_set(OLD.id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM formations_validate_sprint_run_set(NEW.id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION formations_sprint_run_set_sprint_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM formations_validate_sprint_run_set(OLD.project_run_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM formations_validate_sprint_run_set(NEW.project_run_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_sprint_run_set_run_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_projectrun
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_run_set_run_trigger();

CREATE CONSTRAINT TRIGGER formations_sprint_run_set_sprint_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_sprintrun
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_run_set_sprint_trigger();

DO $validation$
DECLARE
    v_project_run_id uuid;
BEGIN
    FOR v_project_run_id IN
        SELECT id FROM formations_projectrun ORDER BY id
    LOOP
        PERFORM formations_validate_sprint_run_set(v_project_run_id);
    END LOOP;
END;
$validation$;
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_sprint_run_set_sprint_constraint
    ON formations_sprintrun;
DROP TRIGGER IF EXISTS formations_sprint_run_set_run_constraint
    ON formations_projectrun;
DROP TRIGGER IF EXISTS projects_referenced_prerequisite_constraint
    ON projects_roleprerequisite;
DROP TRIGGER IF EXISTS projects_referenced_allowed_stack_constraint
    ON projects_projectroleallowedstack;
DROP TRIGGER IF EXISTS projects_referenced_role_requirement_constraint
    ON projects_projectrolerequirement;
DROP TRIGGER IF EXISTS projects_referenced_work_item_constraint
    ON projects_projecttasktemplate;
DROP TRIGGER IF EXISTS projects_referenced_sprint_template_constraint
    ON projects_sprinttemplate;
DROP TRIGGER IF EXISTS projects_referenced_version_constraint
    ON projects_projectversion;
DROP TRIGGER IF EXISTS formations_00_lock_project_run_version_constraint
    ON formations_projectrun;
DROP TRIGGER IF EXISTS formations_00_lock_formation_version_constraint
    ON formations_teamformation;

DROP FUNCTION IF EXISTS formations_sprint_run_set_sprint_trigger();
DROP FUNCTION IF EXISTS formations_sprint_run_set_run_trigger();
DROP FUNCTION IF EXISTS formations_validate_sprint_run_set(uuid);
DROP FUNCTION IF EXISTS projects_referenced_indirect_definition_trigger();
DROP FUNCTION IF EXISTS projects_referenced_direct_definition_trigger();
DROP FUNCTION IF EXISTS projects_referenced_version_trigger();
DROP FUNCTION IF EXISTS formations_lock_project_version_trigger();
DROP FUNCTION IF EXISTS projects_assert_version_unreferenced(uuid);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0006_project_run_terminal_lifecycle"),
        ("projects", "0004_project_definition_integrity_triggers"),
    ]

    operations = [migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL)]
