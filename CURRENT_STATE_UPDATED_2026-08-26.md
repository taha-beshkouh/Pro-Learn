# CURRENT_STATE.md

> Source of truth for the current implementation and validation state.
> Keep this file focused on where the project is now.
> Stable product/architecture/execution rules belong in `PROJECT_RULES.md`.

## Current Workstream

### Helpdesk Lite — Canonical Sprint Content Population
Status: `READY TO IMPLEMENT`

Current position:
- MVP backend Phases 1–8 are validated.
- The existing static Sprint-content architecture has been audited and verified as compatible with the accepted hybrid content architecture.
- Helpdesk Lite Sprint 1–6 content structure and progression are finalized for the current Level 1 specification.
- Canonical Helpdesk Sprint content has not yet been populated into the platform database in this workstream.
- No current schema, API, caching, or media-infrastructure blocker is known.

Immediate goal:
- populate the accepted Helpdesk Lite SprintTemplate/static work dataset through the existing project-data population mechanism,
- preserve ProjectVersion isolation and existing visibility semantics,
- add/retain only focused regression/data coverage that is actually required,
- perform developer-controlled PostgreSQL validation after the population implementation is ready.

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

Proceed with Helpdesk Lite canonical Sprint-content population.

Required implementation sequence:
1. Read `PROJECT_RULES.md` and this `CURRENT_STATE.md`.
2. Inspect the existing Helpdesk ProjectVersion, SprintTemplate rows, ProjectTaskTemplate/static-work model, serializers/selectors, tests, and the repository's existing seed/data-population mechanism.
3. Reuse the existing population mechanism; do not create a second competing mechanism without a demonstrated blocker.
4. Populate the exact supplied canonical Helpdesk Sprint 1–6 dataset.
5. Do not invent, rename, redistribute, summarize, or rewrite accepted Sprint/work-item content.
6. Do not create duplicate SprintTemplates or work items if the current ProjectVersion already contains relevant rows; handle existing data deliberately and report conflicts before destructive replacement.
7. Preserve existing semantics:
   - shared: `role = NULL`, `technology_stack = NULL`
   - generic role-specific: role set, `technology_stack = NULL`
   - deterministic `position` ordering
   - exact ProjectVersion association
8. No schema/model/API/lifecycle/cache/media change is expected. If the current architecture cannot represent the supplied dataset, stop and report the exact blocker before changing architecture.
9. Add/update only focused data/API/regression coverage needed to prove the populated content is complete, isolated, ordered, and visible correctly.
10. Stop before writing to the real `platform_db`; provide exact developer-run PostgreSQL population/migration/validation commands according to `PROJECT_RULES.md`.
11. After developer validation, run/confirm the final full suite and then update this file again.

Expected content validation should prove at minimum:
- exactly six Helpdesk Sprints for the target ProjectVersion
- sequences `1..6`
- accepted titles, briefs, offsets, and seven-day durations
- role-specific content exists for all three platform roles in every Sprint
- shared content exists in every Sprint
- stable positions/order
- no cross-role or cross-stack leakage
- no cross-ProjectVersion leakage
- no project-slug/name hard-coding introduced

---

## Current Known Blockers

- No implementation blocker is currently known for Helpdesk Sprint content population.
- Future media references are not a blocker.
- A generic definition-completeness gate is not a blocker.
- Caching is not a blocker and is not currently justified.

---

## Remaining MVP Work After Helpdesk Content Population

Expected remaining workstreams include:
- platform internal Django CRM/Admin completion/audit for Facilitator operations that are actually required by the MVP
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
