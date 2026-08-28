# Homepage Implementation Specification

Status: planning draft based on `index (1).pdf`. No homepage code exists.

## Export Facts

- Single exported PDF page.
- Canvas: 1440 x 8174.
- Desktop composition only.
- Persian RTL body copy with some English display/technical text.
- No prototype, interaction, breakpoint, or animation specification is included.

## Visual Direction

- Near-black textured background across the page.
- White chalk/sketch line art and off-white type.
- Electric blue/blue-violet primary actions and highlighted headline words.
- Thin white outlines, restrained radii, and long vertical storytelling rhythm.
- Hand-drawn role/project illustrations in the hero and roadmap.
- Oversized serif `PROLEARN` wordmark in the footer.

These are directional observations, not final design tokens. Exact colors,
fonts, font licenses, texture assets, and production-ready illustration exports
are missing.

## Desktop Section Order

### 1. Header

- PROLEARN mark.
- Links for platform explanation and projects.
- Authentication CTA.
- Preserve a centered desktop pill/navigation treatment if it remains readable
  between 1024px and 1920px.
- Replace ambiguous `SKILLS` navigation with an approved destination or section
  label; no standalone skills page is currently defined.

### 2. Hero

- Split composition: sketch illustration on the left, Persian headline and CTAs
  on the right.
- Core message: discover, connect, create.
- Primary CTA: view projects (`/projects`).
- Secondary CTA: registration or platform explanation, depending on final copy.
- Do not reproduce illustration-internal mock product states as actual platform
  features.

### 3. Platform Roadmap

Use the accepted product sequence only:

1. Select one platform role and relevant skills/stacks.
2. Review project prerequisites and role context.
3. Staff-created formation and member Ready Check lead to ProjectRun start.
4. Collaborate through Sprints and produce a presentable project result.

Do not describe assessment, qualification, candidate pools, or matching as
available MVP steps.

The export contains roughly 1400px of empty vertical space between hero and
roadmap. Do not reproduce that spacing until the owner confirms it is
intentional rather than an export/layout artifact.

### 4. Project Showcase

- Export shows four visual project examples.
- No completed-project gallery API exists.
- FRONTEND_RULES permits static marketing previews, so this section may use only
  owner-approved static content and must not imply live member history.
- Embedded PDF images are references, not confirmed production web assets.

### 5. Role Discovery

- Show exactly three role cards: Backend Developer, Frontend Developer, Product
  Designer.
- The export repeats Frontend four times and is therefore placeholder/incomplete.
- Role cards may write guest context and lead to `/projects`, but must not create
  a user, claim eligibility, or imply automatic matching.
- Technical role labels may use local LTR isolation inside the RTL section.

### 6. FAQ

- Static marketing FAQ is allowed.
- The export repeats one question and provides no answers.
- Final approved questions and answers are required before implementation.
- Accordion opening/closing behavior and animation are unspecified; no motion
  should be invented.

### 7. Final CTA

- Encourage project discovery and real team practice.
- Route to `/projects` or `/register`.
- Remove the exported assessment language because assessment is out of scope.
- Do not promise a team immediately; formation is manual and availability is not
  guaranteed by a participant action.

### 8. Footer

- Retain the oversized PROLEARN visual direction only if it remains usable at
  supported desktop widths.
- Footer columns in the export contain placeholder repeated project links.
- Final destinations, legal copy, contact information, and social links are not
  supplied and must not be invented.

## Content Source Rules

- Marketing roadmap, FAQ, and approved project previews may be static frontend data.
- Live project cards must use `/api/v1/projects/` and project-detail APIs.
- Do not advertise unavailable features.
- Do not hard-code Helpdesk-specific runtime behavior.
- Backend ProjectRun/Sprint state must never appear in homepage animation or
  decorative mockups as if it were live user state.

## Desktop Layout Guidance

- Use a centered fluid content container rather than a fixed 1440px canvas.
- Preserve the 1366px-1536px primary composition while avoiding overflow at 1024px.
- Maintain RTL reading order and explicit LTR islands for role names or code.
- Do not create mobile navigation or mobile section variants.
- Large whitespace must be intentional, bounded, and verified at 1024, 1366,
  1440, 1536, and 1920 widths.

## Accessibility Baseline

- Semantic heading order and landmark regions.
- Real links/buttons instead of clickable decorative containers.
- Visible keyboard focus against the dark background.
- Contrast verification for blue text and outlined controls.
- Meaningful illustration alt text, or hidden decorative images.
- FAQ controls must expose expanded/collapsed state if accordion behavior is approved.

## Missing Inputs

- Final Persian copy review.
- Exact fonts and licensing/source files.
- Exact color and spacing tokens.
- Production logo and illustration exports.
- FAQ answers.
- Footer destinations/legal copy.
- Confirmation of hero-to-roadmap blank space.
- Confirmation whether project showcase is static marketing or a future live feed.
- Any approved motion/prototype behavior.
