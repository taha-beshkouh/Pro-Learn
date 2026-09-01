# Frontend Route And API Map

Status: planning draft. No routes or API client have been implemented.

## Runtime Conventions

- API base: same-origin `/api/v1/`.
- Authentication: Django session cookie.
- Browser requests must include credentials.
- Before CSRF-protected mutations, call `GET /api/v1/auth/csrf/` and send the
  returned token in `X-CSRFToken`.
- Backend response state, timestamps, permissions, and `next_action` remain
  authoritative.
- A hidden button is not an authorization control; backend errors must still be
  handled and displayed.
- All user-facing layouts are Persian RTL unless technical values need local LTR
  isolation.

## Participant Route Draft

| Frontend route | Access | Purpose | Backend API | Planning status |
| --- | --- | --- | --- | --- |
| `/` | Public | Landing page and MVP explanation | Optional `GET /projects/`, `GET /auth/me/` | Export exists; marketing content needs corrections |
| `/login` | Guest | Start an authenticated session | `GET /auth/csrf/`, `POST /auth/login/` | No design export |
| `/register` | Guest | Create account and authenticated session | `GET /auth/csrf/`, `POST /auth/register/` | No design export |
| `/onboarding` | Authenticated | Profile basics, one-time role selection, skills | `GET/PATCH /profile/`, `GET /roles/`, `GET /technology-stacks/`, `POST /profile/select-role/`, skills APIs | No design export; role is immutable after selection |
| `/profile` | Authenticated | Edit profile, links, and skills | Profile, profile links, and profile skills APIs | No design export |
| `/projects` | Public | Browse projects by level | `GET /levels/`, `GET /projects/?level=<1-3>` | Export exists; no backend pagination or role query filter |
| `/projects/:projectId` | Public | Project/version detail for current role context | `GET /projects/:id/`, guest-context APIs, stack-selection API | No design export |
| `/ready-check` | Authenticated | View and respond to current invitation | `GET /ready-checks/me/`, confirm/decline actions | No design export; fixed-version disclosure gap |
| `/dashboard` | Authenticated active member | Active ProjectRun summary and next action | `GET /project-runs/me/dashboard/` | Export exists but contains unsupported content |
| `/workspace` | Authenticated active member | Project overview, team, Sprints, static resources | `GET /project-runs/me/workspace/` | No dedicated export |
| `/workspace/sprints` | Authenticated active member | Ordered Sprint runtime list | `GET /project-runs/me/sprints/` | No design export |
| `/workspace/sprints/:sprintRunId` | Authenticated active member | Sprint brief, visible work, submissions, submit/resubmit | Sprint detail and submit action | No design export |

Staff-only formation and lifecycle endpoints are deliberately excluded from the
participant frontend. Platform operations remain in Django admin/staff APIs.

## API Inventory Used By The Draft

### Authentication

| Method | Endpoint | Frontend use |
| --- | --- | --- |
| GET | `/api/v1/auth/csrf/` | Establish CSRF cookie and obtain token |
| POST | `/api/v1/auth/register/` | Register; backend also starts the session and creates a profile |
| POST | `/api/v1/auth/login/` | Login |
| POST | `/api/v1/auth/logout/` | Logout |
| GET | `/api/v1/auth/me/` | Resolve current authenticated user |

### Profile And Guest Context

| Method | Endpoint | Frontend use |
| --- | --- | --- |
| GET | `/api/v1/roles/` | Three platform roles |
| GET | `/api/v1/technology-stacks/` | Normalized stack options |
| GET/PATCH | `/api/v1/profile/` | Read/update current profile |
| POST | `/api/v1/profile/select-role/` | One-time role selection |
| GET/POST | `/api/v1/profile/links/` | List/create links |
| PATCH/DELETE | `/api/v1/profile/links/:linkId/` | Update/delete owned link |
| GET/POST | `/api/v1/profile/skills/` | List/create skills |
| DELETE | `/api/v1/profile/skills/:skillId/` | Delete owned skill |
| GET/PATCH/DELETE | `/api/v1/guest-context/` | Preserve anonymous role/project intent safely in session |

### Project Discovery

| Method | Endpoint | Frontend use |
| --- | --- | --- |
| GET | `/api/v1/levels/` | Level filters |
| GET | `/api/v1/projects/` | Project cards; optional `level` query |
| GET | `/api/v1/projects/:projectId/` | Fixed published detail plus selected role context |
| POST | `/api/v1/projects/:projectId/stack-selection/` | Validate/select compatible stack in guest session |

Project list card content is currently limited to id, slug, name, level, and
published version id. Summary, duration, roles, and stack detail require a
project-detail request; avoid an N+1 detail request per catalog card until the
card contract is intentionally expanded.

### Ready Check

| Method | Endpoint | Frontend use |
| --- | --- | --- |
| GET | `/api/v1/ready-checks/me/` | Current member Ready Checks |
| POST | `/api/v1/ready-checks/:id/confirm/` | Confirm own pending Ready Check |
| POST | `/api/v1/ready-checks/:id/decline/` | Decline own pending Ready Check |

The UI must use `effective_status`, `expires_at`, and backend responses. Local
time may format the countdown but must not decide whether the Ready Check is
valid.

### Active ProjectRun And Sprint Runtime

| Method | Endpoint | Frontend use |
| --- | --- | --- |
| GET | `/api/v1/project-runs/me/dashboard/` | Project, membership snapshot, current Sprint, deadline, team, next action |
| GET | `/api/v1/project-runs/me/workspace/` | Dashboard data plus all Sprints and visible resources |
| GET | `/api/v1/project-runs/me/sprints/` | Ordered Sprint list |
| GET | `/api/v1/project-runs/me/sprints/:sprintRunId/` | Sprint work and append-only submissions |
| POST | `/api/v1/project-runs/:projectRunId/sprints/:sprintRunId/submit/` | Submit/resubmit minimal evidence |

Participant UI must not call staff-only open, review, request-changes, complete,
or incomplete transition endpoints.

## Route Guard Draft

1. Resolve `GET /auth/me/` once through centralized session state.
2. Guest-only pages redirect authenticated users to their safe intended route.
3. Protected pages redirect guests to `/login` while preserving only a safe
   internal return path.
4. After registration/login, load `/profile/`; if `selected_role` is null,
   continue to `/onboarding`.
5. Check `/ready-checks/me/` for current invitations before assuming an active
   ProjectRun exists.
6. Treat a dashboard 404 only as "no active ProjectRun". It does not prove that
   the user has never participated or identify a terminal state.
7. Use dashboard `next_action` to choose participant-facing guidance:
   `WAIT_FOR_FACILITATOR`, `SUBMIT_SPRINT`, `COLLABORATE`, `WAIT_FOR_REVIEW`,
   `RESUBMIT_SPRINT`, `ADDRESS_CHANGES`, `SPRINTS_COMPLETED`, or
   `NO_SPRINT_AVAILABLE`.

## API Contract Gaps To Resolve Before Full Implementation

- Ready Check lacks complete fixed ProjectVersion disclosure data required
  before confirmation.
- No participant terminal/historical ProjectRun detail endpoint exists.
- No project-list pagination metadata exists despite the exported paginator.
- Project cards lack summary/duration/team-role data without per-card detail calls.
- No participant join/apply endpoint exists; project CTAs must not imply matching.
- No completed-project gallery endpoint exists.
- No chat, notification, recent-activity, board, comment, or automated-review API exists.
- No explicit `allowed_actions` object exists; participant guidance currently
  relies primarily on `next_action`, state, and server enforcement.
