from django.db import migrations


FORWARD_SQL = r"""
CREATE FUNCTION projects_validate_role_stack_policy(p_requirement_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_requires_stack boolean;
    v_stack_policy varchar(16);
    v_allowed_count bigint;
BEGIN
    SELECT requirement.requires_stack,
           requirement.stack_policy,
           COUNT(allowed_stack.id)
      INTO v_requires_stack, v_stack_policy, v_allowed_count
      FROM projects_projectrolerequirement AS requirement
      LEFT JOIN projects_projectroleallowedstack AS allowed_stack
        ON allowed_stack.role_requirement_id = requirement.id
     WHERE requirement.id = p_requirement_id
     GROUP BY requirement.id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF (NOT v_requires_stack AND (v_stack_policy IS NOT NULL OR v_allowed_count <> 0))
       OR (v_requires_stack AND v_stack_policy = 'FIXED' AND v_allowed_count <> 1)
       OR (v_requires_stack AND v_stack_policy = 'ALLOWLIST' AND v_allowed_count < 1)
       OR (v_requires_stack AND v_stack_policy = 'OPEN' AND v_allowed_count <> 0)
    THEN
        RAISE EXCEPTION 'Invalid project role stack configuration.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION projects_role_requirement_stack_policy_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM projects_validate_role_stack_policy(NEW.id);
    RETURN NULL;
END;
$$;

CREATE FUNCTION projects_allowed_stack_policy_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM projects_validate_role_stack_policy(OLD.role_requirement_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE')
       AND (TG_OP <> 'UPDATE' OR NEW.role_requirement_id <> OLD.role_requirement_id)
    THEN
        PERFORM projects_validate_role_stack_policy(NEW.role_requirement_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER projects_role_requirement_stack_policy_constraint
AFTER INSERT OR UPDATE ON projects_projectrolerequirement
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_role_requirement_stack_policy_trigger();

CREATE CONSTRAINT TRIGGER projects_allowed_stack_policy_constraint
AFTER INSERT OR UPDATE OR DELETE ON projects_projectroleallowedstack
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_allowed_stack_policy_trigger();

CREATE FUNCTION projects_validate_work_item_sprint_version(p_work_item_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_versions_mismatch boolean;
BEGIN
    SELECT work_item.project_version_id <> sprint.project_version_id
      INTO v_versions_mismatch
      FROM projects_projecttasktemplate AS work_item
      JOIN projects_sprinttemplate AS sprint
        ON sprint.id = work_item.sprint_template_id
     WHERE work_item.id = p_work_item_id;

    IF FOUND AND v_versions_mismatch THEN
        RAISE EXCEPTION 'Static work content and Sprint must use the same project version.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION projects_work_item_sprint_version_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM projects_validate_work_item_sprint_version(NEW.id);
    RETURN NULL;
END;
$$;

CREATE FUNCTION projects_sprint_work_item_version_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_work_item_id uuid;
BEGIN
    FOR v_work_item_id IN
        SELECT id
          FROM projects_projecttasktemplate
         WHERE sprint_template_id = NEW.id
    LOOP
        PERFORM projects_validate_work_item_sprint_version(v_work_item_id);
    END LOOP;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER projects_work_item_sprint_version_constraint
AFTER INSERT OR UPDATE ON projects_projecttasktemplate
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_work_item_sprint_version_trigger();

CREATE CONSTRAINT TRIGGER projects_sprint_work_item_version_constraint
AFTER UPDATE ON projects_sprinttemplate
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_sprint_work_item_version_trigger();

DO $$
DECLARE
    v_id uuid;
BEGIN
    FOR v_id IN SELECT id FROM projects_projectrolerequirement LOOP
        PERFORM projects_validate_role_stack_policy(v_id);
    END LOOP;
    FOR v_id IN
        SELECT id
          FROM projects_projecttasktemplate
         WHERE sprint_template_id IS NOT NULL
    LOOP
        PERFORM projects_validate_work_item_sprint_version(v_id);
    END LOOP;
END;
$$;
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS projects_sprint_work_item_version_constraint
    ON projects_sprinttemplate;
DROP TRIGGER IF EXISTS projects_work_item_sprint_version_constraint
    ON projects_projecttasktemplate;
DROP TRIGGER IF EXISTS projects_allowed_stack_policy_constraint
    ON projects_projectroleallowedstack;
DROP TRIGGER IF EXISTS projects_role_requirement_stack_policy_constraint
    ON projects_projectrolerequirement;

DROP FUNCTION IF EXISTS projects_sprint_work_item_version_trigger();
DROP FUNCTION IF EXISTS projects_work_item_sprint_version_trigger();
DROP FUNCTION IF EXISTS projects_validate_work_item_sprint_version(uuid);
DROP FUNCTION IF EXISTS projects_allowed_stack_policy_trigger();
DROP FUNCTION IF EXISTS projects_role_requirement_stack_policy_trigger();
DROP FUNCTION IF EXISTS projects_validate_role_stack_policy(uuid);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0003_roletechnologystack"),
        ("projects", "0003_sprinttemplate_projecttasktemplate_sprint_template_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
