import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


FORWARD_SQL = r"""
CREATE FUNCTION formations_validate_completion(p_formation_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_ready_confirmed_at timestamptz;
    v_project_version_id uuid;
    v_team_count bigint;
    v_team_id uuid;
    v_project_run_id uuid;
    v_run_project_version_id uuid;
    v_run_started_at timestamptz;
    v_run_ended_at timestamptz;
    v_current_count bigint;
    v_confirmed_count bigint;
    v_member_count bigint;
BEGIN
    SELECT formation.ready_confirmed_at,
           formation.project_version_id
      INTO v_ready_confirmed_at,
           v_project_version_id
      FROM formations_teamformation AS formation
     WHERE formation.id = p_formation_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COUNT(*)
      INTO v_team_count
      FROM formations_team
     WHERE formation_id = p_formation_id;

    IF v_ready_confirmed_at IS NULL THEN
        IF v_team_count <> 0 THEN
            RAISE EXCEPTION 'An unconfirmed formation cannot have a team.'
                USING ERRCODE = '23514';
        END IF;
        RETURN;
    END IF;

    IF v_team_count <> 1 THEN
        RAISE EXCEPTION 'A confirmed formation must have exactly one team.'
            USING ERRCODE = '23514';
    END IF;

    SELECT id
      INTO v_team_id
      FROM formations_team
     WHERE formation_id = p_formation_id;

    SELECT run.id,
           run.project_version_id,
           run.started_at,
           run.ended_at
      INTO v_project_run_id,
           v_run_project_version_id,
           v_run_started_at,
           v_run_ended_at
      FROM formations_projectrun AS run
     WHERE run.team_id = v_team_id;

    IF NOT FOUND
       OR v_run_project_version_id IS DISTINCT FROM v_project_version_id
       OR v_run_started_at IS DISTINCT FROM v_ready_confirmed_at
    THEN
        RAISE EXCEPTION 'A confirmed formation requires its matching project run.'
            USING ERRCODE = '23514';
    END IF;

    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE status = 'CONFIRMED')
      INTO v_current_count,
           v_confirmed_count
      FROM formations_readycheck
     WHERE formation_id = p_formation_id
       AND is_current;

    IF v_current_count <> 3 OR v_confirmed_count <> 3 THEN
        RAISE EXCEPTION 'A team requires three confirmed current Ready Checks.'
            USING ERRCODE = '23514';
    END IF;

    SELECT COUNT(*)
      INTO v_member_count
      FROM formations_teammember
     WHERE project_run_id = v_project_run_id;

    IF v_member_count <> 3 THEN
        RAISE EXCEPTION 'A project run must have exactly three team members.'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM formations_readycheck AS ready_check
          LEFT JOIN formations_teammember AS member
            ON member.project_run_id = v_project_run_id
           AND member.user_id = ready_check.user_id
           AND member.role_id = ready_check.role_id
           AND member.technology_stack_id IS NOT DISTINCT FROM ready_check.technology_stack_id
         WHERE ready_check.formation_id = p_formation_id
           AND ready_check.is_current
           AND member.id IS NULL
    ) OR EXISTS (
        SELECT 1
          FROM formations_teammember AS member
          LEFT JOIN formations_readycheck AS ready_check
            ON ready_check.formation_id = p_formation_id
           AND ready_check.is_current
           AND ready_check.user_id = member.user_id
           AND ready_check.role_id = member.role_id
           AND ready_check.technology_stack_id IS NOT DISTINCT FROM member.technology_stack_id
         WHERE member.project_run_id = v_project_run_id
           AND ready_check.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Team member snapshots must match the confirmed formation.'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM formations_teammember
         WHERE project_run_id = v_project_run_id
           AND ended_at IS DISTINCT FROM v_run_ended_at
    ) THEN
        RAISE EXCEPTION 'Project run and member activity are inconsistent.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

CREATE FUNCTION formations_completion_formation_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM formations_validate_completion(OLD.id);
    ELSE
        PERFORM formations_validate_completion(NEW.id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION formations_completion_team_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM formations_validate_completion(OLD.formation_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM formations_validate_completion(NEW.formation_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION formations_completion_run_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_formation_id uuid;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT formation_id
          INTO v_formation_id
          FROM formations_team
         WHERE id = OLD.team_id;
        PERFORM formations_validate_completion(v_formation_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT formation_id
          INTO v_formation_id
          FROM formations_team
         WHERE id = NEW.team_id;
        PERFORM formations_validate_completion(v_formation_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION formations_completion_member_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_formation_id uuid;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT team.formation_id
          INTO v_formation_id
          FROM formations_projectrun AS run
          JOIN formations_team AS team ON team.id = run.team_id
         WHERE run.id = OLD.project_run_id;
        PERFORM formations_validate_completion(v_formation_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT team.formation_id
          INTO v_formation_id
          FROM formations_projectrun AS run
          JOIN formations_team AS team ON team.id = run.team_id
         WHERE run.id = NEW.project_run_id;
        PERFORM formations_validate_completion(v_formation_id);
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER formations_completion_formation_constraint
AFTER INSERT OR UPDATE ON formations_teamformation
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_completion_formation_trigger();

CREATE CONSTRAINT TRIGGER formations_completion_team_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_team
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_completion_team_trigger();

CREATE CONSTRAINT TRIGGER formations_completion_run_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_projectrun
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_completion_run_trigger();

CREATE CONSTRAINT TRIGGER formations_completion_member_constraint
AFTER INSERT OR UPDATE OR DELETE ON formations_teammember
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION formations_completion_member_trigger();

DO $validation$
DECLARE
    v_formation_id uuid;
BEGIN
    FOR v_formation_id IN
        SELECT id FROM formations_teamformation ORDER BY id
    LOOP
        PERFORM formations_validate_completion(v_formation_id);
    END LOOP;
END;
$validation$;
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_completion_member_constraint
    ON formations_teammember;
DROP TRIGGER IF EXISTS formations_completion_run_constraint
    ON formations_projectrun;
DROP TRIGGER IF EXISTS formations_completion_team_constraint
    ON formations_team;
DROP TRIGGER IF EXISTS formations_completion_formation_constraint
    ON formations_teamformation;

DROP FUNCTION IF EXISTS formations_completion_member_trigger();
DROP FUNCTION IF EXISTS formations_completion_run_trigger();
DROP FUNCTION IF EXISTS formations_completion_team_trigger();
DROP FUNCTION IF EXISTS formations_completion_formation_trigger();
DROP FUNCTION IF EXISTS formations_validate_completion(uuid);
"""


def backfill_confirmed_formations(apps, schema_editor):
    TeamFormation = apps.get_model("formations", "TeamFormation")
    ReadyCheck = apps.get_model("formations", "ReadyCheck")
    Team = apps.get_model("formations", "Team")
    ProjectRun = apps.get_model("formations", "ProjectRun")
    TeamMember = apps.get_model("formations", "TeamMember")
    database_alias = schema_editor.connection.alias

    confirmed_formations = TeamFormation.objects.using(database_alias).filter(
        ready_confirmed_at__isnull=False
    ).order_by("id")
    for formation in confirmed_formations.iterator():
        ready_checks = list(
            ReadyCheck.objects.using(database_alias).filter(
                formation_id=formation.id,
                is_current=True,
                status="CONFIRMED",
            ).order_by("role_id", "id")
        )
        if len(ready_checks) != 3:
            raise RuntimeError(
                "Cannot backfill an invalid confirmed team formation."
            )
        team = Team.objects.using(database_alias).create(
            formation_id=formation.id,
            created_at=formation.ready_confirmed_at,
        )
        project_run = ProjectRun.objects.using(database_alias).create(
            team_id=team.id,
            project_version_id=formation.project_version_id,
            started_at=formation.ready_confirmed_at,
        )
        TeamMember.objects.using(database_alias).bulk_create(
            [
                TeamMember(
                    project_run_id=project_run.id,
                    user_id=ready_check.user_id,
                    role_id=ready_check.role_id,
                    technology_stack_id=ready_check.technology_stack_id,
                )
                for ready_check in ready_checks
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0002_formation_integrity_triggers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Team",
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
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                    ),
                ),
                (
                    "formation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="team",
                        to="formations.teamformation",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ProjectRun",
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
                ("started_at", models.DateTimeField(editable=False)),
                (
                    "ended_at",
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    "project_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="project_runs",
                        to="projects.projectversion",
                    ),
                ),
                (
                    "team",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="project_run",
                        to="formations.team",
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["project_version", "ended_at", "started_at"],
                        name="formations_run_ver_active_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("ended_at__isnull", True),
                            ("ended_at__gte", models.F("started_at")),
                            _connector="OR",
                        ),
                        name="formations_run_end_after_start",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="TeamMember",
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
                    "ended_at",
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    "project_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="members",
                        to="formations.projectrun",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="historical_team_members",
                        to="profiles.role",
                    ),
                ),
                (
                    "technology_stack",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="historical_team_members",
                        to="profiles.technologystack",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="team_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["role__name", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("project_run", "user"),
                        name="formations_run_member_user_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("project_run", "role"),
                        name="formations_run_member_role_unique",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("ended_at__isnull", True)),
                        fields=("user",),
                        name="formations_active_run_user_unique",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            backfill_confirmed_formations,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
