# FRONTEND_RULES.md

## Purpose

This file defines the frontend implementation rules for the PROLEARN platform.

The frontend must support the product rules already established in `PROJECT_RULES.md` and the backend state documented in `CURRENT_STATE.md`.

The frontend is a presentation and interaction layer over the backend API. It must not become a second source of business logic.

---

## Source of Truth Order

When there is a conflict between sources, use this priority order:

1. `PROJECT_RULES.md` — product, domain, lifecycle, and scope rules
2. `CURRENT_STATE.md` — current backend implementation and validation status
3. Backend API responses — runtime state, permissions, deadlines, and allowed actions
4. Figma / design references — visual direction, layout, component style, and interaction intent
5. Frontend implementation details — only UI behavior, not product truth

If Figma or frontend assumptions conflict with `PROJECT_RULES.md`, `CURRENT_STATE.md`, or backend API behavior, do not silently implement the design assumption. Report the conflict.

---

## Backend Runtime Truth

The backend API is the source of truth for:

- authentication state
- current user/profile state
- role and stack data
- project/version data
- Ready Check state
- Team and TeamMember state
- ProjectRun state
- SprintRun state
- deadlines
- allowed actions
- submission/review lifecycle
- terminal states
- permissions

Frontend must not calculate or invent these states locally.

Frontend may format timestamps and display derived UI labels, but it must not use local calculations as business truth.

Examples of forbidden frontend logic:

- deciding that a ProjectRun is `INCOMPLETE` because the local clock says the deadline passed
- opening the next Sprint locally
- deciding who can submit without backend state/permission support
- changing Sprint state locally after a button click without a confirmed backend response
- inventing states that do not exist in backend rules

---

## MVP Frontend Scope

The MVP frontend may include:

- homepage / landing page
- login
- registration
- logout
- current user session handling
- profile setup
- role selection
- stack selection
- project catalog
- project detail
- Ready Check view/actions
- dashboard
- workspace
- team view
- Sprint list
- Sprint detail
- role-specific static work display
- shared/team-wide static work display
- Sprint submission UI
- under-review state UI
- changes-requested state UI
- completed Sprint UI
- ProjectRun completed/incomplete UI
- deadline/status display based on backend data

Anything outside this scope must be explicitly approved before implementation.

---

## Hard Out of Scope

Do not implement or plan as active frontend scope:

- Extension
- Emergency Extension
- Matching
- Candidate Pool
- Trust
- warning/removal workflow
- post-start member replacement/recovery
- AI review
- GitHub automation
- built-in chat
- payment
- notifications
- admin panel
- Helpdesk participant-project Admin UI
- runtime task system
- Kanban
- task assignment workflow
- task completion percentages
- analytics dashboard
- gamified ranking/leaderboards

If any of these appear in a design reference, mark them as out of scope instead of implementing them.

---

## Project-Specific Behavior

Frontend must not hard-code Helpdesk-specific lifecycle behavior.

Do not write logic like:

```ts
if (project.slug === "helpdesk-lite") {
  // special lifecycle behavior
}
```

Project content, Sprint content, roles, stacks, and visibility rules should come from backend APIs.

Static marketing copy may mention Helpdesk as an example only when appropriate, but runtime behavior must remain generic and data-driven.

---

## Responsive Scope

The current frontend implementation target is laptop and desktop only.

Mobile-specific design is not available and must not be invented.

Supported viewport range:

- primary laptop range: `1366px–1536px`
- acceptable desktop/laptop range: `1024px–1920px`

Frontend should avoid layout breakage and horizontal overflow in the supported laptop/desktop range.

For now:

- do not create mobile-first layouts
- do not invent mobile navigation patterns
- do not spend implementation time optimizing phone screens
- do not claim mobile support
- do not treat missing mobile design as a blocker for desktop/laptop implementation

Laptop/desktop responsiveness still matters:

- preserve RTL layout
- keep typography readable
- avoid horizontal overflow
- use flexible containers where appropriate
- scale section widths and spacing for common laptop screens
- avoid brittle fixed-pixel layouts that break inside the supported range

Mobile support can be added later after mobile designs are provided.

---

## RTL and Persian UI

Frontend must support Persian RTL interface requirements:

- use `dir="rtl"` where appropriate
- preserve correct text alignment
- avoid LTR-only layout assumptions
- use readable Persian typography
- handle mixed Persian/English technical terms gracefully
- keep numbers, dates, code snippets, and technical labels readable
- avoid icon placement that assumes LTR direction

---

## Figma and Design Reference Rules

Figma/design references are valid for:

- visual direction
- layout intent
- spacing direction
- typography direction
- component style
- illustration direction
- page composition
- interaction intent when explicitly shown or documented

Figma/design references are not valid for inventing:

- backend states
- permissions
- lifecycle transitions
- deadline rules
- Ready Check rules
- Sprint Runtime rules
- ProjectRun terminal rules
- Extension or replacement behavior

If the design shows a UI state that is not supported by backend rules, report it as a design/backend mismatch.

---

## Motion and Prototype Interaction Scope

Frontend animations and prototype-style interactions are allowed, but they must not be invented by Codex.

Animation behavior must come from one of these sources:

1. Figma prototype behavior
2. an explicit design specification
3. a written instruction from the project owner

If animation details are missing, incomplete, or ambiguous, Codex must report the gap instead of guessing.

Animations may improve visual storytelling and user experience, but they must not create, imply, or replace backend business states.

Frontend must not use scroll position, cursor position, hover state, animation state, or viewport state to determine:

- authentication state
- Ready Check state
- Team state
- ProjectRun state
- SprintRun state
- deadline status
- allowed actions
- submission/review lifecycle
- terminal states

Until a specific animation spec is provided, Codex should implement only simple, safe static layouts or clearly documented placeholder interactions.

---

## Interaction Safety

Frontend interactions must be safe UI wrappers around backend behavior.

Rules:

- button enabled/disabled states must be based on backend-supported state or clearly documented frontend-only form validation
- optimistic UI must not permanently change lifecycle state before backend confirmation
- failed backend actions must show clear errors and must not leave fake success states
- destructive or irreversible actions require clear confirmation when relevant
- frontend must not bypass backend permissions by hiding/showing UI alone

UI hiding is not security. Backend authorization remains required.

---

## API Client Rules

API calls should be centralized and typed where practical.

Avoid scattering raw fetch/axios calls across page components.

Recommended approach:

- one API client layer
- typed request/response shapes where practical
- clear handling for loading, success, empty, validation error, permission error, and server error states
- consistent auth token/session handling
- no hard-coded production URLs in components

Frontend must display backend validation errors rather than replacing them with unrelated messages.

---

## Forms and Validation

Frontend form validation may improve UX, but backend validation remains authoritative.

Frontend may validate:

- required fields
- basic format
- obvious length limits
- empty selections

Frontend must still handle backend validation errors.

Do not duplicate complex backend domain rules in frontend unless the API contract explicitly provides the needed state.

---

## Component Strategy

Prefer a small, reusable component foundation before building complex pages.

Useful base components may include:

- Button
- Input
- Select
- Textarea
- Card
- Badge
- StatusPill
- Modal/Dialog
- Alert
- Toast or inline feedback
- Skeleton/loading state
- PageLayout
- Navbar
- Footer
- FormError

Do not build a large design system, Storybook setup, or component framework unless explicitly approved.

Components should be reusable, but avoid premature abstraction.

---

## Homepage Rules

Homepage may use static frontend data for marketing sections such as:

- role cards
- roadmap items
- FAQ items
- marketing project previews

Do not create backend CMS/media infrastructure for homepage content in the MVP.

Homepage CTAs should route users toward real MVP flows such as:

- registration
- login
- project discovery
- explanation of how the platform works

Homepage must not advertise unavailable features as if they exist.

---

## Project and Workspace Pages

Project catalog, project detail, dashboard, workspace, Sprint detail, and submission/review pages should use backend APIs as their content source.

These pages must not rely on static mock data once the relevant backend API exists.

Static mock data may be used only as temporary scaffolding and must be clearly marked as temporary.

---

## Status and State Display

Frontend may display user-friendly labels for backend states.

Example:

- backend: `UNDER_REVIEW`
- UI label: `در حال بررسی`

But frontend must not introduce unsupported runtime states.

If a new display state is only a visual grouping of backend states, document it clearly and keep backend truth visible in the mapping.

---

## Accessibility Baseline

Within the current laptop/desktop scope, frontend should still follow basic accessibility practices:

- semantic headings
- accessible buttons and links
- visible focus states for interactive controls
- meaningful alt text for meaningful images
- decorative images hidden from screen readers where appropriate
- sufficient text contrast
- no critical action dependent only on visual decoration

Do not overbuild accessibility infrastructure, but avoid obvious accessibility regressions.

---

## Testing Expectations

Frontend tests should focus on custom behavior and critical user flows.

Useful test areas:

- routing guards
- auth state handling
- API error display
- form validation display
- role/stack selection flow
- project detail rendering from API data
- Ready Check actions
- workspace state rendering
- Sprint submission UI behavior
- disabled/allowed actions based on backend-provided state

Do not over-test third-party library internals.

If test infrastructure does not exist yet, propose a minimal setup before adding many tests.

---

## Codex Workflow Rules

Before each frontend phase, Codex must read:

1. `PROJECT_RULES.md`
2. `CURRENT_STATE.md`
3. `FRONTEND_RULES.md`
4. relevant frontend specs/design references
5. existing frontend code

Codex must not rely on memory from earlier phases.

At the end of each frontend phase, Codex must report:

1. sources read
2. files changed
3. routes/components/pages added
4. API contracts used or assumed
5. tests added/updated
6. checks executed
7. unresolved assumptions
8. next recommended step

Codex must not claim validation that was not actually executed.

---

## Current Frontend Decision Summary

Current decisions:

- frontend work starts after backend Helpdesk L1 content population
- laptop/desktop only for now
- mobile design is explicitly out of scope for now
- frontend must not invent mobile behavior
- Figma/design is visual guidance, not product truth
- animation behavior must not be guessed before explicit specification
- backend API remains source of truth for runtime state and permissions
- Extension, Matching, Trust, post-start replacement, AI review, GitHub automation, chat, notifications, admin panel, and runtime task system are out of scope
