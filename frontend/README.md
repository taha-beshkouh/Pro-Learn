# PROLEARN Frontend

Vite, React, and TypeScript foundation for the participant-facing PROLEARN
application. Frontend Phase 1 contains routing, session-aware route protection,
a typed native-fetch client, placeholder pages, base desktop RTL styles, and
Vitest/Testing Library setup only.

## Environment

Use the variable name from `.env.example` in a developer-owned local Vite
environment file when a non-default API origin is required:

```text
VITE_API_BASE_URL=/api/v1
```

The default is the same-origin `/api/v1` API. Authentication uses Django's
session cookie and CSRF flow; no frontend auth token is stored.

## Commands

```powershell
npm run dev
npm run typecheck
npm run test
npm run test:watch
npm run build
npm run lint
```

The current implementation targets laptop/desktop widths from 1024px to 1920px.
Mobile layouts and full product pages are not part of Frontend Phase 1.
