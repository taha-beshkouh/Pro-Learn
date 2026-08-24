# PROJECT_RULES.md

> Compact source of truth for the current backend implementation.
> Product/domain rules only. Do not add Docker, Git/GitHub automation, CI/CD, deployment automation, or frontend implementation here.

## 1. Product

- Target users: pre-junior / junior developers and product designers who need real team collaboration experience.
- The platform simulates structured project work.
- It is not an employer, recruitment marketplace, traditional course, or certificate-first product.
- Main outcome: practical teamwork experience + a defensible project result.

## 2. Platform Roles

MVP roles:
- `BACKEND_DEVELOPER`
- `FRONTEND_DEVELOPER`
- `PRODUCT_DESIGNER`

Rules:
- Every MVP team has exactly 3 active members: one of each role.
- A user selects their current platform role once.
- Project pages use that role automatically.
- Historical project membership must snapshot role and must not change if the user's profile role changes later.

## 3. User / Profile

Registration:
- email
- password

Profile supports:
- display name
- selected role
- timezone
- language
- interests
- profile/project/portfolio/case-study links

Rules:
- A user may have only one active `ProjectRun` at a time.
- Current profile data and historical project membership are separate concepts.

## 4. Guest Context

Anonymous visitors may:
- select a role
- select a stack when relevant
- browse projects
- view project details and role-specific project information

Temporary guest context may be stored in the Django session:
- selected role
- selected stack
- selected project
- intended action
- safe internal return path

Do not create a database User for anonymous visitors.

## 5. Levels

Available levels:
- Level 1
- Level 2
- Level 3

Level means technical/project complexity, not years of professional experience.

Initial projects:
- Level 1 → Helpdesk Lite
- Level 2 → Healthchecks Lite
- Level 3 → Event Ticketing Lite

## 6. Technology Stacks

Technology stacks are normalized platform data.

Supported project-role policies:
- `FIXED` → exactly one allowed stack
- `ALLOWLIST` → one or more configured stacks
- `OPEN` → user chooses from their own registered compatible stacks

Rules:
- Stack policy belongs to a project role, not globally to the platform.
- `OPEN` does not allow arbitrary free-text technologies.
- Some roles, such as Product Designer, may require no technical stack.
- If exactly one compatible stack exists, it may be auto-selected.
- If multiple compatible stacks exist, the user selects one.
- Selected project stack must be snapshotted for historical participation.

## 7. Project Model

These concepts are different:
- `ProjectTemplate`
- `ProjectVersion`
- `ProjectRun`

Rules:
- Project definitions are versioned.
- A `ProjectRun` is permanently tied to the exact `ProjectVersion` it started with.
- Future edits must not mutate active or historical ProjectRuns.
- Project-specific content must be data-driven, not hard-coded by project slug.
- Each ProjectVersion defines role-specific requirements, prerequisites, stack policy, and static work content.

## 8. Project UX / Data Boundaries

### Project Detail
For discovering/understanding a project before participation.

Contains general project information plus the selected role's relevant content.

### Dashboard
Summary of the user's active ProjectRun:
- project
- role / stack
- current Sprint
- deadline/status
- team summary
- next relevant action

### Project Workspace
Used after ProjectRun starts:
- overview
- Sprints
- team
- project resources

### Sprint View
Shows Sprint brief and static work expected from the team/roles.

There is no Jira/Trello-style runtime task system in MVP.

## 9. Static Work Content

Static project/Sprint work items may be:
- role-specific
- shared/team-wide
- optionally stack-specific
- optionally associated with a SprintTemplate

They are informational project content only.

Do NOT implement runtime:
- task statuses
- task assignment workflow
- task deadlines
- task submissions
- Kanban
- Todo workflow
- task completion percentages

## 10. Helpdesk Lite

General:
- Level: 1
- Duration: 6 weeks
- Sprint count: 6
- Expected effort: about 10–12 hours/week/member
- Team: Backend + Frontend + Product Designer

Helpdesk product users:
- Requester
- Agent

These are product roles, not platform roles.
No Admin UI in core scope.

Ticket statuses:
- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`

Flow:
`OPEN → IN_PROGRESS → RESOLVED`

No reopen in core v1.

Priorities:
- `LOW`
- `NORMAL`
- `HIGH`

Default: `NORMAL`

Assignment:
- New Ticket starts unassigned.
- Agent may claim an unassigned Ticket.
- No reassignment in core v1.
- Only assigned Agent may change status and priority.

Comments:
- Requester may comment on their own Ticket.
- Assigned Agent may comment.
- No new comments after `RESOLVED`.
- Comments are immutable.

History must preserve at least:
- claim
- status change
- priority change

Required project scope:
- authentication
- Ticket functionality
- claim
- status/priority
- categories
- comments
- history
- search/filter
- pagination
- validation
- permission enforcement
- Swagger/OpenAPI
- backend tests
- responsive frontend
- README
- deployment

Categories are seeded/predefined.

Backend stack policy:
`ALLOWLIST`

Allowed:
- Django + Django REST Framework
- ASP.NET Core Web API + Entity Framework Core

Frontend stack:
- React
- TypeScript
- Vite
- React Router

Participant-project database:
- MySQL 8 / InnoDB

This is NOT the platform database.

Out of core scope:
- email notifications inside Helpdesk
- attachments
- SLA
- realtime
- internal notes
- multi-organization
- automatic assignment
- knowledge base
- advanced reports
- export
- OAuth
- payment
- mobile app
- Admin UI
- reassignment
- reopen
- mandatory Docker
- mandatory CI
- custom domain

Stretch only:
- reopen
- reassignment
- simple dashboard

Exact Sprint-by-Sprint work distribution is not finalized. Do not invent it.

## 11. Healthchecks Lite / Event Ticketing Lite

Known:
- Healthchecks Lite → Level 2 → PostgreSQL
- Event Ticketing Lite → Level 3 → PostgreSQL

Detailed scope, role work, and Sprint content are not finalized.
Do not invent missing requirements.

## 12. Team Formation

Candidate Pool / Matching is NOT implemented now.

For the current phase, a proposed 3-person formation may be created manually by Facilitator/Admin.

Rules:
- exactly one Backend
- exactly one Frontend
- exactly one Product Designer
- users are unique
- selected stack must satisfy the ProjectVersion role requirement
- roles that require no stack must not receive a fake stack value

## 13. Ready Check

- Duration: 48 hours.
- Each proposed member confirms/declines only their own Ready Check.
- If one member declines or expires, only that role slot is replaced.
- The other two members remain.
- Replacement preserves the same role.
- When all three confirm, Team + ProjectRun are created exactly once.
- ProjectRun begins only after the full Ready Check succeeds.
- The successful full Ready Check is the authoritative start point for ProjectRun time. At that moment, the backend records the server-side start timestamp for the ProjectRun and derives its absolute deadline from the fixed ProjectVersion's configured project duration.
- Client/device time is never authoritative for ProjectRun deadline enforcement. The backend owns the deadline; clients may only display it in the user's timezone.
- Before confirmation, proposed members must be shown the project duration, Sprint cadence, expected weekly effort, and that Sprint review is manual in the MVP.
- Members must be told that Facilitator review may take several hours; the current MVP operational expectation is around 8 hours, but this is not a guaranteed SLA and does not add time to a Sprint or ProjectRun.
- Members are responsible for submitting early enough to leave practical time for review and possible fixes before the relevant deadline.

## 14. Team

`TeamMember` must preserve historical snapshots of:
- user
- role
- selected stack when applicable

Changing Profile/UserSkill later must not rewrite TeamMember history.

## 15. ProjectRun

- Represents one team's execution of one fixed ProjectVersion.
- Starts only after successful Ready Check.
- Each member must satisfy the one-active-ProjectRun rule.

MVP ProjectRun states:
- `ACTIVE`
- `COMPLETED`
- `INCOMPLETE`

Rules:
- A ProjectRun is created as `ACTIVE` only after the full Ready Check succeeds.
- The backend records the ProjectRun's server-side `started_at` at successful full Ready Check and stores an absolute `deadline_at` derived from `started_at + the fixed ProjectVersion's configured project duration`.
- `deadline_at` is the authoritative timestamp for server-side deadline enforcement. Frontend/client timezone conversion is presentation only and must not affect deadline validity.
- `ACTIVE` is the normal state while the team progresses through the project's Sprints.
- Sprint submission, Facilitator review, `CHANGES_REQUESTED`, deployment activity, and ordinary Sprint lateness do not by themselves move the ProjectRun out of `ACTIVE`.
- ProjectRun time does not pause while a Sprint is `SUBMITTED`, `UNDER_REVIEW`, or `CHANGES_REQUESTED`.
- Ordinary Sprint lateness does not automatically extend the current Sprint, shift future planned Sprint deadlines, or extend the overall ProjectRun deadline. The delay consumes the ProjectRun's remaining allowed time.
- Only `ACTIVE` counts as an active ProjectRun for the one-active-ProjectRun rule.
- `COMPLETED` and `INCOMPLETE` are terminal states and no longer count as active ProjectRuns.
- After a ProjectRun becomes terminal, no further Sprint state transitions are allowed. Existing Sprint states and submission history remain as historical truth; do not invent terminal Sprint states such as `FAILED`, `ABORTED`, or `EXPIRED`.

Completion:
- The ProjectRun becomes `COMPLETED` only after Facilitator/Admin reviews the final submission of the final Sprint and confirms that the final deployment and project result satisfy the applicable ProjectVersion requirements.
- Submission alone never completes the ProjectRun.
- If the final Sprint requires changes, those fixes remain inside the same final Sprint and, while the ProjectRun deadline still permits team submission/resubmission, must be resubmitted through the normal Sprint review flow.
- When Facilitator/Admin completes the final Sprint successfully, the final Sprint and the ProjectRun must transition to `COMPLETED` in the same database transaction.

Incomplete outcome:
- The ProjectRun does not automatically become `INCOMPLETE` when its deadline passes. MVP terminalization is Facilitator/Admin-controlled.
- Once `deadline_at` has been reached or passed, team members may not create a new Sprint submission or resubmission. Remaining `ACTIVE` until Facilitator/Admin performs the terminal transition does not grant additional team work/submission time.
- A submission validly created before `deadline_at` may still be reviewed by Facilitator/Admin after the deadline.
- After the allowed ProjectRun deadline has passed, if the project has not been successfully accepted as complete, Facilitator/Admin may mark the ProjectRun `INCOMPLETE`.
- Until Facilitator/Admin performs that terminal transition, the ProjectRun remains `ACTIVE` and continues to count under the one-active-ProjectRun rule, but no automatic extra time is granted and the post-deadline team submission/resubmission block still applies.
- MVP has no Extension workflow, deadline compensation, replacement, failure, trust, or disciplinary workflow. Those areas are handled only by the deferred/post-MVP rules below.

## 16. Sprint Runtime

Allowed Sprint states:
- `LOCKED`
- `ACTIVE`
- `SUBMITTED`
- `UNDER_REVIEW`
- `CHANGES_REQUESTED`
- `COMPLETED`

Main flow:
`LOCKED → ACTIVE → SUBMITTED → UNDER_REVIEW`

Then either:
`UNDER_REVIEW → COMPLETED`

or:
`UNDER_REVIEW → CHANGES_REQUESTED → SUBMITTED → UNDER_REVIEW`

Rules:
- Sprint N+1 cannot be opened before Sprint N is `COMPLETED`.
- This applies even if future work is technically independent.
- Only Facilitator/Admin may open the next Sprint.
- One designated team member submits the Sprint.
- Submission is not approval.
- Requested fixes happen inside the same Sprint.
- Finishing early does not move future planned deadlines earlier.
- Finishing late without an explicitly approved future schedule adjustment does not automatically move future deadlines later.
- ProjectRun time continues to pass while a Sprint is waiting for review or changes.
- A team that submits late risks consuming time that would otherwise have been available for later Sprints; the platform does not automatically compensate for that delay in the MVP.
- For a ProjectVersion whose required scope includes deployment, every Sprint must end with delivery/deployment of the current integrated increment before Sprint submission. Deployment must be progressive and must not be postponed entirely to the final Sprint.
- In the MVP, the final Sprint is deterministically the `SprintTemplate` with the highest `sequence` within the fixed ProjectVersion used by the ProjectRun.
- Do not create a separate FinalSprint model, an `is_final` flag, or a separate final-Sprint reference solely to represent this MVP rule.
- The final Sprint includes the final deployment/result that Facilitator/Admin reviews against the ProjectVersion requirements before the ProjectRun can be completed.
- Sprint submission history should be append-only.

Exact submission evidence fields are not finalized.
Keep the model minimal/extensible and do not build GitHub automation.

## 17. Review / Facilitator

MVP review is manual.

No AI reviewer or automated code review.

In the MVP, Facilitator/Admin authority uses the existing Django staff/admin authorization mechanism. Facilitator is not a new participant platform role, and no separate Facilitator role/model/permission architecture should be introduced for the MVP.

Facilitator/Admin controls:
- opening Sprint
- review transitions
- requesting changes
- completing Sprint
- controlled ProjectRun status changes
- marking an overdue, unfinished ProjectRun `INCOMPLETE` in the MVP

Rules:
- MVP ProjectRun terminal transitions are manual; do not add automatic deadline-expiration jobs merely to change ProjectRun state.
- Completing the final Sprint successfully must complete the ProjectRun in the same transaction.
- Normal users do not perform management transitions.
- Facilitator review turnaround communicated to MVP users is an operational expectation, not a guaranteed SLA and not a source of automatic deadline compensation.

## 18. Deferred / Not Implemented Now

Do NOT implement now:
- Assessment
- Qualification
- Candidate Pool
- Matching algorithm
- runtime Task lifecycle
- Trust algorithm
- Warning/removal disciplinary workflow
- post-start team-member departure/replacement/recovery workflow
- Extension workflow, including Regular Extension and Emergency Extension
- AI review
- built-in chat
- GitHub automation

Do not create speculative tables/abstractions for these deferred areas.

### Post-MVP Extension direction

Extension is completely deferred until after MVP.

- No Extension workflow, including Regular Extension or Emergency Extension, is part of the MVP.
- Do not implement or create speculative models, tables, fields, migrations, APIs, services, permissions, states, timers, background jobs, or abstractions for Extension in the MVP.
- Ordinary Sprint lateness or passing a deadline does not automatically create or imply an Extension.
- All Extension product rules, including type, count/limits, duration, eligibility, allowed Sprint(s), request timing/cutoff, approval/rejection mechanics, deadline effects, repeatability/stacking, terminal behavior, persistence/API design, permissions, and notifications, are intentionally unresolved and will be finalized after MVP.
- Do not treat any previous Extension proposal or assumption as an accepted product rule unless it is explicitly finalized after MVP and added to this file.

### Post-MVP member departure / replacement direction

The following is future product direction only and must not be implemented in the MVP:

- MVP does not implement post-start replacement, leave recovery, Candidate Pool, or Matching.
- For the explicitly discussed future case where two active members leave after a ProjectRun has started, the intended direction is to attempt role-preserving replacement while the remaining member stays in the same ProjectRun.
- A future replacement flow must preserve all historical TeamMember snapshots and Sprint/submission history.
- Previously identified reserve candidates may be considered first if they are still eligible and available; otherwise a new eligible user may be selected. This must not silently become an automated Matching algorithm.
- Replacement candidates must satisfy the same role, stack, uniqueness, and one-active-ProjectRun rules at the time of replacement.
- If the entire active team leaves a ProjectRun, the intended future outcome is a terminal `FAILED` ProjectRun. `FAILED` is not an MVP state and must not be added yet.
- If replacement cannot be completed within the future allowed replacement window, the intended future outcome may also be `FAILED`; the exact replacement window and mechanics are not finalized.
- A member who remains and loses the ProjectRun only because other members left and could not be replaced must not receive a negative Trust consequence merely for that failure.
- A voluntary departure may become a negative Trust input for the member who left, but the exact Trust scoring/algorithm is not finalized and must not be implemented now.
- The behavior for every partial-departure case, including a single member leaving, invitation/acceptance mechanics, reserve ordering, and timing rules remains unresolved.

## 19. Current Unresolved Decisions

Do not invent behavior for:
- exact Helpdesk Sprint-by-Sprint work distribution
- detailed Healthchecks Lite scope
- detailed Event Ticketing Lite scope
- final Qualification scope
- Matching algorithm
- whether stack affects future Matching pools
- exact Sprint submission evidence fields
- all Extension product and technical rules, including types, count/limits, duration, eligibility, allowed Sprint(s), request timing/cutoff, approval/rejection mechanics, deadline effects, repeatability/stacking, terminal behavior, persistence/API design, permissions, and notifications; Extension is entirely post-MVP and no behavior should be invented or implemented now
- post-start member departure/replacement mechanics, including the single-member case, replacement window, reserve selection/ordering, invitation/acceptance, and recovery timing
- future `FAILED` ProjectRun transition details beyond the accepted direction that full-team departure should eventually fail the run
- warning thresholds/timers
- Trust algorithm and exact scoring effects
- exact notification timing
- exact deployment provider

The MVP ProjectRun state machine itself is finalized as `ACTIVE`, `COMPLETED`, and `INCOMPLETE`. Do not add more MVP ProjectRun states.

## 20. Agent Rules

- Treat this file as the product/domain source of truth.
- Do not silently change accepted rules.
- Do not turn proposals into product rules.
- Do not invent unresolved behavior.
- If an unresolved rule blocks implementation, report it.
- If it does not block implementation, choose the least-committal technical design.
- Platform backend uses Python + Django + DRF + PostgreSQL.
- Participant project technologies such as .NET or MySQL must never be confused with the platform backend/database.
- Work only on backend code, database models/migrations, APIs, permissions/security, and tests.
- Do not work on Docker, Git/GitHub setup, CI/CD, deployment automation, or frontend implementation.

## Database Execution & Testing Boundary
# Database, Migration, and Testing Responsibility

Follow these rules for all current and future implementation phases.

## Core responsibility boundary

You are responsible for designing and implementing the complete backend,
including all database-related application logic.

I am responsible only for executing changes against my real local PostgreSQL
development environment and performing the final PostgreSQL-dependent
validation.

This restriction is about DATABASE EXECUTION, not database design.

Do not reduce, simplify, mock away, or avoid proper database logic because
you are not allowed to operate my real PostgreSQL database.


# 1. What you ARE responsible for

You are fully responsible for implementing:

- Django models
- model relationships
- ForeignKey / OneToOne / ManyToMany relationships
- database constraints
- UniqueConstraint
- CheckConstraint
- indexes
- PostgreSQL-compatible field design
- deliberate `on_delete` behavior
- transaction boundaries
- `transaction.atomic`
- `select_for_update`
- concurrency protection
- race-condition prevention
- idempotency logic
- querysets
- selectors
- optimized database reads
- N+1 prevention
- service-layer database workflows
- serializers
- validation
- APIs/views
- authentication
- authorization
- permissions
- object-level authorization
- business rules
- database-backed workflow/state logic

You must design these as if they will run on real PostgreSQL.

PostgreSQL is the source-of-truth database engine for this project.


# 2. Django migration files

You ARE responsible for Django migration SOURCE FILES.

When model/schema changes require migrations, you should:

- create the appropriate migration files,
- inspect them,
- make sure they match the intended model changes,
- avoid unnecessary/destructive migrations,
- report exactly which migration files were created or modified.

Migration files are part of the source code and therefore belong to your
implementation responsibility.

However:

YOU MUST NOT APPLY those migrations to my real development database.

Creating a migration file is allowed.

Executing that migration against `platform_db` is not allowed.


# 3. Real PostgreSQL database boundary

My real development database is:

    platform_db

You MUST NOT:

- connect to `platform_db`,
- inspect data inside `platform_db`,
- modify `platform_db`,
- run `manage.py migrate` against `platform_db`,
- create tables inside `platform_db`,
- alter tables inside `platform_db`,
- insert test data into `platform_db`,
- reset `platform_db`,
- flush `platform_db`,
- drop `platform_db`,
- recreate `platform_db`,
- create or remove databases on my PostgreSQL installation,
- alter PostgreSQL users or roles,
- request my real PostgreSQL password,
- use my real PostgreSQL credentials.

The real development database is developer-controlled.


# 4. Do NOT create disposable PostgreSQL environments

Do not create or manage disposable PostgreSQL instances anymore.

Specifically, do NOT:

- run `initdb`,
- start PostgreSQL processes,
- stop PostgreSQL processes,
- use `pg_ctl`,
- allocate temporary PostgreSQL ports,
- create temporary PostgreSQL clusters,
- create temporary PostgreSQL data directories,
- create disposable validation databases,
- delete PostgreSQL temp directories,
- perform PostgreSQL cleanup operations.

Do not create another PostgreSQL environment just to run tests.

Database execution will be handled manually by me.


# 5. Testing responsibility

You are still responsible for TESTING THE CODE.

Do not interpret the database restriction as permission to skip tests.

You must:

- write all appropriate automated tests,
- write unit tests,
- write service-layer tests,
- write serializer/validation tests,
- write permission/security tests,
- write API tests,
- write model tests,
- write database constraint tests,
- write transaction tests,
- write concurrency tests where required,
- write regression tests for bugs you fix,
- maintain high-value test coverage for implemented behavior.


# 6. Tests you should execute yourself

You should execute all tests and validations that can safely run without
creating, modifying, or managing a PostgreSQL database.

Examples include, where applicable:

- pure Python unit tests,
- isolated domain/business-logic tests,
- tests using mocks/fakes only when the external dependency is NOT the
  behavior under test,
- syntax/import validation,
- safe Django system checks that do not require database access,
- static migration/model consistency inspection,
- other non-database validation.

If a test genuinely requires PostgreSQL, write it completely but do not
execute it yourself.


# 7. Do NOT weaken database tests

This rule is critical.

Do NOT replace real PostgreSQL-dependent behavior with mocks merely so that
you can execute the test yourself.

For example, behavior involving:

- `transaction.atomic`,
- `select_for_update`,
- row locking,
- concurrency,
- race conditions,
- database uniqueness enforcement,
- database constraints,
- foreign-key enforcement,
- indexes,
- transaction rollback,
- PostgreSQL-specific behavior,

must remain real database tests when database behavior itself is what needs
to be verified.

Write those tests correctly for PostgreSQL.

I will execute them manually.

A test that requires PostgreSQL but has not yet been manually executed must
be reported as:

    WRITTEN - MANUAL POSTGRESQL VALIDATION REQUIRED

Do not report it as passed.


# 8. Database-backed Django/API tests

Many Django tests naturally require a database.

You should still write them completely.

Examples:

- registration persisted to database,
- login using stored users,
- permission checks against stored objects,
- serializer create/update behavior,
- API CRUD behavior,
- model constraints,
- relationships,
- transactions,
- workflow state transitions.

If these tests require PostgreSQL, do not avoid writing them.

Instead:

1. Write them.
2. Inspect them.
3. Report them as requiring manual PostgreSQL execution.
4. Give me the exact pytest command to run.


# 9. Manual database validation is my responsibility

When database validation is required, I will manually perform commands such
as:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py migrate --plan
    python manage.py migrate
    python -m pytest <relevant tests> -q
    python -m pytest -q

I will provide you the resulting output if anything fails.

You must then analyze the real output and fix the implementation or tests.

Do not assume a database-dependent test passed until I explicitly confirm
the successful result.


# 10. Full test suite

You are responsible for maintaining the full test suite.

I am responsible for executing the final full suite when it requires
PostgreSQL.

Therefore, at the end of an implementation unit:

- you must tell me the exact full-suite command,
- I will execute it,
- I will confirm whether it passed,
- only then may database-integrated validation be considered complete.

Do not claim:

    "All tests passed"

if you only ran the non-database subset.

Instead report clearly, for example:

    Non-database tests: 18 passed
    PostgreSQL-dependent tests: 12 written, manual execution required
    Full suite: manual PostgreSQL execution required


# 11. Required workflow for database-sensitive changes

Whenever you implement a database-sensitive unit of work, follow this exact
workflow:

STEP 1
Implement the complete feature.

STEP 2
Implement the complete database design and business logic.

STEP 3
Create/update the necessary Django migration files.

STEP 4
Write all relevant automated tests, including PostgreSQL-dependent tests.

STEP 5
Run every safe non-database test/validation you can run yourself.

STEP 6
Perform a code review of:
- models,
- migrations,
- constraints,
- transactions,
- queries,
- permissions,
- tests.

STEP 7
Stop before touching a real or temporary PostgreSQL database.

STEP 8
Give me a manual validation report containing:

- implementation summary,
- files created,
- files modified,
- migration files created/modified,
- non-database tests executed,
- their exact results,
- PostgreSQL-dependent tests written but not executed,
- exact migration commands I should run,
- exact focused pytest command I should run,
- exact final full-suite command I should run.

STEP 9
Wait for my result.

STEP 10
If I report a migration/test failure:
- analyze the output,
- fix the code/migrations/tests,
- provide updated manual validation commands,
- wait for validation again.

Do not continue past an important database-sensitive boundary until I
confirm the PostgreSQL validation succeeded.


# 12. Do not postpone database correctness

Even though I execute PostgreSQL validation manually, you must consider
database correctness while writing the code.

Do not write large amounts of dependent code on top of an unverified
database assumption.

For significant database-sensitive implementation units, stop at a sensible
validation boundary and ask me to run the migration/tests before continuing.

Examples of important validation boundaries include:

- introducing a major new group of models,
- introducing critical constraints,
- changing ownership/relationship rules,
- adding transaction-sensitive workflows,
- adding locking/concurrency logic,
- introducing major schema changes.


# 13. PostgreSQL-specific implementation

Do not change the application to SQLite merely to simplify your local
testing.

Do not write code based on SQLite behavior and assume PostgreSQL will behave
the same.

The target database remains PostgreSQL.

Design and test code should reflect PostgreSQL semantics where relevant.


# 14. Secrets

Do not request, read, print, expose, modify, or copy developer-owned secrets.

Do not inspect `.env` for credentials.

You may inspect `.env.example` or application configuration code to
understand the expected environment-variable names.

Never hard-code passwords, API keys, Django secret keys, or other secrets
into source code, migration files, tests, logs, or prompts.


# 15. Reporting accuracy

Be precise about validation status.

Use these meanings:

PASS
= you actually executed the test/check and it exited successfully.

WRITTEN - MANUAL POSTGRESQL VALIDATION REQUIRED
= the test exists but I still need to execute it against PostgreSQL.

MANUALLY VERIFIED
= I explicitly reported that the PostgreSQL-dependent validation passed.

Do not infer or fabricate test success.


# Final responsibility split

CODE / DATABASE LOGIC:
    Codex

DATABASE ARCHITECTURE:
    Codex

MODELS:
    Codex

CONSTRAINTS / INDEXES:
    Codex

TRANSACTIONS / LOCKING / CONCURRENCY LOGIC:
    Codex

MIGRATION SOURCE FILES:
    Codex

ALL TEST CODE:
    Codex

NON-DATABASE TEST EXECUTION:
    Codex

REAL POSTGRESQL MIGRATION EXECUTION:
    Developer

POSTGRESQL-DEPENDENT TEST EXECUTION:
    Developer

FINAL FULL-SUITE POSTGRESQL VALIDATION:
    Developer

REAL DATABASE CREDENTIALS:
    Developer only


The purpose of this separation is to avoid PostgreSQL environment-management
problems while preserving full responsibility for correct database design,
backend implementation, migration design, and test coverage.

Do not simplify the architecture or reduce test quality because PostgreSQL
execution is manual.
