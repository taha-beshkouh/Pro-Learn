# Frontend Current State

Status: `PHASE 1 IMPLEMENTATION COMPLETE - FRONTEND CHECKS PASSED`

## Authority Read

- `PROJECT_RULES_UPDATED_2026-08-26.md`
- `CURRENT_STATE_UPDATED_2026-08-26.md`
- `FRONTEND_RULES.md`
- `docs/frontend/FRONTEND_ROUTE_API_MAP.md`
- `docs/frontend/FRONTEND_COMPONENT_MAP.md`
- `docs/frontend/HOMEPAGE_IMPLEMENTATION_SPEC.md`
- Current backend account, profile, project, formation, and runtime API routes
- Existing Vite scaffold, package manifest, TypeScript, and ESLint configuration

The repository filenames are dated, but the first two documents identify
themselves as the current `PROJECT_RULES.md` and `CURRENT_STATE.md` sources.

## Frontend Phase 1

Implemented:

- Vite + React + TypeScript app organization under `frontend/src`
- React Router route tree with public and authenticated layouts
- required public and participant placeholder pages
- Django-session-aware `AuthProvider`, `useAuth`, and `ProtectedRoute`
- session resolution through `GET /api/v1/auth/me/`
- native `fetch` API client with typed success values and `ApiError`
- same-origin `/api/v1` default configurable through `VITE_API_BASE_URL`
- `credentials: include` for Django session cookies
- CSRF token retrieval before unsafe requests
- known participant endpoint constants from the current backend URL definitions
- base Button, Card, StatusBadge, Alert, LoadingState, and EmptyState components
- static dark RTL-ready desktop styling and design tokens
- Vitest, jsdom, and Testing Library configuration
- route smoke, anonymous protected-route, and API error regression tests
- build, test, typecheck, and lint scripts

No auth token storage exists because the backend uses Django session
authentication. No frontend role or lifecycle permission logic was invented.

## Routes Scaffolded

Public:

- `/`
- `/login`
- `/register`
- `/projects`
- `/projects/:projectVersionId`

Session-protected:

- `/profile/setup`
- `/ready-check`
- `/dashboard`
- `/workspace`
- `/workspace/sprints/:sprintRunId`

A not-found route is also present. Every product page is a foundation
placeholder; no page-specific API flow or final design has been implemented.

## Responsive And Design Scope

- Current target remains laptop/desktop only.
- Primary range remains 1366px-1536px; acceptable range remains 1024px-1920px.
- Base containers are fluid within the supported range and do not impose a fixed
  canvas width.
- Global document direction is Persian RTL-ready, with local LTR treatment for
  technical route labels.
- No mobile navigation, mobile layout, animation, or homepage visual
  implementation exists.

## Validation

Executed successfully on 2026-08-28:

- `npm run typecheck` - PASS
- `npm run test` - PASS: 2 test files, 3 tests
- `npm run build` - PASS: 51 modules transformed
- `npm run lint` - PASS

No backend or PostgreSQL validation was required or executed for this
frontend-only phase.

## Known API Uncertainties

- The required frontend route uses `:projectVersionId`, while the current
  backend project-detail URL accepts `project_id` and resolves its published
  version. The detail page must not bind the route parameter until this naming
  contract is reconciled.
- Ready Check responses still do not expose all fixed ProjectVersion disclosure
  details required before confirmation.
- No participant terminal/historical ProjectRun read endpoint exists.
- Project catalog responses are unpaginated and expose limited card fields.
- No participant join/apply endpoint exists because formation remains
  staff-created and Matching is out of scope.

These gaps do not block the Phase 1 foundation because its pages are placeholders.

## Intentionally Not Implemented

- full homepage or product-page UI
- registration/login/profile forms
- project catalog/detail data loading
- Ready Check actions
- dashboard/workspace/Sprint data loading or submission
- mobile layouts or animation
- frontend admin UI
- any deferred product feature
- hard-coded Helpdesk Sprint content

## Recommended Next Phase

Implement the participant authentication and profile-setup flow against the
validated Django session, CSRF, profile, role, and skill APIs. Reconcile the
project route identifier before implementing project detail, and resolve the
Ready Check disclosure contract before implementing confirmation UI.
