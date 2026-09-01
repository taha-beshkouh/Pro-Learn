# Frontend Current State

Status: `PHASE 2 HOMEPAGE FIGMA FIDELITY IMPLEMENTATION COMPLETE - FRONTEND CHECKS PASSED`

## Authority Read

- `PROJECT_RULES_UPDATED_2026-08-26.md`
- `CURRENT_STATE_UPDATED_2026-08-26.md`
- `FRONTEND_RULES.md`
- `FRONTEND_ROUTE_API_MAP.md`
- `FRONTEND_COMPONENT_MAP.md`
- `HOMEPAGE_IMPLEMENTATION_SPEC.md`
- current frontend package manifest, routes, components, styles, tests, and
  API/auth foundation

The dated backend rule/state files identify themselves as the current
`PROJECT_RULES.md` and `CURRENT_STATE.md` repository sources.

## Frontend Phase 1 Foundation

Implemented and retained:

- Vite + React + TypeScript application structure
- React Router public and participant route trees
- native typed `fetch` client with session credentials and CSRF support
- session-aware `AuthProvider`
- base UI, loading, empty, and error components
- dark RTL-ready laptop/desktop foundation
- Vitest, jsdom, Testing Library, build, typecheck, and lint setup

`ProtectedRoute` remains a documented temporary pass-through so direct Phase 1
placeholder routes render before real authentication pages are implemented.

## Frontend Phase 2 Homepage

The `/` route implements only the `HOMEPAGE_DESKTOP` frame direction:

- compact pill navigation and PROLEARN brand mark
- split chalkboard hero with the supplied illustration and Persian message
- the intentional long dark breathing interval from the desktop frame
- sparse four-stage connected platform roadmap
- static project-output image strip using assets embedded in the homepage SVG
- compact chalk cards for the three accepted MVP roles only
- compact four-row MVP-safe FAQ
- restrained final project CTA
- oversized serif PROLEARN footer treatment

The previous orbit hero, standalone value section, seven-row generic roadmap,
large abstract project cards, oversized organic role cards, circular final CTA,
and unrelated metadata treatments were removed because they did not match the
supplied homepage frame.

Homepage marketing content remains static frontend content. The project image
strip is identified as a static visual preview and does not claim to be live
backend data or verified past-member history.

## Frame Mapping

- `HOMEPAGE_DESKTOP`, Figma node `129:183`: implemented at `/`.
- `ROLE_CARDS_SECTION`, Figma node `746:865`: reserved for a later `/projects`
  phase and not used by the homepage implementation.
- `PROJECT_INFORMATION`: reserved for a later
  `/projects/:projectVersionId` phase and not used by the homepage.

`/projects` and `/projects/:projectVersionId` remain Phase 1 placeholders.

## Design Sources And Limitations

- Final visual comparison source: `docs/png_files/HOMEPAGE_DESKTOP.PNG`
  (1440 x 8174).
- Vector/asset source: `docs/svg_files/HOMEPAGE_DESKTOP.svg`
  (1440 x 8174).
- Measurement reference: `docs/css_code/HOMEPAGE_DESKTOP.css`.
- The homepage and role-card CSS exports are present but empty (0 bytes), so
  they supplied no usable measurements or layer styles.
- Figma MCP was intentionally not used. Fidelity work used only repository
  exports.
- The SVG contains outlined artwork and embedded raster images. Relevant
  homepage-only assets were copied into `frontend/src/assets/home/` so the page
  remains component-based rather than a single SVG poster.
- The imported hero and project images match their SVG-embedded sources
  byte-for-byte; the roadmap crops match pixel-for-pixel.
- Roadmap placement and connector geometry were refined to reach all four
  exported steps, and the footer now uses the SVG's `#292929` surface landmark.
- No exact local Persian or chalk font files were supplied. The implementation
  uses existing safe font fallbacks and preserves the hierarchy and composition
  without adding font packages or external font requests.
- No prototype timing or animation specification was supplied, so no animation
  was invented.
- No browser surface was connected for automated localhost screenshot
  comparison. Browser visual QA therefore remains manual; PNG/SVG inspection,
  build, tests, lint, source inspection, and asset verification completed.
- `docs/png_files/ROLE_CARDS_SECTION.PNG` was inspected only to confirm its
  later `/projects` scope. Its SVG and styling were not used on the homepage.

## Routes Preserved

Real page:

- `/`

Phase 1 placeholders:

- `/login`
- `/register`
- `/profile/setup`
- `/projects`
- `/projects/:projectVersionId`
- `/ready-check`
- `/dashboard`
- `/workspace`
- `/workspace/sprints/:sprintRunId`

Invalid routes still render the existing NotFound page.

## Responsive Scope

- Current target remains laptop/desktop only.
- Primary range remains 1366px-1536px; acceptable range remains 1024px-1920px.
- Section grids and sizes include laptop-only adjustments at 1180px.
- Full-width visual strips are clipped by the homepage container to avoid
  horizontal document overflow.
- No mobile navigation, mobile composition, or mobile support claim exists.

## Validation

Executed successfully on 2026-08-30:

- `npm run build` - PASS: 65 modules transformed.
- `npm run test -- --run` - PASS: 2 test files, 12 tests.
- `npm run lint` - PASS.

No backend or PostgreSQL validation was required or executed for this
frontend-only phase.

## Intentionally Not Implemented

- real `/projects` or `/projects/:projectVersionId` pages
- authentication forms or action wiring
- project catalog/detail API integration
- Ready Check, dashboard, workspace, or Sprint runtime UI
- backend CMS, media, or homepage APIs
- mobile layouts
- animations
- deferred product features
- hard-coded participant-project runtime behavior

## Recommended Next Phase

Perform a developer visual comparison at 1440px against
`docs/png_files/HOMEPAGE_DESKTOP.PNG`. After visual sign-off, implement the real
login, registration, and profile-setup UI as a separate phase; keep project
catalog implementation independent and use `ROLE_CARDS_SECTION` only when that
later phase begins.
