# CURRENT_STATE.md

> Source of truth for the current implementation and validation state.
> Keep this file focused on where the project is now.
> Stable product/architecture/execution rules belong in `PROJECT_RULES.md`.

## Current Phase

### Phase 1 — Accounts / Authentication
Status: `VALIDATED`

Implemented:
- Custom User
- email/password registration
- login
- logout
- current-user endpoint
- Django session authentication
- CSRF/session flow
- registration creates an authenticated session

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused accounts tests passed
- full Phase 1 test validation passed

---

Phase 2 — Profiles / Roles / Skills
Status: VALIDATED

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused Phase 2 tests: 49 passed
- full test suite: 74 passed
---
Phase 3 — Project Catalog
Status: VALIDATED

Implemented:
- Level
- ProjectTemplate
- ProjectVersion
- ProjectRoleRequirement
- ProjectRoleAllowedStack
- RolePrerequisite
- RoleTechnologyStack
- role-aware project list/detail APIs
- Helpdesk Lite published ProjectVersion
- Healthchecks Lite and Event Ticketing Lite templates without fabricated versions

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- full suite passed


Phase 4 — Sprint Templates / Static Sprint Work Scheduling
Status: VALIDATED

Implemented:
- SprintTemplate
- optional ProjectTaskTemplate.sprint_template relationship
- scheduled and unscheduled static work content
- SprintTemplate PROTECT behavior when referenced by work content
- PostgreSQL integrity enforcement for ProjectTaskTemplate/SprintTemplate ProjectVersion consistency
- no SprintRun, submission workflow, transition workflow, or runtime task lifecycle

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- full suite passed

---

Phase 5 — Team Formation / Ready Check
Status: `VALIDATED`

Implemented:
- staff-created TeamFormation for one published ProjectVersion
- exactly three current role slots: Backend, Frontend, Product Designer
- unique current users and roles per formation
- project-role stack validation and stackless-role enforcement
- 48-hour Ready Checks
- member-only confirm/decline actions
- same-role replacement after decline or expiration
- historical Ready Check snapshots for replaced slots
- concurrency-safe confirmation using transaction.atomic and select_for_update
- ready_confirmed_at recorded exactly once after all three current members confirm
- Team + ProjectRun creation exactly once after all three current members confirm
- TeamMember role and selected-stack historical snapshots
- database-enforced one-active-ProjectRun membership per user
- no Candidate Pool or Matching implementation

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused formations tests passed
- full test suite passed

---

Phase 6 — ProjectRun Workspace Read APIs + Minimal Sprint Runtime
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Implemented:
- current-member dashboard and workspace read APIs
- current-member Sprint list and detail APIs
- historical TeamMember role and selected-stack snapshots in workspace responses
- role/selected-stack-scoped static work content
- SprintRun schedule snapshots initialized from SprintTemplate definitions
- exact six-state Sprint transition workflow
- Facilitator/Admin-only opening and review transitions
- one designated current TeamMember submission rule
- append-only SprintSubmission evidence history
- transaction.atomic and select_for_update transition services
- sequential Sprint opening and fixed planned deadline enforcement
- PostgreSQL constraints/triggers for runtime identity, schedule, sequencing, transitions, submitter compatibility, and append-only history
- no runtime task lifecycle or other deferred feature implementation

Validation:
- safe syntax/import compilation passed
- Django system check passed
- migration/model state comparison passed with no pending model changes
- 13 pure Sprint domain tests passed
- 83 formation tests collected successfully
- PostgreSQL migration application and database-dependent tests are pending developer validation

## Current Environment

Development environment:
- Windows
- PowerShell
- Python virtual environment: `.venv`
- Django / Django REST Framework
- PostgreSQL 17
- pytest / pytest-django
- uv
- `pyproject.toml`
- `uv.lock`

Real development database:
- database: `platform_db`
- application DB role: `platform_user`

Use the project virtual environment explicitly when interpreter ambiguity matters:

```powershell
.\.venv\Scripts\python.exe
```

## Local Environment Loading

Real local `.env` loading is opt-in.

Before developer-controlled PostgreSQL work:

```powershell
$env:LOAD_LOCAL_ENV="1"
```

After database work:

```powershell
Remove-Item Env:LOAD_LOCAL_ENV -ErrorAction SilentlyContinue
```

Do not assume `.env` is loaded unless the developer explicitly enables it.

The database execution and secrets boundary is defined in `PROJECT_RULES.md` and must not be duplicated or weakened here.

## Current Git / Repository State

Before continuing implementation, verify the real repository state instead of assuming it:

```powershell
git status
git branch --show-current
git log --oneline -5
```

Phase 2 implementation should have a Git checkpoint before applying its migrations to the real development database.

Do not infer:
- current branch
- staged files
- uncommitted changes
- latest commit
- migration application state

Verify them when relevant.

## Immediate Next Action

Apply the Phase 6 migration and run the focused formations suite against PostgreSQL.

## Validation Status Rules

Use these meanings consistently:

- `VALIDATED` — required manual PostgreSQL validation has completed successfully.
- `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING` — code/migrations/tests exist, but required PostgreSQL validation is not yet confirmed.
- `NOT STARTED` — implementation has not begun.
- `IN PROGRESS` — implementation has started but the phase is not complete.

Never mark a PostgreSQL-dependent phase as validated based only on Codex's non-database checks.
