# PROJECT_RULES.md

> Updated product/domain source of truth for PROLEARN as of 2026-09-11.
> This file preserves the established MVP scope and incorporates the latest approved changes.

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
- Guests may select a temporary role for discovery.
- Registration remains email + password only.
- After authentication, the persisted role may be selected/changed only when lifecycle blockers do not exist.
- Role change is blocked while the user has an active ProjectReadiness, current Formation/ReadyCheck involvement, or an `ACTIVE` ProjectRun.
- No cancellation/withdrawal/leave flow is added merely to allow role change.
- Historical TeamMember role snapshots never change when profile role later changes.

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
- GitHub username when collected for project participation

Rules:
- A user may have only one active `ProjectRun` at a time.
- Current profile data and historical project membership are separate.
- GitHub username is not collected at registration.
- GitHub username is collected during Ready Check when needed and then persisted on the profile for reuse.
- GitHub username is required for Backend Developer and Frontend Developer Ready Check participation and optional for Product Designer.
- During an `ACTIVE` ProjectRun, the GitHub account used for repository access should not be changed. Changing the profile value does not transfer repository access.
- Exceptional GitHub-account changes require manual coordination with Staff/support in the MVP.

## 4. Guest Context

Anonymous visitors may:
- select a temporary role
- browse projects
- view project details and role-specific information
- view available stack options

Anonymous visitors may NOT:
- confirm participation stack
- create ProjectReadiness
- enter Ready Check
- participate in a ProjectRun

Temporary session context may preserve:
- selected role
- exact selected ProjectVersion
- intended action
- safe internal return path

Do not create database Users for anonymous visitors.

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

Supported project-role policies:
- `FIXED`
- `ALLOWLIST`
- `OPEN`

Rules:
- Stack policy belongs to a project role.
- `OPEN` does not permit arbitrary free text.
- Roles such as Product Designer may require no technical stack.
- Selected project stack is snapshotted historically.
- Stack confirmation requires authentication.

## 7. Project Model

`ProjectTemplate`, `ProjectVersion`, and `ProjectRun` are distinct.

Rules:
- Project definitions are versioned.
- Each ProjectRun remains tied to the exact ProjectVersion it started with.
- Future definition edits must not mutate active/historical runs.
- Project-specific content is data-driven, not slug-hardcoded.

## 8. Project UX / Data Boundaries

### Project Detail
Pre-participation discovery/decision page.

### Dashboard
Active ProjectRun orientation:
- project
- role/stack
- current Sprint
- deadline/status
- team summary
- next relevant action

### Workspace
Daily ProjectRun overview:
- overview
- Sprint journey
- team
- project resources
- canonical repository/design workspace references
- latest actionable Facilitator feedback for the current Sprint

Workspace is not the primary Sprint submission form.

### Sprint Detail
Primary Sprint-specific execution/review page:
- Sprint brief/state/timing
- static work items
- Submit / Resubmit
- append-only submission history
- complete review/feedback history

A same-ProjectRun `LOCKED` Sprint may be viewed read-only but cannot expose participant mutation/submission actions.

There is no Jira/Trello-style runtime task system in MVP.

## 9. Static Work Content

Static work items may be:
- shared/team-wide
- role-specific
- optionally stack-specific
- optionally associated with SprintTemplate

They are informational project content, not runtime tasks.

Do NOT implement runtime:
- task statuses
- task assignment
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

Backend:
- Django + DRF or ASP.NET Core + EF Core

Frontend:
- React
- TypeScript
- Vite
- React Router

Participant-project DB:
- MySQL 8 / InnoDB

Canonical Sprint plan:
- Sprint 1 — Product Foundation & Authentication
- Sprint 2 — Requester Ticket Experience
- Sprint 3 — Agent Workflow
- Sprint 4 — Collaboration & Ticket History
- Sprint 5 — Findability & Product Hardening
- Sprint 6 — Final Integration & Production Delivery

Rules:
- Each Sprint has shared/team work plus role-specific work.
- Testing happens throughout the project.
- Every Sprint must produce/review the current integrated increment.
- Deployment must not be postponed entirely to Sprint 6.

## 11. Healthchecks Lite / Event Ticketing Lite

Known:
- Healthchecks Lite → Level 2 → PostgreSQL
- Event Ticketing Lite → Level 3 → PostgreSQL

Detailed scope remains unresolved.
Do not invent it.

## 12. Team Formation

Candidate Pool / Matching is NOT implemented now.

Formation is manual by Facilitator/Admin.

Rules:
- exactly one Backend Developer
- exactly one Frontend Developer
- exactly one Product Designer
- unique users
- exact ProjectVersion consistency
- valid stack snapshots

## 13. Ready Check

- Duration: exactly 48 hours.
- Each proposed member confirms/declines only their own Ready Check.
- Decline/expiry replaces only that role slot.
- Other confirmed/current members remain.
- When all three current members confirm, Team + ProjectRun are created exactly once.
- ProjectRun begins immediately when all three confirm; 48 hours is a maximum response window, not a mandatory wait.
- Successful Ready Check is the authoritative ProjectRun start point.
- Backend/server time is authoritative.
- Members are shown duration, Sprint cadence, weekly effort, and manual review expectations.
- Review may take several hours; the current operational expectation is around 8 hours, not a guaranteed SLA.
- Teams must submit early enough to leave practical time for review/fixes.
- Ready Check collects GitHub username when it is not already stored on the profile.
- GitHub username is required for Backend/Frontend and optional for Product Designer.
- A GitHub username entered in Ready Check is stored on the profile.
- UI must warn that the GitHub account used for an active ProjectRun should not be changed without Staff/support coordination.
- Changing the profile GitHub username does not automatically transfer repository access.

## 14. Team

`TeamMember` preserves snapshots of:
- user
- role
- selected stack when applicable

Later profile changes do not rewrite TeamMember history.

## 15. ProjectRun

MVP states:
- `ACTIVE`
- `COMPLETED`
- `INCOMPLETE`

Rules:
- ProjectRun is created `ACTIVE` only after successful full Ready Check.
- Backend records authoritative `started_at` and `deadline_at`.
- ProjectRun time never pauses for `SUBMITTED`, `UNDER_REVIEW`, or `CHANGES_REQUESTED`.
- Ordinary Sprint lateness does not move future planned deadlines or extend ProjectRun deadline.
- Only `ACTIVE` counts for the one-active-run rule.
- `COMPLETED` and `INCOMPLETE` are terminal.
- No Sprint transitions occur after ProjectRun terminalization.

Repository:
- After full Ready Check succeeds and Team + ProjectRun exist, Staff manually creates one private repository in the PROLEARN GitHub Organization for that ProjectRun.
- Repo creation and collaborator access are manual in MVP.
- The ProjectRun has one canonical GitHub repository root URL managed by Staff.
- One canonical repository may belong to only one ProjectRun; repository reuse across different ProjectRuns is not allowed.
- Staff may register, correct, replace, or clear the PROLEARN repository reference. Clearing the reference does not delete the GitHub repository, revoke access, remove collaborators, or perform any GitHub-side operation.
- Team members may use normal Git workflows: clone, branch, commit, push, pull request, merge.
- PROLEARN does not care how many commits are created.
- Sprint delivery identifies the exact final commit/revision being submitted.
- Repository access is based on GitHub username, not PROLEARN registration email.
- Canonical repository is expected to remain stable during the ProjectRun.
- Exceptional repo/account changes are Staff-coordinated and must not rewrite historical evidence.

Design workspace:
- ProjectRun has one current canonical design workspace URL (Figma or equivalent).
- Product Designer introduces it during Sprint 1.
- The current design URL is reused by default for later Sprints.
- Product Designer may update it when genuinely needed; Staff may correct it operationally.
- Changing current design URL must not rewrite historical SprintSubmission snapshots.

Completion:
- ProjectRun becomes `COMPLETED` only after Facilitator/Admin accepts the final Sprint.
- Completing the final Sprint completes the ProjectRun in the same transaction.

Incomplete:
- Deadline passage does not automatically terminalize the ProjectRun.
- At/after `deadline_at`, team submissions/resubmissions are blocked.
- A valid pre-deadline submission may still be reviewed after the deadline.
- Facilitator/Admin may manually mark overdue unfinished work `INCOMPLETE`.
- No MVP Extension workflow exists.

Repository behavior after ProjectRun completion/incompletion is deferred to post-MVP.

## 16. Sprint Runtime

States:
- `LOCKED`
- `ACTIVE`
- `SUBMITTED`
- `UNDER_REVIEW`
- `CHANGES_REQUESTED`
- `COMPLETED`

Flow:
`ACTIVE → SUBMITTED → UNDER_REVIEW`

Then:
`UNDER_REVIEW → COMPLETED`

or:
`UNDER_REVIEW → CHANGES_REQUESTED → SUBMITTED → UNDER_REVIEW`

Initialization/opening:
- At successful ProjectRun startup, Sprint 1 becomes `ACTIVE` immediately.
- Sprint 2..N remain `LOCKED`.
- Sprint 1 requires no manual Staff opening.
- Sprint 1 requires no designated submitter.
- Sprint N+1 cannot open before Sprint N is `COMPLETED`.
- Completing Sprint N does NOT auto-open Sprint N+1.
- For Sprint 2+, Facilitator/Admin explicitly opens the eligible next Sprint.

Submission authorization:
- Any authenticated, active, current TeamMember of the exact ProjectRun may submit/resubmit when Sprint/ProjectRun state and deadline rules permit.
- `designated_submitter` is no longer MVP business authority.
- The legacy nullable field may remain for compatibility/history, but it must not control activation, authorization, next_action, or participant UX.
- Actual actor is recorded by `SprintSubmission.submitted_by`.
- Submission happens from the corresponding Sprint Detail page.
- Submission does not equal approval.
- Resubmission happens inside the same Sprint after `CHANGES_REQUESTED`.
- Submission history is append-only.
- Submission/resubmission after ProjectRun deadline is forbidden.

Submission evidence:
- Each Sprint submission is an exact reviewable snapshot.
- ProjectRun repository URL is canonical and is not re-entered as the Sprint version identifier.
- Each SprintSubmission must identify one exact final commit/revision in the canonical ProjectRun repository.
- Repo URL or mutable branch alone is not sufficient.
- Each SprintSubmission includes the deployed URL for the current integrated increment when the ProjectVersion requires deployment; Helpdesk Lite requires deployment every Sprint.
- Current design workspace URL is the default design reference.
- Each SprintSubmission snapshots the design workspace URL used at submission time.
- Later design-workspace changes do not rewrite old SprintSubmission history.
- Existing `evidence` text is treated as an optional participant note.
- `submitted_by` and `submitted_at` are server-authoritative.

Final Sprint:
- Final Sprint is the SprintTemplate with the highest sequence in the fixed ProjectVersion.
- Do not introduce FinalSprint model or `is_final` solely for this rule.

## 17. Review / Facilitator

MVP review is manual.
No AI review.

Facilitator/Admin controls:
- opening eligible later Sprints
- review transitions
- requesting changes
- completing Sprints
- controlled ProjectRun terminalization

Review history:
- Review decisions are persisted as append-only records tied to the exact SprintSubmission being reviewed.
- Review history preserves reviewer, decision, participant-readable feedback, and server-authoritative review timestamp.
- `CHANGES_REQUESTED` requires non-empty Facilitator feedback explaining what must change.
- `COMPLETED` feedback may be optional.
- A resubmission creates a new SprintSubmission; later review is tied to that new submission.
- Earlier submission/review history is never overwritten.
- Workspace surfaces the latest actionable Facilitator feedback for the current Sprint.
- Sprint Detail shows the full submission/review history.

Staff UX:
- Sprint Review UI belongs in the existing minimal Staff area used for readiness/Formation.
- Do not build a separate large Staff dashboard solely for review.
- Staff can inspect final commit/revision, deployment, design reference, actual submitting member, and submission timestamp before review.

## 18. Deferred / Not Implemented Now

Do NOT implement now:
- Assessment
- Qualification
- Candidate Pool
- Matching algorithm
- runtime Task lifecycle
- Trust algorithm
- Warning/removal disciplinary workflow
- post-start member departure/replacement/recovery
- Extension / Emergency Extension
- AI review
- built-in chat
- GitHub automation

GitHub repository creation/access remains manual in MVP.

## 19. Current Unresolved Decisions

Do not invent behavior for:
- detailed Healthchecks Lite scope
- detailed Event Ticketing Lite scope
- final Qualification scope
- Matching algorithm
- stack effects on future Matching
- repository-access/ownership behavior after ProjectRun completion/incompletion
- all Extension rules
- post-start member replacement/recovery mechanics
- future `FAILED` transition details
- warning thresholds/timers
- Trust scoring
- exact notification timing
- exact deployment provider

The MVP ProjectRun state machine is finalized as `ACTIVE`, `COMPLETED`, `INCOMPLETE`.

## 20. Agent Rules

- Treat this file as product/domain source of truth.
- Do not silently change accepted rules.
- Do not turn proposals into product rules.
- Do not invent unresolved behavior.
- If an unresolved rule blocks implementation, report it.
- Platform backend uses Python + Django + DRF + PostgreSQL.
- PostgreSQL remains the source-of-truth database.
- Frontend must not become a second source of business logic.
- GitHub automation is out of MVP scope.
- Do not add runtime task lifecycle.

## Database Execution & Testing Boundary

- Codex owns database architecture, models, constraints, transactions, migrations source files, APIs, permissions, and tests.
- Codex must NOT connect to or modify the user's real PostgreSQL `platform_db`.
- Codex must NOT run real migrations against `platform_db`.
- Codex must NOT create disposable PostgreSQL clusters/environments.
- PostgreSQL-dependent tests must be written correctly but reported as:
  `WRITTEN - MANUAL POSTGRESQL VALIDATION REQUIRED`
  until the user executes and confirms them.
- The user performs real PostgreSQL migration execution and final DB-dependent validation.
- Codex must never weaken DB tests or replace PostgreSQL semantics with SQLite/mocks simply to execute tests itself.
- Never request/read/expose developer secrets or real DB credentials.
