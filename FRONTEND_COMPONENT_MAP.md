# Frontend Component Map

Status: planning draft. No components have been implemented.

## Component Principles

- Keep the first component foundation small.
- Preserve Persian RTL globally and isolate mixed technical text locally.
- Components render backend state; they do not own lifecycle rules.
- Prefer composition over a large speculative design system.
- Do not introduce a component library or Storybook without separate approval.

## Shells And Navigation

| Planned component | Responsibility |
| --- | --- |
| `PublicShell` | Public header, centered desktop container, footer |
| `AuthenticatedShell` | Session-aware header and protected-page container |
| `WorkspaceShell` | Project identity and navigation among overview/Sprints |
| `PublicHeader` | Homepage/projects navigation and auth CTA |
| `AccountHeader` | Current user identity, dashboard/workspace links, logout |
| `Footer` | Approved static destinations and brand treatment |

No mobile drawer or mobile navigation is planned.

## Base UI

| Planned component | Notes |
| --- | --- |
| `Button` | Primary, secondary, danger/confirm variants; loading and disabled states |
| `TextInput` | Label, help text, backend field errors |
| `Textarea` | Minimal Sprint evidence input |
| `Select` | Role, stack, level, timezone/language where approved |
| `Card` | Shared surface primitive for marketing and runtime summaries |
| `Badge` | Level, role, and stack metadata |
| `StatusPill` | Friendly label for an exact backend state |
| `Alert` | Permission, validation, deadline, and server errors |
| `Dialog` | Confirmation for decline/logout or other genuinely consequential actions |
| `Skeleton` | Stable loading layout without fabricated data |
| `EmptyState` | No project, no Ready Check, or no active ProjectRun guidance |
| `FormErrorSummary` | Consistent non-field and field error display |

Toast behavior is not specified by the exports. Prefer inline feedback until a
notification pattern is approved; this does not create a product notification feature.

## Homepage Components

| Planned component | Data source |
| --- | --- |
| `HeroSection` | Approved static marketing copy and visual asset |
| `PlatformRoadmap` | Approved static copy aligned with product rules |
| `RoadmapStep` | Static semantic step, not runtime state |
| `MarketingProjectGallery` | Approved static previews only |
| `RoleDiscoveryGrid` | Public role API or approved static labels; guest context on action |
| `RoleCard` | One of the three exact platform roles |
| `FaqList` | Approved static questions/answers |
| `FinalCta` | `/projects` and/or `/register` links |

## Authentication And Profile Components

| Planned component | Backend contract |
| --- | --- |
| `LoginForm` | `/auth/csrf/`, `/auth/login/` |
| `RegistrationForm` | `/auth/csrf/`, `/auth/register/` |
| `ProfileBasicsForm` | `GET/PATCH /profile/` |
| `RoleSelectionGrid` | `GET /roles/`, `POST /profile/select-role/` |
| `SkillEditor` | Stack list and profile skill endpoints |
| `ProfileLinkEditor` | Profile link endpoints |

Role selection must clearly communicate that the platform role is selected once.

## Project Discovery Components

| Planned component | Backend contract |
| --- | --- |
| `LevelFilter` | `/levels/` and `?level=` |
| `ProjectGrid` | `/projects/` array |
| `ProjectCard` | List fields only unless the API contract is expanded |
| `ProjectOverview` | Project detail and published version fields |
| `RoleContextPanel` | Role context, prerequisites, compatible stacks, visible work |
| `StackSelector` | Compatible stacks and stack-selection endpoint |
| `SprintTemplateOutline` | Published version Sprint templates |

Do not implement the exported paginator until backend pagination exists or the
owner explicitly approves a purely client-side presentation for the small array.

## Ready Check Components

| Planned component | Backend contract |
| --- | --- |
| `ReadyCheckCard` | My Ready Check fields and effective status |
| `ReadyCheckDisclosure` | Fixed ProjectVersion duration/cadence/effort/manual review; backend gap |
| `ReadyCheckActions` | Own confirm/decline actions only |
| `DeadlineDisplay` | Server timestamp formatted in user timezone |

The disclosure component is blocked until the API exposes fixed-version details
without resolving through mutable/latest catalog state.

## Dashboard And Workspace Components

| Planned component | Backend fields |
| --- | --- |
| `ProjectRunHeader` | project, state, started/deadline timestamps, membership |
| `TeamSummary` | historical TeamMember snapshots from `team` |
| `CurrentSprintCard` | `current_sprint` exact runtime state and schedule |
| `NextActionCard` | backend `next_action`; links to the relevant Sprint when applicable |
| `SprintJourney` | ordered SprintRun list and exact states, not task progress |
| `SprintList` | workspace/Sprint list response |
| `SprintDetailHeader` | sequence, title, brief, state, schedule |
| `StaticWorkList` | backend-filtered shared and member-relevant work items |
| `SubmissionForm` | evidence submission/resubmission by a current TeamMember of the exact ProjectRun; backend authorizes the authenticated actor |
| `SubmissionHistory` | append-only submissions from Sprint detail |
| `ProjectResourceList` | workspace static work resources, not invented file links |

`SprintJourney` may visually group completed versus remaining Sprints, but must
not present an unsupported task completion percentage or locally advance state.

## Backend State Label Map

The UI may translate labels while preserving these exact values:

- ProjectRun: `ACTIVE`, `COMPLETED`, `INCOMPLETE`.
- SprintRun: `LOCKED`, `ACTIVE`, `SUBMITTED`, `UNDER_REVIEW`,
  `CHANGES_REQUESTED`, `COMPLETED`.
- Ready Check: `PENDING`, `CONFIRMED`, `DECLINED`, `EXPIRED`.
- Next action: `WAIT_FOR_FACILITATOR`, `SUBMIT_SPRINT`, `WAIT_FOR_REVIEW`,
  `RESUBMIT_SPRINT`, `SPRINTS_COMPLETED`, `NO_SPRINT_AVAILABLE`.
- Legacy decode-only aliases: `COLLABORATE` renders the same guidance as
  `SUBMIT_SPRINT`, and `ADDRESS_CHANGES` renders the same guidance as
  `RESUBMIT_SPRINT`; neither alias represents current submission authority.

## Standard Page States

Every API-backed page must plan for:

- Loading.
- Success.
- Empty/no current resource.
- Field validation error.
- Authentication required.
- Permission denied or privacy-preserving not found.
- Deadline/transition conflict.
- Server/network failure with safe retry.

## Components Explicitly Not Planned

- Chat/channel UI.
- Notifications center.
- Activity feed.
- Comment system.
- Sprint board or Kanban.
- Runtime task cards/status/assignment.
- Task or project completion percentage widgets.
- Automated or AI review widgets.
- Matching/candidate pool.
- Trust/warnings/removal.
- Extension or replacement workflow.
- Participant admin panel or Helpdesk Admin UI.
- Staff lifecycle controls.

## Testing Targets For A Later Implementation Phase

- Route guards and safe return paths.
- Session/CSRF handling.
- Backend validation error rendering.
- One-time role selection.
- Role/stack project context rendering.
- Ready Check confirm/decline states.
- Dashboard `next_action` mapping.
- Member-only Sprint detail and submission behavior.
- Changes-requested resubmission rendering.
- No unsupported management action exposed to participants.
