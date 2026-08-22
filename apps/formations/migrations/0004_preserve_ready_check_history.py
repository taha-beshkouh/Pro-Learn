from django.db import migrations


FORWARD_SQL = r"""
CREATE FUNCTION formations_preserve_ready_check_history_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM formations_teamformation
         WHERE id = OLD.formation_id
    ) THEN
        RAISE EXCEPTION 'Ready Check history is immutable.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_ready_check_history_constraint
AFTER DELETE ON formations_readycheck
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_preserve_ready_check_history_trigger();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_ready_check_history_constraint
    ON formations_readycheck;
DROP FUNCTION IF EXISTS formations_preserve_ready_check_history_trigger();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0003_team_project_run"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
