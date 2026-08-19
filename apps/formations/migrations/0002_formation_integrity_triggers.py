from django.db import migrations


FORWARD_SQL = r"""
CREATE FUNCTION formations_validate_current_slots(p_formation_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_ready_confirmed_at timestamptz;
    v_current_count bigint;
    v_confirmed_count bigint;
BEGIN
    SELECT formation.ready_confirmed_at
      INTO v_ready_confirmed_at
      FROM formations_teamformation AS formation
     WHERE formation.id = p_formation_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE status = 'CONFIRMED')
      INTO v_current_count, v_confirmed_count
      FROM formations_readycheck
     WHERE formation_id = p_formation_id
       AND is_current;

    IF v_current_count <> 3 THEN
        RAISE EXCEPTION 'A team formation must have exactly three current role slots.'
            USING ERRCODE = '23514';
    END IF;

    IF (v_ready_confirmed_at IS NULL AND v_confirmed_count = 3)
       OR (v_ready_confirmed_at IS NOT NULL AND v_confirmed_count <> 3)
    THEN
        RAISE EXCEPTION 'Formation readiness and current confirmations are inconsistent.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION formations_formation_slots_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (
            SELECT 1
              FROM accounts_user AS creator
              JOIN projects_projectversion AS project_version
                ON project_version.id = NEW.project_version_id
             WHERE creator.id = NEW.created_by_id
               AND creator.is_staff
               AND creator.is_active
               AND project_version.published_at IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'A team formation requires a staff creator and published project version.'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.project_version_id IS DISTINCT FROM OLD.project_version_id
           OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR (
               OLD.ready_confirmed_at IS NOT NULL
               AND NEW.ready_confirmed_at IS DISTINCT FROM OLD.ready_confirmed_at
           )
        THEN
            RAISE EXCEPTION 'Team formation identity and readiness are immutable.'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM formations_validate_current_slots(NEW.id);
    RETURN NULL;
END;
$$;

CREATE FUNCTION formations_ready_check_slots_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM formations_validate_current_slots(NEW.formation_id);
    ELSIF TG_OP = 'UPDATE' THEN
        PERFORM formations_validate_current_slots(OLD.formation_id);
        PERFORM formations_validate_current_slots(NEW.formation_id);
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM formations_validate_current_slots(OLD.formation_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_exact_current_slots_constraint
AFTER INSERT OR UPDATE ON formations_teamformation
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_formation_slots_trigger();

CREATE CONSTRAINT TRIGGER formations_ready_check_slots_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_readycheck
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_ready_check_slots_trigger();

CREATE FUNCTION formations_validate_ready_check(p_ready_check_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id uuid;
    v_user_active boolean;
    v_proposer_authorized boolean;
    v_profile_id uuid;
    v_profile_role_id uuid;
    v_role_id uuid;
    v_stack_id uuid;
    v_requires_stack boolean;
    v_stack_policy varchar(16);
    v_requirement_id uuid;
    v_valid_stack boolean;
BEGIN
    SELECT ready_check.user_id,
           account.is_active,
           proposer.is_staff AND proposer.is_active,
           profile.id,
           profile.selected_role_id,
           ready_check.role_id,
           ready_check.technology_stack_id,
           requirement.requires_stack,
           requirement.stack_policy,
           requirement.id
      INTO v_user_id,
           v_user_active,
           v_proposer_authorized,
           v_profile_id,
           v_profile_role_id,
           v_role_id,
           v_stack_id,
           v_requires_stack,
           v_stack_policy,
           v_requirement_id
      FROM formations_readycheck AS ready_check
      JOIN formations_teamformation AS formation
        ON formation.id = ready_check.formation_id
      JOIN accounts_user AS account
        ON account.id = ready_check.user_id
      JOIN accounts_user AS proposer
        ON proposer.id = ready_check.proposed_by_id
      LEFT JOIN profiles_userprofile AS profile
        ON profile.user_id = ready_check.user_id
      LEFT JOIN projects_projectrolerequirement AS requirement
        ON requirement.project_version_id = formation.project_version_id
       AND requirement.role_id = ready_check.role_id
     WHERE ready_check.id = p_ready_check_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF NOT v_user_active
       OR NOT v_proposer_authorized
       OR v_profile_id IS NULL
       OR v_profile_role_id IS DISTINCT FROM v_role_id
       OR v_requirement_id IS NULL
    THEN
        RAISE EXCEPTION 'Ready Check member and project role are incompatible.'
            USING ERRCODE = '23514';
    END IF;

    IF NOT v_requires_stack THEN
        v_valid_stack := v_stack_id IS NULL;
    ELSIF v_stack_id IS NULL THEN
        v_valid_stack := false;
    ELSIF v_stack_policy IN ('FIXED', 'ALLOWLIST') THEN
        SELECT EXISTS (
            SELECT 1
              FROM projects_projectroleallowedstack
             WHERE role_requirement_id = v_requirement_id
               AND technology_stack_id = v_stack_id
        ) INTO v_valid_stack;
    ELSIF v_stack_policy = 'OPEN' THEN
        SELECT EXISTS (
            SELECT 1
              FROM profiles_roletechnologystack AS role_stack
              JOIN profiles_userskill AS skill
                ON skill.technology_stack_id = role_stack.technology_stack_id
             WHERE role_stack.role_id = v_role_id
               AND role_stack.technology_stack_id = v_stack_id
               AND skill.profile_id = v_profile_id
        ) INTO v_valid_stack;
    ELSE
        v_valid_stack := false;
    END IF;

    IF NOT v_valid_stack THEN
        RAISE EXCEPTION 'Ready Check stack is incompatible with the project role.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION formations_ready_check_validity_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PENDING'
           OR NOT NEW.is_current
           OR NEW.responded_at IS NOT NULL
        THEN
            RAISE EXCEPTION 'A new Ready Check must be current and pending.'
                USING ERRCODE = '23514';
        END IF;
        PERFORM formations_validate_ready_check(NEW.id);
        RETURN NULL;
    END IF;

    IF NEW.formation_id IS DISTINCT FROM OLD.formation_id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.role_id IS DISTINCT FROM OLD.role_id
       OR NEW.technology_stack_id IS DISTINCT FROM OLD.technology_stack_id
       OR NEW.proposed_by_id IS DISTINCT FROM OLD.proposed_by_id
       OR NEW.started_at IS DISTINCT FROM OLD.started_at
       OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
    THEN
        RAISE EXCEPTION 'Ready Check identity snapshots are immutable.'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status
       AND NOT (
           OLD.status = 'PENDING'
           AND NEW.status IN ('CONFIRMED', 'DECLINED', 'EXPIRED')
       )
    THEN
        RAISE EXCEPTION 'Invalid Ready Check status transition.'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.is_current IS DISTINCT FROM OLD.is_current
       AND NOT (
           OLD.is_current
           AND NOT NEW.is_current
           AND NEW.status IN ('DECLINED', 'EXPIRED')
       )
    THEN
        RAISE EXCEPTION 'Only declined or expired Ready Checks may be replaced.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_ready_check_validity_constraint
AFTER INSERT OR UPDATE ON formations_readycheck
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_ready_check_validity_trigger();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_ready_check_validity_constraint
    ON formations_readycheck;
DROP TRIGGER IF EXISTS formations_ready_check_slots_constraint
    ON formations_readycheck;
DROP TRIGGER IF EXISTS formations_exact_current_slots_constraint
    ON formations_teamformation;

DROP FUNCTION IF EXISTS formations_ready_check_validity_trigger();
DROP FUNCTION IF EXISTS formations_validate_ready_check(uuid);
DROP FUNCTION IF EXISTS formations_ready_check_slots_trigger();
DROP FUNCTION IF EXISTS formations_formation_slots_trigger();
DROP FUNCTION IF EXISTS formations_validate_current_slots(uuid);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
