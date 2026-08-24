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
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

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
- safe non-database checks completed
- PostgreSQL migrations and database-backed tests require manual developer execution
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

Review the Phase 5 migrations, including `0003_team_project_run.py` and
`0004_preserve_ready_check_history.py`, before applying changes.

Then:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Run the focused Phase 5 PostgreSQL-dependent tests supplied by Codex.

Finally run the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

After validation:

```powershell
Remove-Item Env:LOAD_LOCAL_ENV -ErrorAction SilentlyContinue
```

## Validation Status Rules

Use these meanings consistently:

- `VALIDATED` — required manual PostgreSQL validation has completed successfully.
- `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING` — code/migrations/tests exist, but required PostgreSQL validation is not yet confirmed.
- `NOT STARTED` — implementation has not begun.
- `IN PROGRESS` — implementation has started but the phase is not complete.

Never mark a PostgreSQL-dependent phase as validated based only on Codex's non-database checks.

Phase 5 — Team Formation / Ready Check
Status: VALIDATED

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused formations tests passed
- full test suite passed



## Phase 6 — ProjectRun Workspace Read APIs + Minimal Sprint Runtime
Status: VALIDATED

Implemented:
- active ProjectRun dashboard/workspace read APIs
- SprintRun runtime foundation
- Sprint list/detail APIs
- allowed Sprint state transitions
- Facilitator/Admin-controlled management transitions
- team-member Sprint submission
- append-only Sprint submission history
- member-relevant static Sprint/workspace content filtering
- no runtime task lifecycle, Kanban, Todo workflow, GitHub automation, or AI review

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- formations tests passed (83 passed)
- full test suite passed (233 passed)


## Phase 7 - MVP ProjectRun Terminal Lifecycle & Deadline Enforcement
Status: IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING

Implemented:
- immutable ProjectRun deadline derived from the fixed ProjectVersion duration
- exact ProjectRun states: ACTIVE, COMPLETED, and INCOMPLETE
- inclusive Sprint submission/resubmission cutoff at the ProjectRun deadline
- post-deadline review of evidence submitted before the deadline
- canonical final Sprint detection by highest SprintTemplate sequence
- atomic final Sprint and ProjectRun completion
- staff-only manual INCOMPLETE transition after the deadline
- atomic TeamMember membership closure for terminal ProjectRuns
- terminal Sprint transition/submission blocking and history preservation
- PostgreSQL constraints/triggers for lifecycle, deadline, and final-Sprint coherence
- no automatic expiration job, extension workflow, or runtime task lifecycle

Validation:
- safe syntax, Django system, migration-state, and pure domain checks completed
- PostgreSQL migration and database-dependent tests pending developer validation
