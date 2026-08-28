# CURRENT_STATE.md

> Source of truth for the current implementation and validation state.
> Keep this file focused on where the project is now.
> Stable product/architecture/execution rules belong in `PROJECT_RULES.md`.

## Current Workstream

### Phase 10 — Platform Internal Django Admin / CRM
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- MVP backend core lifecycle and Helpdesk Lite canonical Sprint content population are complete from the preceding workstreams.
- All current MVP account/profile, project/content, formation, team, ProjectRun, SprintRun, Ready Check, and submission models now have an internal Django admin inspection surface.
- Project definitions, participant profile data, historical snapshots, Ready Checks, Teams, and submission history are read-only through admin forms.
- Sprint review transitions and overdue ProjectRun `INCOMPLETE` terminalization are exposed only through actions that call the existing validated services.
- No schema, model, API, runtime-service, frontend, cache, or deferred-workflow change was introduced.

Validation state:
- safe import/compile and Django system checks are complete,
- source-only admin registration/action checks are complete,
- PostgreSQL-backed admin permission, immutability, and lifecycle-action tests are written,
- developer-controlled focused and full-suite PostgreSQL validation is still required.

Immediate goal:
- run the focused Phase 10 admin tests against PostgreSQL,
- run the full suite,
- report the developer results before marking Phase 10 `VALIDATED`.

---

## Validated Backend Phases

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

### Phase 2 — Profiles / Roles / Skills
Status: `VALIDATED`

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused Phase 2 tests passed
- full suite passed

---

### Phase 3 — Project Catalog
Status: `VALIDATED`

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

---

### Phase 4 — Sprint Templates / Static Sprint Work Scheduling
Status: `VALIDATED`

Implemented:
- SprintTemplate
- optional ProjectTaskTemplate.sprint_template relationship
- scheduled and unscheduled static work content
- SprintTemplate PROTECT behavior when referenced by work content
- PostgreSQL integrity enforcement for ProjectTaskTemplate/SprintTemplate ProjectVersion consistency
- no runtime Task lifecycle, Kanban, Todo workflow, or task completion percentages

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- full suite passed

---

### Phase 5 — Team Formation / Ready Check
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
- concurrency-safe confirmation using `transaction.atomic` and `select_for_update`
- `ready_confirmed_at` recorded exactly once after all three current members confirm
- Team + ProjectRun creation exactly once after all three current members confirm
- TeamMember role and selected-stack historical snapshots
- database-enforced one-active-ProjectRun membership per user
- no Candidate Pool or Matching implementation

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused formations tests passed
- full suite passed

---

### Phase 6 — ProjectRun Workspace Read APIs + Minimal Sprint Runtime
Status: `VALIDATED`

Implemented:
- active ProjectRun dashboard/workspace read APIs
- SprintRun runtime foundation
- Sprint list/detail APIs
- allowed Sprint state transitions
- Facilitator/Admin-controlled management transitions
- team-member Sprint submission
- append-only Sprint submission history
- member-relevant static Sprint/workspace content filtering
- no runtime Task lifecycle, Kanban, Todo workflow, GitHub automation, or AI review

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused formations/runtime tests passed
- full suite passed

---

### Phase 7 — MVP ProjectRun Terminal Lifecycle & Deadline Enforcement
Status: `VALIDATED`

Implemented:
- immutable ProjectRun deadline derived from the fixed ProjectVersion duration
- exact ProjectRun states: `ACTIVE`, `COMPLETED`, and `INCOMPLETE`
- inclusive Sprint submission/resubmission cutoff at the ProjectRun deadline
- post-deadline review of evidence submitted before the deadline
- canonical final Sprint detection by highest SprintTemplate sequence
- atomic final Sprint and ProjectRun completion
- staff-only manual `INCOMPLETE` transition after the deadline
- atomic TeamMember membership closure for terminal ProjectRuns
- terminal Sprint transition/submission blocking and history preservation
- PostgreSQL constraints/triggers for lifecycle, deadline, and final-Sprint coherence
- no automatic expiration job, Extension workflow, or runtime Task lifecycle

Validation:
- migrations applied successfully
- PostgreSQL validation completed
- focused database/lifecycle tests passed
- full suite passed

---

### Phase 8 — MVP Backend Integration, Security & Lifecycle Hardening
Status: `VALIDATED`

Implemented:
- end-to-end lifecycle, authorization, deadline, transaction, and query audit
- inactive-user guards in Ready Check response and Sprint submission services
- ProjectVersion row locking during ProjectRun initialization
- immutable ProjectVersion definitions once referenced by a TeamFormation/ProjectRun
- exact SprintTemplate/SprintRun set integrity for each ProjectRun
- concurrent final Sprint completion regression coverage
- expanded participant management-action authorization coverage
- bounded dashboard/workspace query regression coverage
- no new product features or deferred-feature architecture

Validation:
- PostgreSQL-dependent validation completed by the developer
- full suite re-run successfully
- no known Phase 8 validation blocker remains

---

## Static Sprint Content Architecture Verification
Status: `VALIDATED / READY FOR HELPDESK CONTENT POPULATION`

The architecture verification concluded:
- cross-role content leakage prevented: YES
- cross-stack content leakage prevented: YES
- shared content semantics proven: YES
- deterministic ordering proven: YES
- ProjectVersion isolation proven: YES
- Helpdesk-specific hard-coding found: NO

Verified content semantics:
- shared/team-wide static content is explicitly represented by `role = NULL` and `technology_stack = NULL`
- the database/domain integrity rules prevent ambiguous stack-scoped shared rows (`role = NULL`, `technology_stack != NULL`)
- generic role-specific content uses a role with `technology_stack = NULL`
- stack-specific role content may use a matching role + technology stack
- runtime visibility includes shared content before role/stack-specific filtering
- role/stack content is filtered against the requesting TeamMember
- static work ordering is deterministic through `position`, then `id`
- ProjectRun runtime content resolves through the exact `project_run.project_version`
- no Helpdesk slug/name/sequence-specific content branching was found in the relevant paths

Architecture audit change impact:
- production behavior changed: NO
- schema changed: NO
- API changed: NO
- caching infrastructure added: NO
- media infrastructure added: NO
- the focused implementation change from the audit was regression coverage only

Remaining non-blocking concerns:
- definition-completeness enforcement remains a future/general concern; for the current Helpdesk population, completeness should be verified with focused dataset/API regression coverage rather than a speculative platform-wide framework
- project-specific media references remain a future concern; the current hybrid architecture leaves a clean extension seam and no media model/storage/CDN implementation is required now
- caching remains evidence-driven; no current performance finding justifies Redis/Memcached or a custom cache layer

---

## Finalized Helpdesk Lite Sprint Plan

Current Level 1 specification:
- duration: 6 weeks
- Sprint count: 6
- planned Sprint duration: 7 days each
- role-specific content: Backend Developer, Frontend Developer, Product Designer
- shared/team-wide content: `role = NULL`, `technology_stack = NULL`
- current accepted role-specific work content is stack-neutral: `technology_stack = NULL`

Canonical Sprint schedule:
1. `Product Foundation & Authentication` — offset 0, duration 7
2. `Requester Ticket Experience` — offset 7, duration 7
3. `Agent Workflow` — offset 14, duration 7
4. `Collaboration & Ticket History` — offset 21, duration 7
5. `Findability & Product Hardening` — offset 28, duration 7
6. `Final Integration & Production Delivery` — offset 35, duration 7

Content principles:
- static Sprint content is informational/versioned content, not a runtime Jira/Trello Task system
- testing is introduced throughout the Sprint progression rather than postponed to Sprint 6
- every Sprint should produce/review the current integrated increment
- Sprint 6 is for final integration, verification, documentation, deployment, and delivery quality; it must not become a new-feature Sprint
- exact row-level titles, descriptions, positions, roles, and Sprint briefs supplied in the canonical population dataset are authoritative for this current Helpdesk ProjectVersion

---

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

---

## Current Git / Repository State

Before continuing implementation, verify the real repository state instead of assuming it:

```powershell
git status
git branch --show-current
git log --oneline -5
```

Do not infer:
- current branch
- staged files
- uncommitted changes
- latest commit
- migration application state

Verify them when relevant.

---

## Immediate Next Action

Validate the Phase 10 internal Django admin implementation against PostgreSQL.

Required validation sequence:
1. Run Django `check` and `makemigrations --check --dry-run`.
2. Run the focused admin tests in `tests/formations/test_admin.py`.
3. Run the existing formation lifecycle/service tests together with the new admin adapter tests.
4. Run the full suite.
5. Report the exact developer results before changing Phase 10 from manual-validation-pending to `VALIDATED`.

---

## Current Known Blockers

- No Phase 10 implementation blocker is known.
- PostgreSQL-backed admin security and lifecycle-action validation is pending developer execution.
- TeamFormation creation, Ready Check replacement, and opening a Sprint remain available through their existing validated staff APIs rather than unsafe or input-incomplete bulk admin actions.

---

## Remaining MVP Work After Phase 10 Validation

Expected remaining workstreams include:
- participant-facing frontend MVP
- final end-to-end/manual MVP acceptance testing and bug fixes

Do not confuse the platform internal Facilitator/Admin operational UI with the Helpdesk participant project's out-of-scope internal Admin UI.

---

## Validation Status Rules

Use these meanings consistently:

- `VALIDATED` — required manual PostgreSQL validation has completed successfully.
- `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING` — code/migrations/tests exist, but required PostgreSQL validation is not yet confirmed.
- `NOT STARTED` — implementation has not begun.
- `IN PROGRESS` — implementation has started but the phase is not complete.
- `READY TO IMPLEMENT` — prerequisites/architecture are validated and the next implementation unit may begin.

Never mark a PostgreSQL-dependent implementation unit as validated based only on Codex's non-database checks.

---

## Handoff Rule

For a new ChatGPT/Codex conversation:

1. Provide `PROJECT_RULES.md`.
2. Provide this `CURRENT_STATE.md`.
3. Provide the canonical Helpdesk Sprint-content dataset when working on content population.
4. Treat:
   - `PROJECT_RULES.md` as the source of truth for accepted product, architecture, scope, and execution rules.
   - `CURRENT_STATE.md` as the source of truth for current implementation and validation status.
   - the supplied canonical Helpdesk dataset as the authoritative row-level content for the target Helpdesk ProjectVersion.
5. Do not assume an unvalidated database write has happened.
6. Continue from **Immediate Next Action**.
7. Do not silently change accepted rules or content. Proposed changes must be reported explicitly with rationale and trade-offs.

## Update Policy

Update this file after meaningful state transitions, especially:
- canonical Helpdesk content is populated
- PostgreSQL-dependent population/data tests are manually verified
- the final full suite passes
- the next workstream starts
- a real blocker appears or is resolved

Do not add long-term product rules here. Put those in `PROJECT_RULES.md`.

We are starting the next backend phase.

# Phase 10 — Platform Internal Django Admin / CRM

IMPORTANT CONTEXT:

The previous phases completed the backend MVP core lifecycle and Helpdesk L1 canonical content population.

This phase is NOT participant frontend work.

This phase is NOT the Admin UI inside the Helpdesk participant project.

This phase is an internal operational Django Admin / lightweight CRM layer for platform staff/facilitator operations.

The goal is to make the existing backend operationally manageable through Django's staff/admin interface without bypassing product rules, service-layer validation, database constraints, transactions, or permissions.

Do NOT build a large custom CRM product.

Do NOT implement public frontend.

Do NOT implement Helpdesk product Admin UI.

Do NOT add speculative models or workflows.

============================================================
0. READ AUTHORITATIVE SOURCES FIRST
============================================================

Before changing any code, re-read the CURRENT repository versions of:

1. PROJECT_RULES.md
2. CURRENT_STATE.md

Do not rely on memory from previous phases.

Treat:
- PROJECT_RULES.md as the product/domain/architecture source of truth.
- CURRENT_STATE.md as the implementation and validation source of truth.

Also inspect the existing codebase, especially:

- existing Django admin registrations
- accounts/users/profiles admin
- projects admin
- formations admin
- ProjectTemplate / ProjectVersion
- SprintTemplate / ProjectTaskTemplate
- TeamFormation / Ready Check
- Team / TeamMember
- ProjectRun
- SprintRun
- Sprint submission/review models
- existing services/selectors
- existing permission/service-layer patterns
- existing tests

If PROJECT_RULES.md appears to prohibit a requested item, distinguish carefully between:

- Helpdesk participant-project Admin UI — OUT OF SCOPE
- Platform internal Django staff/admin operations — THIS PHASE

If a real contradiction remains, stop that specific implementation item and report it instead of inventing a rule.

============================================================
1. PHASE GOAL
============================================================

Implement a minimal, safe, staff-only internal Django Admin / CRM layer that lets the platform operator inspect and manage the MVP operational backend.

The admin should support real operational needs for:

- viewing users/profiles/roles/skills where relevant
- viewing project catalog/version/static content
- viewing Helpdesk L1 Sprint content
- managing manual Team Formation / Ready Check operational state if existing backend rules support it
- viewing Teams and TeamMembers
- viewing ProjectRuns
- viewing SprintRuns
- viewing submissions / review history
- performing already-accepted staff/facilitator transitions through existing service-layer logic where appropriate

The key principle:

Django admin may expose operational controls, but it must not become a second source of business logic.

All meaningful state-changing admin actions must call existing application services or reuse the same validated domain logic.

Do NOT directly mutate lifecycle fields in ModelAdmin methods if that bypasses:
- authorization rules
- transaction.atomic
- select_for_update
- terminal-state guards
- deadline enforcement
- ProjectVersion immutability
- TeamFormation/Ready Check constraints
- Sprint Runtime service rules

============================================================
2. HARD SCOPE LIMITS
============================================================

Do NOT implement:

- participant frontend
- custom React/Vue frontend
- Helpdesk product Admin UI
- internal notes
- matching algorithm
- Candidate Pool
- Extension
- Trust
- warnings/removal disciplinary workflow
- replacement/recovery
- AI review
- GitHub automation
- built-in chat
- runtime task system
- custom CMS/media system
- dashboard analytics platform
- Redis/cache layer
- Celery/background jobs
- broad audit/event framework
- new generic permission architecture
- new Facilitator model/role
- new workflow states
- schema changes unless a real admin blocker absolutely requires one

Do NOT redesign models or services.

Prefer Django `ModelAdmin`, list displays, filters, search, readonly fields, inline displays, and carefully controlled admin actions.

============================================================
3. ADMIN COVERAGE AUDIT
============================================================

First inspect what admin registrations already exist.

Report before implementation:

1. Which models are already registered in Django admin.
2. Which important MVP operational models are missing.
3. Which registered admin classes are too weak for operational use.
4. Which admin actions already exist.
5. Which state-changing actions can safely be exposed through existing services.
6. Which actions should remain read-only because no safe service exists yet.

Do not create admin actions for operations unless there is a safe service-layer path.

============================================================
4. ADMIN UX REQUIREMENTS — MINIMAL BUT USEFUL
============================================================

For relevant models, improve Django admin using minimal built-in admin features.

Use appropriate:

- `list_display`
- `list_filter`
- `search_fields`
- `readonly_fields`
- `ordering`
- `date_hierarchy` if useful
- `list_select_related`
- simple inlines only when useful and not risky
- safe links to related objects if existing patterns support it

Focus on staff/facilitator efficiency.

Avoid decorative admin customization.

Avoid custom templates unless there is a strong operational reason.

============================================================
5. MODELS TO REVIEW FOR ADMIN REGISTRATION
============================================================

Inspect actual model names before coding. Do not assume names.

At minimum review admin coverage for these conceptual areas:

## Accounts / Profiles
- User account model, if custom
- Profile
- Role
- TechnologyStack / UserSkill equivalents

Goal:
Staff can inspect users, current selected role/stack data, and relevant profile info.

Avoid allowing casual edits that could corrupt historical snapshots.

## Projects / Content
- Level
- ProjectTemplate
- ProjectVersion
- ProjectRoleRequirement
- allowed stacks/prerequisites if separate models
- SprintTemplate
- ProjectTaskTemplate

Goal:
Staff can inspect project definitions and canonical Helpdesk content.

Respect ProjectVersion immutability once referenced.

If project definition models are editable through admin while unreferenced, that is acceptable only if existing rules allow it.

If referenced, admin must not bypass database triggers/immutability.

Prefer read-only for risky versioned content unless current architecture safely supports edits.

## Formation / Ready Check
- TeamFormation
- Ready Check / ReadyCheckMember equivalents
- proposed members / slots

Goal:
Staff can inspect manual formation state and Ready Check status.

If current services support staff-created formation, admin may expose the minimum safe create/view tooling.

If not, keep creation out of admin and report the gap.

Do not invent matching/candidate-pool behavior.

## Team / ProjectRun
- Team
- TeamMember
- ProjectRun

Goal:
Staff can inspect active/terminal runs, team members, role/stack snapshots, deadlines, state, and related SprintRuns.

Do not let admin mutate terminal state directly except through safe service-layer actions.

## Sprint Runtime / Review
- SprintRun
- submission / review / history models

Goal:
Staff can inspect Sprint state, submission state/history, designated submitter, deadlines, and review status.

Admin may expose staff actions only if they call the existing services safely.

Potential actions to inspect for safe exposure:
- open next Sprint
- mark submitted Sprint under review
- request changes
- complete Sprint
- mark ProjectRun INCOMPLETE

Only implement an admin action if:
- the product rule exists,
- the service already exists or can be minimally reused without duplicating domain logic,
- the action enforces staff-only access,
- the action preserves transaction/locking behavior,
- tests can cover it.

If any action lacks a safe service path, report it instead of implementing unsafe direct mutation.

============================================================
6. STATE-CHANGING ADMIN ACTION RULES
============================================================

Any state-changing admin action must follow these rules:

- only staff/admin can execute it
- call existing service-layer functions wherever possible
- do not duplicate state transition logic inside admin.py
- do not bypass `transaction.atomic`
- do not bypass `select_for_update`
- do not bypass terminal guards
- do not bypass deadline guards
- do not bypass designated submitter or participant rules where relevant
- do not mutate historical snapshots
- do not alter append-only submission history
- do not change ProjectVersion definitions once referenced
- show clear success/error admin messages
- handle validation/domain errors gracefully
- fail closed, not open

Admin should be an operational surface over the same backend rules, not a privileged loophole.

============================================================
7. PROJECTVERSION / CONTENT IMMUTABILITY
============================================================

Be very careful with admin edit permissions for:

- ProjectVersion
- SprintTemplate
- ProjectTaskTemplate
- role requirements
- allowed stacks
- prerequisites

Phase 8 introduced/validated immutability for referenced ProjectVersion definitions.

Admin must respect that.

If the database already enforces immutability through triggers, do not try to bypass them.

Optionally improve admin readability by showing referenced/immutable status if it can be computed safely and cheaply.

Do not add speculative fields just for this.

If preventing edits in admin requires too much new code, prefer readonly admin behavior for versioned content.

============================================================
8. SECURITY REQUIREMENTS
============================================================

Write tests proving:

- non-staff users cannot access admin
- staff users can access relevant admin pages
- state-changing admin actions reject non-staff users
- admin actions call safe rules and do not bypass service-layer validation
- forbidden transitions remain forbidden through admin
- terminal ProjectRuns remain protected
- ProjectVersion immutability cannot be bypassed through admin
- project content cannot be corrupted through admin editing

Do not rely on Django admin default behavior alone for custom actions.

If using only standard Django admin views with no custom action, minimal access tests may be enough.

If adding actions, write focused tests for each action.

============================================================
9. ADMIN PERFORMANCE / QUERY SANITY
============================================================

Use `list_select_related` or queryset optimization where obvious and useful.

Do not add caching.

Do not add complex query frameworks.

Avoid admin pages that accidentally perform severe N+1 queries for common list views.

If a model has heavy relations, keep list_display modest.

============================================================
10. EXPECTED IMPLEMENTATION STYLE
============================================================

This phase should mostly modify/add:

- `admin.py` files
- admin tests
- maybe small service wrappers only if needed to reuse existing logic cleanly

It should usually NOT modify:

- models
- migrations
- API serializers
- API views
- runtime services
- selectors
- canonical Helpdesk content
- PROJECT_RULES.md
- frontend

If you believe a non-admin file must change, explain exactly why and keep it minimal.

No schema migration is expected for this phase unless you find a real blocker.

============================================================
11. TESTING
============================================================

Add focused tests for admin registration, permissions, and any custom admin action.

Relevant test types may include:

- `admin_client` access tests
- staff vs non-staff admin access
- ModelAdmin changelist/detail availability
- readonly field behavior where important
- admin action success path
- admin action invalid transition path
- admin action permission rejection
- admin action service-layer consistency

Do not over-test Django built-in behavior.

Test custom behavior and security boundaries.

Use existing fixture/helper patterns.

Do not create invalid database states.

Do not weaken constraints to make admin tests pass.

============================================================
12. DATABASE / MIGRATION BOUNDARY
============================================================

Follow PROJECT_RULES.md exactly.

You must NOT:

- connect to my real PostgreSQL database
- apply migrations
- create disposable PostgreSQL
- inspect `.env`
- use real credentials

If no migration is required, say explicitly:

No migration required.

If a migration is somehow required, justify it and create only the migration source file, then stop before DB execution.

Run only safe non-database checks yourself.

PostgreSQL-dependent tests must be written but reported as:

WRITTEN - MANUAL POSTGRESQL VALIDATION REQUIRED

unless I execute them and report success.

============================================================
13. CURRENT_STATE.md
============================================================

Do not mark Phase 10 as validated.

Update CURRENT_STATE.md only according to the established workflow.

If implementation is complete but PostgreSQL/manual validation is pending, state that truthfully.

Do not write MANUALLY VERIFIED unless I explicitly report successful validation.

============================================================
14. COMPLETION REPORT
============================================================

At the end, report with this exact title:

# PHASE 10 PLATFORM INTERNAL DJANGO ADMIN / CRM REPORT

Include:

1. SOURCES READ
2. EXISTING ADMIN COVERAGE FOUND
3. ADMIN COVERAGE ADDED
4. ADMIN ACTIONS ADDED
5. ADMIN ACTIONS DELIBERATELY NOT ADDED
6. SERVICE-LAYER REUSE / SAFETY
7. AUTHORIZATION / SECURITY DECISIONS
8. PROJECTVERSION IMMUTABILITY HANDLING
9. FILES CHANGED
10. FILES CREATED
11. MIGRATIONS CREATED OR CONFIRMATION NONE REQUIRED
12. TESTS ADDED OR UPDATED
13. SAFE CHECKS EXECUTED BY CODEX
14. POSTGRESQL VALIDATION REQUIRED
15. EXACT COMMANDS FOR DEVELOPER TO RUN
16. KNOWN REMAINING ADMIN/CRM GAPS
17. NEXT STEP AFTER SUCCESSFUL VALIDATION

Also explicitly confirm:

- no frontend was implemented
- no Helpdesk product Admin UI was implemented
- no new Facilitator model/role was introduced
- no Extension/Matching/Trust/deferred workflow was implemented
- no ProjectVersion immutability bypass was introduced
- no lifecycle rule was duplicated unsafely in admin

Do not claim full validation until I provide PostgreSQL/manual test results.
