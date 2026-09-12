# AGENT.md

## Purpose

Default operating rules for Codex in the PROLEARN repository.
Keep every change narrow, testable, and aligned with the current product rules.

## Source of truth

Before implementing:
- Read the current authoritative `PROJECT_RULES`.
- Read the current `CURRENT_STATE`.
- Read `FRONTEND_RULES.md` when frontend work is involved.
- Inspect the actual code/API/tests before assuming behavior.

Do not invent missing product rules.
If a required decision is unresolved, stop and report the blocker.

## Scope discipline

- Implement only the requested task.
- Do not redesign unrelated modules.
- Do not add speculative abstractions, cleanup, refactors, or post-MVP features.
- Do not silently change accepted business rules.
- Do not turn mockups/examples into backend requirements unless explicitly approved.
- Reuse existing architecture and patterns when they are correct.
- Prefer the smallest safe change.

## Database safety

Database/schema changes are NOT implicitly allowed.

Do not change:
- Django models in a way that changes schema
- migration files
- constraints
- indexes
- PostgreSQL triggers/functions
- database relationships
- database-backed invariants

If the requested task requires any database/schema change:
1. STOP before implementing that part.
2. Report exactly why the DB change is required.
3. Report the minimal proposed change and its impact.
4. Wait for explicit approval before continuing.

Never connect to, inspect, modify, migrate, reset, flush, drop, or recreate the user's real PostgreSQL database.

Never create disposable PostgreSQL clusters/databases.

Never request or read real database credentials or secrets.

## Business logic

- Backend is authoritative for lifecycle, permissions, state, deadlines, and security.
- Frontend must not become a second source of business rules.
- Do not hardcode role/project/stack behavior that already belongs to backend data.
- Do not weaken authorization or DB integrity merely to make tests/UI pass.
- Preserve exact ProjectVersion and runtime snapshots where the current domain requires them.
- Treat deferred/post-MVP features as out of scope unless explicitly requested.

## API work

Before using or changing an API:
- Inspect the real serializer/view/service contract.
- Do not guess request or response fields.
- Do not fabricate data for missing API fields.
- If required data is absent, report `API GAP FOUND` instead of inventing a workaround.
- Preserve existing auth, permission, CSRF, and object-scope protections.

## Frontend work

- Focus on correct API connections, loading/error states, refresh behavior, permissions, and flow before polish.
- Keep API/data logic separate from presentation so UI can be redesigned later.
- Do not add fake members, progress, activity, resources, links, states, or metrics.
- Do not duplicate backend authorization in JSX.
- Use the current PROLEARN design system and RTL/Persian conventions when UI work is requested.
- Do not redesign unrelated pages.

## Testing

For every implementation:
- Add or update focused regression tests.
- Preserve valid existing tests.
- Do not weaken tests to force green results.
- Run all safe tests/checks available in the environment.
- If PostgreSQL-dependent tests are required, write them but do not execute them against the user's DB.

Report DB-dependent tests as:
`WRITTEN - MANUAL POSTGRESQL VALIDATION REQUIRED`

Never claim a test passed unless it was actually executed successfully.

## Validation/reporting

At the end of a task, report concisely:
- what changed
- files changed
- APIs/contracts affected
- tests added/updated
- tests actually run and exact results
- PostgreSQL/manual validation still required
- any gaps/blockers
- confirmation that unrelated business rules were not changed

If a task is blocked, stop instead of partially implementing an unsafe solution.

## Documentation

- Update `CURRENT_STATE` only after an approved implementation changes the actual system state.
- Update `PROJECT_RULES` only when the product decision itself has explicitly changed.
- Modify only relevant sections.
- Do not rewrite or translate unrelated content.
- Do not update stale duplicate rules files unless explicitly required.

## Git / commits

- Do not commit unless explicitly asked.
- Do not rewrite history.
- Do not include unrelated local changes in the task.
- If unrelated/manual changes are present, report them instead of absorbing them.

## Security

- Never expose or log passwords, tokens, API keys, secret keys, DB credentials, or private environment values.
- Do not inspect `.env` for secrets; use `.env.example` or configuration code when needed.
- Client-provided identity, timestamps, roles, permissions, and lifecycle state are never authoritative unless the approved API contract explicitly says otherwise.

## Stop conditions

STOP and report before proceeding when:
- a DB/schema change is required
- an unresolved product decision blocks correctness
- a change would weaken security/integrity
- the requested behavior conflicts with authoritative rules
- an unexpected dependency expands the approved scope
- required API/data does not exist and implementing it would expand scope
