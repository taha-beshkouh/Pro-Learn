import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


FORWARD_SQL = r"""
CREATE FUNCTION formations_review_decision_insert_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_sprint_run_id uuid;
    v_sprint_state varchar(20);
    v_project_run_state varchar(20);
    v_project_run_ended_at timestamptz;
    v_submitted_at timestamptz;
    v_latest_submission_id uuid;
    v_reviewer_is_active boolean;
    v_reviewer_is_staff boolean;
BEGIN
    SELECT submission.sprint_run_id,
           sprint.state,
           run.state,
           run.ended_at,
           submission.submitted_at
      INTO v_sprint_run_id,
           v_sprint_state,
           v_project_run_state,
           v_project_run_ended_at,
           v_submitted_at
      FROM formations_sprintsubmission AS submission
      JOIN formations_sprintrun AS sprint
        ON sprint.id = submission.sprint_run_id
      JOIN formations_projectrun AS run
        ON run.id = sprint.project_run_id
     WHERE submission.id = NEW.sprint_submission_id;

    SELECT submission.id
      INTO v_latest_submission_id
      FROM formations_sprintsubmission AS submission
     WHERE submission.sprint_run_id = v_sprint_run_id
     ORDER BY submission.submitted_at DESC, submission.id DESC
     LIMIT 1;

    SELECT reviewer.is_active, reviewer.is_staff
      INTO v_reviewer_is_active, v_reviewer_is_staff
      FROM accounts_user AS reviewer
     WHERE reviewer.id = NEW.reviewed_by_id;

    IF v_sprint_run_id IS NULL
       OR v_sprint_state IS DISTINCT FROM 'UNDER_REVIEW'
       OR v_project_run_state IS DISTINCT FROM 'ACTIVE'
       OR v_project_run_ended_at IS NOT NULL
       OR v_latest_submission_id IS DISTINCT FROM NEW.sprint_submission_id
       OR v_reviewer_is_active IS DISTINCT FROM TRUE
       OR v_reviewer_is_staff IS DISTINCT FROM TRUE
       OR NEW.reviewed_at < v_submitted_at
       OR NEW.decision NOT IN ('CHANGES_REQUESTED', 'COMPLETED')
       OR (
           NEW.decision = 'CHANGES_REQUESTED'
           AND (
               NEW.feedback IS NULL
               OR NEW.feedback !~ '[^[:space:]]'
           )
       )
    THEN
        RAISE EXCEPTION 'Invalid Sprint review decision.'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_review_decision_insert_constraint
BEFORE INSERT ON formations_reviewdecision
FOR EACH ROW
EXECUTE FUNCTION formations_review_decision_insert_trigger();

CREATE FUNCTION formations_review_decision_immutable_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Sprint review decision history is append-only.'
        USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER formations_review_decision_immutable_constraint
BEFORE UPDATE OR DELETE ON formations_reviewdecision
FOR EACH ROW
EXECUTE FUNCTION formations_review_decision_immutable_trigger();

CREATE FUNCTION formations_sprint_review_decision_pair_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_latest_submission_id uuid;
BEGIN
    IF OLD.state = 'UNDER_REVIEW'
       AND NEW.state IN ('CHANGES_REQUESTED', 'COMPLETED')
    THEN
        SELECT submission.id
          INTO v_latest_submission_id
          FROM formations_sprintsubmission AS submission
         WHERE submission.sprint_run_id = NEW.id
         ORDER BY submission.submitted_at DESC, submission.id DESC
         LIMIT 1;

        IF v_latest_submission_id IS NULL
           OR NOT EXISTS (
               SELECT 1
                 FROM formations_reviewdecision AS decision
                WHERE decision.sprint_submission_id = v_latest_submission_id
                  AND decision.decision = NEW.state
           )
        THEN
            RAISE EXCEPTION 'Sprint review transition requires a matching decision.'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER formations_sprint_review_decision_constraint
AFTER UPDATE ON formations_sprintrun
FOR EACH ROW
EXECUTE FUNCTION formations_sprint_review_decision_pair_trigger();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS formations_sprint_review_decision_constraint
    ON formations_sprintrun;
DROP TRIGGER IF EXISTS formations_review_decision_immutable_constraint
    ON formations_reviewdecision;
DROP TRIGGER IF EXISTS formations_review_decision_insert_constraint
    ON formations_reviewdecision;

DROP FUNCTION IF EXISTS formations_sprint_review_decision_pair_trigger();
DROP FUNCTION IF EXISTS formations_review_decision_immutable_trigger();
DROP FUNCTION IF EXISTS formations_review_decision_insert_trigger();
"""


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("formations", "0013_structured_sprint_submission_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewDecision",
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
                    "decision",
                    models.CharField(
                        choices=[
                            ("CHANGES_REQUESTED", "Changes requested"),
                            ("COMPLETED", "Completed"),
                        ],
                        max_length=20,
                    ),
                ),
                ("feedback", models.TextField(blank=True)),
                (
                    "reviewed_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sprint_review_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sprint_submission",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="review_decision",
                        to="formations.sprintsubmission",
                    ),
                ),
            ],
            options={
                "ordering": ["reviewed_at", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("decision__in", ["CHANGES_REQUESTED", "COMPLETED"])
                        ),
                        name="formations_review_decision_known",
                    )
                ],
            },
        ),
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
