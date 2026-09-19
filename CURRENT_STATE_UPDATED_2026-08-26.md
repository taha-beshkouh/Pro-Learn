# CURRENT_STATE.md

> Source of truth for the current implementation and validation state.
> Keep this file focused on where the project is now.
> Stable product/architecture/execution rules belong in `PROJECT_RULES.md`.

## Current Workstream

### Deployment Phase 3 — Production Security and Environment Configuration
Status: `IMPLEMENTED - DATABASE-FREE VALIDATION PASSED - RUNFLARE HOST/PROXY/DATABASE VALIDATION PENDING`

Current position:
- `DJANGO_DEBUG=false` is the explicit production-mode signal. Boolean environment values are parsed strictly; malformed values fail startup instead of silently becoming truthy or falsey, while local development retains `DEBUG=True` defaults.
- production startup requires a nonblank `DJANGO_SECRET_KEY`, explicit non-wildcard `DJANGO_ALLOWED_HOSTS`, and all five PostgreSQL connection values; missing or blank required values fail fast without connecting to a database.
- `DJANGO_CSRF_TRUSTED_ORIGINS` is optional for the same-origin topology, accepts normalized comma-separated full origins, and requires HTTPS origins in production. Session and CSRF cookies are secure in production and cannot be explicitly disabled there; existing SameSite/session/CSRF authentication behavior is unchanged.
- forwarded-protocol trust and Django HTTPS redirects are separate opt-in settings. Redirects require confirmed forwarded-protocol trust to avoid the supported reverse-proxy deployment entering a redirect loop; `USE_X_FORWARDED_HOST` remains disabled.
- HSTS remains intentionally disabled (`SECURE_HSTS_SECONDS=0`, no subdomains/preload) until the real public host, HTTPS termination, and proxy headers are validated. No Runflare hostname, origin, custom domain, or proxy behavior is hardcoded.
- production PostgreSQL remains environment-configured with no SQLite fallback. Database SSL behavior is unchanged and awaits the actual Runflare database contract; no database connection, migration, schema, trigger, or constraint change was made.
- the root `.env.example` documents the production runtime contract. The frontend example now reflects the existing browser-visible, same-origin `/api/v1` default; no absolute production API URL or frontend secret was introduced.

Validation state:
- focused production settings and existing Phase 2 production-serving tests pass together (`51 passed`), covering production fail-fast behavior, strict parsing, secure cookies, proxy controls, PostgreSQL value parsing, SPA/static serving, API/Admin ownership, and CSRF enforcement,
- Django `check` and `makemigrations --check --dry-run` pass with database-free settings; `check --deploy` with safe production placeholders reports only the intentionally deferred HSTS warning,
- all 203 frontend tests, typecheck, lint, and the Vite production build pass; same-origin API behavior remains unchanged,
- real PostgreSQL and Runflare were not accessed. Final public hostname/origin values, forwarded-proto behavior, HTTPS redirect enablement, HSTS rollout, and any provider-required database SSL mode remain manual deployment validation boundaries.

---

### Deployment Phase 2 — Production Process and Combined Django/React Serving
Status: `IMPLEMENTED - LOCAL STATIC/FRONTEND VALIDATION PASSED - LINUX/PROVIDER VALIDATION PENDING`

Current position:
- Gunicorn is the production WSGI server for the synchronous Django application; the provider-independent Linux start command is `gunicorn config.wsgi:application` (bind address, port, and worker count remain deployment settings).
- Vite builds the React frontend to ignored `frontend/dist`. Django serves that generated `index.html` for the root and frontend routes; WhiteNoise serves its hashed `/assets/*` files and current root public files (`favicon.svg`, `icons.svg`) from the same build directory.
- `STATIC_ROOT` is `staticfiles`; `collectstatic` prepares Django/Admin files for WhiteNoise at `/static/*`. The SPA fallback excludes `/api/*`, `/admin/*`, `/static/*`, `/assets/*`, and the root public filenames, so missing backend/static resources do not return SPA HTML.
- Same-origin `/api/v1`, session cookies, CSRF, and frontend credentials behavior remain unchanged. The Vite development server and its API proxy remain available without a production build for normal frontend development.
- Provider-independent build sequence: `uv sync --locked`, `npm ci` in `frontend/`, `npm run build` in `frontend/`, then `python manage.py collectstatic --noinput`; start Gunicorn after build artifacts are present. Database migrations are not part of this application build.
- No production hostname, proxy/HTTPS security values, provider configuration, or PostgreSQL setup was added. Gunicorn process execution on Linux and PostgreSQL-backed regression tests remain manual deployment/developer validation boundaries.

Validation state:
- `uv lock` reconciled the new Gunicorn/WhiteNoise dependencies; the developer reported successful `uv sync --locked --extra test` and lock resolution.
- `npm ci`, all 203 frontend tests, typecheck, lint, and Vite production build pass. Focused production serving/static tests pass (18), including current built-asset references; 572 backend tests collect and a 41-test database-free subset passes.
- `manage.py check` and `makemigrations --check --dry-run` pass using `config.settings_static`; WSGI application import passes. No real PostgreSQL connection, migration, or schema change was made.

---

### Deployment Phase 1 — Release Baseline Preparation
Status: `COMMITTED BY DEVELOPER - SAFE VALIDATION PASSED - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- the uncommitted FAQ expand/collapse regression identified during release inspection was fixed before this baseline preparation; its focused regression tests pass,
- `pyproject.toml` and `uv.lock` are the canonical Python dependency source; `uv.lock` was reconciled with the existing `python-dotenv==1.2.2` declaration through `uv lock --offline`, and `uv lock --check --offline` passes,
- `frontend/package-lock.json` remains the canonical Node lock; `npm ci` restores the dependency tree without changing the manifest or lock,
- untracked formations migrations `0011`–`0014` are intended release source in a sequential chain; tracked historical migrations were not modified and the static-settings model-drift check reports no changes,
- the developer committed the intended Phase-1 release baseline before Phase 2 began,
- no Runflare, Cloud VPS, Docker, production-server, static-serving, or provider-specific deployment configuration was implemented in Phase 1.

Validation state:
- frontend: `npm ci`, 203 tests, typecheck, lint, and Vite production build pass; output is `frontend/dist`, which remains ignored,
- backend without PostgreSQL: Django system check and `makemigrations --check --dry-run` pass with `config.settings_static`; 45 selected pure tests pass and 554 tests collect,
- PostgreSQL-backed migration execution and tests remain developer-controlled; Codex did not connect to or change the real PostgreSQL database.

---

### Participant Sprint Submission Form Stale-Value Fix
Status: `IMPLEMENTED - FRONTEND VALIDATED`

Current position:
- a browser-restored/autofilled DOM value could differ from the old `finalCommitUrl` React state because the submit handler read that state, not the visible form control; the same duplicate-state path affected deployment URL and optional evidence,
- Sprint Detail now takes one synchronous `FormData` snapshot from the visible form at submit time for `final_commit_url`, `deployment_url`, and `evidence` in `ACTIVE` Submit, `SUBMITTED` Update Submission, and `CHANGES_REQUESTED` Resubmit,
- empty and invalid current values are validated from that snapshot; failed submissions keep visible edits, authoritative revalidation does not restore an older value, and a successful submit still refetches Sprint Detail before resetting the form,
- `latest_submission` remains historical display data, not a second form-value source; backend request contract, repository matching, submission authorization, state/deadline rules, and append-only history are unchanged; no schema or migration change was made.

Validation state:
- focused Sprint Detail frontend tests pass (36 tests), including visible-value/payload agreement across all three actions, cleared input, backend-error retry, deployment/note edits, and unsaved-edit preservation across revalidation,
- the full frontend suite passes (201 tests), and frontend typecheck, lint, and production build pass; Django system check passes using the repository virtual environment,
- a separate full-suite run had a `RoleSelectionFlow` guest-catalog wait failure; that test passed in isolation and the subsequent full-suite rerun passed without an unrelated code change.

---

### Staff ProjectRun Mark-INCOMPLETE UI
Status: `IMPLEMENTED - FRONTEND VALIDATED - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- the existing locked `mark_project_run_incomplete()` service and Staff-only `POST /api/v1/project-runs/{project_run_id}/incomplete/` action remain the sole terminalization path for an overdue `ACTIVE` ProjectRun,
- the existing Staff active-ProjectRun list now exposes `deadline_at` and read-only, server-derived `can_mark_incomplete`; the service rechecks eligibility under its transaction lock,
- the existing `/staff/formations` area offers a basic confirmation before marking an eligible run incomplete, sends an empty request body, and refetches the authoritative Staff run list after success or rejection,
- an INCOMPLETE run leaves the active list while its Sprint/submission/review history remains available through the existing Staff Sprint read area; Django Admin remains a fallback, not the required normal operational path,
- no automatic deadline terminalization, SprintRun state addition, model/schema/migration change, or Workspace feedback change was introduced.

Validation state:
- focused Staff frontend tests pass (28 tests), the full frontend suite passes (194 tests), and frontend typecheck, lint, and production build pass,
- Django system check and pure ProjectRun lifecycle tests pass (7 tests); PostgreSQL-backed action, security, historical-read, and concurrency tests are written but remain developer-controlled and pending.

---

### ReadyCheck Decline / Expiry Replacement UI
Status: `IMPLEMENTED - FRONTEND VALIDATED - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- participant ReadyCheck keeps the authenticated user's existing Confirm/Decline actions and now explains that Decline exits the current pre-ProjectRun Formation slot; it refetches server state after the response,
- a declined or server-expired ReadyCheck remains the current Formation role slot until Staff replacement, but no longer blocks that user's new readiness or eligible role change; confirmed and unexpired pending slots still block participation elsewhere,
- the participant ReadyCheck selector prioritizes an active invitation over an older declined/expired current slot while retaining the previous terminal-status display when no newer invitation exists,
- the existing Staff replacement API/service still validates exact Formation, role, ProjectVersion, stack, candidate readiness, and active lifecycle before atomically preserving the old ReadyCheck as historical and creating a new pending current slot,
- the existing `/staff/formations` page now displays current ReadyCheck statuses and offers replacement for declined or effectively expired slots using only server-returned readiness candidates and an authoritative Formation refetch,
- Team + ProjectRun startup remains conditional on all three current slots confirming; no Trust/penalty, post-start departure, new schema, or migration was introduced.

Validation state:
- focused ReadyCheck/Staff frontend tests pass (33 tests); the full frontend suite passes (190 tests), as do typecheck, lint, and production build,
- Django system check, Python compilation, and focused backend test collection pass (89 collected); PostgreSQL-backed lifecycle, replacement, and concurrency execution remains developer-controlled and pending.

---

### New ProjectRun Sprint 1 Startup
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- successful full Ready Check still creates the Team and `ACTIVE` ProjectRun exactly once inside the existing transaction,
- SprintRun rows are inserted `LOCKED` with `opened_at = NULL` so the existing PostgreSQL insert invariant remains unchanged,
- only for a newly created ProjectRun, Sprint 1 is then transitioned to `ACTIVE` in that same startup transaction with `opened_at = ProjectRun.started_at`,
- Sprint 2..N remain `LOCKED` with null `opened_at`; completing Sprint N still does not auto-open Sprint N+1, and Staff/Admin still explicitly opens Sprint 2+,
- existing ProjectRun/SprintRun rows are not remediated or reopened by this change.

Validation state:
- focused startup, API, later-Sprint, idempotency, and concurrent final-confirmation regression coverage is updated,
- Django system checks, migration-source drift inspection, Python compile checks, pytest collection, pure Sprint-domain tests, and focused frontend Dashboard tests pass,
- PostgreSQL-backed lifecycle and concurrency execution remains developer-controlled and pending.

---

### MVP Phase A — GitHub Identity and Canonical ProjectRun Repository
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- `UserProfile.github_username` is a nullable, locally validated GitHub identity collected through the authenticated user's own Ready Check confirmation flow rather than registration or generic profile mutation,
- Backend and Frontend Developer confirmation requires an existing or supplied valid GitHub username; Product Designer confirmation remains valid without one,
- a supplied username is persisted in the same transaction as Ready Check confirmation, while decline and server-authoritative expiry behavior remain independent of GitHub identity,
- `ProjectRun.repository_url` is a nullable canonical repository reference so ProjectRun creation remains independent of manual GitHub setup,
- Staff/Admin can list active ProjectRuns with authoritative Team member role/email/GitHub data and register, replace, or explicitly clear the canonical GitHub repository root URL,
- accepted repository aliases are normalized to `https://github.com/<owner>/<repository>` before persistence; non-root GitHub URLs and non-GitHub hosts are rejected,
- application validation plus the pending conditional database uniqueness constraint prevent one canonical repository from being assigned to different ProjectRuns while allowing multiple ProjectRuns with no repository,
- clearing removes only the PROLEARN reference and performs no GitHub repository, collaborator, invitation, or access operation,
- participant Workspace exposes the persisted repository link or a non-error pending-setup state,
- repository creation, invitations, access changes, account verification, OAuth, and all GitHub API operations remain outside PROLEARN.

Validation state:
- model/API/service/frontend implementation and migration source files are complete, including Staff add/edit/clear handling and controlled database-race errors,
- known existing duplicate repository assignments must be corrected manually before applying the new repository-uniqueness migration; no existing data is automatically rewritten or removed,
- Django system checks, migration drift inspection, pure GitHub validator tests, full frontend tests, typecheck, lint, and production build pass,
- no migration has been applied to the developer's PostgreSQL database,
- PostgreSQL-backed Ready Check, repository permission, lifecycle, and full-suite validation remain developer-controlled and pending.

---

### MVP Sprint Submission Authority — Legacy Designation Retained
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- `SprintRun.designated_submitter` remains nullable for legacy/historical compatibility; existing non-null values are preserved, but the field has no current business authority and the current Sprint-opening flow does not write it,
- any authenticated, active, current TeamMember of the exact ProjectRun may submit or resubmit when the existing ProjectRun, Sprint-state, deadline, and transition rules allow it,
- before Staff starts review, a `SUBMITTED` Sprint accepts a newer append-only `SprintSubmission`; the Sprint remains `SUBMITTED`, the new row becomes the deterministic latest review candidate, and all earlier rows remain unchanged,
- once Staff transitions the Sprint to `UNDER_REVIEW`, participant submission is blocked until the existing `CHANGES_REQUESTED` resubmission path becomes available,
- `SprintSubmission.submitted_by` remains the authoritative append-only record of the actual actor for every submission and resubmission,
- Sprint state/timestamp integrity, exact-ProjectRun current-membership enforcement, deadline enforcement, review transitions, terminal ProjectRun behavior, and transaction/row-locking guarantees remain in place,
- dashboard `SUBMIT_SPRINT` and `RESUBMIT_SPRINT` guidance no longer branches by designation; `COLLABORATE` and `ADDRESS_CHANGES` are retained only as designation-free frontend decode aliases.

Validation state:
- the trigger-only migration source, service/API replacement behavior, append-only/history regressions, update-versus-review concurrency coverage, and Sprint Detail `Update submission` flow are implemented,
- Django system checks, Python compilation, PostgreSQL test collection, full frontend tests, typecheck, lint, and production build pass,
- no migration has been applied to the developer's real PostgreSQL database,
- PostgreSQL-specific and final full-suite validation remain developer-controlled and pending.

---

### Structured Sprint Submission Evidence Foundation
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- `ProjectRun.design_workspace_url` is a nullable current canonical design-workspace reference; the exact current Product Designer may set/update it and Staff/Admin may correct it while the ProjectRun is active,
- Backend/Frontend Developers, non-members, and members of another ProjectRun cannot mutate that ProjectRun's canonical design workspace,
- every new participant `SprintSubmission` requires an exact GitHub commit URL from that ProjectRun's canonical repository and a valid deployment URL,
- `design_url_snapshot` is derived server-side from the locked ProjectRun's current design workspace; the client cannot select it, and later workspace changes do not rewrite earlier snapshots,
- existing `evidence` remains an optional participant note, while `submitted_by` and `submitted_at` remain server-authoritative,
- historical SprintSubmission rows remain nullable for the new structured fields and are not backfilled or rewritten,
- the INSERT trigger keeps the existing state/current-membership/timing/terminal protections and additionally rejects new rows with missing structured evidence or a design snapshot different from the current ProjectRun workspace,
- append-only history, pre-review replacement, deadline enforcement, exact-run authorization, and designated-submitter-free submission behavior remain unchanged.

Validation state:
- migration source, service/API contracts, participant Sprint Detail integration, and focused PostgreSQL regression coverage are implemented,
- Django system checks and migration-source drift checks pass; pure URL/serializer tests and the full frontend suite pass, as do frontend typecheck, lint, and production build,
- no migration or PostgreSQL-dependent test has been executed by Codex; developer-controlled migration and PostgreSQL validation remain required.

---

### Participant Design Workspace Management
Status: `ACTIVE-RUN FRONTEND COMPLETE - TERMINAL READ API GAP - BACKEND POSTGRESQL VALIDATION PENDING`

Current position:
- participant Workspace reads the current `ProjectRun.design_workspace_url`, exact TeamMember role snapshot, and ProjectRun state from the existing Workspace API,
- while the run is `ACTIVE`, the current Product Designer can add or replace the design URL through the existing `PATCH /api/v1/project-runs/{project_run_id}/design-workspace/` action; Workspace refetches authoritative data after saving,
- Backend/Frontend Developers see the current link read-only or a role-aware waiting message when it is missing; mutation controls are gated on `ACTIVE`,
- the current participant Workspace selector returns only active ProjectRuns, so historical terminal-run Workspace viewing is not available through this API (no backend read-path change was made in this frontend slice),
- the existing Staff/Admin correction path and backend role/run authorization are unchanged; historical `SprintSubmission.design_url_snapshot` values are not rewritten,
- Sprint Detail now directs users to Workspace when the design prerequisite is missing and distinguishes the Product Designer from other members using exact-run Workspace membership context,
- no Figma integration, design-history model, schema change, migration, or new participant submission contract was introduced.

Validation state:
- focused Workspace and Sprint Detail frontend tests pass (41 tests); the full frontend suite passes (177 tests), as do lint, typecheck through production build, and the production build,
- existing PostgreSQL-backed design-workspace permission, cross-run, terminal-state, and historical-snapshot tests were not run by Codex and remain developer-controlled.

---

### Participant Sprint Structured Submission UI
Status: `FRONTEND IMPLEMENTATION COMPLETE - BACKEND POSTGRESQL VALIDATION PENDING`

Current position:
- the existing participant Sprint Detail route uses the current SprintRun detail and submit APIs for `ACTIVE` Submit, `SUBMITTED` Update Submission, and `CHANGES_REQUESTED` Resubmit; `LOCKED`, `UNDER_REVIEW`, and `COMPLETED` remain read-only,
- each successful action refetches authoritative Sprint state, `latest_submission`, and oldest-to-newest append-only submission history; frontend does not edit earlier submissions or synthesize state,
- the form sends only required `final_commit_url`, required `deployment_url`, and optional `evidence`; submitter, time, and design snapshot remain server-derived,
- current canonical repository and design workspace links are displayed separately from per-submission final commit, deployment, and historical design snapshots,
- submission is disabled when the Staff-managed repository or Product-Designer-managed design workspace is missing, with role-aware design guidance and basic local HTTP(S) input validation; backend repository matching, membership, state, deadline, and concurrency remain authoritative,
- participant Sprint Detail now exposes a participant-safe nullable `review_decision` on each submission (and `latest_submission`), with only decision, feedback, and reviewed_at; the page shows historical decisions on their exact submissions and current feedback beside Resubmit only while the Sprint is `CHANGES_REQUESTED`,
- after a new submission returns the Sprint to `SUBMITTED`, old feedback remains in history but is no longer shown as a current warning; Staff reviewer identity is not exposed through this participant contract.
- participant Sprint Detail still uses the existing active-ProjectRun selector, so terminal-run participant historical access remains a separate read-path limitation; a Workspace actionable-feedback summary remains deferred.

Validation state:
- focused Sprint Detail frontend tests pass (29 tests), full frontend tests pass (187 tests), and frontend lint, typecheck, and production build pass,
- Django system check and non-database review serializer/input tests pass (16 tests); participant, ReviewDecision, structured-submission, and Staff-read PostgreSQL tests collect (47 tests) but execution remains developer-controlled,
- this feedback phase changed only the participant read serializer/query prefetch, frontend types/presentation/tests, and this status note; no model, schema, migration, review mutation, or real database data changed.

---

### Persisted Sprint ReviewDecision History
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- `ReviewDecision` is an append-only, one-to-one final decision for the exact latest `SprintSubmission` being reviewed,
- `SUBMITTED -> UNDER_REVIEW` remains a decision-free review-start transition,
- `UNDER_REVIEW -> CHANGES_REQUESTED` now requires trimmed non-empty Staff feedback and atomically records the authenticated active Staff actor, server-authoritative review time, decision, and reviewed submission,
- `UNDER_REVIEW -> COMPLETED` atomically records the same review history with optional feedback and preserves existing final-Sprint ProjectRun completion behavior,
- participant submissions remain blocked during `UNDER_REVIEW`, so the deterministic latest submission ordered by `submitted_at, id` is the authoritative review candidate without a mutable review pointer,
- the database enforces one decision per submission, active Staff reviewers, latest-submission binding, valid decision/feedback data, append-only history, and prevents a final Sprint transition without its matching latest-submission decision,
- review action serializers reject client-controlled reviewer, timestamp, submission identity, and arbitrary decision values,
- Staff Review UI and participant Sprint Detail feedback presentation are now available in their separate frontend/read-contract phases; review action and persistence semantics remain unchanged.

Validation state:
- model, service, strict review inputs, migration source, API behavior, and focused service/API/database/concurrency regressions are implemented,
- Django system checks, Python compilation, full pytest collection, and pure serializer/domain tests pass,
- no migration has been applied to the developer's PostgreSQL database,
- PostgreSQL-backed review integrity, concurrency, lifecycle, and full-suite execution remain developer-controlled and pending.

---

### Staff Sprint Read / Discovery API
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- authenticated active Staff/Admin may list the ordered SprintRuns for any exact ProjectRun through `GET /api/v1/project-runs/{project_run_id}/sprints/`, including terminal ProjectRuns retained for audit history,
- authenticated active Staff/Admin may inspect one exact-run-scoped SprintRun through `GET /api/v1/project-runs/{project_run_id}/sprints/{sprint_run_id}/`,
- the detail response exposes append-only SprintSubmission history oldest-to-newest with structured commit, deployment, design snapshot, evidence, actual submitter, and server submission time,
- each submission exposes its nullable one-to-one ReviewDecision with decision, participant-readable feedback, actual Staff reviewer, and server review time,
- `latest_submission` is resolved server-side as the final item under the authoritative `submitted_at, id` ordering; no mutable current-submission pointer or persisted derived review flag was added,
- exact ProjectRun/SprintRun filtering returns a non-revealing not-found response for cross-run mismatches, and participants, anonymous users, and inactive Staff cannot use these endpoints,
- Staff read querysets select related submitter/reviewer identity and prefetch ordered history, while participant Workspace/Sprint Detail selectors and all review mutations remain unchanged,
- this phase adds no model, schema, migration, state transition, or mutation behavior and does not include a Staff Review UI.

Validation state:
- focused Staff list/detail, history, latest-submission, permission, cross-run, terminal-read, no-mutation, and bounded-query test source is implemented (three list queries and two detail queries regardless of nested history size),
- Django system checks, Python compilation, route/serializer inspection, and pytest collection pass,
- PostgreSQL-backed endpoint and regression-suite execution remain developer-controlled and pending.

---

### Staff Sprint Review UI
Status: `IMPLEMENTATION COMPLETE - FRONTEND VALIDATED`

Current position:
- the existing `/staff/formations` area now contains a deliberately basic functional Sprint Review section rather than a separate Staff dashboard,
- Staff selects an active or preserved historical ProjectRun, navigates the server-ordered SprintRun list, and reads the Staff Sprint detail contract with explicit `latest_submission` plus oldest-to-newest submission/ReviewDecision history,
- structured final commit, deployment, design-workspace snapshot, optional evidence note, actual submitter/time, final decision, feedback, and actual reviewer/time are displayed from API data,
- `SUBMITTED` exposes the existing start-review action; `UNDER_REVIEW` exposes request-changes with required meaningful feedback and complete with optional feedback; eligible `LOCKED` Sprints can be sent to the existing Staff open action,
- every successful or rejected mutation re-fetches authoritative Sprint list/detail state; no optimistic lifecycle state, reviewer assignment, designated-submitter behavior, or client-authored ReviewDecision is used,
- terminal ProjectRuns discovered through preserved Formation records remain history-only, while the active ProjectRun list remains the authority for whether mutation controls may be offered,
- completing a Sprint does not auto-open the next Sprint; Staff opens a later eligible Sprint explicitly through the existing endpoint,
- participant Sprint Detail review-feedback presentation is now available; a Workspace actionable-feedback card, global review inbox, notifications, and final visual redesign remain deferred,
- no backend API, model, schema, migration, or database state changed in this frontend phase.

Validation state:
- focused Staff Sprint Review tests cover discovery, ordered state display, explicit latest submission, structured evidence/history, all review actions and payloads, open-Sprint behavior, terminal read-only behavior, empty history, authorization failure, and stale-action revalidation,
- focused Staff tests pass (`23 passed`), the complete frontend suite passes (`165 passed`), and frontend typecheck, lint, and production build pass.

---

### Finalized MVP Role Selection / Role Change / Login Conflict
Status: `IMPLEMENTATION COMPLETE - MANUAL POSTGRESQL VALIDATION PENDING`

Current position:
- the existing authenticated role-selection endpoint is the single mutation entry point for initial selection, same-role idempotency, and eligible persisted-role changes,
- persisted-role changes are blocked by the canonical active ProjectReadiness, current unresolved Formation/ReadyCheck, and ACTIVE ProjectRun predicates,
- role mutation locks the authenticated User and UserProfile in the participation lock order before rechecking blockers,
- blocked changes return HTTP 409 with stable `role_change_blocked` and reason values,
- login returns structured guest-role versus persisted-role conflict data without mutating the persisted role or losing exact ProjectVersion continuation,
- explicit approval uses the normal role-selection endpoint; decline continues to use per-key guest-context clearing,
- no schema or migration change was required.

Validation state:
- safe AST/import, Django system-check, and pytest collection checks are complete,
- 66 pure/non-database tests pass,
- PostgreSQL-backed service, API, historical-lifecycle, and concurrency regressions are written,
- developer-controlled focused and full-suite PostgreSQL validation is still required.

Immediate goal:
- run the focused role-policy tests against PostgreSQL,
- run the relevant account/profile/project/formation regressions,
- run the full suite before marking this focused backend phase `VALIDATED`.

---

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
Staff can inspect Sprint state, submission state/history, deadlines, review status, and any nullable legacy designated-submitter value as read-only historical data.

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
- do not bypass exact-ProjectRun current-TeamMember or other participant rules where relevant
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
