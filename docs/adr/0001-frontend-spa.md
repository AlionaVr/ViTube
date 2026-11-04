# 0001. Frontend: React + TypeScript + Vite SPA

**Status:** accepted · 2026-11-04

**Context.** The clone is graded on how close it looks and feels to YouTube. YouTube is a SPA: no page reloads, infinite
feed.

**Decision.**

- SPA with React, TypeScript, Vite, React Router, TanStack Query.
- Own CSS with CSS variables (light and dark themes).
- FastAPI serves JSON only. TS types are generated from the OpenAPI schema.
- nginx serves the built files from the same origin as the API, so no CORS.

**Alternatives.**

- Jinja2 + HTMX: one language, but hard to match YouTube UX.
- Vanilla JS: no build step, but does not scale to 10+ screens.

**Consequences.**

- ➕ Clean API/UI split; easy to mimic YouTube behavior.
- ➖ Needs Node to build — done in a multi-stage Docker build, not on the server.
